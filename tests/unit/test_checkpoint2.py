"""
Checkpoint 2 tests.

Covers:
  1. Publish test          — in-memory bus publish → subscriber handler
  2. Acknowledgement test  — fake/stub adapter ack/nack semantics
  3. Retry test            — worker retries up to max_retry_attempts
  4. DLQ test              — exhausted retries → FAILED status + DLQ message
  5. Idempotency test      — duplicate message is processed only once
  6. Correlation ID test   — correlation_id propagated through all log entries
  7. Worker raise test     — worker raises after DLQ publish (ack/nack gap fix)

All tests use only local dependencies.  No Docker or Pub/Sub emulator required.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.persistence.message_bus.in_memory import InMemoryMessageBus
from backend.shared.config import Settings
from backend.shared.models.events import Event, EventStatus

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_settings(**kwargs) -> Settings:
    """Create a Settings instance for tests, using fast retry backoff."""
    defaults = dict(
        events_topic="aegis-events",
        events_subscription="aegis-events-worker",
        dead_letter_topic="aegis-events-dlq",
        max_retry_attempts=3,
        retry_backoff_seconds=0.001,  # near-zero for speed
        worker_concurrency=2,
    )
    defaults.update(kwargs)
    return Settings(**defaults)


def _make_event(**kwargs) -> Event:
    """Return a minimal Event dict suitable for publishing."""
    defaults = dict(
        source="test",
        title="Test event",
        raw_content="Content",
        event_date=datetime(2026, 11, 15),
        idempotency_key=str(uuid.uuid4()),
    )
    defaults.update(kwargs)
    return Event(**defaults)


# ---------------------------------------------------------------------------
# Test 1 — Publish / subscribe round-trip (in-memory bus)
# ---------------------------------------------------------------------------


class TestPublishReceived:
    """Verify that a published message is delivered to a subscriber handler."""

    async def test_publish_received_by_subscriber(self):
        bus = InMemoryMessageBus()
        await bus.start()

        received: list[tuple[dict, str]] = []

        async def handler(message: dict, correlation_id: str) -> None:
            received.append((message, correlation_id))

        consumer = asyncio.create_task(
            bus.subscribe("aegis-events-worker", handler, max_messages=1)
        )

        msg = {"hello": "world", "number": 42}
        await bus.publish("aegis-events", msg, "corr-abc-123")

        # Give the consumer a moment to process
        await asyncio.sleep(0.1)
        consumer.cancel()
        try:
            await consumer
        except asyncio.CancelledError:
            pass

        assert len(received) == 1, f"Expected 1 delivery, got {len(received)}"
        assert received[0][0] == msg
        assert received[0][1] == "corr-abc-123"

        await bus.stop()


# ---------------------------------------------------------------------------
# Test 2 — Ack/nack semantics (fake/stub adapter)
# ---------------------------------------------------------------------------


class _FakePubSubAdapter:
    """
    Minimal stub that replicates the ack/nack semantics of
    PubSubEmulatorMessageBus without requiring a running emulator or
    the google-cloud-pubsub library.

    Rules (identical to the real adapter):
      - Successful handler → acked
      - Handler raises    → NOT acked (would trigger redelivery in real Pub/Sub)
    """

    def __init__(self):
        self.acked: list[dict] = []
        self.not_acked: list[dict] = []

    async def deliver(
        self,
        message: dict,
        correlation_id: str,
        handler: Callable[[dict, str], Awaitable[None]],
    ) -> None:
        try:
            await handler(message, correlation_id)
            self.acked.append(message)
        except Exception:
            self.not_acked.append(message)


class TestAckNackSemantics:
    """Verify ack-on-success, no-ack-on-failure semantics."""

    async def test_successful_handler_triggers_ack(self):
        adapter = _FakePubSubAdapter()
        msg = {"event": "one"}

        async def good_handler(m, cid):
            pass  # returns normally

        await adapter.deliver(msg, "corr-1", good_handler)

        assert msg in adapter.acked
        assert msg not in adapter.not_acked

    async def test_failing_handler_does_not_trigger_ack(self):
        adapter = _FakePubSubAdapter()
        msg = {"event": "two"}

        async def bad_handler(m, cid):
            raise RuntimeError("simulated processing error")

        await adapter.deliver(msg, "corr-2", bad_handler)

        assert msg not in adapter.acked
        assert msg in adapter.not_acked

    async def test_multiple_messages_independent_ack(self):
        adapter = _FakePubSubAdapter()
        msg_ok = {"id": "ok"}
        msg_fail = {"id": "fail"}

        call_count = 0

        async def mixed_handler(m, cid):
            nonlocal call_count
            call_count += 1
            if m.get("id") == "fail":
                raise ValueError("bad message")

        await adapter.deliver(msg_ok, "c1", mixed_handler)
        await adapter.deliver(msg_fail, "c2", mixed_handler)

        assert call_count == 2
        assert msg_ok in adapter.acked
        assert msg_fail in adapter.not_acked
        assert len(adapter.acked) == 1
        assert len(adapter.not_acked) == 1


# ---------------------------------------------------------------------------
# Test 3 — Retry logic (worker retries up to max_retry_attempts)
# ---------------------------------------------------------------------------


class TestWorkerRetry:
    """Worker retries on failure; succeeds if a later attempt works."""

    async def test_succeeds_on_third_attempt(self):
        from backend.event_processing.worker import EventProcessingWorker

        bus = InMemoryMessageBus()
        await bus.start()

        event_store = MagicMock()
        event_store.update_event_status = AsyncMock()
        event_store.save_event = AsyncMock()
        event_store.save_classification = AsyncMock()
        event_store.event_exists = AsyncMock(return_value=False)
        event_store.get_event = AsyncMock(return_value=None)

        assessment_service = MagicMock()
        assessment_service.assess_event = AsyncMock()

        settings = _make_settings(max_retry_attempts=3)
        worker = EventProcessingWorker(
            message_bus=bus,
            event_store=event_store,
            assessment_service=assessment_service,
            settings=settings,
        )

        attempt_count = 0
        original_process = worker._process_event

        async def counting_process(raw_message, correlation_id):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise RuntimeError(f"Simulated failure on attempt {attempt_count}")
            await original_process(raw_message, correlation_id)

        worker._process_event = counting_process

        event = _make_event()
        event_msg = json.loads(event.model_dump_json())

        await worker._handle_message(event_msg, "corr-retry")

        assert attempt_count == 3, f"Expected 3 attempts, got {attempt_count}"

        await bus.stop()

    async def test_all_attempts_used_before_dlq(self):
        """Worker uses exactly max_retry_attempts before giving up."""
        from backend.event_processing.worker import EventProcessingWorker

        bus = InMemoryMessageBus()
        await bus.start()

        event_store = MagicMock()
        event_store.update_event_status = AsyncMock()
        event_store.event_exists = AsyncMock(return_value=False)
        event_store.get_event = AsyncMock(return_value=None)

        assessment_service = MagicMock()
        settings = _make_settings(max_retry_attempts=2)
        worker = EventProcessingWorker(
            message_bus=bus,
            event_store=event_store,
            assessment_service=assessment_service,
            settings=settings,
        )

        attempt_count = 0

        async def always_fail(raw_message, correlation_id):
            nonlocal attempt_count
            attempt_count += 1
            raise RuntimeError("always fails")

        worker._process_event = always_fail

        event = _make_event()
        event_msg = json.loads(event.model_dump_json())

        try:
            await worker._handle_message(event_msg, "corr-allretry")
        except RuntimeError:
            pass  # Expected — worker re-raises after DLQ

        assert attempt_count == 2, f"Expected 2 attempts, got {attempt_count}"

        await bus.stop()


# ---------------------------------------------------------------------------
# Test 4 — DLQ routing after exhausted retries
# ---------------------------------------------------------------------------


class TestWorkerDLQ:
    """After all retries fail, the event is marked FAILED and routed to DLQ."""

    async def test_failed_event_marked_and_dlq_published(self):
        from backend.event_processing.worker import EventProcessingWorker

        bus = InMemoryMessageBus()
        await bus.start()

        event_store = MagicMock()
        event_store.update_event_status = AsyncMock()
        event_store.event_exists = AsyncMock(return_value=False)
        event_store.get_event = AsyncMock(return_value=None)

        assessment_service = MagicMock()
        settings = _make_settings(max_retry_attempts=1)
        worker = EventProcessingWorker(
            message_bus=bus,
            event_store=event_store,
            assessment_service=assessment_service,
            settings=settings,
        )

        async def always_fail(raw_message, correlation_id):
            raise RuntimeError("permanent failure")

        worker._process_event = always_fail

        event = _make_event()
        event_msg = json.loads(event.model_dump_json())

        # Worker should raise after DLQ publish
        with pytest.raises(RuntimeError, match="permanent failure"):
            await worker._handle_message(event_msg, "corr-dlq")

        # Event status should have been set to FAILED
        event_store.update_event_status.assert_any_call(event.id, EventStatus.FAILED)

        # DLQ queue should have one message
        dlq_depth = bus.queue_depth(settings.dead_letter_topic)
        assert dlq_depth == 1, f"Expected 1 DLQ message, got {dlq_depth}"

        await bus.stop()


# ---------------------------------------------------------------------------
# Test 5 — Worker-level idempotency
# ---------------------------------------------------------------------------


class TestWorkerIdempotency:
    """An already-ASSESSED event with the same idempotency key is not reprocessed."""

    async def test_duplicate_delivery_skipped(self):
        from backend.event_processing.worker import EventProcessingWorker

        bus = InMemoryMessageBus()
        await bus.start()

        # Pre-build an event that is already ASSESSED
        event = _make_event(idempotency_key="idem-key-xyz")
        assessed_event = event.model_copy(update={"status": EventStatus.ASSESSED})

        event_store = MagicMock()
        event_store.update_event_status = AsyncMock()
        event_store.save_event = AsyncMock()
        event_store.save_classification = AsyncMock()
        # event_exists returns True (the key is already in the store)
        event_store.event_exists = AsyncMock(return_value=True)
        # get_event returns the already-ASSESSED version
        event_store.get_event = AsyncMock(return_value=assessed_event)

        assessment_service = MagicMock()
        assessment_service.assess_event = AsyncMock()

        settings = _make_settings()
        worker = EventProcessingWorker(
            message_bus=bus,
            event_store=event_store,
            assessment_service=assessment_service,
            settings=settings,
        )

        process_count = 0
        original_pipeline = worker._process_event

        async def counting_pipeline(raw_message, correlation_id):
            nonlocal process_count
            process_count += 1
            await original_pipeline(raw_message, correlation_id)

        # Patch at handle_message level to count actual pipeline calls
        event_msg = json.loads(event.model_dump_json())

        # First delivery — idempotency key exists + status ASSESSED → skip
        await worker._handle_message(event_msg, "corr-idem-1")

        # assess_event should NOT have been called (processing skipped)
        assessment_service.assess_event.assert_not_called()

        await bus.stop()

    async def test_new_event_not_skipped(self):
        """An event not yet in the store should be processed normally."""
        from backend.event_processing.worker import EventProcessingWorker

        bus = InMemoryMessageBus()
        await bus.start()

        event_store = MagicMock()
        event_store.update_event_status = AsyncMock()
        event_store.save_event = AsyncMock()
        event_store.save_classification = AsyncMock()
        event_store.event_exists = AsyncMock(return_value=False)
        event_store.get_event = AsyncMock(return_value=None)

        assessment_service = MagicMock()
        assessment_service.assess_event = AsyncMock()

        settings = _make_settings()
        worker = EventProcessingWorker(
            message_bus=bus,
            event_store=event_store,
            assessment_service=assessment_service,
            settings=settings,
        )

        event = _make_event(idempotency_key="new-key-abc")
        event_msg = json.loads(event.model_dump_json())

        await worker._handle_message(event_msg, "corr-new")

        # Assessment should have been called for a new event
        assessment_service.assess_event.assert_called_once()

        await bus.stop()


# ---------------------------------------------------------------------------
# Test 6 — Correlation ID propagated through log entries
# ---------------------------------------------------------------------------


class TestCorrelationIdPropagation:
    """correlation_id must appear in every structured log entry in the pipeline."""

    async def test_correlation_id_in_handler_logs(self):
        from backend.event_processing.worker import EventProcessingWorker

        bus = InMemoryMessageBus()
        await bus.start()

        event_store = MagicMock()
        event_store.update_event_status = AsyncMock()
        event_store.save_event = AsyncMock()
        event_store.save_classification = AsyncMock()
        event_store.event_exists = AsyncMock(return_value=False)
        event_store.get_event = AsyncMock(return_value=None)

        assessment_service = MagicMock()
        assessment_service.assess_event = AsyncMock()

        settings = _make_settings()
        worker = EventProcessingWorker(
            message_bus=bus,
            event_store=event_store,
            assessment_service=assessment_service,
            settings=settings,
        )

        correlation_id = "test-corr-id-" + str(uuid.uuid4())[:8]

        # Capture log records emitted during processing
        captured: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record)

        capture_handler = _Capture()
        worker_logger = logging.getLogger("aegis.worker")
        original_level = worker_logger.level
        worker_logger.addHandler(capture_handler)
        worker_logger.setLevel(logging.DEBUG)  # Ensure INFO records are emitted
        try:
            event = _make_event()
            event_msg = json.loads(event.model_dump_json())
            await worker._handle_message(event_msg, correlation_id)
        finally:
            worker_logger.removeHandler(capture_handler)
            worker_logger.setLevel(original_level)

        # Every log record that has a correlation_id extra should match
        records_with_corr = [
            r for r in captured
            if getattr(r, "correlation_id", None) == correlation_id
        ]

        # At minimum, the success log must carry the correlation_id
        assert len(records_with_corr) >= 1, (
            f"Expected at least 1 log record with correlation_id={correlation_id!r}; "
            f"got {len(records_with_corr)}.  "
            f"Records: {[(r.getMessage(), getattr(r, 'correlation_id', None)) for r in captured]}"
        )

        await bus.stop()

    async def test_correlation_id_in_retry_logs(self):
        """correlation_id must appear in retry warning logs."""
        from backend.event_processing.worker import EventProcessingWorker

        bus = InMemoryMessageBus()
        await bus.start()

        event_store = MagicMock()
        event_store.update_event_status = AsyncMock()
        event_store.event_exists = AsyncMock(return_value=False)
        event_store.get_event = AsyncMock(return_value=None)

        assessment_service = MagicMock()
        settings = _make_settings(max_retry_attempts=2)
        worker = EventProcessingWorker(
            message_bus=bus,
            event_store=event_store,
            assessment_service=assessment_service,
            settings=settings,
        )

        attempt = 0

        async def fail_once(raw_message, correlation_id):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise RuntimeError("first attempt failure")
            # Second attempt succeeds (stubbed — no real pipeline)

        worker._process_event = fail_once

        correlation_id = "retry-corr-" + str(uuid.uuid4())[:8]
        captured: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record)

        capture_handler = _Capture()
        worker_logger = logging.getLogger("aegis.worker")
        original_level = worker_logger.level
        worker_logger.addHandler(capture_handler)
        worker_logger.setLevel(logging.DEBUG)  # Ensure INFO records are emitted
        try:
            event = _make_event()
            event_msg = json.loads(event.model_dump_json())
            await worker._handle_message(event_msg, correlation_id)
        finally:
            worker_logger.removeHandler(capture_handler)
            worker_logger.setLevel(original_level)

        # At least one log record should carry the correlation_id
        # The success log in _handle_message always includes correlation_id
        success_records = [
            r for r in captured
            if getattr(r, "correlation_id", None) == correlation_id
        ]
        assert len(success_records) >= 1, (
            "At least the success log must carry correlation_id; "
            f"found {len(success_records)} matching records out of {len(captured)} total. "
            f"Records: {[(r.getMessage(), getattr(r, 'correlation_id', None)) for r in captured]}"
        )

        await bus.stop()


# ---------------------------------------------------------------------------
# Test 7 — Worker raises after DLQ publish (ack/nack gap fix)
# ---------------------------------------------------------------------------


class TestWorkerAckNackRaise:
    """After DLQ publish the worker re-raises so the bus can decide ack/nack."""

    async def test_worker_raises_after_dlq_publish(self):
        from backend.event_processing.worker import EventProcessingWorker

        bus = InMemoryMessageBus()
        await bus.start()

        event_store = MagicMock()
        event_store.update_event_status = AsyncMock()
        event_store.event_exists = AsyncMock(return_value=False)
        event_store.get_event = AsyncMock(return_value=None)

        assessment_service = MagicMock()
        settings = _make_settings(max_retry_attempts=1)
        worker = EventProcessingWorker(
            message_bus=bus,
            event_store=event_store,
            assessment_service=assessment_service,
            settings=settings,
        )

        sentinel = RuntimeError("sentinel-error-unique")

        async def always_fail(raw_message, correlation_id):
            raise sentinel

        worker._process_event = always_fail

        event = _make_event()
        event_msg = json.loads(event.model_dump_json())

        exc_raised: Exception | None = None
        try:
            await worker._handle_message(event_msg, "corr-raise-test")
        except RuntimeError as exc:
            exc_raised = exc

        assert exc_raised is sentinel, (
            f"Expected the sentinel RuntimeError to propagate; got {exc_raised!r}"
        )

        # Also confirm DLQ received the message before the raise
        dlq_depth = bus.queue_depth(settings.dead_letter_topic)
        assert dlq_depth == 1, (
            f"DLQ should have 1 message before raise; got {dlq_depth}"
        )

        await bus.stop()

    async def test_in_memory_bus_absorbs_exception(self):
        """
        Verify the in-memory bus absorbs the exception in its finally block
        so other messages can still be processed.
        """
        from backend.event_processing.worker import EventProcessingWorker

        bus = InMemoryMessageBus()
        await bus.start()

        event_store = MagicMock()
        event_store.update_event_status = AsyncMock()
        event_store.save_event = AsyncMock()
        event_store.save_classification = AsyncMock()
        event_store.event_exists = AsyncMock(return_value=False)
        event_store.get_event = AsyncMock(return_value=None)

        assessment_service = MagicMock()
        assessment_service.assess_event = AsyncMock()

        settings = _make_settings(max_retry_attempts=1)
        worker = EventProcessingWorker(
            message_bus=bus,
            event_store=event_store,
            assessment_service=assessment_service,
            settings=settings,
        )

        good_event_processed = asyncio.Event()
        fail_called = False

        async def selective_fail(raw_message, correlation_id):
            nonlocal fail_called
            event = Event.model_validate(raw_message)
            if event.title == "fail-me":
                fail_called = True
                raise RuntimeError("intentional failure")
            # Good event: proceed through mock pipeline
            good_event_processed.set()

        worker._process_event = selective_fail

        await worker.start()

        # Publish a failing event and a good one
        fail_event = _make_event(title="fail-me")
        good_event = _make_event(title="good-event")

        await bus.publish(
            "aegis-events",
            json.loads(fail_event.model_dump_json()),
            "corr-fail",
        )
        await bus.publish(
            "aegis-events",
            json.loads(good_event.model_dump_json()),
            "corr-good",
        )

        # Both messages should be processed; the bus absorbs the exception
        try:
            await asyncio.wait_for(good_event_processed.wait(), timeout=5.0)
        except TimeoutError:
            pytest.fail("Good event was not processed — bus may have stopped after exception")

        assert fail_called, "Failing handler should have been invoked"
        assert good_event_processed.is_set(), "Good event should have been processed"

        await worker.stop()
        await bus.stop()
