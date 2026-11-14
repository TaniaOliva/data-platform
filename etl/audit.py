"""Auditoría de corridas y etapas (D-22). Usa una conexión autocommit propia,
para que el registro de una falla sobreviva al rollback de la etapa."""
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class Step:
    id: int
    name: str
    rows_read: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_rejected: int = 0
    watermark_end: str | None = None


class Audit:
    def __init__(self, conn, execution_id: int | None = None):
        self.conn = conn
        self.execution_id = execution_id

    def start_execution(self, pipeline: str) -> int:
        row = self.conn.execute(
            "SET NOCOUNT ON; INSERT INTO audit.Execution (PipelineName) OUTPUT inserted.ExecutionID VALUES (?)",
            pipeline,
        ).fetchone()
        self.execution_id = int(row[0])
        return self.execution_id

    def last_step_id(self) -> int:
        row = self.conn.execute("SELECT ISNULL(MAX(StepID), 0) FROM audit.Step").fetchone()
        return int(row[0])

    def mark_rolled_back(self, after_step_id: int, reason: str) -> None:
        """Marca como fallidos los pasos 'success' de una etapa cuya transacción se revirtió (D-20)."""
        self.conn.execute(
            "UPDATE audit.Step SET Status = 'failed', ErrorDetail = ? "
            "WHERE ExecutionID = ? AND StepID > ? AND Status = 'success'",
            reason, self.execution_id, after_step_id,
        )

    def finish_execution(self, status: str, error: str | None = None) -> None:
        self.conn.execute(
            "UPDATE audit.Execution SET EndTime = SYSUTCDATETIME(), Status = ?, ErrorDetail = ? WHERE ExecutionID = ?",
            status, error, self.execution_id,
        )

    @contextmanager
    def step(self, name: str, source: str | None = None, target: str | None = None,
             watermark_start: str | None = None):
        row = self.conn.execute(
            "SET NOCOUNT ON; INSERT INTO audit.Step (ExecutionID, StepName, SourceObject, TargetObject, WatermarkStart) "
            "OUTPUT inserted.StepID VALUES (?, ?, ?, ?, CONVERT(datetime2, ?, 126))",
            self.execution_id, name, source, target, watermark_start,
        ).fetchone()
        st = Step(id=int(row[0]), name=name)
        try:
            yield st
        except Exception as exc:
            self._finish_step(st, "failed", repr(exc)[:4000])
            raise
        self._finish_step(st, "success", None)

    def _finish_step(self, st: Step, status: str, error: str | None) -> None:
        self.conn.execute(
            "UPDATE audit.Step SET EndTime = SYSUTCDATETIME(), Status = ?, ErrorDetail = ?, RowsRead = ?, "
            "RowsInserted = ?, RowsUpdated = ?, RowsRejected = ?, WatermarkEnd = CONVERT(datetime2, ?, 126) "
            "WHERE StepID = ?",
            status, error, st.rows_read, st.rows_inserted, st.rows_updated, st.rows_rejected,
            st.watermark_end, st.id,
        )
