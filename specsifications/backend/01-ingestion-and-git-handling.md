==================================================
SPECIFICATION 01: CORE INGESTION & GIT HANDLING
==================================================

1. MODULE OBJECTIVE:
   Build the `/app/routers/ingestion.py` module to handle receiving, securely storing, and parsing target repositories. It must support both ZIP file uploads and GitHub URL cloning.

2. ENDPOINTS TO IMPLEMENT:

- `POST /api/ingest/github`: Accepts a JSON payload with a `repo_url`.
- `POST /api/ingest/zip`: Accepts a multipart/form-data `.zip` file upload.

3. CORE LOGIC & CONSTRAINTS:

- Temporary Storage: Use Python's built-in `tempfile.TemporaryDirectory` to securely isolate downloaded or extracted files. The directory must be cleaned up automatically after processing is complete or if an error occurs.
- Git Operations: Use GitPython's `Repo.clone_from` method to fetch remote cloud repositories directly into the temporary directory.
- File Parsing: Create a utility function `parse_directory_tree(path: str) -> dict` that recursively maps the directory structure.
- Ignored Directories: The parser MUST explicitly ignore junk folders to save memory: `.git`, `node_modules`, `venv`, `.venv`, `__pycache__`, and `dist`.
- Output: Both endpoints should return a standard JSON response containing a unique `job_id` (UUID) and the `file_tree` mapping.
