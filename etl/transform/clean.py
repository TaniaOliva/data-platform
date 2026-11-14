"""Paso raw -> clean (D-18, D-19, D-20).

1. Lee de raw las filas de la ventana incremental.
2. Aplica las reglas de rules.py; los incumplimientos van a stg.Quarantine (sin duplicarse al reejecutar).
3. Las filas que pasan se limpian (espacios, vacíos a NULL, tipos explícitos) y se mezclan en clean por llave.
4. Si una fila ya limpia ahora incumple una regla, se retira de clean.
"""
from dataclasses import dataclass

from etl.extract.extract_raw import TABLES
from etl.sqlutil import QUERY_HINT, build_merge, run_merge, run_merge_chunked
from etl.transform import rules
from etl.watermark import effective_since


def txt(col: str) -> str:
    """Texto limpio: sin espacios sobrantes; vacío pasa a NULL (D-19)."""
    return f"NULLIF(LTRIM(RTRIM(r.[{col}])), N'') COLLATE DATABASE_DEFAULT"


def dec(col: str, precision: int, scale: int) -> str:
    return f"CAST(r.[{col}] AS decimal({precision},{scale}))"


def same(*cols: str) -> dict:
    return {c: f"r.[{c}]" for c in cols}


@dataclass(frozen=True)
class CleanSpec:
    source: str                 # "Schema.Table" del origen
    clean_table: str
    keys: tuple[str, ...]
    columns: dict               # columna clean -> expresión sobre raw (alias r)
    rule_columns: tuple[str, ...]  # columnas de raw que necesitan las reglas

    def key_expr(self, alias: str) -> str:
        parts = []
        for k in self.keys:
            if k == "ValidFrom":
                parts.append(f"CONVERT(varchar(27), {alias}.[{k}], 126)")
            else:
                parts.append(f"CAST({alias}.[{k}] AS varchar(20))")
        return " + '|' + ".join(parts)


SPECS = [
    CleanSpec("Application.People", "clean.People", ("PersonID",),
              {**same("PersonID", "IsEmployee", "IsSalesperson"), "FullName": txt("FullName")},
              ("PersonID", "IsEmployee", "IsSalesperson")),
    CleanSpec("Application.Countries", "clean.Countries", ("CountryID",),
              {"CountryID": "r.[CountryID]", "CountryName": txt("CountryName"), "Continent": txt("Continent"),
               "Region": txt("Region"), "Subregion": txt("Subregion")},
              ("CountryID",)),
    CleanSpec("Application.StateProvinces", "clean.StateProvinces", ("StateProvinceID",),
              {**same("StateProvinceID", "CountryID"), "StateProvinceName": txt("StateProvinceName"),
               "SalesTerritory": txt("SalesTerritory")},
              ("StateProvinceID", "CountryID")),
    CleanSpec("Application.Cities", "clean.Cities", ("CityID",),
              {**same("CityID", "StateProvinceID"), "CityName": txt("CityName")},
              ("CityID", "StateProvinceID")),
    CleanSpec("Sales.CustomerCategories", "clean.CustomerCategories", ("CustomerCategoryID",),
              {"CustomerCategoryID": "r.[CustomerCategoryID]", "CustomerCategoryName": txt("CustomerCategoryName")},
              ("CustomerCategoryID",)),
    CleanSpec("Sales.Customers", "clean.Customers", ("CustomerID", "ValidFrom"),
              {**same("CustomerID", "ValidFrom", "ValidTo", "CustomerCategoryID", "DeliveryCityID"),
               "CustomerName": txt("CustomerName"), "DeliveryRun": txt("DeliveryRun")},
              ("CustomerID", "ValidFrom", "ValidTo", "CustomerCategoryID", "DeliveryCityID")),
    CleanSpec("Sales.Invoices", "clean.Invoices", ("InvoiceID",),
              same("InvoiceID", "CustomerID", "SalespersonPersonID", "InvoiceDate", "IsCreditNote"),
              ("InvoiceID", "CustomerID", "SalespersonPersonID", "InvoiceDate", "IsCreditNote")),
    CleanSpec("Sales.InvoiceLines", "clean.InvoiceLines", ("InvoiceLineID",),
              {**same("InvoiceLineID", "InvoiceID", "StockItemID", "Quantity"),
               "UnitPrice": dec("UnitPrice", 18, 2), "TaxRate": dec("TaxRate", 18, 3),
               "TaxAmount": dec("TaxAmount", 18, 2), "LineProfit": dec("LineProfit", 18, 2),
               "ExtendedPrice": dec("ExtendedPrice", 18, 2)},
              ("InvoiceLineID", "InvoiceID", "StockItemID", "Quantity", "TaxRate", "TaxAmount",
               "LineProfit", "ExtendedPrice")),
    CleanSpec("Warehouse.StockGroups", "clean.StockGroups", ("StockGroupID",),
              {"StockGroupID": "r.[StockGroupID]", "StockGroupName": txt("StockGroupName")},
              ("StockGroupID",)),
    CleanSpec("Warehouse.StockItems", "clean.StockItems", ("StockItemID",),
              {"StockItemID": "r.[StockItemID]", "StockItemName": txt("StockItemName"), "Brand": txt("Brand"),
               "Size": txt("Size"), "UnitPrice": dec("UnitPrice", 18, 2), "TaxRate": dec("TaxRate", 18, 3)},
              ("StockItemID",)),
    CleanSpec("Warehouse.StockItemStockGroups", "clean.StockItemStockGroups", ("StockItemStockGroupID",),
              same("StockItemStockGroupID", "StockItemID", "StockGroupID"),
              ("StockItemStockGroupID", "StockItemID", "StockGroupID")),
]

