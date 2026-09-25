# ArchModernizer AI

A full-stack developer assistant platform that automates **legacy code modernization**, **cloud/IaC infrastructure optimization**, and provides an **interactive onboarding chat** powered by multi-agent workflows.

```
┌─────────────────────────────────────────────────────┐
│              ArchModernizer AI                       │
│                                                      │
│  ┌──────────────┐        ┌───────────────────────┐  │
│  │  Next.js     │ ──────▶│  FastAPI Backend       │  │
│  │  Frontend    │  HTTP  │  /api/refactor         │  │
│  │  :3000       │◀────── │  /api/optimize         │  │
│  └──────────────┘        └───────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer    | Technology                                                    |
| -------- | ------------------------------------------------------------- |
| Backend  | Python 3.11+, FastAPI, Uvicorn, Pydantic v2                   |
| Frontend | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS 3 |

---

## Project Structure

```
archmodernizer-ai/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, router mounts
│   │   └── routers/
│   │       ├── modernizer.py     # POST /api/refactor
│   │       └── cloud.py          # POST /api/optimize
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx        # Root layout (dark theme)
│   │   │   ├── page.tsx          # Tabbed dashboard shell
│   │   │   └── globals.css
│   │   └── components/
│   │       ├── CodeModernizer.tsx  # Tab 1 – code refactor
│   │       ├── CloudOptimizer.tsx  # Tab 2 – IaC analysis
│   │       └── OnboardingChat.tsx  # Tab 3 – chat interface
│   ├── package.json
│   └── .env.local
└── README.md
```

---

## Prerequisites

- **Python** 3.11 or newer
- **Node.js** 18 or newer (LTS recommended)
- **npm** 9+ (bundled with Node)

---

## Quick Start

### 1 — Clone & enter the repo

```bash
git clone <your-repo-url> archmodernizer-ai
cd archmodernizer-ai
```

### 2 — Start the FastAPI backend

```bash
# Create and activate a virtual environment
cd backend
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start the dev server (reload on file changes)
uvicorn app.main:app --reload
```

The API is now live at **http://localhost:8000**  
Interactive Swagger docs: **http://localhost:8000/docs**

### 3 — Start the Next.js frontend (new terminal)

```bash
cd frontend
npm install
npm run dev
```

The app is now live at **http://localhost:3000**

---

## Running Both Concurrently (optional)

Install [`concurrently`](https://www.npmjs.com/package/concurrently) once:

```bash
npm install -g concurrently
```

Then from the repo root:

```bash
concurrently \
  "cd backend && uvicorn app.main:app --reload" \
  "cd frontend && npm run dev"
```

---

## API Reference

### `POST /api/refactor` — Code Modernizer

Decompose a legacy monolith into microservice blueprints.

| Field  | Type        | Description                       |
| ------ | ----------- | --------------------------------- |
| `code` | form string | Raw source code to refactor       |
| `file` | file upload | Alternative: upload a source file |

**Response** (`RefactorResponse`):

```json
{
  "original_lines": 42,
  "summary": "Decomposed 42 lines into 3 microservice(s).",
  "modules": [
    {
      "name": "auth-service",
      "description": "Extracted microservice handling responsibilities from block 1.",
      "suggested_language": "Python (FastAPI)",
      "code_snippet": "..."
    }
  ]
}
```

---

### `POST /api/optimize` — Cloud Optimizer

Analyse a Terraform or Kubernetes manifest for security, cost, and reliability issues.

| Field      | Type        | Description                              |
| ---------- | ----------- | ---------------------------------------- |
| `manifest` | form string | Raw `.tf` or YAML manifest text          |
| `file`     | file upload | Alternative: upload a `.tf`/`.yaml` file |

**Response** (`OptimizeResponse`):

```json
{
  "manifest_type": "terraform",
  "total_findings": 3,
  "critical_count": 2,
  "warning_count": 1,
  "info_count": 0,
  "overall_score": 50,
  "findings": [
    {
      "severity": "critical",
      "category": "security",
      "description": "RDS or resource is publicly accessible.",
      "recommendation": "Set `publicly_accessible = false`...",
      "line_hint": 8
    }
  ]
}
```

**Scoring**: starts at 100, deducts 20 per critical, 10 per warning, 5 per info finding.

---

## Environment Variables

### Backend (`backend/.env`)

Copy `backend/.env.example` to `backend/.env`:

```env
CORS_ORIGINS=http://localhost:3000
```

### Frontend (`frontend/.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Change this URL to point to a deployed backend in production.

---

## Dashboard Features

| Tab                 | Feature                                                                                               |
| ------------------- | ----------------------------------------------------------------------------------------------------- |
| **Code Modernizer** | Paste or upload legacy code → side-by-side microservice blueprint view with module tabs               |
| **Cloud Optimizer** | Paste or upload Terraform/K8s YAML → health-score cards + detailed findings with line hints           |
| **Onboarding Chat** | Keyword-aware chat assistant covering microservices, Terraform, Kubernetes, security, and cost topics |

---

## Extending the Project

- **Real LLM integration**: Replace `_mock_refactor()` in [`backend/app/routers/modernizer.py`](backend/app/routers/modernizer.py) and `_analyze_manifest()` in [`backend/app/routers/cloud.py`](backend/app/routers/cloud.py) with calls to watsonx, OpenAI, or another model provider.
- **Chat backend**: Add a `POST /api/chat` endpoint and update [`OnboardingChat.tsx`](frontend/src/components/OnboardingChat.tsx) to call it instead of the client-side mock.
- **Authentication**: Add FastAPI dependency injection for JWT/API-key auth on the backend routes.

---

## License

MIT — see `LICENSE` for details.
