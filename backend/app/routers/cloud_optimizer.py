"""
Cloud Optimizer Job Router – /api/cloud

Provides the job-based cloud infrastructure analysis endpoint (Spec 05).
The /api/optimize endpoint remains in cloud.py.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _run_cloud_background(job_id: str) -> None:
    from backend.app.services.job_tracker import ACTIVE_JOBS, JobStatus, update_job
    from backend.app.services.cloud_engine import run_cloud_optimizer

    try:
        update_job(job_id, status=JobStatus.PROCESSING, active_module="cloud_optimizer")

        record = ACTIVE_JOBS.get(job_id)
        file_tree: dict = {}
        workspace_root: str = "."

        if record is not None:
            for artifact in record.artifacts:
                if isinstance(artifact, dict) and "file_tree" in artifact:
                    file_tree = artifact["file_tree"]
                    workspace_root = artifact.get("workspace_root", ".")
                    break

        findings = run_cloud_optimizer(job_id, file_tree, workspace_root)

        record = ACTIVE_JOBS.get(job_id)
        current_artifacts = list(record.artifacts) if record else []
        new_artifacts = current_artifacts + [{"module": "cloud_optimizer", "optimizations": findings}]
        update_job(job_id, status=JobStatus.COMPLETED, active_module=None, artifacts=new_artifacts)

    except Exception as exc:
        logger.exception("Cloud optimizer background task failed for job %s: %s", job_id, exc)
        from backend.app.services.job_tracker import JobStatus, update_job
        update_job(job_id, status=JobStatus.FAILED)


@router.post("/cloud/run/{job_id}")
async def run_cloud_optimizer_job(job_id: str, background_tasks: BackgroundTasks) -> JSONResponse:
    from backend.app.services.job_tracker import ACTIVE_JOBS

    if job_id not in ACTIVE_JOBS:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    background_tasks.add_task(_run_cloud_background, job_id)
    return JSONResponse(status_code=202, content={"message": "Cloud optimizer started", "job_id": job_id})
