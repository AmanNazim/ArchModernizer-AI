# Project Specification: ArchModernizer AI

## 1. Project Objective
Build a full-stack developer assistant platform powered by multi-agent workflows. The app consists of a FastAPI backend and a Next.js frontend to automate legacy code modernization, cloud/IaC infrastructure optimization, and interactive documentation generation.

## 2. Backend Requirements (FastAPI in `/app`)
- `/app/main.py`: Initialize the main FastAPI application, configure CORS middleware, and include routers from `/routers`.
- `/app/routers/modernizer.py`: Create a POST endpoint (`/api/refactor`) that accepts uploaded legacy files/code strings, simulates breaking monolithic scripts into microservice blueprints, and returns structured JSON with refactored code modules.
- `/app/routers/cloud.py`: Create a POST endpoint (`/api/optimize`) that parses text inputs or files containing Terraform (`.tf`) or Kubernetes YAML manifests, flags security compliance risks, and outputs structured optimization suggestions.

## 3. Frontend Requirements (Next.js / Tailwind CSS)
Create a responsive multi-tab dashboard interface:
* **Tab 1: "Code Modernizer"** (File upload zone + side-by-side code diff view).
* **Tab 2: "Cloud Optimizer"** (Manifest input area + security/cost metrics cards).
* **Tab 3: "Onboarding Chat"** (Chat bubble layout for querying generated architecture insights).

## 4. Execution Instructions for Bob
- Use parallel subagents to generate the FastAPI routing logic and the Next.js UI components simultaneously.
- Write clean, production-ready code with inline comments explaining the architecture choices.