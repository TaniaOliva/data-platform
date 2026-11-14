"""Ejecuta una etapa del pipeline (D-04, D-20, D-22).

Uso:  python -m etl.run_stage <etapa> [--execution-id N] [--error TEXTO]
Etapas: start, extract, clean, ready, load, commit, fail

Cada etapa corre en su propia transacción: si falla, se revierte, el watermark no se mueve
y la falla queda registrada en la auditoría. Solo `start` imprime en stdout el ExecutionID.
"""
import argparse
import sys
from dataclasses import dataclass

from etl.audit import Audit
from etl.config import Settings, load_settings
from etl.db import connect
from etl.extract import extract_raw
from etl.load import load_dw
from etl.transform import clean, ready
from etl.watermark import commit_watermark

PIPELINE_NAME = "wwi_sales_batch"


@dataclass
class Context:
    settings: Settings
    audit: Audit
    execution_id: int


def stage_commit(conn, ctx: Context) -> None:
    """Confirma los watermarks de la corrida y la marca como exitosa (D-16)."""
    cur = conn.cursor()
    with ctx.audit.step("commit watermarks", "audit.Step", "ctl.Watermark") as step:
        rows = cur.execute(
            "SELECT SUBSTRING(StepName, 9, 200), CONVERT(varchar(27), WatermarkEnd, 126) FROM audit.Step "
            "WHERE ExecutionID = ? AND StepName LIKE 'extract %' AND Status = 'success' AND WatermarkEnd IS NOT NULL",
            ctx.execution_id).fetchall()
        step.rows_read = len(rows)
        for table_name, value in rows:
            commit_watermark(cur, table_name, value)
            step.rows_updated += 1


# etapa -> (función, base de datos de la conexión de trabajo)
STAGES = {
    "extract": (extract_raw.run, "staging"),
    "clean": (clean.run, "staging"),
    "ready": (ready.run, "staging"),
    "load": (load_dw.run, "dw"),
    "commit": (stage_commit, "staging"),
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["start", "fail", *STAGES])
    parser.add_argument("--execution-id", type=int)
    parser.add_argument("--error")
    args = parser.parse_args(argv)

    settings = load_settings()
    audit_conn = connect(settings, settings.staging_db, autocommit=True)  # conexión de auditoría aparte
    audit = Audit(audit_conn, args.execution_id)

    if args.stage == "start":
        print(audit.start_execution(PIPELINE_NAME))
        return 0
    if args.execution_id is None:
        parser.error("--execution-id es obligatorio")
    if args.stage == "fail":
        audit.finish_execution("failed", args.error)
        return 0

    func, db_kind = STAGES[args.stage]
    work = connect(settings, settings.staging_db if db_kind == "staging" else settings.dw_db)
    first_step = audit.last_step_id()  # pasos de esta etapa = los posteriores a este
    try:
        func(work, Context(settings, audit, args.execution_id))
        work.commit()
        if args.stage == "commit":
            audit.finish_execution("success")
        print(f"Etapa {args.stage}: OK")
        return 0
    except Exception as exc:  # la etapa se revierte completa
        work.rollback()
        # La transacción se revirtió completa: los pasos que habían terminado bien ya no valen
        audit.mark_rolled_back(first_step, f"Revertido por la falla de la etapa {args.stage}")
        print(f"Etapa {args.stage}: ERROR {exc!r}", file=sys.stderr)
        return 1
    finally:
        work.close()
        audit_conn.close()


if __name__ == "__main__":
    sys.exit(main())
