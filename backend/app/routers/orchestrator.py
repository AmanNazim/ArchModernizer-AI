"""
Orchestrator Router – /api

Exposes job-status polling and analysis dispatch endpoints.  Analysis work is
offloaded to a FastAPI BackgroundTask so the HTTP response is returned
immediately (HTTP 202) while processing continues asynchronously.

Endpoints
---------
POST /api/analyze
    Accept a GitHub repository URL and a list of modules to run.
    Supported module values: ``onboarding``, ``modernize``, ``cloud``, or
    the special sentinel ``ALL`` (expands to all three).
    Creates a job, kicks off a background pipeline, and returns 202.

GET /api/status/{job_id}
    Return the current state of a job including per-module statuses.

POST /api/analyze/{job_id}   (legacy / programmatic)
    Dispatch analysis modules for an already-existing job.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import Literal

import git
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from backend.app.services.job_tracker import (
    ACTIVE_JOBS,
    JobRecord,
    JobStatus,
    ModuleStatus,
    create_job,
    get_job,
    update_job,
    update_module_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Orchestrator"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_MODULES: tuple[str, ...] = ("onboarding", "modernize", "cloud")


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """Body for the legacy /api/analyze/{job_id} endpoint."""
    modules: list[str]


class GithubAnalyzeRequest(BaseModel):
    """
    Body for the primary POST /api/analyze endpoint.

    ``github_url`` must be a non-empty string pointing at a public GitHub repo.
    ``modules`` accepts any combination of ``onboarding``, ``modernize``,
    ``cloud``, or the single value ``ALL`` to run every module.
    """
    github_url: str
    modules: list[str]

    @field_validator("github_url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("github_url must not be empty.")
        if not (v.startswith("https://") or v.startswith("http://") or v.startswith("git@")):
            raise ValueError(
                "github_url must start with https://, http://, or git@."
            )
        return v

    @field_validator("modules")
    @classmethod
    def _validate_modules(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("modules must contain at least one entry.")
        normalised = [m.strip().lower() for m in v]
        # Expand ALL sentinel
        if "all" in normalised:
            return list(VALID_MODULES)
        invalid = [m for m in normalised if m not in VALID_MODULES]
        if invalid:
            raise ValueError(
                f"Unknown module(s): {invalid}. "
                f"Valid values are: {list(VALID_MODULES)} or 'ALL'."
            )
        return normalised


# ---------------------------------------------------------------------------
# Background analysis pipeline
# ---------------------------------------------------------------------------

async def _run_analysis_pipeline(
    job_id: str,
    modules: list[str],
    workspace_root: str,
    file_tree: dict,
) -> None:
    """
    Full analysis pipeline executed as a background task.

    For each selected module the per-module status is updated independently
    so clients polling /api/status/{job_id} get granular progress.
    """
    # Initialise every selected module as PENDING
    for module in modules:
        update_module_status(job_id, module, ModuleStatus.PENDING)

    update_job(job_id, status=JobStatus.PROCESSING)

    failed_modules: list[str] = []

    for module in modules:
        update_module_status(job_id, module, ModuleStatus.PROCESSING)
        update_job(job_id, active_module=module)
        try:
            if module == "onboarding":
                await _run_onboarding(job_id, file_tree, workspace_root)
            elif module == "modernize":
                await _run_modernize(job_id, file_tree, workspace_root)
            elif module == "cloud":
                await _run_cloud(job_id, file_tree, workspace_root)
            update_module_status(job_id, module, ModuleStatus.COMPLETED)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[job=%s] Module '%s' failed: %s", job_id, module, exc)
            update_module_status(job_id, module, ModuleStatus.FAILED)
            failed_modules.append(module)

    # Overall job status: FAILED if any module failed, COMPLETED otherwise
    final_status = JobStatus.FAILED if failed_modules else JobStatus.COMPLETED
    update_job(job_id, status=final_status, active_module=None)


async def _run_onboarding(job_id: str, file_tree: dict, workspace_root: str) -> None:
    """Delegate to the RAG engine for vector indexing."""
    from backend.app.services import rag_engine  # avoid circular at module load

    await asyncio.to_thread(
        rag_engine.index_repository, job_id, file_tree, workspace_root
    )


async def _run_modernize(job_id: str, file_tree: dict, workspace_root: str) -> None:
    """Delegate to the modernizer engine."""
    from backend.app.services.modernizer_engine import run_modernizer

    blueprints = await asyncio.to_thread(
        run_modernizer, job_id, file_tree, workspace_root
    )
    record = ACTIVE_JOBS.get(job_id)
    current_artifacts = list(record.artifacts) if record else []
    update_job(
        job_id,
        artifacts=current_artifacts + [{"module": "modernizer", "blueprints": blueprints}],
    )


async def _run_cloud(job_id: str, file_tree: dict, workspace_root: str) -> None:
    """Delegate to the cloud optimizer engine."""
    from backend.app.services.cloud_engine import run_cloud_optimizer

    findings = await asyncio.to_thread(
        run_cloud_optimizer, job_id, file_tree, workspace_root
    )
    record = ACTIVE_JOBS.get(job_id)
    current_artifacts = list(record.artifacts) if record else []
    update_job(
        job_id,
        artifacts=current_artifacts + [{"module": "cloud_optimizer", "optimizations": findings}],
    )


# ---------------------------------------------------------------------------
# Legacy _run_analysis (used by /api/analyze/{job_id})
# ---------------------------------------------------------------------------

async def _run_analysis(job_id: str, modules: list[str]) -> None:
    """
    Iterate over modules, updating job state, then mark completed.

    Updates both the top-level ``active_module`` and the per-module status
    so both polling patterns work correctly.
    """
    # Initialise per-module statuses
    for module in modules:
        update_module_status(job_id, module, ModuleStatus.PENDING)

    try:
        for module in modules:
            update_module_status(job_id, module, ModuleStatus.PROCESSING)
            update_job(job_id, status=JobStatus.PROCESSING, active_module=module)
            await asyncio.sleep(0)  # yield – placeholder for real LLM work
            update_module_status(job_id, module, ModuleStatus.COMPLETED)
        update_job(job_id, status=JobStatus.COMPLETED, active_module=None)
    except Exception:
        update_job(job_id, status=JobStatus.FAILED)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/status/{job_id}", response_model=JobRecord, summary="Get job status")
async def get_job_status(job_id: str) -> JobRecord:
    """Return the current state of a job by its ID, including per-module statuses."""
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return record


@router.post("/api/analyze", summary="Analyze a GitHub repository", status_code=202)
async def analyze_github(
    body: GithubAnalyzeRequest,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """
    Primary analysis entry point.

    1. Validates ``github_url`` and ``modules``.
    2. Creates a new job in PENDING state.
    3. Clones the repository to a temporary directory (synchronous, fast-path).
    4. Builds a file tree and stores it as a job artifact.
    5. Schedules the analysis pipeline as a background task.
    6. Returns **202 Accepted** with the new ``job_id``.

    ``modules`` accepts: ``onboarding``, ``modernize``, ``cloud``, or ``ALL``.
    """
    job = create_job()
    job_id = job.job_id

    # Clone repository synchronously before accepting the background task so
    # we can return a 422 immediately if the URL is invalid.
    try:
        tmp_dir = tempfile.mkdtemp(prefix=f"archai_{job_id}_")
        await asyncio.to_thread(git.Repo.clone_from, body.github_url, tmp_dir)
    except git.exc.GitCommandError as exc:
        # Remove the job we just created – it will never run.
        ACTIVE_JOBS.pop(job_id, None)
        raise HTTPException(
            status_code=422,
            detail=f"Failed to clone repository: {exc}",
        ) from exc

    # Build the file tree from the cloned workspace
    from backend.app.routers.ingestion import parse_directory_tree

    file_tree = parse_directory_tree(tmp_dir)

    # Persist ingestion artifact so downstream modules can use it
    update_job(
        job_id,
        artifacts=[{"file_tree": file_tree, "workspace_root": tmp_dir}],
    )

    background_tasks.add_task(
        _run_analysis_pipeline, job_id, body.modules, tmp_dir, file_tree
    )

    return JSONResponse(
        status_code=202,
        content={
            "message": "Analysis started",
            "job_id": job_id,
            "modules": body.modules,
        },
    )


@router.post("/api/analyze/{job_id}", summary="Start analysis for an existing job")
async def analyze_job(
    job_id: str,
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """
    Schedule background analysis over the supplied modules for an already-existing job.

    Returns **202 Accepted** immediately; poll `/api/status/{job_id}` for progress.
    """
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    background_tasks.add_task(_run_analysis, job_id, body.modules)
    return JSONResponse(
        status_code=202,
        content={"message": "Analysis started", "job_id": job_id},
    )