_RAW = {t.full_name: t for t in TABLES}


def _fetch_dicts(cur, sql: str, params=()) -> list[dict]:
    cur.execute(sql, params)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def clean_source(conn, audit, settings, spec: CleanSpec) -> None:
    table = _RAW[spec.source]
    cur = conn.cursor()
    since = effective_since(cur, spec.source)
    with audit.step(f"clean {spec.source}", table.raw_table, spec.clean_table, since) as step:
        window = f"r.[{table.wm_col}] > CONVERT(datetime2, ?, 126)"

        # Contexto de las reglas entre tablas
        ctx = {}
        if spec.source == "Sales.InvoiceLines":
            ctx["invoice_is_credit_note"] = {
                r[0]: bool(r[1]) for r in cur.execute(
                    "SELECT InvoiceID, IsCreditNote FROM raw.Sales_Invoices").fetchall()
            }

        cols = ", ".join(f"r.[{c}]" for c in spec.rule_columns)
        rows = _fetch_dicts(
            cur, f"SELECT {spec.key_expr('r')} AS _key, {cols} FROM {table.raw_table} r WHERE {window}", since)
        step.rows_read = len(rows)
        violations = rules.evaluate(spec.source, rows, ctx)

        # Llaves que fallan (temporal) y cuarentena
        cur.execute("CREATE TABLE #fail (k varchar(80) NOT NULL PRIMARY KEY)")
        cur.execute("CREATE TABLE #q (RuleID nvarchar(50) NOT NULL, Detail nvarchar(max) NULL)")
        failed_keys = sorted({v.key for v in violations})
        if failed_keys:
            cur.executemany("INSERT INTO #fail (k) VALUES (?)", [(k,) for k in failed_keys])
            cur.executemany("INSERT INTO #q (RuleID, Detail) VALUES (?, ?)", [(v.rule_id, v.detail) for v in violations])
        # Se evita repetir un mismo incumplimiento en corridas posteriores (ventana de solapamiento)
        cur.execute(
            "INSERT INTO stg.Quarantine (SourceName, ExecutionID, RuleID, Detail) "
            "SELECT ?, ?, q.RuleID, q.Detail FROM #q q WHERE NOT EXISTS ("
            "SELECT 1 FROM stg.Quarantine x WHERE x.SourceName = ? AND x.RuleID = q.RuleID AND x.Detail = q.Detail)",
            spec.source, audit.execution_id, spec.source)
        step.rows_rejected = len(failed_keys)

        # Una fila ya limpia que ahora incumple se retira de clean
        cur.execute(f"DELETE c FROM {spec.clean_table} c WHERE EXISTS "
                    f"(SELECT 1 FROM #fail f WHERE f.k = {spec.key_expr('c')}) {QUERY_HINT}")

        cols_names = list(spec.columns)
        select = (", ".join(f"{expr} AS [{name}]" for name, expr in spec.columns.items()))
        source_sql = (f"SELECT {select} FROM {table.raw_table} r WHERE {window} "
                      f"AND NOT EXISTS (SELECT 1 FROM #fail f WHERE f.k = {spec.key_expr('r')})")
        if len(spec.keys) == 1:
            # Por rangos de llave, para no pedir concesiones grandes de memoria
            lo, hi = cur.execute(f"SELECT ISNULL(MIN([{spec.keys[0]}]), 0), ISNULL(MAX([{spec.keys[0]}]), -1) "
                                 f"FROM {table.raw_table}").fetchone()
            step.rows_inserted, step.rows_updated = run_merge_chunked(
                cur, lambda a, b: build_merge(
                    spec.clean_table, f"{source_sql} AND r.[{spec.keys[0]}] >= {a} AND r.[{spec.keys[0]}] < {b}",
                    spec.keys, cols_names),
                lo, hi, (since,))
        else:
            step.rows_inserted, step.rows_updated = run_merge(
                cur, build_merge(spec.clean_table, source_sql, spec.keys, cols_names), (since,))
        cur.execute("DROP TABLE #fail; DROP TABLE #q;")


def run(conn, ctx) -> None:
    for spec in SPECS:
        clean_source(conn, ctx.audit, ctx.settings, spec)
        print(f"  limpiado {spec.source}")
