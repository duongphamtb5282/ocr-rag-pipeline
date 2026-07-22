"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth import auth_middleware
from app.config import settings
from app.db.database import create_db_and_tables

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    logger.info("Starting OCR Form Fill System...")
    await create_db_and_tables()
    from app.api.v1 import sessions, review, search, health, admin_gateway
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
    app.include_router(review.router, prefix="/api/v1", tags=["review"])
    app.include_router(search.router, prefix="/api/v1", tags=["search"])
    app.include_router(admin_gateway.router, prefix="/api/v1/admin/gateway", tags=["admin"])
    yield
    logger.info("Shutting down OCR Form Fill System...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="OCR Form Fill System",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add auth middleware for API routes
    @app.middleware("http")
    async def auth_middleware_handler(request: Request, call_next):
        # Skip auth for web UI, static files, health, and open endpoints
        path = request.url.path
        if any(path.startswith(p) for p in ["/static", "/health", "/api/v1/health"]):
            return await call_next(request)
        try:
            auth = await auth_middleware.authenticate(request)
            request.state.auth = auth
        except Exception as e:
            if settings.ENVIRONMENT in ("development", "test"):
                from app.auth import ANONYMOUS_CONTEXT
                request.state.auth = ANONYMOUS_CONTEXT
            else:
                return JSONResponse(status_code=401, content={"detail": str(e)})
        return await call_next(request)

    # Mount static files
    static_dir = settings.upload_path.parent / "app" / "web" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Mount web UI routes
    from app.web.routes import router as web_router
    app.include_router(web_router)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
