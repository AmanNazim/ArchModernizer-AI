"""
Job Tracker – in-memory job store.

Provides a lightweight job lifecycle manager (create / get / update) used by
the Orchestrator router to track background analysis tasks.
"""

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ModuleStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus
    active_module: str | None = None
    # Per-module granular status – keyed by module name
    module_statuses: dict[str, ModuleStatus] = {}
    artifacts: list[Any] = []


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

ACTIVE_JOBS: dict[str, JobRecord] = {}


# ---------------------------------------------------------------------------
# Store helpers
# ---------------------------------------------------------------------------

def create_job() -> JobRecord:
    """Create a new PENDING job, store it, and return it."""
    record = JobRecord(job_id=str(uuid.uuid4()), status=JobStatus.PENDING)
    ACTIVE_JOBS[record.job_id] = record
    return record


def get_job(job_id: str) -> JobRecord | None:
    """Retrieve job by id, return None if not found."""
    return ACTIVE_JOBS.get(job_id)


def update_job(job_id: str, **kwargs) -> JobRecord | None:
    """Update fields on a job in-place, return updated record or None if not found."""
    record = ACTIVE_JOBS.get(job_id)
    if record is None:
        return None
    updated = record.model_copy(update=kwargs)
    ACTIVE_JOBS[job_id] = updated
    return updated


def update_module_status(
    job_id: str, module: str, status: ModuleStatus
) -> JobRecord | None:
    """
    Update the status for a single module within a job.

    Does not touch the top-level ``JobRecord.status``; callers must separately
    decide when to mark the overall job COMPLETED or FAILED.
    """
    record = ACTIVE_JOBS.get(job_id)
    if record is None:
        return None
    new_statuses = dict(record.module_statuses)
    new_statuses[module] = status
    updated = record.model_copy(update={"module_statuses": new_statuses})
    ACTIVE_JOBS[job_id] = updated
    return updated
