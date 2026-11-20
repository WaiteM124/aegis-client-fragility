"""
Pub/Sub emulator message bus adapter.

Architecture note — emulator vs production
───────────────────────────────────────────
The Pub/Sub emulator gives realistic at-least-once messaging semantics for
local development and integration testing.  It does NOT guarantee:
  - exactly-once processing (use worker-level idempotency for that)
  - production resilience, ordering guarantees, or dead-letter policy parity
  - performance or scalability equivalent to live GCP Pub/Sub

Use PubSubMessageBus (checkpoint 4) for production GCP deployments.

Ack/nack design
───────────────
Messages are acked **only** after the handler returns without raising.
If the handler raises, the message is NOT acked; the emulator will redeliver
it after the ack deadline expires.  This is the key property that the
in-memory bus cannot provide.

The synchronous pull API is used (not streaming pull) so each message can be
acked or skipped individually.  Sync client calls are wrapped in
``asyncio.to_thread`` to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid

from ...shared.logging import get_logger
from ...shared.ports.message_bus import MessageBusPort, MessageHandler

logger = get_logger("message_bus.pubsub_emulator")

# Short pull timeout (seconds) so the loop can respond to asyncio cancellation
# without long blocking periods.
_PULL_TIMEOUT_S = 1.0
_IDLE_SLEEP_S = 0.5


class PubSubEmulatorMessageBus(MessageBusPort):
    """
    Message bus backed by the GCP Pub/Sub emulator.

    Parameters
    ----------
    project_id:
        GCP project ID used to form topic/subscription paths.
    emulator_host:
        ``host:port`` of the running Pub/Sub emulator, e.g. ``localhost:8085``.
    settings:
        Optional Settings override.  Defaults to the global singleton.
    publisher_client, subscriber_client:
        Injection points for unit tests — pass pre-built mock clients to bypass
        the network and avoid requiring a running emulator.
    """

    def __init__(
        self,
        project_id: str,
        emulator_host: str,
        settings=None,
        publisher_client=None,
        subscriber_client=None,
    ) -> None:
        from ...shared.config import get_settings

        self._project_id = project_id
        self._emulator_host = emulator_host
        self._settings = settings or get_settings()
        # Pre-injected clients take priority (used in tests)
        self._publisher = publisher_client
        self._subscriber = subscriber_client

    # ── MessageBusPort ────────────────────────────────────────────────────────

    async def start(self) -> None:
        """
        Set the emulator environment variable, create clients, and ensure
        the required topics and subscription exist.
        """
        # Only set the env var and create real clients when none were injected
        if self._publisher is None or self._subscriber is None:
            os.environ["PUBSUB_EMULATOR_HOST"] = self._emulator_host
            from google.cloud import pubsub_v1  # noqa: PLC0415 (lazy import)

            if self._publisher is None:
                self._publisher = pubsub_v1.PublisherClient()
            if self._subscriber is None:
                self._subscriber = pubsub_v1.SubscriberClient()

            await asyncio.to_thread(self._create_topics_and_subscriptions)

        logger.info(
            "Pub/Sub emulator message bus started",
            extra={
                "emulator_host": self._emulator_host,
                "project_id": self._project_id,
            },
        )

    async def stop(self) -> None:
        """Close publisher and subscriber clients."""
        if self._publisher:
            try:
                self._publisher.close()
            except Exception:
                pass
        if self._subscriber:
            try:
                self._subscriber.close()
            except Exception:
                pass
        logger.info("Pub/Sub emulator message bus stopped")

    async def publish(
        self,
        topic: str,
        message: dict,
        correlation_id: str,
        attributes: dict[str, str] | None = None,
    ) -> str:
        """
        Serialise and publish a message.

        The correlation_id is stored as a Pub/Sub message attribute so it
        survives serialisation and can be threaded through the subscriber.
        """
        topic_path = f"projects/{self._project_id}/topics/{topic}"
        data = json.dumps(message).encode("utf-8")
        attrs: dict[str, str] = {"correlation_id": correlation_id}
        if attributes:
            attrs.update(attributes)

        def _do_publish() -> str:
            future = self._publisher.publish(topic_path, data=data, **attrs)
            return future.result()

        message_id = await asyncio.to_thread(_do_publish)
        logger.debug(
            "Message published",
            extra={
                "topic": topic,
                "message_id": message_id,
                "correlation_id": correlation_id,
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

        Each pulled message is dispatched to ``handler``.  On success the
        message is acked.  On failure the message is NOT acked; the emulator
        will redeliver it after the ack deadline expires.

        The synchronous pull client is called in an executor so the event loop
        stays responsive.
        """
        subscription_path = f"projects/{self._project_id}/subscriptions/{subscription}"

        logger.info(
            "Consumer started",
            extra={
                "subscription": subscription_path,
                "concurrency": max_messages,
            },
        )

        try:
            while True:
                response = await asyncio.to_thread(
                    self._pull, subscription_path, max_messages
                )

                for received_message in response.received_messages:
                    await self._dispatch(subscription_path, received_message, handler)

                if not response.received_messages:
                    # No messages right now — sleep briefly to avoid hot-loop
                    await asyncio.sleep(_IDLE_SLEEP_S)

        except asyncio.CancelledError:
            logger.info(
                "Consumer cancelled",
                extra={"subscription": subscription},
            )
            raise

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _dispatch(self, subscription_path: str, received_message, handler: MessageHandler) -> None:
        """
        Deserialise, call handler, then ack or not-ack based on outcome.

        Ack → handler returned normally
        No ack → handler raised (Pub/Sub will redeliver after ack deadline)
        """
        ack_id = received_message.ack_id
        message = received_message.message
        raw_data = message.data.decode("utf-8") if isinstance(message.data, (bytes, bytearray)) else message.data
        data = json.loads(raw_data)
        # Attributes may be a Mapping; convert to plain dict for safety
        attrs = dict(message.attributes) if message.attributes else {}
        correlation_id = attrs.get("correlation_id") or str(uuid.uuid4())

        logger.debug(
            "Message received",
            extra={
                "message_id": message.message_id,
                "correlation_id": correlation_id,
            },
        )

        try:
            await handler(data, correlation_id)
            # ── Ack on success ────────────────────────────────────────────
            await asyncio.to_thread(self._ack, subscription_path, [ack_id])
            logger.debug(
                "Message acked",
                extra={"message_id": message.message_id, "correlation_id": correlation_id},
            )
        except Exception as exc:
            # ── No ack on failure — Pub/Sub redelivers ───────────────────
            logger.warning(
                "Handler raised — message will be redelivered (not acked)",
                extra={
                    "message_id": message.message_id,
                    "correlation_id": correlation_id,
                    "error": str(exc),
                },
            )

    def _pull(self, subscription_path: str, max_messages: int):
        """Synchronous pull (called in executor)."""
        return self._subscriber.pull(
            request={
                "subscription": subscription_path,
                "max_messages": max_messages,
            },
            timeout=_PULL_TIMEOUT_S,
        )

    def _ack(self, subscription_path: str, ack_ids: list[str]) -> None:
        """Synchronous acknowledge (called in executor)."""
        self._subscriber.acknowledge(
            request={
                "subscription": subscription_path,
                "ack_ids": ack_ids,
            }
        )

    def _create_topics_and_subscriptions(self) -> None:
        """
        Ensure the events topic, DLQ topic, and events subscription all exist.
        Called once during start() in a thread executor.
        """
        try:
            from google.api_core.exceptions import AlreadyExists  # noqa: PLC0415
        except ImportError:
            # Shouldn't happen if google-cloud-pubsub is installed
            raise

        events_topic_path = (
            f"projects/{self._project_id}/topics/{self._settings.events_topic}"
        )
        dlq_topic_path = (
            f"projects/{self._project_id}/topics/{self._settings.dead_letter_topic}"
        )
        events_sub_path = (
            f"projects/{self._project_id}/subscriptions/"
            f"{self._settings.events_subscription}"
        )

        for topic_path in [events_topic_path, dlq_topic_path]:
            try:
                self._publisher.create_topic(request={"name": topic_path})
                logger.debug("Topic created", extra={"topic": topic_path})
            except AlreadyExists:
                logger.debug("Topic already exists", extra={"topic": topic_path})

        try:
            self._subscriber.create_subscription(
                request={"name": events_sub_path, "topic": events_topic_path}
            )
            logger.debug(
                "Subscription created", extra={"subscription": events_sub_path}
            )
        except AlreadyExists:
            logger.debug(
                "Subscription already exists",
                extra={"subscription": events_sub_path},
            )
