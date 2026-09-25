"""
Unit tests for the ArchModernizer AI API gateway.

Coverage
--------
* JobTracker  – create_job, get_job, update_job, update_module_status
* GithubAnalyzeRequest validator – url & module validation, ALL expansion
* POST /api/analyze  – happy path (mocked clone), invalid URL, bad modules
* GET  /api/status/{job_id} – found / not-found
* POST /api/analyze/{job_id} (legacy) – happy path, not-found
* _run_analysis  – per-module status progression
* _run_analysis_pipeline – success, partial failure, ALL-module expansion
* Ingestion router helpers – parse_directory_tree
* /api/refactor  – code form field, file upload, missing input
* /api/optimize  – terraform manifest, kubernetes manifest, missing input
* /health        – liveness probe
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# App and service imports
# ---------------------------------------------------------------------------
from backend.app.main import app
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
from backend.app.routers.orchestrator import (
    GithubAnalyzeRequest,
    VALID_MODULES,
    _run_analysis,
    _run_analysis_pipeline,
)
from backend.app.routers.ingestion import parse_directory_tree

# ---------------------------------------------------------------------------
# Test client fixture
# ---------------------------------------------------------------------------

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_jobs() -> None:
    """Wipe the in-memory store between tests."""
    ACTIVE_JOBS.clear()


# ===========================================================================
# 1. JobTracker unit tests
# ===========================================================================

class TestJobTracker:
    def setup_method(self):
        _clear_jobs()

    # --- create_job ---------------------------------------------------------

    def test_create_job_returns_pending_record(self):
        record = create_job()
        assert record.status == JobStatus.PENDING
        assert record.job_id != ""
        assert record.active_module is None
        assert record.module_statuses == {}
        assert record.artifacts == []

    def test_create_job_stores_in_active_jobs(self):
        record = create_job()
        assert record.job_id in ACTIVE_JOBS

    def test_create_job_generates_unique_ids(self):
        ids = {create_job().job_id for _ in range(10)}
        assert len(ids) == 10

    # --- get_job ------------------------------------------------------------

    def test_get_job_returns_existing_record(self):
        record = create_job()
        fetched = get_job(record.job_id)
        assert fetched is not None
        assert fetched.job_id == record.job_id

    def test_get_job_returns_none_for_unknown(self):
        assert get_job("nonexistent-id") is None

    # --- update_job ---------------------------------------------------------

    def test_update_job_changes_status(self):
        record = create_job()
        updated = update_job(record.job_id, status=JobStatus.PROCESSING)
        assert updated is not None
        assert updated.status == JobStatus.PROCESSING
        # Verify persisted
        assert get_job(record.job_id).status == JobStatus.PROCESSING  # type: ignore[union-attr]

    def test_update_job_sets_active_module(self):
        record = create_job()
        updated = update_job(record.job_id, active_module="modernize")
        assert updated is not None
        assert updated.active_module == "modernize"

    def test_update_job_returns_none_for_unknown(self):
        assert update_job("bad-id", status=JobStatus.FAILED) is None

    def test_update_job_appends_artifacts(self):
        record = create_job()
        update_job(record.job_id, artifacts=[{"key": "value"}])
        fetched = get_job(record.job_id)
        assert fetched is not None
        assert fetched.artifacts == [{"key": "value"}]

    # --- update_module_status -----------------------------------------------

    def test_update_module_status_sets_status(self):
        record = create_job()
        updated = update_module_status(record.job_id, "onboarding", ModuleStatus.PROCESSING)
        assert updated is not None
        assert updated.module_statuses["onboarding"] == ModuleStatus.PROCESSING

    def test_update_module_status_does_not_affect_other_modules(self):
        record = create_job()
        update_module_status(record.job_id, "onboarding", ModuleStatus.COMPLETED)
        update_module_status(record.job_id, "modernize", ModuleStatus.PROCESSING)
        fetched = get_job(record.job_id)
        assert fetched is not None
        assert fetched.module_statuses["onboarding"] == ModuleStatus.COMPLETED
        assert fetched.module_statuses["modernize"] == ModuleStatus.PROCESSING

    def test_update_module_status_returns_none_for_unknown_job(self):
        assert update_module_status("no-such-id", "cloud", ModuleStatus.FAILED) is None

    def test_update_module_status_overwrites_existing(self):
        record = create_job()
        update_module_status(record.job_id, "cloud", ModuleStatus.PROCESSING)
        update_module_status(record.job_id, "cloud", ModuleStatus.COMPLETED)
        fetched = get_job(record.job_id)
        assert fetched is not None
        assert fetched.module_statuses["cloud"] == ModuleStatus.COMPLETED

    def test_job_record_is_immutable_between_updates(self):
        """model_copy must produce a new object, not mutate in place."""
        record = create_job()
        old_id = id(ACTIVE_JOBS[record.job_id])
        update_job(record.job_id, status=JobStatus.COMPLETED)
        new_id = id(ACTIVE_JOBS[record.job_id])
        # The stored object should be a new instance
        assert old_id != new_id


# ===========================================================================
# 2. GithubAnalyzeRequest validation tests
# ===========================================================================

class TestGithubAnalyzeRequestValidation:

    # --- github_url ---------------------------------------------------------

    def test_valid_https_url_accepted(self):
        req = GithubAnalyzeRequest(github_url="https://github.com/org/repo", modules=["cloud"])
        assert req.github_url == "https://github.com/org/repo"

    def test_valid_git_ssh_url_accepted(self):
        req = GithubAnalyzeRequest(github_url="git@github.com:org/repo.git", modules=["cloud"])
        assert req.github_url.startswith("git@")

    def test_blank_url_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            GithubAnalyzeRequest(github_url="   ", modules=["cloud"])
        assert "github_url must not be empty" in str(exc_info.value)

    def test_invalid_scheme_raises(self):
        with pytest.raises(ValidationError):
            GithubAnalyzeRequest(github_url="ftp://github.com/org/repo", modules=["cloud"])

    def test_url_whitespace_is_stripped(self):
        req = GithubAnalyzeRequest(github_url="  https://github.com/org/repo  ", modules=["cloud"])
        assert req.github_url == "https://github.com/org/repo"

    # --- modules ------------------------------------------------------------

    def test_single_valid_module(self):
        req = GithubAnalyzeRequest(github_url="https://github.com/org/repo", modules=["modernize"])
        assert req.modules == ["modernize"]

    def test_multiple_valid_modules(self):
        req = GithubAnalyzeRequest(
            github_url="https://github.com/org/repo",
            modules=["onboarding", "modernize", "cloud"],
        )
        assert set(req.modules) == {"onboarding", "modernize", "cloud"}

    def test_all_sentinel_expands_to_all_modules(self):
        req = GithubAnalyzeRequest(github_url="https://github.com/org/repo", modules=["ALL"])
        assert set(req.modules) == set(VALID_MODULES)

    def test_all_sentinel_case_insensitive(self):
        req = GithubAnalyzeRequest(github_url="https://github.com/org/repo", modules=["all"])
        assert set(req.modules) == set(VALID_MODULES)

    def test_module_names_are_lowercased(self):
        req = GithubAnalyzeRequest(
            github_url="https://github.com/org/repo", modules=["Onboarding"]
        )
        assert "onboarding" in req.modules

    def test_unknown_module_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            GithubAnalyzeRequest(github_url="https://github.com/org/repo", modules=["unknown"])
        assert "Unknown module" in str(exc_info.value)

    def test_empty_modules_list_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            GithubAnalyzeRequest(github_url="https://github.com/org/repo", modules=[])
        assert "at least one entry" in str(exc_info.value)

    def test_mix_of_valid_and_invalid_modules_raises(self):
        with pytest.raises(ValidationError):
            GithubAnalyzeRequest(
                github_url="https://github.com/org/repo", modules=["cloud", "bogus"]
            )


# ===========================================================================
# 3. Health endpoint
# ===========================================================================

class TestHealthEndpoint:
    def test_health_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ===========================================================================
# 4. GET /api/status/{job_id}
# ===========================================================================

class TestGetJobStatus:
    def setup_method(self):
        _clear_jobs()

    def test_returns_existing_job(self):
        record = create_job()
        response = client.get(f"/api/status/{record.job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == record.job_id
        assert data["status"] == "PENDING"

    def test_returns_404_for_unknown_job(self):
        response = client.get("/api/status/does-not-exist")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_module_statuses_included_in_response(self):
        record = create_job()
        update_module_status(record.job_id, "cloud", ModuleStatus.COMPLETED)
        response = client.get(f"/api/status/{record.job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["module_statuses"]["cloud"] == "COMPLETED"

    def test_status_reflects_update(self):
        record = create_job()
        update_job(record.job_id, status=JobStatus.PROCESSING, active_module="modernize")
        response = client.get(f"/api/status/{record.job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PROCESSING"
        assert data["active_module"] == "modernize"


# ===========================================================================
# 5. POST /api/analyze (primary endpoint)
# ===========================================================================

class TestAnalyzeGithubEndpoint:
    def setup_method(self):
        _clear_jobs()

    @patch("backend.app.routers.orchestrator.git.Repo.clone_from")
    @patch("backend.app.routers.ingestion.parse_directory_tree", return_value={"_files": []})
    def test_returns_202_with_job_id(self, mock_tree, mock_clone):
        response = client.post(
            "/api/analyze",
            json={"github_url": "https://github.com/org/repo", "modules": ["cloud"]},
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["message"] == "Analysis started"
        assert data["modules"] == ["cloud"]

    @patch("backend.app.routers.orchestrator.git.Repo.clone_from")
    @patch("backend.app.routers.ingestion.parse_directory_tree", return_value={})
    def test_all_modules_expanded(self, mock_tree, mock_clone):
        response = client.post(
            "/api/analyze",
            json={"github_url": "https://github.com/org/repo", "modules": ["ALL"]},
        )
        assert response.status_code == 202
        data = response.json()
        assert set(data["modules"]) == set(VALID_MODULES)

    @patch("backend.app.routers.orchestrator.git.Repo.clone_from")
    @patch("backend.app.routers.ingestion.parse_directory_tree", return_value={})
    def test_job_created_in_active_jobs(self, mock_tree, mock_clone):
        response = client.post(
            "/api/analyze",
            json={"github_url": "https://github.com/org/repo", "modules": ["modernize"]},
        )
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        assert job_id in ACTIVE_JOBS

    @patch(
        "backend.app.routers.orchestrator.git.Repo.clone_from",
        side_effect=__import__("git").exc.GitCommandError("clone", 128),
    )
    def test_invalid_repo_url_returns_422(self, mock_clone):
        response = client.post(
            "/api/analyze",
            json={"github_url": "https://github.com/nonexistent/repo", "modules": ["cloud"]},
        )
        assert response.status_code == 422
        assert "clone" in response.json()["detail"].lower()

    @patch(
        "backend.app.routers.orchestrator.git.Repo.clone_from",
        side_effect=__import__("git").exc.GitCommandError("clone", 128),
    )
    def test_failed_clone_removes_job_from_store(self, mock_clone):
        initial_count = len(ACTIVE_JOBS)
        client.post(
            "/api/analyze",
            json={"github_url": "https://github.com/nonexistent/repo", "modules": ["cloud"]},
        )
        assert len(ACTIVE_JOBS) == initial_count

    def test_invalid_github_url_scheme_returns_422(self):
        response = client.post(
            "/api/analyze",
            json={"github_url": "ftp://bad.example.com/repo", "modules": ["cloud"]},
        )
        assert response.status_code == 422

    def test_unknown_module_returns_422(self):
        response = client.post(
            "/api/analyze",
            json={"github_url": "https://github.com/org/repo", "modules": ["unknown"]},
        )
        assert response.status_code == 422

    def test_empty_modules_list_returns_422(self):
        response = client.post(
            "/api/analyze",
            json={"github_url": "https://github.com/org/repo", "modules": []},
        )
        assert response.status_code == 422

    def test_missing_github_url_returns_422(self):
        response = client.post("/api/analyze", json={"modules": ["cloud"]})
        assert response.status_code == 422

    def test_missing_modules_returns_422(self):
        response = client.post(
            "/api/analyze", json={"github_url": "https://github.com/org/repo"}
        )
        assert response.status_code == 422


# ===========================================================================
# 6. POST /api/analyze/{job_id}  (legacy endpoint)
# ===========================================================================

class TestAnalyzeJobLegacyEndpoint:
    def setup_method(self):
        _clear_jobs()

    def test_returns_202_for_existing_job(self):
        record = create_job()
        response = client.post(
            f"/api/analyze/{record.job_id}",
            json={"modules": ["cloud", "modernize"]},
        )
        assert response.status_code == 202
        assert response.json()["job_id"] == record.job_id

    def test_returns_404_for_unknown_job(self):
        response = client.post(
            "/api/analyze/nonexistent-id",
            json={"modules": ["cloud"]},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_message_field_present(self):
        record = create_job()
        response = client.post(
            f"/api/analyze/{record.job_id}",
            json={"modules": ["onboarding"]},
        )
        assert response.json()["message"] == "Analysis started"


# ===========================================================================
# 7. _run_analysis (legacy background function)
# ===========================================================================

class TestRunAnalysis:
    def setup_method(self):
        _clear_jobs()

    def test_single_module_progresses_through_states(self):
        record = create_job()
        asyncio.run(_run_analysis(record.job_id, ["cloud"]))
        job = get_job(record.job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED
        assert job.module_statuses["cloud"] == ModuleStatus.COMPLETED
        assert job.active_module is None

    def test_multiple_modules_all_completed(self):
        record = create_job()
        asyncio.run(_run_analysis(record.job_id, ["onboarding", "modernize", "cloud"]))
        job = get_job(record.job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED
        for module in ["onboarding", "modernize", "cloud"]:
            assert job.module_statuses[module] == ModuleStatus.COMPLETED

    def test_all_modules_initialised_as_pending(self):
        """Ensure PENDING is set before any module starts processing."""
        states: list[dict] = []

        original_update_module = update_module_status

        def spy_update(job_id, module, status):
            states.append({"module": module, "status": status})
            return original_update_module(job_id, module, status)

        record = create_job()
        with patch(
            "backend.app.routers.orchestrator.update_module_status", side_effect=spy_update
        ):
            asyncio.run(_run_analysis(record.job_id, ["cloud", "modernize"]))

        # First two calls must be PENDING (initialisation phase)
        pending_calls = [s for s in states if s["status"] == ModuleStatus.PENDING]
        assert len(pending_calls) == 2

    def test_nonexistent_job_does_not_raise(self):
        """_run_analysis must be resilient to a stale job_id."""
        asyncio.run(_run_analysis("stale-id", ["cloud"]))


# ===========================================================================
# 8. _run_analysis_pipeline (primary background pipeline)
# ===========================================================================

class TestRunAnalysisPipeline:
    def setup_method(self):
        _clear_jobs()

    @patch("backend.app.routers.orchestrator._run_onboarding", new_callable=AsyncMock)
    @patch("backend.app.routers.orchestrator._run_modernize", new_callable=AsyncMock)
    @patch("backend.app.routers.orchestrator._run_cloud", new_callable=AsyncMock)
    def test_all_modules_run_and_complete(self, mock_cloud, mock_modernize, mock_onboarding):
        record = create_job()
        asyncio.run(
            _run_analysis_pipeline(
                record.job_id,
                ["onboarding", "modernize", "cloud"],
                "/tmp/workspace",
                {},
            )
        )
        job = get_job(record.job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED
        for module in ["onboarding", "modernize", "cloud"]:
            assert job.module_statuses[module] == ModuleStatus.COMPLETED
        mock_onboarding.assert_awaited_once()
        mock_modernize.assert_awaited_once()
        mock_cloud.assert_awaited_once()

    @patch("backend.app.routers.orchestrator._run_cloud", new_callable=AsyncMock, side_effect=RuntimeError("boom"))
    @patch("backend.app.routers.orchestrator._run_onboarding", new_callable=AsyncMock)
    def test_failing_module_marks_module_failed_and_job_failed(
        self, mock_onboarding, mock_cloud
    ):
        record = create_job()
        asyncio.run(
            _run_analysis_pipeline(
                record.job_id, ["onboarding", "cloud"], "/tmp/workspace", {}
            )
        )
        job = get_job(record.job_id)
        assert job is not None
        assert job.status == JobStatus.FAILED
        assert job.module_statuses["cloud"] == ModuleStatus.FAILED
        assert job.module_statuses["onboarding"] == ModuleStatus.COMPLETED

    @patch("backend.app.routers.orchestrator._run_cloud", new_callable=AsyncMock)
    def test_single_module_pipeline(self, mock_cloud):
        record = create_job()
        asyncio.run(
            _run_analysis_pipeline(
                record.job_id, ["cloud"], "/tmp/workspace", {}
            )
        )
        job = get_job(record.job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED
        assert job.module_statuses["cloud"] == ModuleStatus.COMPLETED

    @patch("backend.app.routers.orchestrator._run_onboarding", new_callable=AsyncMock)
    @patch("backend.app.routers.orchestrator._run_modernize", new_callable=AsyncMock)
    @patch("backend.app.routers.orchestrator._run_cloud", new_callable=AsyncMock)
    def test_modules_run_in_order(self, mock_cloud, mock_modernize, mock_onboarding):
        call_order: list[str] = []
        mock_onboarding.side_effect = lambda *_: call_order.append("onboarding") or None
        mock_modernize.side_effect = lambda *_: call_order.append("modernize") or None
        mock_cloud.side_effect = lambda *_: call_order.append("cloud") or None

        record = create_job()
        asyncio.run(
            _run_analysis_pipeline(
                record.job_id,
                ["onboarding", "modernize", "cloud"],
                "/tmp",
                {},
            )
        )
        assert call_order == ["onboarding", "modernize", "cloud"]

    @patch("backend.app.routers.orchestrator._run_onboarding", new_callable=AsyncMock)
    @patch("backend.app.routers.orchestrator._run_modernize", new_callable=AsyncMock, side_effect=Exception("fail"))
    @patch("backend.app.routers.orchestrator._run_cloud", new_callable=AsyncMock)
    def test_remaining_modules_run_after_one_fails(
        self, mock_cloud, mock_modernize, mock_onboarding
    ):
        """Pipeline must continue executing subsequent modules after a failure."""
        record = create_job()
        asyncio.run(
            _run_analysis_pipeline(
                record.job_id,
                ["onboarding", "modernize", "cloud"],
                "/tmp",
                {},
            )
        )
        mock_cloud.assert_awaited_once()  # cloud still ran despite modernize failing

    @patch("backend.app.routers.orchestrator._run_onboarding", new_callable=AsyncMock)
    @patch("backend.app.routers.orchestrator._run_modernize", new_callable=AsyncMock)
    @patch("backend.app.routers.orchestrator._run_cloud", new_callable=AsyncMock)
    def test_active_module_cleared_when_done(self, mock_cloud, mock_modernize, mock_onboarding):
        record = create_job()
        asyncio.run(
            _run_analysis_pipeline(
                record.job_id,
                ["onboarding"],
                "/tmp",
                {},
            )
        )
        job = get_job(record.job_id)
        assert job is not None
        assert job.active_module is None


# ===========================================================================
# 9. Ingestion helpers
# ===========================================================================

class TestParseDirectoryTree:
    def test_flat_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "a.py"), "w").close()
            open(os.path.join(tmp, "b.txt"), "w").close()
            tree = parse_directory_tree(tmp)
        assert set(tree.get("_files", [])) == {"a.py", "b.txt"}

    def test_nested_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            sub = os.path.join(tmp, "src")
            os.makedirs(sub)
            open(os.path.join(sub, "main.py"), "w").close()
            tree = parse_directory_tree(tmp)
        assert "src" in tree
        assert "main.py" in tree["src"].get("_files", [])

    def test_ignored_dirs_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            for ignored in ["node_modules", "__pycache__", ".git"]:
                os.makedirs(os.path.join(tmp, ignored))
                open(os.path.join(tmp, ignored, "file.js"), "w").close()
            tree = parse_directory_tree(tmp)
        for ignored in ["node_modules", "__pycache__", ".git"]:
            assert ignored not in tree

    def test_empty_directory_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = parse_directory_tree(tmp)
        assert tree == {}


# ===========================================================================
# 10. POST /api/refactor
# ===========================================================================

class TestRefactorEndpoint:
    def test_refactor_with_code_form_field(self):
        code = "def hello():\n    print('hi')\n\ndef world():\n    print('world')\n"
        response = client.post("/api/refactor", data={"code": code})
        assert response.status_code == 200
        data = response.json()
        assert "modules" in data
        assert isinstance(data["modules"], list)
        assert data["original_lines"] > 0

    def test_refactor_missing_input_returns_422(self):
        response = client.post("/api/refactor", data={})
        assert response.status_code == 422

    def test_refactor_single_block_returns_one_module(self):
        code = "x = 1"
        response = client.post("/api/refactor", data={"code": code})
        assert response.status_code == 200
        data = response.json()
        assert len(data["modules"]) == 1

    def test_refactor_capped_at_five_modules(self):
        # Six blank-line-separated blocks
        code = "\n\n".join([f"block_{i} = {i}" for i in range(10)])
        response = client.post("/api/refactor", data={"code": code})
        assert response.status_code == 200
        data = response.json()
        assert len(data["modules"]) <= 5

    def test_refactor_response_schema(self):
        code = "import os"
        response = client.post("/api/refactor", data={"code": code})
        assert response.status_code == 200
        data = response.json()
        assert "original_lines" in data
        assert "modules" in data
        assert "summary" in data
        for module in data["modules"]:
            assert "name" in module
            assert "description" in module
            assert "suggested_language" in module
            assert "code_snippet" in module


# ===========================================================================
# 11. POST /api/optimize
# ===========================================================================

class TestOptimizeEndpoint:
    def test_terraform_manifest_detected(self):
        manifest = 'resource "aws_instance" "web" {\n  publicly_accessible = true\n}'
        response = client.post("/api/optimize", data={"manifest": manifest})
        assert response.status_code == 200
        data = response.json()
        assert data["manifest_type"] == "terraform"
        assert data["total_findings"] >= 1

    def test_kubernetes_manifest_detected(self):
        manifest = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: web\n"
        response = client.post("/api/optimize", data={"manifest": manifest})
        assert response.status_code == 200
        data = response.json()
        assert data["manifest_type"] == "kubernetes"

    def test_critical_finding_reduces_score(self):
        manifest = 'resource "aws_db" "db" {\n  publicly_accessible = true\n}'
        response = client.post("/api/optimize", data={"manifest": manifest})
        assert response.status_code == 200
        data = response.json()
        assert data["overall_score"] < 100

    def test_missing_manifest_returns_422(self):
        response = client.post("/api/optimize", data={})
        assert response.status_code == 422

    def test_optimize_response_schema(self):
        manifest = 'resource "aws_instance" "web" {}'
        response = client.post("/api/optimize", data={"manifest": manifest})
        assert response.status_code == 200
        data = response.json()
        for key in [
            "manifest_type",
            "total_findings",
            "critical_count",
            "warning_count",
            "info_count",
            "findings",
            "overall_score",
        ]:
            assert key in data

    def test_score_capped_at_100_for_clean_manifest(self):
        manifest = "# clean terraform config\nresource \"null_resource\" \"noop\" {}"
        response = client.post("/api/optimize", data={"manifest": manifest})
        assert response.status_code == 200
        assert response.json()["overall_score"] == 100

    def test_score_minimum_zero(self):
        """Many critical findings must not produce a negative score."""
        manifest = "\n".join(
            ['resource "r" "x" {', "  publicly_accessible = true"]
            + ['  cidr_blocks = ["0.0.0.0/0"]'] * 10
            + ["}"]
        )
        response = client.post("/api/optimize", data={"manifest": manifest})
        assert response.status_code == 200
        assert response.json()["overall_score"] >= 0


# ===========================================================================
# 12. Cross-cutting / integration smoke tests
# ===========================================================================

class TestIntegrationSmoke:
    def setup_method(self):
        _clear_jobs()

    def test_status_endpoint_reflects_manual_job_update(self):
        record = create_job()
        update_job(record.job_id, status=JobStatus.COMPLETED)
        update_module_status(record.job_id, "modernize", ModuleStatus.COMPLETED)
        response = client.get(f"/api/status/{record.job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert data["module_statuses"]["modernize"] == "COMPLETED"

    @patch("backend.app.routers.orchestrator.git.Repo.clone_from")
    @patch("backend.app.routers.ingestion.parse_directory_tree", return_value={})
    def test_analyze_then_status_round_trip(self, mock_tree, mock_clone):
        response = client.post(
            "/api/analyze",
            json={"github_url": "https://github.com/org/repo", "modules": ["cloud"]},
        )
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        status_response = client.get(f"/api/status/{job_id}")
        assert status_response.status_code == 200
        assert status_response.json()["job_id"] == job_id

    def test_legacy_analyze_then_status_round_trip(self):
        record = create_job()
        analyze_response = client.post(
            f"/api/analyze/{record.job_id}",
            json={"modules": ["cloud"]},
        )
        assert analyze_response.status_code == 202

        status_response = client.get(f"/api/status/{record.job_id}")
        assert status_response.status_code == 200
