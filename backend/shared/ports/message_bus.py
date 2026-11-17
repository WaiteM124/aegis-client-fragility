"""
Port: message bus / event streaming.

Concrete adapters:
  - InMemoryMessageBus   — asyncio.Queue, zero dependencies, default for local dev
  - PubSubEmulatorBus    — GCP Pub/Sub emulator (checkpoint 2)
  - PubSubBus            — Live GCP Pub/Sub (checkpoint 4)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Optional

# A handler receives the deserialised message payload and the correlation ID.
MessageHandler = Callable[[dict, str], Awaitable[None]]


class MessageBusPort(ABC):

    @abstractmethod
    async def publish(
        self,
        topic: str,
        message: dict,
        correlation_id: str,
        attributes: Optional[dict[str, str]] = None,
    ) -> str:
        """
        Publish a message to a topic.

        Returns the message ID assigned by the bus.
        The call must be idempotent at the transport level
        (duplicate delivery is handled by the subscriber).
        """
        ...

    @abstractmethod
    async def subscribe(
        self,
        subscription: str,
        handler: MessageHandler,
        max_messages: int = 10,
    ) -> None:
        """
        Start consuming messages.

        This coroutine runs until cancelled.  The caller is responsible for
        wrapping it in ``asyncio.create_task`` and cancelling it on shutdown.

        ``max_messages`` bounds how many messages are dispatched concurrently.
        """
        ...

    @abstractmethod
    async def start(self) -> None:
        """Open connections, create topics / subscriptions if missing."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully drain and close."""
        ...
