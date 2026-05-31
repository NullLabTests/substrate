from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import AsyncIterator

from core.distributed.protocol import DistributedMessage


class MessageQueueBackend(ABC):
    @abstractmethod
    async def publish(self, message: DistributedMessage, channel: str = "default") -> None:
        ...

    @abstractmethod
    async def subscribe(self, channel: str = "default") -> AsyncIterator[DistributedMessage]:
        ...

    @abstractmethod
    async def request(
        self, message: DistributedMessage, channel: str = "default",
        timeout: float = 30.0,
    ) -> DistributedMessage | None:
        ...

    @abstractmethod
    async def acknowledge(self, message: DistributedMessage) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...


class SubscriberQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[DistributedMessage | None] = asyncio.Queue()

    async def put(self, msg: DistributedMessage) -> None:
        await self._queue.put(msg)

    async def get(self) -> DistributedMessage:
        item = await self._queue.get()
        if item is None:
            raise asyncio.CancelledError("Subscriber closed")
        return item

    async def close(self) -> None:
        await self._queue.put(None)


class InProcessMessageQueue(MessageQueueBackend):
    def __init__(self) -> None:
        self._subscribers: dict[str, list[SubscriberQueue]] = defaultdict(list)
        self._pending_requests: dict[str, asyncio.Future[DistributedMessage]] = {}
        self._closed = False

    async def publish(self, message: DistributedMessage, channel: str = "default") -> None:
        if self._closed:
            return
        if message.correlation_id and message.correlation_id in self._pending_requests:
            future = self._pending_requests.pop(message.correlation_id)
            future.set_result(message)
            return
        for sub in self._subscribers.get(channel, []):
            await sub.put(message)

    async def subscribe(self, channel: str = "default") -> AsyncIterator[DistributedMessage]:
        sub = SubscriberQueue()
        self._subscribers[channel].append(sub)
        try:
            while not self._closed:
                try:
                    msg = await asyncio.wait_for(sub.get(), timeout=1.0)
                    yield msg
                except TimeoutError:
                    if self._closed:
                        break
                    continue
        finally:
            subs = self._subscribers.get(channel, [])
            if sub in subs:
                subs.remove(sub)

    async def request(
        self, message: DistributedMessage, channel: str = "default",
        timeout: float = 30.0,
    ) -> DistributedMessage | None:
        correlation_id = message.correlation_id or f"req_{id(message)}"
        message.correlation_id = correlation_id
        future: asyncio.Future[DistributedMessage] = asyncio.Future()
        self._pending_requests[correlation_id] = future
        for sub in self._subscribers.get(channel, []):
            await sub.put(message)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError:
            self._pending_requests.pop(correlation_id, None)
            return None

    async def acknowledge(self, message: DistributedMessage) -> None:
        pass

    async def close(self) -> None:
        self._closed = True
        for subs in self._subscribers.values():
            for sub in subs:
                await sub.close()
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()
