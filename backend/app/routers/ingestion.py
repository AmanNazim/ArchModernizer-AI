"""
Ingestion Router – /api/ingest

Two ingestion paths:
  POST /api/ingest/github  – clone a public GitHub repo and return a file tree
  POST /api/ingest/zip     – upload a .zip archive and return a file tree

Both endpoints clone / extract into a secure temporary directory that is
guaranteed to be cleaned up on success or on any error.
"""

import asyncio
import os
import tempfile
import uuid
import zipfile
from typing import Any

import git
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class GitHubIngestRequest(BaseModel):
    repo_url: str


class IngestResponse(BaseModel):
    job_id: str
    file_tree: dict[str, Any]


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

_IGNORED_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist"}


def parse_directory_tree(path: str) -> dict[str, Any]:
    """
    Recursively walks *path* using os.walk and builds a nested dict.

    Keys are directory names; leaves are lists of filenames.
    Directories listed in _IGNORED_DIRS are skipped entirely.
    """
    tree: dict[str, Any] = {}

    for root, dirs, files in os.walk(path):
        # Prune ignored directories in-place so os.walk won't descend into them
        dirs[:] = [d for d in dirs if d not in _IGNORED_DIRS]

        rel_root = os.path.relpath(root, path)

        # Navigate to the correct node in the tree
        if rel_root == ".":
            node = tree
        else:
            parts = rel_root.split(os.sep)
            node = tree
            for part in parts:
                node = node.setdefault(part, {})

        # Attach files as a list under the special key "_files", then merge
        # them into the node so the top-level stays clean
        for filename in files:
            node.setdefault("_files", []).append(filename)

    return tree


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/github", response_model=IngestResponse, summary="Ingest a GitHub repository")
async def ingest_github(body: GitHubIngestRequest) -> IngestResponse:
    """
    Clones *repo_url* into a secure temporary directory, builds a file tree,
    then cleans up before returning.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            await asyncio.to_thread(git.Repo.clone_from, body.repo_url, tmp_dir)
        except git.exc.GitCommandError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        file_tree = parse_directory_tree(tmp_dir)

    return IngestResponse(job_id=str(uuid.uuid4()), file_tree=file_tree)


@router.post("/zip", response_model=IngestResponse, summary="Ingest a ZIP archive")
async def ingest_zip(file: UploadFile = File(..., description="ZIP archive to ingest")) -> IngestResponse:
    """
    Accepts a *.zip* upload, extracts it into a secure temporary directory,
    builds a file tree, then cleans up before returning.
    """
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted.")

    raw = await file.read()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Write the uploaded bytes to a temp file inside the same temp dir
        zip_path = os.path.join(tmp_dir, "upload.zip")
        extract_path = os.path.join(tmp_dir, "extracted")
        os.makedirs(extract_path, exist_ok=True)

        with open(zip_path, "wb") as fh:
            fh.write(raw)

        def _extract() -> None:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_path)

        await asyncio.to_thread(_extract)

        file_tree = parse_directory_tree(extract_path)

    return IngestResponse(job_id=str(uuid.uuid4()), file_tree=file_tree)
