"""
Onboarding Router – /api/onboarding

Exposes repository indexing and context-grounded Q&A endpoints.

Endpoints
---------
POST /api/onboarding/index/{job_id}
    Accepts the file_tree (from the ingestion router) and the path to the
    workspace on disk.  Triggers a background task that chunks all supported
    source files, embeds them in micro-batches, and upserts the vectors into a
    per-job Qdrant collection.

POST /api/onboarding/chat
    Embeds the user query, retrieves the top-4 most relevant code chunks, and
    returns a structured answer with source references.

Notes
-----
* The LLM call falls back to Ollama (``OLLAMA_URL`` / ``OLLAMA_MODEL`` env
  vars, defaulting to ``llama3`` on localhost:11434).  If Ollama is unavailable
  the endpoint still returns the retrieved context so callers can render it
  without an answer.
* Background indexing updates job state in ``job_tracker.py`` so clients can
  poll ``GET /api/status/{job_id}`` for progress.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.app.services import rag_engine
from backend.app.services.job_tracker import JobStatus, get_job, update_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])

# ---------------------------------------------------------------------------
# LLM configuration (Ollama)
# ---------------------------------------------------------------------------

OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class IndexRequest(BaseModel):
    """Body for the indexing endpoint."""
    file_tree: dict[str, Any]
    workspace_root: str


class ChatRequest(BaseModel):
    """Body for the chat endpoint."""
    job_id: str
    query: str


class SourceRef(BaseModel):
    file_path: str
    lines: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceRef]


# ---------------------------------------------------------------------------
# Background indexing task
# ---------------------------------------------------------------------------


async def _index_task(job_id: str, file_tree: dict, workspace_root: str) -> None:
    """
    Run inside a FastAPI BackgroundTask.

    Delegates the CPU-bound indexing work to a thread so the event loop
    remains unblocked, then updates the job record with the final status.
    """
    update_job(job_id, status=JobStatus.PROCESSING, active_module="onboarding")
    try:
        await asyncio.to_thread(
            rag_engine.index_repository, job_id, file_tree, workspace_root
        )
        update_job(job_id, status=JobStatus.COMPLETED, active_module="onboarding")
        logger.info("Indexing completed for job %s", job_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Indexing failed for job %s: %s", job_id, exc)
        update_job(job_id, status=JobStatus.FAILED, active_module="onboarding")


# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are RepoVibe, an expert developer-onboarding assistant. "
    "Answer the user's question using ONLY the code context provided below. "
    "Be concise and cite file paths when relevant."
)


def _build_context_block(results: list[rag_engine.SearchResult]) -> str:
    """Assemble retrieved chunks into a readable context window."""
    parts: list[str] = []
    for idx, r in enumerate(results, start=1):
        parts.append(
            f"--- [{idx}] {r.file_path}  lines {r.start_line}–{r.end_line} ---\n{r.text}"
        )
    return "\n\n".join(parts)


async def _call_ollama(context: str, query: str) -> str:
    """
    Send a chat completion request to Ollama and return the assistant reply.

    Returns an empty string on any network / timeout error so the caller can
    still return sources without an answer.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Context:\n{context}\n\n"
                    f"Question: {query}"
                ),
            },
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ollama call failed (%s); returning sources only.", exc)
        return ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/index/{job_id}",
    status_code=202,
    summary="Trigger background vector indexing for a job",
)
async def index_repository(
    job_id: str,
    body: IndexRequest,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """
    Enqueue background chunking + embedding of the workspace at
    ``workspace_root``.

    Returns **202 Accepted** immediately.  Poll ``GET /api/status/{job_id}``
    to detect completion.  The job must already exist (created by the
    ingestion router or the orchestrator).
    """
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    background_tasks.add_task(
        _index_task, job_id, body.file_tree, body.workspace_root
    )
    return JSONResponse(
        status_code=202,
        content={"message": "Indexing started", "job_id": job_id},
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Query the repository with a natural-language question",
)
async def chat(body: ChatRequest) -> ChatResponse:
    """
    Retrieve the top-4 most relevant code chunks for *query* and pass them to
    the LLM to generate a grounded answer.

    If the job has not been indexed yet a ``404`` is returned.
    If Ollama is unreachable the endpoint still returns ``sources`` with an
    empty ``answer`` string.
    """
    record = get_job(body.job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job '{body.job_id}' not found.")

    # Perform vector search in a thread (fastembed / Qdrant are sync)
    results: list[rag_engine.SearchResult] = await asyncio.to_thread(
        rag_engine.search, body.job_id, body.query, 4
    )

    if not results:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No index found for job '{body.job_id}'. "
                "Call POST /api/onboarding/index/{job_id} first."
            ),
        )

    context = _build_context_block(results)
    answer = await _call_ollama(context, body.query)

    sources = [
        SourceRef(
            file_path=r.file_path,
            lines=f"{r.start_line}–{r.end_line}",
        )
        for r in results
    ]

    return ChatResponse(answer=answer, sources=sources)


@router.delete(
    "/index/{job_id}",
    status_code=200,
    summary="Delete the vector index for a job",
)
async def delete_index(job_id: str) -> JSONResponse:
    """
    Purge the Qdrant collection for *job_id*.

    Safe to call when the temporary workspace is deleted or a session expires.
    """
    await asyncio.to_thread(rag_engine.cleanup_job_index, job_id)
    return JSONResponse(content={"message": "Index deleted", "job_id": job_id})
