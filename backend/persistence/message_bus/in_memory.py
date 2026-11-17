"""
In-memory asyncio message bus.

Implements MessageBusPort using asyncio.Queue per topic.

This is genuine async processing:
  - publish() puts a message envelope onto the queue and returns immediately.
  - subscribe() runs a blocking pull-loop (until cancelled) that dispatches
    to the handler under a semaphore.
  - The API path and the worker share only the queue — they never call each
    other directly.

Subscription routing: the subscription name is mapped to a topic by stripping
common suffixes (-worker, -sub).  Publish to topic 'aegis-events';
subscribe with 'aegis-events-worker' — they resolve to the same queue.

Dead-letter: a DLQ topic is just another queue; the worker publishes there
after exhausting retries.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from ...shared.logging import get_logger
from ...shared.ports.message_bus import MessageBusPort, MessageHandler

logger = get_logger("message_bus.in_memory")


class InMemoryMessageBus(MessageBusPort):

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}
        # Track in-flight dispatch tasks so stop() can drain them before the
        # caller closes dependent resources (e.g. SQLite connections on Windows).
        self._dispatch_tasks: set[asyncio.Task] = set()

    # ── MessageBusPort ────────────────────────────────────────────────────────

    async def start(self) -> None:
        logger.info("In-memory message bus started")

    async def stop(self) -> None:
        # Drain any in-flight dispatch tasks so callers can safely close
        # dependent resources (e.g. SQLite files on Windows) right after stop().
        if self._dispatch_tasks:
            await asyncio.gather(*list(self._dispatch_tasks), return_exceptions=True)
        logger.info("In-memory message bus stopped")

    async def publish(
        self,
        topic: str,
        message: dict,
        correlation_id: str,
        attributes: Optional[dict[str, str]] = None,
    ) -> str:
        queue = self._get_queue(topic)
        message_id = str(uuid.uuid4())
        envelope = {
            "message_id": message_id,
            "correlation_id": correlation_id,
            "attributes": attributes or {},
            "data": message,
        }
        await queue.put(envelope)
        logger.debug(
            "Message published",
            extra={
                "topic": topic,
                "message_id": message_id,
                "correlation_id": correlation_id,
                "queue_depth": queue.qsize(),
            },
        )
        return message_id

    async def subscribe(
        self,
        subscription: str,
        handler: MessageHandler,
        max_messages: int = 10,
    ) -> None:
        """
        Pull-loop: runs until cancelled.

        Dispatches each message to ``handler`` concurrently, bounded by
        a semaphore of size ``max_messages``.
        """
        topic = _subscription_to_topic(subscription)
        queue = self._get_queue(topic)
        semaphore = asyncio.Semaphore(max_messages)

        logger.info(
            "Consumer started",
            extra={"subscription": subscription, "topic": topic, "concurrency": max_messages},
        )

        while True:
            try:
                envelope = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                logger.info("Consumer cancelled", extra={"subscription": subscription})
                break

            async def _dispatch(env: dict) -> None:
                async with semaphore:
                    try:
                        await handler(env["data"], env["correlation_id"])
                    except Exception as exc:
                        logger.error(
                            "Handler raised an exception",
                            extra={"subscription": subscription, "error": str(exc)},
                        )
                    finally:
                        queue.task_done()

            task = asyncio.create_task(_dispatch(envelope))
            self._dispatch_tasks.add(task)
            task.add_done_callback(self._dispatch_tasks.discard)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_queue(self, topic: str) -> asyncio.Queue:
        if topic not in self._queues:
            self._queues[topic] = asyncio.Queue()
        return self._queues[topic]

    def queue_depth(self, topic: str) -> int:
        """Return the current depth of a topic queue (useful in tests)."""
        return self._queues.get(topic, asyncio.Queue()).qsize()


def _subscription_to_topic(subscription: str) -> str:
    """Map a subscription name back to its topic."""
    for suffix in ("-worker", "-sub", "-subscription"):
        if subscription.endswith(suffix):
            return subscription[: -len(suffix)]
    return subscription
