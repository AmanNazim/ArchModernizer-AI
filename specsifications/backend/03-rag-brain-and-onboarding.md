==================================================
SPECIFICATION 03: RAG BRAIN & ONBOARDING ASSISTANT
==================================================

1. MODULE OBJECTIVE:
   Build the `/app/services/rag_engine.py` and `/app/routers/onboarding.py` modules to create "RepoVibe"—a repository-aware Retrieval-Augmented Generation (RAG) engine. This system indexes the ingested codebase, stores vector embeddings in Qdrant, and provides context-grounded Q&A for developer onboarding.

2. VECTOR STORE & RAG LOGIC (app/services/rag_engine.py):

- Qdrant Initialization: Instantiate `qdrant-client` in local in-memory or file-backed storage mode (`:memory:` or local folder) to eliminate external infrastructure requirements and minimize memory footprint.
- Code Chunking Pipeline:
  - Implement `chunk_repository(file_tree: dict)` to iterate through supported source files (`.py`, `.js`, `.ts`, `.tsx`, `.tf`, `.yaml`, `.md`).
  - Chunking Strategy: Use recursive character or syntax-aware splitting (500–800 tokens per chunk with a 100-token overlap) to preserve code block continuity.
  - Metadata Schema: Store `file_path`, `start_line`, `end_line`, `file_extension`, and `job_id` alongside each vector payload.
- Embedding Generation: Use a lightweight embedding pipeline (e.g., `fastembed` or Ollama embeddings) executed in small batches (batch size $\le 16$) to prevent local system thrashing.

3. ENDPOINTS TO IMPLEMENT (app/routers/onboarding.py):

- `POST /api/onboarding/index/{job_id}`:
  - Triggers background parsing and vector indexing of the workspace associated with `job_id`.
  - Upserts vectors into a Qdrant collection scoped by `job_id`.
  - Updates job state in `job_tracker.py` upon completion (`status: COMPLETED`, `module: onboarding`).

- `POST /api/onboarding/chat`:
  - Payload: `{ "job_id": "string", "query": "string" }`
  - Similarity Search: Queries the job's Qdrant collection for the top $k=4$ most relevant code chunks.
  - Contextual Prompting: Assembles the retrieved code chunks, file paths, and line ranges into a structured context window for the LLM.
  - Response Format: Returns structured JSON containing `{ "answer": "string", "sources": [ { "file_path": "string", "lines": "string" } ] }`.

4. PERFORMANCE & RESOURCE GUARDRAILS:

- File Filtering: Skip binary files, lockfiles (`package-lock.json`, `poetry.lock`), and auto-generated assets during indexing.
- Index Cleanup: Include a `cleanup_job_index(job_id: str)` utility to purge Qdrant collections when a session expires or temporary workspace is deleted.
