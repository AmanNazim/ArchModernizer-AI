"""
Cloud Optimizer Router – /api/optimize

Accepts Terraform (.tf) or Kubernetes YAML manifests as text, flags
security/compliance risks, and returns structured optimization suggestions.
The analysis logic is mocked; swap `_analyze_manifest` for a real LLM or
rule-engine call when ready.
"""

import re
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class OptimizationFinding(BaseModel):
    severity: str          # "critical" | "warning" | "info"
    category: str          # e.g. "security", "cost", "reliability"
    description: str
    recommendation: str
    line_hint: Optional[int] = None


class OptimizeResponse(BaseModel):
    manifest_type: str                     # "terraform" | "kubernetes" | "unknown"
    total_findings: int
    critical_count: int
    warning_count: int
    info_count: int
    findings: list[OptimizationFinding]
    overall_score: int                     # 0–100 (100 = fully optimised)


# ---------------------------------------------------------------------------
# Mock analysis logic
# ---------------------------------------------------------------------------

# Simple keyword rules – each entry: (regex, severity, category, description, recommendation)
_TERRAFORM_RULES: list[tuple] = [
    (
        r'publicly_accessible\s*=\s*true',
        "critical", "security",
        "RDS or resource is publicly accessible.",
        "Set `publicly_accessible = false` and restrict access via security groups.",
    ),
    (
        r'cidr_blocks\s*=\s*\[\"0\.0\.0\.0/0\"\]',
        "critical", "security",
        "Security group allows unrestricted inbound traffic (0.0.0.0/0).",
        "Restrict CIDR blocks to known IP ranges or private subnets.",
    ),
    (
        r'skip_final_snapshot\s*=\s*true',
        "warning", "reliability",
        "RDS final snapshot is disabled – data loss risk on destroy.",
        "Set `skip_final_snapshot = false` for production databases.",
    ),
    (
        r'instance_type\s*=\s*\"(t2\.\w+|t3\.micro)\"',
        "info", "cost",
        "Small/burstable instance type detected.",
        "Validate that burst credit balance is sufficient under sustained load.",
    ),
    (
        r'#\s*TODO|#\s*FIXME',
        "info", "reliability",
        "Unresolved TODO/FIXME comment found in Terraform config.",
        "Review and resolve outstanding TODO items before production deployment.",
    ),
]

_KUBERNETES_RULES: list[tuple] = [
    (
        r'privileged:\s*true',
        "critical", "security",
        "Container is running in privileged mode.",
        "Remove `privileged: true` unless absolutely required; use fine-grained capabilities instead.",
    ),
    (
        r'runAsRoot:\s*true|runAsUser:\s*0',
        "critical", "security",
        "Container is configured to run as root.",
        "Set `runAsNonRoot: true` and specify a non-zero `runAsUser`.",
    ),
    (
        r'image:\s*\S+:latest',
        "warning", "reliability",
        "Container image uses the `latest` tag – non-deterministic deployments.",
        "Pin the image to a specific digest or semantic version tag.",
    ),
    (
        r'resources:\s*\{\}|(?<!#)(?:^|\n)\s{6,}(?!resources)',
        "warning", "cost",
        "No resource requests/limits detected for a container.",
        "Define `resources.requests` and `resources.limits` for every container.",
    ),
    (
        r'hostNetwork:\s*true',
        "warning", "security",
        "Pod shares the host network namespace.",
        "Avoid `hostNetwork: true`; use ClusterIP services instead.",
    ),
    (
        r'allowPrivilegeEscalation:\s*true',
        "warning", "security",
        "`allowPrivilegeEscalation` is enabled.",
        "Set `allowPrivilegeEscalation: false` in the container security context.",
    ),
]


def _detect_type(text: str) -> str:
    if re.search(r'\bresource\b|\bprovider\b|\bterraform\b', text):
        return "terraform"
    if re.search(r'\bapiVersion\b|\bkind\b|\bmetadata\b', text):
        return "kubernetes"
    return "unknown"


def _analyze_manifest(text: str) -> OptimizeResponse:
    manifest_type = _detect_type(text)
    rules = _TERRAFORM_RULES if manifest_type == "terraform" else _KUBERNETES_RULES

    findings: list[OptimizationFinding] = []
    lines = text.splitlines()

    for pattern, severity, category, description, recommendation in rules:
        for i, line in enumerate(lines, start=1):
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(
                    OptimizationFinding(
                        severity=severity,
                        category=category,
                        description=description,
                        recommendation=recommendation,
                        line_hint=i,
                    )
                )
                break  # one finding per rule per manifest

    critical = sum(1 for f in findings if f.severity == "critical")
    warning = sum(1 for f in findings if f.severity == "warning")
    info = sum(1 for f in findings if f.severity == "info")

    # Score degrades 20 pts per critical, 10 per warning, 5 per info
    score = max(0, 100 - critical * 20 - warning * 10 - info * 5)

    return OptimizeResponse(
        manifest_type=manifest_type,
        total_findings=len(findings),
        critical_count=critical,
        warning_count=warning,
        info_count=info,
        findings=findings,
        overall_score=score,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/optimize", response_model=OptimizeResponse, summary="Optimize IaC manifest")
async def optimize_manifest(
    manifest: Optional[str] = Form(None, description="Raw Terraform / Kubernetes YAML text"),
    file: Optional[UploadFile] = File(None, description="Uploaded .tf or .yaml/.yml file"),
) -> OptimizeResponse:
    """
    Accepts either a raw **manifest** string or an **uploaded file** (.tf / .yaml),
    then returns a list of security, cost, and reliability findings with recommendations.
    """
    if file is not None:
        raw = (await file.read()).decode("utf-8", errors="replace")
    elif manifest:
        raw = manifest
    else:
        raise HTTPException(
            status_code=422,
            detail="Provide either a 'manifest' form field or a file upload.",
        )

    return _analyze_manifest(raw)
