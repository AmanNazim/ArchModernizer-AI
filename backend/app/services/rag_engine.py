"""
RAG Engine – vector indexing and retrieval for repository codebases.

Architecture
------------
* Qdrant runs in *local file-backed* mode under ``QDRANT_PATH`` (default
  ``./qdrant_storage``).  No external server is required.
* Embeddings are generated with ``fastembed`` (BAAI/bge-small-en-v1.5,
  384-dim) in micro-batches of ≤16 to avoid OOM on 8 GB machines.
* One Qdrant collection per ``job_id`` keeps indexes isolated.
* Chunks are 600 characters (~150 tokens) with a 100-character overlap,
  roughly matching the 500-800 token / 100 overlap spec.

Public API
----------
    chunk_repository(file_tree, workspace_root)  ->  list[ChunkRecord]
    index_repository(job_id, file_tree, workspace_root)  ->  None
    search(job_id, query, top_k)  ->  list[SearchResult]
    cleanup_job_index(job_id)  ->  None
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)
from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

QDRANT_PATH: str = os.getenv("QDRANT_PATH", "./qdrant_storage")
EMBED_MODEL: str = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
EMBED_DIM: int = 384          # bge-small-en-v1.5 output dimension
CHUNK_SIZE: int = 600         # characters per chunk
CHUNK_OVERLAP: int = 100      # character overlap between consecutive chunks
EMBED_BATCH: int = 16         # max docs per embedding call

# File extensions the pipeline will index
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".js", ".ts", ".tsx", ".tf", ".yaml", ".yml", ".md"}
)

# Files / directories to skip during indexing
SKIP_FILENAMES: frozenset[str] = frozenset(
    {"package-lock.json", "poetry.lock", "yarn.lock", "pnpm-lock.yaml"}
)

SKIP_DIRNAMES: frozenset[str] = frozenset(
    {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build", ".mypy_cache"}
)

# ---------------------------------------------------------------------------
# Lazy singletons – initialised once per process to avoid re-loading weights
# ---------------------------------------------------------------------------

_qdrant_client: QdrantClient | None = None
_embed_model: TextEmbedding | None = None


def _get_qdrant() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        Path(QDRANT_PATH).mkdir(parents=True, exist_ok=True)
        _qdrant_client = QdrantClient(path=QDRANT_PATH)
        logger.info("Qdrant initialised at %s", QDRANT_PATH)
    return _qdrant_client


def _get_embedder() -> TextEmbedding:
    global _embed_model
    if _embed_model is None:
        logger.info("Loading embedding model %s …", EMBED_MODEL)
        _embed_model = TextEmbedding(model_name=EMBED_MODEL)
        logger.info("Embedding model ready.")
    return _embed_model


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

@dataclass
class ChunkRecord:
    """A single text chunk with associated metadata."""
    text: str
    file_path: str
    start_line: int
    end_line: int
    file_extension: str
    job_id: str = ""


@dataclass
class SearchResult:
    """A ranked retrieval result returned by :func:`search`."""
    text: str
    file_path: str
    start_line: int
    end_line: int
    score: float


# ---------------------------------------------------------------------------
# Chunking helpers
# ---------------------------------------------------------------------------

def _is_binary(path: Path, sample_size: int = 512) -> bool:
    """Return True when *path* looks like a binary file."""
    try:
        with path.open("rb") as fh:
            chunk = fh.read(sample_size)
        return b"\x00" in chunk
    except OSError:
        return True


def _char_splitter(text: str, size: int, overlap: int) -> Generator[tuple[str, int, int], None, None]:
    """
    Yield ``(chunk_text, start_char, end_char)`` tuples by sliding a window of
    ``size`` characters with ``overlap`` character step-back.

    Lines are preserved as best-effort by splitting on newlines so that
    ``start_line`` / ``end_line`` metadata remains meaningful.
    """
    start = 0
    length = len(text)
    lines = text.splitlines(keepends=True)
    # Build a cumulative character offset → line-number map for fast lookup
    offsets: list[int] = []
    acc = 0
    for line in lines:
        offsets.append(acc)
        acc += len(line)

    def _char_to_line(char_pos: int) -> int:
        """Binary-search the offset list for the line number at *char_pos*."""
        lo, hi = 0, len(offsets) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if offsets[mid] <= char_pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1  # 1-based

    while start < length:
        end = min(start + size, length)
        yield text[start:end], _char_to_line(start), _char_to_line(end - 1)
        if end == length:
            break
        start = end - overlap


def _iter_source_files(file_tree: dict, workspace_root: str) -> Generator[Path, None, None]:
    """
    Walk *file_tree* (the nested dict produced by the ingestion router) and
    yield :class:`~pathlib.Path` objects for every supported, non-binary source
    file under *workspace_root*.

    The file_tree structure is::

        {
            "subdir": {
                "_files": ["a.py", "b.ts"],
                "nested": {"_files": ["c.md"]}
            },
            "_files": ["README.md"]
        }
    """
    root = Path(workspace_root)

    def _walk(node: dict, current_path: Path) -> Generator[Path, None, None]:
        for filename in node.get("_files", []):
            if filename in SKIP_FILENAMES:
                continue
            file_path = current_path / filename
            ext = file_path.suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            if not file_path.exists():
                continue
            if _is_binary(file_path):
                continue
            yield file_path

        for key, value in node.items():
            if key == "_files":
                continue
            if key in SKIP_DIRNAMES:
                continue
            if isinstance(value, dict):
                yield from _walk(value, current_path / key)

    yield from _walk(file_tree, root)


# ---------------------------------------------------------------------------
# Public: chunking
# ---------------------------------------------------------------------------

def chunk_repository(file_tree: dict, workspace_root: str, job_id: str = "") -> list[ChunkRecord]:
    """
    Iterate through all supported source files in *workspace_root* guided by
    *file_tree* and return a flat list of :class:`ChunkRecord` objects ready
    for embedding.
    """
    records: list[ChunkRecord] = []
    for path in _iter_source_files(file_tree, workspace_root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue

        rel_path = str(path.relative_to(workspace_root))
        ext = path.suffix.lower()

        for chunk_text, start_line, end_line in _char_splitter(text, CHUNK_SIZE, CHUNK_OVERLAP):
            if not chunk_text.strip():
                continue
            records.append(
                ChunkRecord(
                    text=chunk_text,
                    file_path=rel_path,
                    start_line=start_line,
                    end_line=end_line,
                    file_extension=ext,
                    job_id=job_id,
                )
            )

    logger.info("chunk_repository produced %d chunks for job %s", len(records), job_id)
    return records


# ---------------------------------------------------------------------------
# Public: indexing
# ---------------------------------------------------------------------------

def _collection_name(job_id: str) -> str:
    return f"repo_{job_id.replace('-', '_')}"


def index_repository(job_id: str, file_tree: dict, workspace_root: str) -> None:
    """
    Chunk *workspace_root*, embed the chunks in micro-batches, and upsert them
    into a Qdrant collection scoped by *job_id*.

    Existing collections for the same *job_id* are deleted first so this call
    is idempotent.
    """
    client = _get_qdrant()
    embedder = _get_embedder()
    col = _collection_name(job_id)

    # Re-create collection for idempotent re-indexing
    existing = {c.name for c in client.get_collections().collections}
    if col in existing:
        client.delete_collection(col)

    client.create_collection(
        collection_name=col,
        vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
    )

    chunks = chunk_repository(file_tree, workspace_root, job_id=job_id)
    if not chunks:
        logger.warning("No indexable chunks found for job %s", job_id)
        return

    # Process in micro-batches to keep RAM usage bounded
    for batch_start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[batch_start : batch_start + EMBED_BATCH]
        texts = [c.text for c in batch]

        # fastembed returns a generator; consume into list
        vectors = list(embedder.embed(texts))

        points = [
            PointStruct(
                id=batch_start + i,
                vector=list(vec),
                payload={
                    "text": chunk.text,
                    "file_path": chunk.file_path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "file_extension": chunk.file_extension,
                    "job_id": chunk.job_id,
                },
            )
            for i, (chunk, vec) in enumerate(zip(batch, vectors))
        ]
        client.upsert(collection_name=col, points=points)

    logger.info("Indexed %d chunks into collection '%s'", len(chunks), col)


# ---------------------------------------------------------------------------
# Public: retrieval
# ---------------------------------------------------------------------------

def search(job_id: str, query: str, top_k: int = 4) -> list[SearchResult]:
    """
    Embed *query* and return the top-*k* most similar chunks from the
    collection for *job_id*.

    Returns an empty list if the collection does not exist.
    """
    client = _get_qdrant()
    embedder = _get_embedder()
    col = _collection_name(job_id)

    existing = {c.name for c in client.get_collections().collections}
    if col not in existing:
        logger.warning("Collection '%s' not found – job not indexed yet.", col)
        return []

    query_vector = list(embedder.embed([query]))[0]
    hits = client.search(collection_name=col, query_vector=list(query_vector), limit=top_k)

    return [
        SearchResult(
            text=hit.payload.get("text", ""),
            file_path=hit.payload.get("file_path", ""),
            start_line=hit.payload.get("start_line", 0),
            end_line=hit.payload.get("end_line", 0),
            score=hit.score,
        )
        for hit in hits
    ]


# ---------------------------------------------------------------------------
# Public: cleanup
# ---------------------------------------------------------------------------

def cleanup_job_index(job_id: str) -> None:
    """Delete the Qdrant collection for *job_id* if it exists."""
    client = _get_qdrant()
    col = _collection_name(job_id)
    existing = {c.name for c in client.get_collections().collections}
    if col in existing:
        client.delete_collection(col)
        logger.info("Deleted Qdrant collection '%s'", col)
