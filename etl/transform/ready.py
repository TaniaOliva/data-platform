"""Paso clean -> ready: zona de integración con la forma de las dimensiones y el hecho.

ready se recalcula completa en cada corrida (TRUNCATE + INSERT), así que es idempotente.
Los textos vacíos se muestran como "Desconocido" (D-19); marca y tamaño conservan NULL.
"""
from etl.sqlutil import CHUNK_SIZE as CHUNK, QUERY_HINT

UNKNOWN = "N'Desconocido'"

# (tabla ready, sentencia INSERT ... SELECT)
READY_BUILDS = [
    ("ready.Geography", f"""
INSERT INTO ready.Geography (CityID, CityName, StateProvinceName, SalesTerritory, CountryName, Continent, Region, Subregion)
SELECT ci.CityID,
       ISNULL(ci.CityName, {UNKNOWN}), ISNULL(sp.StateProvinceName, {UNKNOWN}), ISNULL(sp.SalesTerritory, {UNKNOWN}),
       ISNULL(co.CountryName, {UNKNOWN}), ISNULL(co.Continent, {UNKNOWN}), ISNULL(co.Region, {UNKNOWN}),
       ISNULL(co.Subregion, {UNKNOWN})
FROM clean.Cities ci
LEFT JOIN clean.StateProvinces sp ON sp.StateProvinceID = ci.StateProvinceID
LEFT JOIN clean.Countries co ON co.CountryID = sp.CountryID
"""),
    ("ready.Employee", f"""
INSERT INTO ready.Employee (PersonID, FullName)
SELECT PersonID, ISNULL(FullName, {UNKNOWN}) FROM clean.People WHERE IsEmployee = 1
"""),
    # Grupo principal = menor StockGroupID del producto (D-25, D-26)
    ("ready.Product", f"""
INSERT INTO ready.Product (StockItemID, StockItemName, Brand, Size, CatalogUnitPrice, CatalogTaxRate, PrimaryStockGroup)
SELECT si.StockItemID, ISNULL(si.StockItemName, {UNKNOWN}), si.Brand, si.Size, si.UnitPrice, si.TaxRate,
       ISNULL(sg.StockGroupName, {UNKNOWN})
FROM clean.StockItems si
LEFT JOIN (SELECT StockItemID, MIN(StockGroupID) AS StockGroupID
           FROM clean.StockItemStockGroups GROUP BY StockItemID) pg ON pg.StockItemID = si.StockItemID
LEFT JOIN clean.StockGroups sg ON sg.StockGroupID = pg.StockGroupID
"""),
    # SCD tipo 2: las versiones consecutivas con los mismos atributos rastreados se fusionan (D-21)
    ("ready.Customer", f"""
WITH v AS (
    SELECT c.CustomerID, c.ValidFrom, c.ValidTo,
           ISNULL(c.CustomerName, {UNKNOWN}) AS CustomerName,
           ISNULL(cc.CustomerCategoryName, {UNKNOWN}) AS CustomerCategoryName,
           ISNULL(c.DeliveryRun, {UNKNOWN}) AS DeliveryRun,
           ISNULL(ci.CityName, {UNKNOWN}) AS City,
           ISNULL(sp.StateProvinceName, {UNKNOWN}) AS StateProvince,
           ISNULL(co.CountryName, {UNKNOWN}) AS Country
    FROM clean.Customers c
    LEFT JOIN clean.CustomerCategories cc ON cc.CustomerCategoryID = c.CustomerCategoryID
    LEFT JOIN clean.Cities ci ON ci.CityID = c.DeliveryCityID
    LEFT JOIN clean.StateProvinces sp ON sp.StateProvinceID = ci.StateProvinceID
    LEFT JOIN clean.Countries co ON co.CountryID = sp.CountryID
), f AS (
    SELECT v.*,
           CASE WHEN LAG(CustomerName) OVER (PARTITION BY CustomerID ORDER BY ValidFrom) = CustomerName AND LAG(CustomerCategoryName) OVER (PARTITION BY CustomerID ORDER BY ValidFrom) = CustomerCategoryName
                 AND LAG(DeliveryRun) OVER (PARTITION BY CustomerID ORDER BY ValidFrom) = DeliveryRun AND LAG(City) OVER (PARTITION BY CustomerID ORDER BY ValidFrom) = City
                 AND LAG(StateProvince) OVER (PARTITION BY CustomerID ORDER BY ValidFrom) = StateProvince AND LAG(Country) OVER (PARTITION BY CustomerID ORDER BY ValidFrom) = Country
                THEN 0 ELSE 1 END AS IsNewVersion
    FROM v
), g AS (
    SELECT f.*, SUM(IsNewVersion) OVER (PARTITION BY CustomerID ORDER BY ValidFrom ROWS UNBOUNDED PRECEDING) AS Grp
    FROM f
)
INSERT INTO ready.Customer (CustomerID, ValidFrom, ValidTo, CustomerName, CustomerCategoryName, DeliveryRun, City, StateProvince, Country)
SELECT CustomerID, MIN(ValidFrom), MAX(ValidTo), MAX(CustomerName), MAX(CustomerCategoryName), MAX(DeliveryRun),
       MAX(City), MAX(StateProvince), MAX(Country)
FROM g GROUP BY CustomerID, Grp
"""),
    # Cada línea hereda la ciudad de entrega de la versión de cliente vigente en la fecha de la factura
    ("ready.SalesLine", """
INSERT INTO ready.SalesLine (InvoiceLineID, InvoiceID, InvoiceDate, CustomerID, StockItemID, SalespersonPersonID,
                             DeliveryCityID, Quantity, UnitPrice, TaxRate, TaxAmount, LineProfit, ExtendedPrice)
SELECT l.InvoiceLineID, l.InvoiceID, i.InvoiceDate, i.CustomerID, l.StockItemID, i.SalespersonPersonID,
       cv.DeliveryCityID, l.Quantity, l.UnitPrice, l.TaxRate, l.TaxAmount, l.LineProfit, l.ExtendedPrice
FROM clean.InvoiceLines l
JOIN clean.Invoices i ON i.InvoiceID = l.InvoiceID
LEFT JOIN clean.Customers cv ON cv.CustomerID = i.CustomerID
     AND CAST(i.InvoiceDate AS datetime2) >= cv.ValidFrom AND CAST(i.InvoiceDate AS datetime2) < cv.ValidTo
"""),
]


