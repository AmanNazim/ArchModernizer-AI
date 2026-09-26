==================================================
SPECIFICATION 06: UI SHELL & INGESTION (FRONTEND)
==================================================

1. MODULE OBJECTIVE:
   Build the global application wrapper and the main entry point for the ArchModernizer AI Next.js frontend. This includes the global layout, Zustand state management for asynchronous job tracking, a drag-and-drop ingestion interface, and a custom polling hook to sync the UI with the FastAPI backend.

2. GLOBAL STATE & LAYOUT (App Router):

- **Layout Shell:** Implement a responsive Sidebar and Top Navigation bar using Tailwind CSS. The sidebar should contain navigation links to the three main views (Setup, Modernizer, Cloud Optimizer).
- **Zustand Store:** Create a per-request Zustand store (using React Context and `useRef` to be App Router compliant) to globally manage:
  - `job_id`: string (UUID) or null.
  - `job_status`: string (`IDLE`, `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`).
  - `active_modules`: array of strings.

3. INGESTION UI (PROJECT SETUP VIEW):

- Build the main "Project Setup" view component containing two primary input methods:
  - **File Upload:** A drag-and-drop zone for `.zip` files. On drop/submit, send a `multipart/form-data` POST request to `http://127.0.0.1:8000/api/ingest/zip`.
  - **GitHub Import:** A text input field for GitHub URLs with a submit button. On submit, send a JSON POST request (`{ "repo_url": "..." }`) to `http://127.0.0.1:8000/api/ingest/github`.
- Upon a successful ingestion response, update the global Zustand store with the returned `job_id` and set `job_status` to `PENDING`.
- Show a loading spinner overlay while the repository is initially uploading or cloning.

4. ASYNC POLLING HOOK (`useJobPolling`):

- Create a custom React hook `useJobPolling(job_id: string | null)` inside a `/hooks` directory.
- **Logic:**
  - If a `job_id` exists and the `job_status` is not `COMPLETED` or `FAILED`, initialize a `setInterval` that fires every 3000ms (3 seconds).
  - Inside the interval, fetch `http://127.0.0.1:8000/api/status/{job_id}`.
  - Update the Zustand `job_status` state based on the backend response.
  - Clear the interval using `clearInterval` upon unmount or when the status reaches a terminal state (`COMPLETED` or `FAILED`).

5. EXECUTION CONSTRAINTS:

- Use React Functional Components with the `"use client"` directive where state or hooks (Zustand, `useEffect`, `useState`) are required.
- Do not use external component libraries (like Material UI or Chakra); rely strictly on custom Tailwind CSS utility classes.
