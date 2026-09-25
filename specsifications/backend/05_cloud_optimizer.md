==================================================
SPECIFICATION 05: CLOUD OPTIMIZER (INFRASTRUCTURE & SECURITY)
==================================================

1. MODULE OBJECTIVE:
   Build the `/app/services/cloud_engine.py` and `/app/routers/cloud_optimizer.py` modules. This engine scans Infrastructure-as-Code (IaC) manifests to flag security vulnerabilities, identify cost waste (over-provisioning), and generate optimized replacement scripts.

2. CORE LOGIC (app/services/cloud_engine.py):

- File Filtering: Isolate infrastructure and deployment files (`.tf`, `.yaml`, `.yml`, `Dockerfile`, `docker-compose.yml`) from the ingested file tree.
- Cost & Security Analysis Pipeline:
  - Send the IaC file contents to the LLM.
  - Prompt the LLM specifically to flag: hardcoded secrets, overly permissive IAM roles, deprecated Terraform modules, and expensive/over-provisioned instance types (e.g., suggesting t3.micro or autoscaling groups instead of static large instances).
- Structured Output: Force the LLM to return a strict JSON array of `optimizations`.
  - Required fields per finding: `file_path`, `issue_type` (Cost or Security), `severity` (Low, Medium, High), `description`, and `optimized_code_snippet`.

3. ENDPOINTS TO IMPLEMENT (app/routers/cloud_optimizer.py):

- `POST /api/cloud/run/{job_id}`:
  - Invoked by the Orchestrator (from Spec 02).
  - Runs the `cloud_engine.py` scanner in the background.
  - Updates `ACTIVE_JOBS` tracking (`status: PROCESSING`, `module: cloud_optimizer`).
  - Appends the final JSON optimization report to the job's artifacts upon completion.

4. ERROR HANDLING:

- If no IaC files are found in the repository, gracefully bypass the LLM calls, append a `{ "message": "No infrastructure files detected" }` artifact to the job, and mark the module as `COMPLETED`.
