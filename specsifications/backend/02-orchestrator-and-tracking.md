==================================================
SPECIFICATION 02: ORCHESTRATOR & JOB TRACKING
==================================================

1. MODULE OBJECTIVE:
   Build the `/app/services/job_tracker.py` and `/app/routers/orchestrator.py` modules. Because repository modernization and infrastructure scanning are heavy tasks, the frontend cannot wait for synchronous HTTP responses. We must decouple I/O-bound jobs from the main response.

2. JOB TRACKING LOGIC (job_tracker.py):

- Implement a global in-memory dictionary `ACTIVE_JOBS = {}` to store job states.
- Data Structure: Each job should track its UUID, current status (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`), current active module (e.g., `modernizer`, `cloud_optimizer`), and a list of generated artifacts.
- Note: Keep this in-memory for the hackathon MVP to avoid database overhead.

3. ENDPOINTS TO IMPLEMENT (orchestrator.py):

- `GET /api/status/{job_id}`: Returns the current state of the job from `ACTIVE_JOBS`.
- `POST /api/analyze/{job_id}`: Accepts a JSON payload specifying which AI engines to run on the ingested repository (`modules: ["onboarding", "modernize", "cloud"]`).

4. ASYNC EXECUTION (BackgroundTasks):

- The `/api/analyze/{job_id}` endpoint must use FastAPI's `BackgroundTasks` feature to kick off the selected AI engines in a fire-and-forget manner.
- It must instantly return a `202 Accepted` response while the heavy LLM tasks process in the background and update the `ACTIVE_JOBS` state.
