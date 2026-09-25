"""
Cloud Optimizer Engine – IaC security and cost analysis.

Reads infrastructure/deployment files from an ingested repository and sends
them to a local Ollama LLM to identify security vulnerabilities and cost-waste
patterns.  Outputs a structured list of optimization findings in job artifacts.
"""

import json
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_IAC_EXTENSIONS = {".tf", ".yaml", ".yml"}
_IAC_EXACT_NAMES = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml"}

_OLLAMA_URL = "http://localhost:11434/api/generate"
_OLLAMA_TIMEOUT = 120.0

_PROMPT_TEMPLATE = """\
You are a cloud security and cost optimization expert. Analyze the following Infrastructure-as-Code file and identify ALL security vulnerabilities and cost optimization opportunities.

Output ONLY valid JSON (no markdown, no explanation) with this exact schema:
{{
  "optimizations": [
    {{
      "file_path": "<path to the file>",
      "issue_type": "Cost or Security",
      "severity": "Low, Medium, or High",
      "description": "<clear description of the issue>",
      "optimized_code_snippet": "<corrected or improved code snippet>"
    }}
  ]
}}

Focus on: hardcoded secrets, overly permissive IAM roles, deprecated Terraform modules, expensive/over-provisioned instance types (suggest t3.micro or autoscaling groups instead of static large instances), open ports, missing encryption.

File: {file_path}
Contents:
{file_contents}
"""


def _collect_iac_files(file_tree: dict, workspace_root: str) -> list[str]:
    """Walk the nested file_tree dict and return paths to IaC/deployment files."""
    results: list[str] = []

    def _walk(node: dict, current_path: Path) -> None:
        for key, value in node.items():
            if key == "_files":
                for filename in value:
                    name = Path(filename).name
                    suffix = Path(filename).suffix
                    if suffix in _IAC_EXTENSIONS or name in _IAC_EXACT_NAMES:
                        results.append(str(current_path / filename))
            else:
                if isinstance(value, dict):
                    _walk(value, current_path / key)

    _walk(file_tree, Path(workspace_root))
    return results


def _fallback_finding(file_path: str) -> dict:
    return {
        "file_path": file_path,
        "issue_type": "Security",
        "severity": "Low",
        "description": "Automated analysis unavailable – manual review recommended.",
        "optimized_code_snippet": "# Review this file manually for security and cost issues.",
    }


def _analyze_file(file_path: str, model: str) -> list[dict]:
    """Call Ollama for a single file and return the optimizations list."""
    try:
        contents = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Could not read %s: %s", file_path, exc)
        return []

    prompt = _PROMPT_TEMPLATE.format(file_path=file_path, file_contents=contents)

    response = httpx.post(
        _OLLAMA_URL,
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=_OLLAMA_TIMEOUT,
    )
    response.raise_for_status()

    raw_text: str = response.json().get("response", "")
    try:
        parsed = json.loads(raw_text)
        optimizations = parsed.get("optimizations", [])
        valid = [
            item for item in optimizations
            if all(k in item for k in (
                "file_path", "issue_type", "severity", "description", "optimized_code_snippet"
            ))
        ]
        return valid
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.warning("JSON parse error for %s: %s", file_path, exc)
        return []


def run_cloud_optimizer(job_id: str, file_tree: dict, workspace_root: str) -> list[dict]:
    """
    Returns a list of optimization finding dicts.
    Each finding has keys: file_path, issue_type, severity, description, optimized_code_snippet.
    Returns [{"message": "No infrastructure files detected"}] if no IaC files exist.
    """
    model = os.environ.get("OLLAMA_MODEL", "codellama")

    iac_files = _collect_iac_files(file_tree, workspace_root)
    logger.info("job=%s cloud_optimizer found %d IaC file(s)", job_id, len(iac_files))

    if not iac_files:
        return [{"message": "No infrastructure files detected"}]

    findings: list[dict] = []
    use_fallback = False

    for file_path in iac_files:
        if use_fallback:
            findings.append(_fallback_finding(file_path))
            continue

        try:
            file_findings = _analyze_file(file_path, model)
            if file_findings:
                findings.extend(file_findings)
            else:
                logger.info("No findings returned for %s", file_path)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning(
                "Ollama unreachable for %s (%s); switching to fallback for all remaining files.",
                file_path, exc,
            )
            use_fallback = True
            findings.append(_fallback_finding(file_path))
        except httpx.HTTPError as exc:
            logger.warning("HTTP error analyzing %s: %s", file_path, exc)

    return findings
