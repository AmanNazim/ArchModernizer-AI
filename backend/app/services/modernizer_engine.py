"""
Modernizer Engine – legacy-to-microservices blueprint generator.

Reads application logic files from an ingested repository, chunks them, and
sends each chunk sequentially to a local Ollama LLM to identify DDD bounded
contexts and apply the Strangler Fig pattern.  Outputs a structured list of
microservice blueprints in the job artifacts.
"""

import json
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_APP_EXTENSIONS = {".py", ".java", ".js", ".ts", ".cs", ".go"}
_CHUNK_SIZE = 2000
_CHUNK_OVERLAP = 200
_OLLAMA_URL = "http://localhost:11434/api/generate"
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "codellama")


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def _collect_files(file_tree: dict, workspace_root: str) -> list[str]:
    """Walk the nested file_tree dict and return absolute paths for app logic files."""
    root = Path(workspace_root)
    collected: list[str] = []

    def _walk(node: dict, current_path: Path) -> None:
        for key, value in node.items():
            if key == "_files":
                # value is a list of file names
                for fname in value:
                    fpath = current_path / fname
                    if Path(fname).suffix in _APP_EXTENSIONS:
                        collected.append(str(fpath))
            elif isinstance(value, dict):
                _walk(value, current_path / key)

    _walk(file_tree, root)
    return collected


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks of ~_CHUNK_SIZE characters."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - _CHUNK_OVERLAP
    return chunks


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _call_ollama(file_path: str, chunk: str) -> list[dict]:
    """Send one chunk to Ollama and return parsed services list (may be empty)."""
    prompt = (
        "You are an expert software architect. Analyze the following legacy code chunk "
        "and identify microservice boundaries using Domain-Driven Design (Strangler Fig pattern).\n\n"
        "Output ONLY valid JSON (no markdown, no explanation) with this exact schema:\n"
        "{\n"
        '  "services": [\n'
        "    {\n"
        '      "service_name": "<name>",\n'
        '      "description": "<what this service does>",\n'
        '      "original_files_referenced": ["<file_path>"],\n'
        '      "suggested_endpoints": ["/api/resource"],\n'
        '      "openapi_spec_yaml": "<draft OpenAPI 3.0 yaml string>"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Code chunk from file {file_path}:\n{chunk}"
    )

    try:
        response = httpx.post(
            _OLLAMA_URL,
            json={"model": _OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120.0,
        )
        response.raise_for_status()
        model_text = response.json().get("response", "")
        parsed = json.loads(model_text)
        return parsed.get("services", [])
    except (httpx.ConnectError, httpx.TimeoutException):
        raise  # bubble up so caller can trigger fallback
    except (httpx.HTTPStatusError, json.JSONDecodeError, KeyError) as exc:
        logger.warning("Skipping chunk from %s – %s: %s", file_path, type(exc).__name__, exc)
        return []


# ---------------------------------------------------------------------------
# Fallback blueprint
# ---------------------------------------------------------------------------

def _mock_blueprint(file_path: str) -> dict:
    stem = Path(file_path).stem
    return {
        "service_name": f"{stem}-service",
        "description": f"Microservice extracted from {file_path}",
        "original_files_referenced": [file_path],
        "suggested_endpoints": [f"/api/{stem}"],
        "openapi_spec_yaml": (
            f"openapi: 3.0.0\ninfo:\n  title: {stem}-service\n  version: 1.0.0\npaths: {{}}\n"
        ),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_modernizer(job_id: str, file_tree: dict, workspace_root: str) -> list[dict]:
    """
    Returns a list of microservice blueprint dicts.
    Each dict has keys: service_name, description, original_files_referenced,
    suggested_endpoints, openapi_spec_yaml.
    """
    logger.info("[job=%s] Modernizer started", job_id)

    files = _collect_files(file_tree, workspace_root)
    logger.info("[job=%s] Discovered %d application file(s)", job_id, len(files))

    all_services: list[dict] = []
    ollama_reachable = True

    for file_path in files:
        try:
            text = Path(file_path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("[job=%s] Cannot read %s – %s", job_id, file_path, exc)
            continue

        if not ollama_reachable:
            all_services.append(_mock_blueprint(file_path))
            continue

        chunks = _chunk_text(text)
        for chunk in chunks:
            try:
                services = _call_ollama(file_path, chunk)
                all_services.extend(services)
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                logger.warning(
                    "[job=%s] Ollama not reachable (%s); switching to fallback mode", job_id, exc
                )
                ollama_reachable = False
                all_services.append(_mock_blueprint(file_path))
                break  # move on to next file using fallback

    # Deduplicate by service_name – last occurrence wins
    merged: dict[str, dict] = {}
    for svc in all_services:
        name = svc.get("service_name", "")
        if name:
            merged[name] = svc

    blueprints = list(merged.values())
    logger.info("[job=%s] Modernizer finished – %d blueprint(s) produced", job_id, len(blueprints))
    return blueprints
