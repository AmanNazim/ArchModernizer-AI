---
name: fastapi-backend-standard
description: Enforces async-first FastAPI backend conventions and memory-safe AI integration for resource-constrained (8GB RAM) environments. Use this whenever writing or reviewing FastAPI route handlers, building an AI/agent backend, wiring up Qdrant vector search, or integrating local (Ollama) or hosted LLM calls into a Python API — even if the user just says "add an endpoint" or "hook this up to the model" without mentioning FastAPI, async, or memory by name. Also use when reviewing existing FastAPI code for blocking calls, missing Pydantic validation, or memory-heavy patterns.
---

# FastAPI Backend Standard

FastAPI's whole performance story depends on the event loop never getting stuck. One synchronous, blocking call in a route handler — a `requests.get()`, a `time.sleep()`, a sync DB driver, an in-process model load — freezes every other request being served by that worker, not just the one that made the call. On an 8GB RAM machine with no room for extra worker processes to paper over that, a single blocking call is the difference between an API that serves 50 concurrent users and one that serves 1. This skill exists so that constraint gets designed in from the first line of code, not discovered in production.

## Core rules

### 1. Every route handler is `async def`, and every I/O call inside it is awaited

Not "async when convenient" — the handler is `async def` and nothing inside it blocks the event loop. That means:

- HTTP calls to other services (Ollama, hosted LLM APIs, external tools): `httpx.AsyncClient`, never `requests`.
- Database access: an async driver (`asyncpg`, SQLAlchemy's async engine, Motor for Mongo), never a sync driver called from inside `async def`.
- Vector store calls (Qdrant): the `AsyncQdrantClient`, never the sync `QdrantClient`, inside a route.
- File I/O: `aiofiles` for anything beyond trivial reads, especially if the file could be large.
- Sleeps/waits: `asyncio.sleep`, never `time.sleep`.

If a piece of work is genuinely CPU-bound and has no async equivalent (heavy local computation, a legacy sync library with no async fork), don't call it directly from the route — offload it with `run_in_executor` or a background task queue, and say so explicitly in a code comment, since this is the one place a "blocking" operation is intentional and reviewers should not "fix" it back into the main thread.

### 2. Every request and response is a Pydantic model

No raw `dict` bodies, no untyped `**kwargs` request handling, no manually parsing `await request.json()` when a model would do it. This isn't just style — it's what makes FastAPI validate, document, and reject malformed input for free instead of that logic being reinvented per-endpoint. Define:

- A `BaseModel` for the request body, with `Field(...)` constraints (`min_length`, `ge`/`le`, `max_items`) wherever a bad value could cause silent failures downstream (e.g., an empty prompt string, a negative `top_k`).
- A `BaseModel` for the response, even for simple endpoints — it keeps the API contract explicit and lets FastAPI generate accurate OpenAPI docs.
- `response_model=` on the route decorator, so a handler can't accidentally leak fields it wasn't supposed to.

### 3. AI integration defaults to local-first, memory-bounded execution

This project runs on an 8GB RAM machine with free-tier API access. That changes the default architecture:

- **Default to Ollama for local inference**, called over HTTP via `httpx.AsyncClient` to Ollama's own server process — never load a model in-process in the FastAPI app (no `transformers` pipeline held in app memory, no local weights loaded at import time). Ollama manages its own model memory outside the API process, which is the only way to keep the FastAPI process's own footprint predictable.
- **Default to Qdrant for vector storage**, accessed only through its client (local Qdrant instance or Qdrant Cloud free tier) — never hold embeddings in an in-memory list/array as a substitute for a vector store once the collection could grow past a trivial size.
- **Cap what's held in memory at once.** Stream large LLM responses token-by-token (`StreamingResponse`) rather than buffering the full output; batch embedding generation in small chunks rather than embedding an entire document set in one call; paginate any Qdrant query that could return more than a few dozen results rather than pulling a whole collection into memory.
- **Pick the smallest model that satisfies the task**, not the most capable one available. See the routing table below before defaulting to a large local model or a hosted API call.

### 4. Route AI tasks by a fixed decision table, not by habit

When a route needs to call a model, decide where that call goes using this table before writing the call:

| Task profile                                                                                                                             | Route to                                                                                                             |
| ---------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Short prompt, no tool use, latency-tolerant, fits a small quantized model (≤3–4B params)                                                 | Local Ollama model                                                                                                   |
| Needs function/tool calling, long context (>8K tokens), or higher reasoning quality                                                      | Hosted API (OpenAI Agents SDK / equivalent)                                                                          |
| Embedding generation for RAG/Qdrant                                                                                                      | Local Ollama embedding model by default; hosted embedding API only if local quality is insufficient for the use case |
| Anything whose estimated working-set size (model + context + batch) would push resident memory within roughly 1–1.5GB of the 8GB ceiling | Reject the local path — call the hosted API, or reduce batch size/stream instead of loading more at once             |

Log or comment which branch of the table a given integration takes — this makes the memory-vs-capability tradeoff auditable instead of implicit.

## Reference

`references/patterns.md` has full before/after code examples for: a correct async endpoint with Pydantic validation, an async Ollama call via `httpx`, async Qdrant upsert/query, streaming a large LLM response, and offloading a genuinely CPU-bound task without blocking the loop. Read it before writing new integration code, and use it to check existing code for the blocking patterns it calls out.

## When reviewing existing code

Flag, in order of severity:

1. Any blocking call (sync HTTP client, sync DB driver, `time.sleep`, sync Qdrant client) inside an `async def` route — this is the one that silently degrades every other in-flight request.
2. Request/response bodies handled as raw dicts instead of Pydantic models.
3. A model loaded in-process instead of routed to Ollama, or an unbounded response/query that isn't streamed or paginated.
4. A local-model call that the routing table above says should have gone to a hosted API (or vice versa) given its actual requirements.
