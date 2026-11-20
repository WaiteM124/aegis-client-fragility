"""
Worker entry-point.

Starts ONLY the event processing worker (no API server).
Designed for the worker Cloud Run container or standalone deployment.

Flow:
  1. Load settings from environment / .env.
  2. Configure structured logging.
  3. Build the dependency container (stores, bus, services, worker).
  4. Start the worker's async consumer loop.
  5. Block until SIGTERM (or SIGINT) then shut down gracefully.
"""

from __future__ import annotations

import asyncio
import signal

from .shared.config import get_settings
from .shared.logging import configure_logging, get_logger

logger = get_logger("worker_main")

_STOP_EVENT: asyncio.Event | None = None


def _handle_stop_signal(*_args) -> None:  # noqa: ANN001
    """Signal handler: set the stop event to initiate graceful shutdown."""
    logger.info("Stop signal received — initiating graceful shutdown")
    if _STOP_EVENT is not None:
        _STOP_EVENT.set()


async def main() -> None:
    global _STOP_EVENT
    _STOP_EVENT = asyncio.Event()

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    logger.info(
        "Aegis worker starting",
        extra={"env": settings.app_env, "model_provider": settings.model_provider},
    )

    # Register graceful-shutdown signal handlers.
    # asyncio.get_event_loop().add_signal_handler is not available on Windows;
    # fall back to signal.signal for portability.
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_stop_signal)
        except (NotImplementedError, AttributeError):
            # Windows: add_signal_handler is not supported on the ProactorEventLoop
            signal.signal(sig, _handle_stop_signal)

    # Build the full dependency container (stores, bus, all services)
    from .api.dependencies import Container  # noqa: PLC0415 — deferred to allow settings

    container = await Container.create(settings)
    await container.worker.start()

    logger.info(
        "Aegis worker ready — consuming events from message bus",
        extra={"subscription": settings.events_subscription},
    )

    try:
        await _STOP_EVENT.wait()
    finally:
        logger.info("Aegis worker stopping")
        await container.worker.stop()
        await container.message_bus.stop()
        await container.event_store.close()
        await container.assessment_store.close()
        logger.info("Aegis worker stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())
