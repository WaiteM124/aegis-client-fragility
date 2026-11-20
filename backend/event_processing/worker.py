"""
Asynchronous event processing worker.

Architecture note — genuine async processing
─────────────────────────────────────────────
The worker is an independent asyncio consumer.  It shares *nothing* with the
API request path except the message bus queue and the persistence stores.

Flow:
  1. worker.start() wraps bus.subscribe() in an asyncio.Task.
  2. The task runs a blocking loop: pull envelope → dispatch handler.
  3. The API path publishes to the bus queue and returns 202 immediately.
  4. The handler runs concurrently with the API, bounded by a semaphore.
  5. worker.stop() cancels the consumer task; in-flight handlers finish.

Retry and dead-letter design
─────────────────────────────
  - Up to max_retry_attempts with exponential back-off.
  - After exhausted retries the event is marked FAILED and an envelope is
    published to the dead-letter topic for offline triage.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from ..shared.config import get_settings
from ..shared.logging import get_logger
from ..shared.models.events import Event, EventStatus
from ..shared.ports.event_store import EventStorePort
from ..shared.ports.message_bus import MessageBusPort
from .classifier import RuleBasedClassifier
from .normaliser import EventNormaliser

if TYPE_CHECKING:
    from ..assessment.service import AssessmentService

logger = get_logger("worker")


class EventProcessingWorker:
    def __init__(
        self,
        message_bus: MessageBusPort,
        event_store: EventStorePort,
        assessment_service: AssessmentService,
        settings=None,
    ) -> None:
        self._bus = message_bus
        self._event_store = event_store
        self._assessment_service = assessment_service
        self._settings = settings or get_settings()
        self._normaliser = EventNormaliser()
        self._classifier = RuleBasedClassifier()
        self._consumer_task: asyncio.Task | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """
        Start the consumer as a background asyncio task.

        The task calls bus.subscribe(), which runs a blocking pull-loop
        until cancelled.  The API continues to serve requests independently.
        """
        self._consumer_task = asyncio.create_task(
            self._bus.subscribe(
                subscription=self._settings.events_subscription,
                handler=self._handle_message,
                max_messages=self._settings.worker_concurrency,
            ),
            name="aegis-event-worker",
        )
        logger.info(
            "Event processing worker started",
            extra={
                "subscription": self._settings.events_subscription,
                "concurrency": self._settings.worker_concurrency,
            },
        )

    async def stop(self) -> None:
        """Cancel the consumer task and wait for it to drain."""
        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        logger.info("Event processing worker stopped")

    # ── Message handler ───────────────────────────────────────────────────────

    async def _handle_message(self, message: dict, correlation_id: str) -> None:
        """
        Called by the bus for each received message.

        Wraps _process_event in a retry loop; routes to DLQ on exhaustion.
        """
        event_id = message.get("id", "unknown")
        start_time = time.monotonic()

        last_error: Exception | None = None

        for attempt in range(1, self._settings.max_retry_attempts + 1):
            try:
                await self._process_event(message, correlation_id)
                duration_ms = int((time.monotonic() - start_time) * 1000)
                logger.info(
                    "Event processed successfully",
                    extra={
                        "event_id": event_id,
                        "correlation_id": correlation_id,
                        "attempt": attempt,
                        "duration_ms": duration_ms,
                    },
                )
                return

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Processing attempt failed",
                    extra={
                        "event_id": event_id,
                        "attempt": attempt,
                        "max_attempts": self._settings.max_retry_attempts,
                        "error": str(exc),
                    },
                )
                if attempt < self._settings.max_retry_attempts:
                    backoff = self._settings.retry_backoff_seconds * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)

        # All retries exhausted
        logger.error(
            "Event processing failed after all retries — routing to DLQ",
            extra={"event_id": event_id, "error": str(last_error)},
        )
        await self._event_store.update_event_status(event_id, EventStatus.FAILED)

        try:
            await self._bus.publish(
                topic=self._settings.dead_letter_topic,
                message={**message, "_dlq_reason": str(last_error)},
                correlation_id=correlation_id,
                attributes={"dlq": "true", "original_error": str(last_error)[:200]},
            )
        except Exception as dlq_exc:
            logger.error(
                "Failed to publish to DLQ",
                extra={"event_id": event_id, "error": str(dlq_exc)},
            )

        # Re-raise so the message bus adapter can decide to ack or nack.
        # The DLQ publish is a notification — it does NOT swallow the error.
        # The in-memory bus absorbs this in a finally block; the Pub/Sub
        # emulator bus will not ack, allowing redelivery tracking upstream.
        logger.debug(
            "Re-raising after DLQ publish — bus adapter will decide ack/nack",
            extra={"event_id": event_id, "correlation_id": correlation_id},
        )
        raise last_error

    # ── Processing pipeline ───────────────────────────────────────────────────

    async def _process_event(self, raw_message: dict, correlation_id: str) -> None:
        """Execute the full processing pipeline for one event."""
        event = Event.model_validate(raw_message)

        # 0. Idempotency guard — skip if the event was already fully processed.
        #    Pub/Sub can redeliver messages even after ack; this prevents
        #    redundant pipeline runs for the same idempotency key.
        if event.idempotency_key:
            if await self._event_store.event_exists(event.idempotency_key):
                existing = await self._event_store.get_event(event.id)
                if existing and existing.status in (
                    EventStatus.ASSESSED,
                    EventStatus.FAILED,
                ):
                    logger.warning(
                        "Duplicate delivery — event already processed, skipping",
                        extra={
                            "event_id": event.id,
                            "correlation_id": correlation_id,
                            "status": str(existing.status),
                            "idempotency_key": event.idempotency_key,
                        },
                    )
                    return

        # 1. Normalise
        normalised = self._normaliser.normalise(event)
        await self._event_store.update_event_status(event.id, EventStatus.NORMALISED)
        await self._event_store.save_event(normalised)

        # 2. Classify (deterministic, no LLM)
        classification = self._classifier.classify(normalised)
        await self._event_store.update_event_status(event.id, EventStatus.CLASSIFIED)
        await self._event_store.save_classification(classification)

        # 3. Assessment (client matching → evidence retrieval → model → scoring)
        await self._event_store.update_event_status(event.id, EventStatus.PROCESSING)
        await self._assessment_service.assess_event(normalised, classification)

        # 4. Done
        await self._event_store.update_event_status(event.id, EventStatus.ASSESSED)