# Tablas grandes que se cargan por rangos: tabla -> (columna del rango, tabla y columna para los límites)
CHUNKED = {
    "ready.Geography": ("ci.CityID", "clean.Cities", "CityID"),
    "ready.SalesLine": ("l.InvoiceLineID", "clean.InvoiceLines", "InvoiceLineID"),
}


def run(conn, ctx) -> None:
    cur = conn.cursor()
    for table, insert_sql in READY_BUILDS:
        with ctx.audit.step(f"ready {table}", "clean", f"{ctx.settings.staging_db}.{table}") as step:
            cur.execute(f"TRUNCATE TABLE {table}")
            if table in CHUNKED:
                # Por rangos de llave, para no pedir concesiones grandes de memoria
                col, bounds_table, bounds_col = CHUNKED[table]
                lo, hi = cur.execute(f"SELECT ISNULL(MIN({bounds_col}), 0), ISNULL(MAX({bounds_col}), -1) "
                                     f"FROM {bounds_table}").fetchone()
                total = 0
                for a in range(lo, hi + 1, CHUNK):
                    cur.execute("SET NOCOUNT OFF;\n" + insert_sql.rstrip() +
                                f"\nWHERE {col} >= {a} AND {col} < {a + CHUNK}\n" + QUERY_HINT)
                    total += cur.rowcount
                step.rows_inserted = step.rows_read = total
            else:
                cur.execute("SET NOCOUNT OFF;\n" + insert_sql.rstrip() + "\n" + QUERY_HINT)
                step.rows_inserted = step.rows_read = cur.rowcount
            if table == "ready.SalesLine":
                # Líneas limpias que no llegan a ready porque su factura no está en clean
                lost = cur.execute(
                    "SELECT COUNT(*) FROM clean.InvoiceLines l WHERE NOT EXISTS "
                    "(SELECT 1 FROM clean.Invoices i WHERE i.InvoiceID = l.InvoiceID)").fetchone()[0]
                step.rows_rejected = lost
        print(f"  ready {table}: {step.rows_inserted} filas")
