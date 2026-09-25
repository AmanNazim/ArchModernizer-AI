"""
Code Modernizer Router – /api

Endpoints:
  POST /api/refactor              – legacy inline refactor (existing, keep as-is)
  POST /api/modernize/run/{job_id} – job-based LLM modernizer (new, Spec 04)
"""

import logging
import textwrap
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class ModuleBlueprint(BaseModel):
    name: str
    description: str
    suggested_language: str
    code_snippet: str


class RefactorResponse(BaseModel):
    original_lines: int
    modules: list[ModuleBlueprint]
    summary: str


# ---------------------------------------------------------------------------
# Mock refactor logic
# ---------------------------------------------------------------------------

def _mock_refactor(code: str) -> RefactorResponse:
    """
    Simulates an LLM-based monolith decomposition.

    Splits the input by blank lines to discover logical "blocks", then wraps
    each block into a microservice blueprint.  A real implementation would
    call an LLM (e.g. watsonx, OpenAI) here.
    """
    lines = code.splitlines()
    original_lines = len(lines)

    # Naive block detection: split on blank lines
    blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.strip() == "":
            if current:
                blocks.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))

    # Fall back to treating the whole file as one block
    if not blocks:
        blocks = [code]

    modules: list[ModuleBlueprint] = []
    service_names = [
        "auth-service",
        "data-service",
        "notification-service",
        "api-gateway",
        "worker-service",
    ]

    for i, block in enumerate(blocks[:5]):  # cap at 5 microservices
        name = service_names[i] if i < len(service_names) else f"service-{i + 1}"
        modules.append(
            ModuleBlueprint(
                name=name,
                description=f"Extracted microservice handling responsibilities from block {i + 1}.",
                suggested_language="Python (FastAPI)",
                code_snippet=textwrap.dedent(
                    f"""
                    # --- {name} ---
                    from fastapi import FastAPI

                    app = FastAPI(title="{name}")

                    @app.get("/")
                    def root():
                        return {{"service": "{name}", "status": "healthy"}}

                    # Original logic:
                    {block[:300]}
                    """
                ).strip(),
            )
        )

    return RefactorResponse(
        original_lines=original_lines,
        modules=modules,
        summary=(
            f"Decomposed {original_lines} lines into {len(modules)} microservice(s). "
            "Each module exposes an independent FastAPI application ready for containerisation."
        ),
    )


# ---------------------------------------------------------------------------
# Existing endpoint
# ---------------------------------------------------------------------------

@router.post("/refactor", response_model=RefactorResponse, summary="Refactor legacy code")
async def refactor_code(
    code: Optional[str] = Form(None, description="Raw legacy code string"),
    file: Optional[UploadFile] = File(None, description="Uploaded source file"),
) -> RefactorResponse:
    """
    Accepts either a raw **code** string (form field) or an **uploaded file**,
    then returns a structured decomposition into microservice blueprints.
    """
    if file is not None:
        raw = (await file.read()).decode("utf-8", errors="replace")
    elif code:
        raw = code
    else:
        raise HTTPException(
            status_code=422,
            detail="Provide either a 'code' form field or a file upload.",
        )

    return _mock_refactor(raw)


# ---------------------------------------------------------------------------
# Job-based modernizer endpoint
# ---------------------------------------------------------------------------

def _run_modernizer_background(job_id: str) -> None:
    from backend.app.services.job_tracker import ACTIVE_JOBS, JobStatus, update_job
    from backend.app.services.modernizer_engine import run_modernizer

    try:
        update_job(job_id, status=JobStatus.PROCESSING, active_module="modernizer")

        record = ACTIVE_JOBS.get(job_id)

        # Extract file_tree and workspace_root from the ingestion artifact
        file_tree: dict = {}
        workspace_root: str = "."
        if record is not None:
            for artifact in record.artifacts:
                if isinstance(artifact, dict) and "file_tree" in artifact:
                    file_tree = artifact["file_tree"]
                    workspace_root = artifact.get("workspace_root", ".")
                    break

        blueprints = run_modernizer(job_id, file_tree, workspace_root)

        record = ACTIVE_JOBS.get(job_id)
        current_artifacts = list(record.artifacts) if record else []
        new_artifacts = current_artifacts + [{"module": "modernizer", "blueprints": blueprints}]
        update_job(job_id, status=JobStatus.COMPLETED, active_module=None, artifacts=new_artifacts)

    except Exception as exc:
        logger.exception("[job=%s] Modernizer background task failed: %s", job_id, exc)
        from backend.app.services.job_tracker import JobStatus, update_job  # noqa: F811
        update_job(job_id, status=JobStatus.FAILED)


@router.post(
    "/modernize/run/{job_id}",
    summary="Run LLM-based modernizer for a job",
    status_code=202,
)
async def run_modernizer_job(
    job_id: str,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """
    Starts the modernizer engine as a background task for the given job.
    Returns 202 Accepted immediately; poll the job status endpoint to track progress.
    """
    from backend.app.services.job_tracker import ACTIVE_JOBS

    if job_id not in ACTIVE_JOBS:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    background_tasks.add_task(_run_modernizer_background, job_id)
    return JSONResponse(
        status_code=202,
        content={"message": "Modernizer started", "job_id": job_id},
    )
