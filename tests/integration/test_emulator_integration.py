"""
Integration tests for the Pub/Sub emulator message bus.

These tests are skipped unless PUBSUB_EMULATOR_HOST is set, as they
require a running Pub/Sub emulator instance.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("PUBSUB_EMULATOR_HOST"),
    reason="requires a running Pub/Sub emulator (set PUBSUB_EMULATOR_HOST)",
)


def _make_bus(project_id: str, topic: str, subscription: str):
    """Build a PubSubEmulatorMessageBus with custom topic/subscription."""
    from backend.persistence.message_bus.pubsub_emulator import PubSubEmulatorMessageBus
    from backend.shared.config import Settings

    settings = Settings(
        events_topic=topic,
        events_subscription=subscription,
        dead_letter_topic=f"{topic}-dlq",
        max_retry_attempts=2,
        retry_backoff_seconds=0.01,
        worker_concurrency=1,
        pubsub_project_id=project_id,
        pubsub_emulator_host=os.getenv("PUBSUB_EMULATOR_HOST", "localhost:8085"),
    )
    return PubSubEmulatorMessageBus(
        project_id=project_id,
        emulator_host=settings.pubsub_emulator_host,
        settings=settings,
    )


async def test_publish_consume_ack_cycle():
    """
    Publish one message and confirm the subscriber receives it with
    the correct correlation_id before the timeout.
    """
    unique = uuid.uuid4().hex[:8]
    project_id = f"test-project-{unique}"
    topic = f"test-topic-{unique}"
    subscription = f"test-sub-{unique}"

    bus = _make_bus(project_id, topic, subscription)
    await bus.start()

    received: list[dict] = []
    correlation_ids: list[str] = []

    async def handler(data: dict, correlation_id: str) -> None:
        received.append(data)
        correlation_ids.append(correlation_id)

    expected_correlation_id = str(uuid.uuid4())
    payload = {"event": "test_event", "value": 42}

    await bus.publish(topic, payload, correlation_id=expected_correlation_id)

    # Run the subscriber for up to 3 seconds
    task = asyncio.create_task(
        bus.subscribe(subscription=subscription, handler=handler, max_messages=5)
    )
    try:
        await asyncio.wait_for(
            asyncio.shield(task),
            timeout=3.0,
        )
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await bus.stop()

    assert len(received) >= 1, "Expected at least one message to be received"
    assert correlation_ids[0] == expected_correlation_id


async def test_nack_causes_redelivery():
    """
    A handler that raises on the first call (causing a nack) should
    cause the message to be redelivered. The second call succeeds.
    """
    unique = uuid.uuid4().hex[:8]
    project_id = f"test-project-{unique}"
    topic = f"test-topic-{unique}"
    subscription = f"test-sub-{unique}"

    bus = _make_bus(project_id, topic, subscription)
    await bus.start()

    call_count = 0
    received_data: list[dict] = []

    async def handler(data: dict, correlation_id: str) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Simulated handler failure — expect redelivery")
        received_data.append(data)

    correlation_id = str(uuid.uuid4())
    payload = {"event": "redelivery_test"}

    await bus.publish(topic, payload, correlation_id=correlation_id)

    # Run subscriber for up to 10 seconds to allow ack deadline expiry + redelivery
    task = asyncio.create_task(
        bus.subscribe(subscription=subscription, handler=handler, max_messages=5)
    )
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=10.0)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await bus.stop()

    assert call_count >= 2, f"Expected handler to be called at least twice, got {call_count}"
    assert len(received_data) >= 1, "Expected at least one successful delivery"
