"""Carga de WWI_DW desde WWI_Staging.ready (D-10, D-19, D-21).

Todas las cargas son idempotentes: MERGE por clave de negocio que solo toca filas con cambios.
"""
from datetime import date, timedelta

from etl.sqlutil import QUERY_HINT, build_merge, run_merge, run_merge_chunked

DATE_START = date(2013, 1, 1)
DATE_END = date(2016, 12, 31)
MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def date_rows(start: date = DATE_START, end: date = DATE_END):
    """Filas de dim.DimDate para el rango dado."""
    d = start
    while d <= end:
        yield (d.year * 10000 + d.month * 100 + d.day, d, d.day, d.month, MONTHS_ES[d.month - 1],
               (d.month - 1) // 3 + 1, d.year, 1 if d.weekday() >= 5 else 0)
        d += timedelta(days=1)


def load_dim_date(cur, step) -> None:
    """Se genera una sola vez (D-21): si ya hay fechas además del miembro 0, no hace nada."""
    existing = cur.execute("SELECT COUNT(*) FROM dim.DimDate WHERE DateKey <> 0").fetchone()[0]
    rows = list(date_rows())
    step.rows_read = len(rows)
    if existing:
        return
    cur.executemany(
        "INSERT INTO dim.DimDate (DateKey, [Date], [Day], [Month], MonthName, [Quarter], [Year], IsWeekend) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    step.rows_inserted = len(rows)


def load_dim_scd1(cur, step, stg: str, source_table: str, target: str, key: str, cols: list[str]) -> None:
    source_sql = f"SELECT {', '.join(f'[{c}]' for c in [key] + cols)} FROM {stg}.ready.{source_table}"
    step.rows_read = cur.execute(f"SELECT COUNT(*) FROM {stg}.ready.{source_table}").fetchone()[0]
    lo, hi = cur.execute(f"SELECT ISNULL(MIN([{key}]), 0), ISNULL(MAX([{key}]), -1) FROM {stg}.ready.{source_table}").fetchone()
    step.rows_inserted, step.rows_updated = run_merge_chunked(
        cur, lambda a, b: build_merge(target, f"{source_sql} WHERE [{key}] >= {a} AND [{key}] < {b}",
                                      [key], [key] + cols), lo, hi)


CUSTOMER_ATTRS = ["CustomerName", "CustomerCategoryName", "DeliveryRun", "City", "StateProvince", "Country"]


def load_dim_customer(cur, step, stg: str) -> None:
    """SCD tipo 2: cierra versiones con ValidTo y agrega las nuevas. Versión = (CustomerID, ValidFrom)."""
    cur.execute("SET NOCOUNT ON")
    step.rows_read = cur.execute(f"SELECT COUNT(*) FROM {stg}.ready.Customer").fetchone()[0]
    changed = ["ValidTo"] + CUSTOMER_ATTRS
    is_current = "CASE WHEN s.ValidTo >= CAST('9999-12-31' AS datetime2) THEN 1 ELSE 0 END"
    cmp_s = ", ".join([f"s.[{c}]" for c in changed] + [is_current])
    cmp_t = ", ".join([f"t.[{c}]" for c in changed] + ["t.IsCurrent"])
    sets = ", ".join([f"t.[{c}] = s.[{c}]" for c in changed] + [f"t.IsCurrent = {is_current}"])
    cur.execute("SET NOCOUNT OFF")
    cur.execute(
        f"UPDATE t SET {sets} FROM dim.DimCustomer t "
        f"JOIN {stg}.ready.Customer s ON s.CustomerID = t.CustomerID AND s.ValidFrom = t.ValidFrom "
        f"WHERE NOT EXISTS (SELECT {cmp_s} INTERSECT SELECT {cmp_t}) {QUERY_HINT}")
    step.rows_updated = cur.rowcount
    cols = ["CustomerID", "CustomerName", "CustomerCategoryName", "DeliveryRun", "City", "StateProvince",
            "Country", "ValidFrom", "ValidTo"]
    cur.execute(
        f"INSERT INTO dim.DimCustomer ({', '.join(f'[{c}]' for c in cols)}, IsCurrent) "
        f"SELECT {', '.join(f's.[{c}]' for c in cols)}, {is_current} FROM {stg}.ready.Customer s "
        f"WHERE NOT EXISTS (SELECT 1 FROM dim.DimCustomer t WHERE t.CustomerID = s.CustomerID AND t.ValidFrom = s.ValidFrom) {QUERY_HINT}")
    step.rows_inserted = cur.rowcount


FACT_COLS = ["InvoiceLineID", "DateKey", "CustomerKey", "ProductKey", "EmployeeKey", "GeographyKey",
             "Quantity", "UnitPrice", "TaxRate", "TaxAmount", "LineProfit", "ExtendedPrice"]


def load_fact_sales(cur, step, stg: str) -> None:
    """MERGE por InvoiceLineID. Cada clave se resuelve en el momento de la venta; sin dimensión va al miembro 0."""
    source_sql = f"""
SELECT l.InvoiceLineID,
       ISNULL(d.DateKey, 0) AS DateKey,
       ISNULL(c.CustomerKey, 0) AS CustomerKey,
       ISNULL(p.ProductKey, 0) AS ProductKey,
       ISNULL(e.EmployeeKey, 0) AS EmployeeKey,
       ISNULL(g.GeographyKey, 0) AS GeographyKey,
       l.Quantity, l.UnitPrice, l.TaxRate, l.TaxAmount, l.LineProfit, l.ExtendedPrice
FROM {stg}.ready.SalesLine l
LEFT JOIN dim.DimDate d ON d.DateKey = CONVERT(int, CONVERT(char(8), l.InvoiceDate, 112))
LEFT JOIN dim.DimCustomer c ON c.CustomerID = l.CustomerID
     AND CAST(l.InvoiceDate AS datetime2) >= c.ValidFrom AND CAST(l.InvoiceDate AS datetime2) < c.ValidTo
LEFT JOIN dim.DimProduct p ON p.StockItemID = l.StockItemID
LEFT JOIN dim.DimEmployee e ON e.PersonID = l.SalespersonPersonID
LEFT JOIN dim.DimGeography g ON g.CityID = l.DeliveryCityID"""
    step.rows_read = cur.execute(f"SELECT COUNT(*) FROM {stg}.ready.SalesLine").fetchone()[0]
    lo, hi = cur.execute(f"SELECT ISNULL(MIN(InvoiceLineID), 0), ISNULL(MAX(InvoiceLineID), -1) "
                         f"FROM {stg}.ready.SalesLine").fetchone()
    step.rows_inserted, step.rows_updated = run_merge_chunked(
        cur, lambda a, b: build_merge(
            "fact.FactSales", f"{source_sql}\nWHERE l.InvoiceLineID >= {a} AND l.InvoiceLineID < {b}",
            ["InvoiceLineID"], FACT_COLS), lo, hi)


def run(conn, ctx) -> None:
    cur = conn.cursor()
    stg = f"[{ctx.settings.staging_db}]"
    audit = ctx.audit
    dw = ctx.settings.dw_db

    with audit.step("load dim.DimDate", "generated", f"{dw}.dim.DimDate") as s:
        load_dim_date(cur, s)
    with audit.step("load dim.DimGeography", f"{ctx.settings.staging_db}.ready.Geography", f"{dw}.dim.DimGeography") as s:
        load_dim_scd1(cur, s, stg, "Geography", "dim.DimGeography", "CityID",
                      ["CityName", "StateProvinceName", "SalesTerritory", "CountryName", "Continent", "Region", "Subregion"])
    with audit.step("load dim.DimEmployee", f"{ctx.settings.staging_db}.ready.Employee", f"{dw}.dim.DimEmployee") as s:
        load_dim_scd1(cur, s, stg, "Employee", "dim.DimEmployee", "PersonID", ["FullName"])
    with audit.step("load dim.DimProduct", f"{ctx.settings.staging_db}.ready.Product", f"{dw}.dim.DimProduct") as s:
        load_dim_scd1(cur, s, stg, "Product", "dim.DimProduct", "StockItemID",
                      ["StockItemName", "Brand", "Size", "CatalogUnitPrice", "CatalogTaxRate", "PrimaryStockGroup"])
    with audit.step("load dim.DimCustomer", f"{ctx.settings.staging_db}.ready.Customer", f"{dw}.dim.DimCustomer") as s:
        load_dim_customer(cur, s, stg)
    with audit.step("load fact.FactSales", f"{ctx.settings.staging_db}.ready.SalesLine", f"{dw}.fact.FactSales") as s:
        load_fact_sales(cur, s, stg)

    unknown = cur.execute(
        "SELECT SUM(CASE WHEN CustomerKey=0 THEN 1 ELSE 0 END), SUM(CASE WHEN ProductKey=0 THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN EmployeeKey=0 THEN 1 ELSE 0 END), SUM(CASE WHEN GeographyKey=0 THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN DateKey=0 THEN 1 ELSE 0 END) FROM fact.FactSales").fetchone()
    print("  hechos asignados al miembro 0 (cliente, producto, empleado, geografía, fecha):", tuple(unknown))
