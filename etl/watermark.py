"""Marca de carga incremental (D-16). Las marcas viajan como texto ISO 8601 para no perder precisión."""
from etl.config import MIN_WATERMARK, OVERLAP_DAYS


def last_watermark(cur, table_name: str) -> str:
    """Última marca confirmada; si la tabla nunca se cargó, el valor mínimo."""
    row = cur.execute(
        "SELECT CONVERT(varchar(27), LastWatermark, 126) FROM ctl.Watermark WHERE TableName = ?", table_name
    ).fetchone()
    return row[0] if row else MIN_WATERMARK


def effective_since(cur, table_name: str) -> str:
    """Inicio de la ventana de lectura: última marca menos el solapamiento (registros tardíos)."""
    row = cur.execute(
        "SELECT CONVERT(varchar(27), CASE WHEN LastWatermark <= DATEADD(day, ?, CAST(? AS datetime2)) "
        "THEN CAST(? AS datetime2) ELSE DATEADD(day, -?, LastWatermark) END, 126) "
        "FROM ctl.Watermark WHERE TableName = ?",
        OVERLAP_DAYS, MIN_WATERMARK, MIN_WATERMARK, OVERLAP_DAYS, table_name,
    ).fetchone()
    return row[0] if row else MIN_WATERMARK


def commit_watermark(cur, table_name: str, value: str) -> None:
    """Confirma la marca. Solo se llama cuando toda la corrida terminó bien."""
    cur.execute(
        "MERGE ctl.Watermark AS t USING (SELECT ? AS TableName, CONVERT(datetime2, ?, 126) AS V) AS s "
        "ON t.TableName = s.TableName "
        "WHEN MATCHED AND s.V > t.LastWatermark THEN UPDATE SET LastWatermark = s.V, UpdatedAt = SYSUTCDATETIME() "
        "WHEN NOT MATCHED THEN INSERT (TableName, LastWatermark) VALUES (s.TableName, s.V);",
        table_name, value,
    )
