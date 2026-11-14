"""Extracción de WideWorldImporters a WWI_Staging.raw (D-12, D-16).

- Excluye HashedPassword y Photo desde la consulta (D-12) y las columnas espaciales.
- Lee solo los cambios posteriores a la marca (con solapamiento) y los mezcla por llave: idempotente.
"""
from dataclasses import dataclass

from etl.sqlutil import build_merge, q, run_merge
from etl.watermark import effective_since, last_watermark

EXCLUDED_COLUMNS = {"HashedPassword", "Photo"}
EXCLUDED_TYPES = {"geography", "geometry", "hierarchyid"}


@dataclass(frozen=True)
class SourceTable:
    schema: str
    name: str
    keys: tuple[str, ...]
    wm_col: str
    with_archive: bool = False  # tabla temporal: se une el historial (Customers_Archive)

    @property
    def full_name(self) -> str:
        return f"{self.schema}.{self.name}"

    @property
    def raw_table(self) -> str:
        return f"raw.{self.schema}_{self.name}"


TABLES = [
    SourceTable("Application", "People", ("PersonID",), "ValidFrom"),
    SourceTable("Application", "Countries", ("CountryID",), "ValidFrom"),
    SourceTable("Application", "StateProvinces", ("StateProvinceID",), "ValidFrom"),
    SourceTable("Application", "Cities", ("CityID",), "ValidFrom"),
    SourceTable("Sales", "CustomerCategories", ("CustomerCategoryID",), "ValidFrom"),
    SourceTable("Sales", "Customers", ("CustomerID", "ValidFrom"), "ValidFrom", with_archive=True),
    SourceTable("Sales", "Invoices", ("InvoiceID",), "LastEditedWhen"),
    SourceTable("Sales", "InvoiceLines", ("InvoiceLineID",), "LastEditedWhen"),
    SourceTable("Warehouse", "StockGroups", ("StockGroupID",), "ValidFrom"),
    SourceTable("Warehouse", "StockItems", ("StockItemID",), "ValidFrom"),
    SourceTable("Warehouse", "StockItemStockGroups", ("StockItemStockGroupID",), "LastEditedWhen"),
]


def type_ddl(type_name: str, max_length: int, precision: int, scale: int) -> str:
    """Tipo T-SQL equivalente al del origen (D-14: se conserva la precisión)."""
    t = type_name.lower()
    if t in ("nvarchar", "nchar"):
        return f"{t}(max)" if max_length == -1 else f"{t}({max_length // 2})"
    if t in ("varchar", "char", "varbinary", "binary"):
        return f"{t}(max)" if max_length == -1 else f"{t}({max_length})"
    if t in ("decimal", "numeric"):
        return f"{t}({precision},{scale})"
    if t in ("datetime2", "time", "datetimeoffset"):
        return f"{t}({scale})"
    return t


def source_columns(cur, source_db: str, table: SourceTable) -> list[tuple[str, str, bool]]:
    """Columnas (nombre, tipo DDL, admite nulos) a extraer, sin las excluidas."""
    rows = cur.execute(
        f"SELECT c.name, TYPE_NAME(c.user_type_id), c.max_length, c.precision, c.scale, c.is_nullable, c.collation_name "
        f"FROM {q(source_db)}.sys.columns c "
        f"JOIN {q(source_db)}.sys.tables t ON t.object_id = c.object_id "
        f"JOIN {q(source_db)}.sys.schemas s ON s.schema_id = t.schema_id "
        f"WHERE s.name = ? AND t.name = ? ORDER BY c.column_id",
        table.schema, table.name,
    ).fetchall()
    cols = [
        (r[0], type_ddl(r[1], r[2], r[3], r[4]) + (f" COLLATE {r[6]}" if r[6] else ""), bool(r[5]))
        for r in rows
        if r[0] not in EXCLUDED_COLUMNS and r[1].lower() not in EXCLUDED_TYPES
    ]
    if not cols:
        raise RuntimeError(f"No se encontraron columnas para {table.full_name}")
    return cols


def ensure_raw_table(cur, table: SourceTable, cols) -> None:
    defs = ",\n    ".join(f"{q(n)} {t} {'NULL' if nullable else 'NOT NULL'}" for n, t, nullable in cols)
    pk = ", ".join(q(k) for k in table.keys)
    cur.execute(
        f"IF OBJECT_ID(N'{table.raw_table}', N'U') IS NULL\n"
        f"CREATE TABLE {table.raw_table} (\n    {defs},\n"
        f"    [_ExecutionID] bigint NOT NULL,\n"
        f"    [_LoadedAt] datetime2 NOT NULL CONSTRAINT DF_{table.schema}_{table.name}_LoadedAt DEFAULT (SYSUTCDATETIME()),\n"
        f"    CONSTRAINT PK_raw_{table.schema}_{table.name} PRIMARY KEY ({pk}))"
    )


def source_select(source_db: str, table: SourceTable, col_names: list[str]) -> str:
    cols = ", ".join(q(c) for c in col_names)
    base = f"{q(source_db)}.{q(table.schema)}.{q(table.name)}"
    if table.with_archive:
        arch = f"{q(source_db)}.{q(table.schema)}.{q(table.name + '_Archive')}"
        # Supervivencia (D-18): el archivo puede repetir la llave de la fila actual (versión de largo cero);
        # se conserva la versión con mayor ValidTo.
        keys = ", ".join(q(k) for k in table.keys)
        return (f"SELECT {cols} FROM (SELECT {cols}, ROW_NUMBER() OVER (PARTITION BY {keys} ORDER BY [ValidTo] DESC) AS rn "
                f"FROM (SELECT {cols} FROM {base} UNION ALL SELECT {cols} FROM {arch}) AS u) AS ranked WHERE rn = 1")
    return f"SELECT {cols} FROM {base}"


def extract_table(conn, audit, settings, table: SourceTable, execution_id: int) -> None:
    cur = conn.cursor()
    last = last_watermark(cur, table.full_name)
    since = effective_since(cur, table.full_name)
    with audit.step(f"extract {table.full_name}", f"{settings.source_db}.{table.full_name}",
                    f"{settings.staging_db}.{table.raw_table}", last) as step:
        cols = source_columns(cur, settings.source_db, table)
        names = [c[0] for c in cols]
        ensure_raw_table(cur, table, cols)
        inner = source_select(settings.source_db, table, names)
        filtered = f"SELECT * FROM ({inner}) AS src WHERE {q(table.wm_col)} > CONVERT(datetime2, ?, 126)"

        # Filas leídas y marca máxima (texto ISO para conservar los 7 decimales)
        row = cur.execute(
            f"SELECT COUNT(*), CONVERT(varchar(27), MAX({q(table.wm_col)}), 126) FROM ({filtered}) AS f", since
        ).fetchone()
        step.rows_read = int(row[0])
        # Sin filas nuevas la marca no retrocede
        step.watermark_end = row[1] if row[1] and row[1] > last else last

        merge = build_merge(
            table.raw_table, filtered, table.keys, names,
            extra_update="t.[_ExecutionID] = ?, t.[_LoadedAt] = SYSUTCDATETIME()",
            extra_insert_cols=("[_ExecutionID]",), extra_insert_vals=("?",),
        )
        # Orden de los parámetros en el texto: filtro (since), UPDATE (exec), INSERT (exec)
        step.rows_inserted, step.rows_updated = run_merge(cur, merge, (since, execution_id, execution_id))


def run(conn, ctx) -> None:
    for table in TABLES:
        extract_table(conn, ctx.audit, ctx.settings, table, ctx.execution_id)
        print(f"  extraído {table.full_name}")
