from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from pipeline.config.settings import settings
from pipeline.main import run
from pipeline.persistence.db import Database

app = FastAPI(title="Leads Pipeline", version=settings.pipeline_version)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="leads-pipeline")

class RunRequest(BaseModel):
    source_dir: str | None = None

class RunResponse(BaseModel):
    run_id: UUID
    status: str


def _resolve_source_dir(source_dir: str | None) -> str | None:
    """Confine an API-supplied source_dir to settings.data_dir.

    source_dir comes from an untrusted HTTP request body; without this check
    a caller could point the pipeline at any readable directory on the host
    (path traversal / arbitrary local file read) via prepare_raw()'s copy.
    """
    if source_dir is None:
        return None
    base = settings.data_dir.resolve()
    candidate = Path(source_dir)
    candidate = candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError("source_dir must be inside the configured data directory")
    return str(candidate)


def _execute(run_id: UUID, source_dir: str | None):
    try:
        run(source_dir=source_dir, no_db=False, run_id=run_id)
    except Exception as exc:
        try:
            Database().save_run({
                "run_id": run_id, "started_at": datetime.now(timezone.utc),
                "finished_at": datetime.now(timezone.utc), "status": "FAILED",
                "pipeline_version": settings.pipeline_version, "records_read": 0,
                "records_processed": 0, "records_failed": 1, "error": str(exc)
            })
        except Exception:
            pass

@app.get("/api/v1/health")
def health():
    return {"status": "ok", "pipeline_version": settings.pipeline_version}

@app.post("/api/v1/pipeline/runs", response_model=RunResponse, status_code=202)
def start_pipeline(request: RunRequest):
    try:
        source_dir = _resolve_source_dir(request.source_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    run_id = uuid4()
    try:
        Database().save_run({
            "run_id": run_id, "started_at": datetime.now(timezone.utc), "finished_at": None,
            "status": "RUNNING", "pipeline_version": settings.pipeline_version,
            "records_read": 0, "records_processed": 0, "records_failed": 0, "error": None
        })
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")
    _executor.submit(_execute, run_id, source_dir)
    return RunResponse(run_id=run_id, status="RUNNING")
