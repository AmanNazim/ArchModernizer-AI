"""
ArchModernizer AI – FastAPI entry point.

Configures CORS, mounts the modernizer and cloud routers, and provides
a basic health-check endpoint.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import modernizer, cloud, cloud_optimizer, ingestion, orchestrator, onboarding

app = FastAPI(
    title="ArchModernizer AI",
    description="Multi-agent platform for legacy code modernization and cloud/IaC optimization.",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS – allow the Next.js dev server (port 3000) and production origin.
# Adjust origins in production via environment variable if needed.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(modernizer.router, prefix="/api", tags=["Code Modernizer"])
app.include_router(cloud.router, prefix="/api", tags=["Cloud Optimizer"])
app.include_router(cloud_optimizer.router, prefix="/api", tags=["Cloud Optimizer Jobs"])
app.include_router(ingestion.router, prefix="/api", tags=["Ingestion"])
# orchestrator declares full /api/... paths internally; no extra prefix needed
app.include_router(orchestrator.router)
# onboarding declares full /api/onboarding/... paths internally
app.include_router(onboarding.router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Simple liveness probe."""
    return {"status": "ok"}
