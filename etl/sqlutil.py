"""Utilidades para generar sentencias MERGE con detección de cambios."""
from typing import Sequence


# Pista de consulta: sin paralelismo y con uniones de bucles anidados (no piden memoria de trabajo). El equipo de desarrollo tiene poca memoria
# disponible para SQL Server y una consulta que pide más de su límite de trabajo se queda esperando.
QUERY_HINT = "OPTION (MAXDOP 1, LOOP JOIN)"


def q(name: str) -> str:
    return f"[{name}]"


def build_merge(target: str, source_sql: str, keys: Sequence[str], cols: Sequence[str],
                extra_update: str = "", extra_insert_cols: Sequence[str] = (),
                extra_insert_vals: Sequence[str] = ()) -> str:
    """MERGE idempotente: solo actualiza si alguna columna cambió (INTERSECT maneja NULL).

    Devuelve un lote cuya última salida es (insertadas, actualizadas).
    """
    non_keys = [c for c in cols if c not in keys]
    on = " AND ".join(f"t.{q(k)} = s.{q(k)}" for k in keys)
    cmp_s = ", ".join(f"s.{q(c)}" for c in non_keys)
    cmp_t = ", ".join(f"t.{q(c)}" for c in non_keys)
    sets = ", ".join(f"t.{q(c)} = s.{q(c)}" for c in non_keys)
    if extra_update:
        sets += ", " + extra_update
    ins_cols = ", ".join([q(c) for c in cols] + list(extra_insert_cols))
    ins_vals = ", ".join([f"s.{q(c)}" for c in cols] + list(extra_insert_vals))
    return (
        "DECLARE @act TABLE (a nvarchar(10));\n"
        f"MERGE {target} AS t USING ({source_sql}) AS s ON {on}\n"
        f"WHEN MATCHED AND NOT EXISTS (SELECT {cmp_s} INTERSECT SELECT {cmp_t}) THEN UPDATE SET {sets}\n"
        f"WHEN NOT MATCHED BY TARGET THEN INSERT ({ins_cols}) VALUES ({ins_vals})\n"
        "OUTPUT $action INTO @act\n"
        f"{QUERY_HINT};\n"
        "SELECT ISNULL(SUM(CASE WHEN a = 'INSERT' THEN 1 ELSE 0 END), 0), "
        "ISNULL(SUM(CASE WHEN a = 'UPDATE' THEN 1 ELSE 0 END), 0) FROM @act;"
    )


def run_merge(cursor, sql: str, params=()) -> tuple[int, int]:
    """Ejecuta un lote de build_merge y devuelve (insertadas, actualizadas)."""
    cursor.execute("SET NOCOUNT ON;\n" + sql, params)
    while True:
        if cursor.description is not None:
            row = cursor.fetchone()
            return int(row[0]), int(row[1])
        if not cursor.nextset():
            raise RuntimeError("El MERGE no devolvió conteos")


CHUNK_SIZE = 5000


def run_merge_chunked(cursor, make_sql, lo: int, hi: int, params=(), step: int = CHUNK_SIZE) -> tuple[int, int]:
    """Ejecuta el MERGE por rangos de llave [a, b). Con pocos recursos evita las concesiones
    grandes de memoria que dejan la consulta esperando. `make_sql(a, b)` devuelve el lote."""
    inserted = updated = 0
    a = lo
    while a <= hi:
        i, u = run_merge(cursor, make_sql(a, a + step), params)
        inserted += i
        updated += u
        a += step
    return inserted, updated
