"""
FastAPI application factory.

Startup sequence:
  1. Configure logging.
  2. Build the dependency container (stores, bus, services, worker).
  3. Start the async event processing worker.
  4. Attach routers.

Shutdown sequence:
  1. Stop the worker (cancel consumer task, drain).
  2. Stop the message bus.
  3. Close database connections.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..shared.config import get_settings
from ..shared.logging import configure_logging, get_logger
from .dependencies import Container
from .routers import dashboard, events, health

logger = get_logger("api")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "Aegis starting",
            extra={"env": settings.app_env, "model_provider": settings.model_provider},
        )
        container = await Container.create(settings)
        app.state.container = container
        await container.worker.start()
        logger.info("Aegis ready — event processing worker active")

        yield

        logger.info("Aegis shutting down")
        await container.worker.stop()
        await container.message_bus.stop()
        await container.event_store.close()
        await container.assessment_store.close()
        logger.info("Aegis stopped cleanly")

    app = FastAPI(
        title="Aegis Global Intelligence",
        description=(
            "Global Event Intelligence and Client Impact Assessment Platform. "
            "Events are submitted via the ingestion API and processed asynchronously "
            "by an independent worker."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = settings.api_prefix
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(events.router, prefix=f"{prefix}/events", tags=["events"])
    app.include_router(dashboard.router, prefix=f"{prefix}/dashboard", tags=["dashboard"])

    return app
