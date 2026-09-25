==================================================
SPECIFICATION 04: MODERNIZER AI (LEGACY TO MICROSERVICES)
==================================================

1. MODULE OBJECTIVE:
   Build the `/app/services/modernizer_engine.py` and `/app/routers/modernizer.py` modules. This engine iterates through the business logic of a legacy repository, uses an LLM to identify bounded contexts, and generates microservice blueprints complete with OpenAPI specifications.

2. CORE LOGIC (app/services/modernizer_engine.py):

- File Filtering: Extract only application logic files (`.py`, `.java`, `.js`, `.ts`, `.cs`, `.go`) from the ingested file tree.
- LLM Processing Pipeline:
  - Chunk the application logic and feed it to the local LLM via Ollama.
  - Prompt the LLM to identify domain boundaries (Domain-Driven Design) and apply the Strangler Fig pattern to decouple monolithic classes/functions.
- Structured Output: Force the LLM to output a strict JSON schema representing the new microservices architecture.
  - Required fields per microservice: `service_name`, `description`, `original_files_referenced`, `suggested_endpoints`, and `openapi_spec_yaml` (a draft OpenAPI 3.0 string).

3. ENDPOINTS TO IMPLEMENT (app/routers/modernizer.py):

- `POST /api/modernize/run/{job_id}`:
  - This is invoked by the Orchestrator (from Spec 02).
  - It runs the `modernizer_engine.py` processing pipeline in the background.
  - Updates the `ACTIVE_JOBS` dictionary to `status: PROCESSING` and `module: modernizer`.
  - Upon completion, appends the generated JSON blueprint to the job's artifact list and sets `status: COMPLETED`.

4. PERFORMANCE GUARDRAILS:

- To respect the 8GB RAM local constraint, the LLM calls must be processed sequentially per chunk, not concurrently. Do not load the entire repository codebase into the LLM context at once.
