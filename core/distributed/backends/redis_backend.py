from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator

from core.distributed.message_queue import MessageQueueBackend
from core.distributed.protocol import DistributedMessage


class RedisMessageQueue(MessageQueueBackend):
    def __init__(
        self,
        redis_url: str | None = None,
        prefix: str = "substrate:",
    ) -> None:
        self._url = redis_url or os.environ.get(
            "SUBSTRATE_REDIS_URL", "redis://localhost:6379"
        )
        self._prefix = prefix
        self._redis = None
        self._pubsub = None
        self._pending_requests: dict[str, asyncio.Future[DistributedMessage]] = {}
        self._running = False

    async def _ensure_connected(self) -> None:
        if self._redis is not None:
            return
        try:
            import redis.asyncio as aioredis

            self._redis = await aioredis.from_url(
                self._url, decode_responses=True
            )
            self._pubsub = self._redis.pubsub()
        except ImportError:
            raise RuntimeError(
                "redis-py is required for RedisMessageQueue. "
                "Install with: pip install substrate[redis]"
            )

    async def publish(self, message: DistributedMessage, channel: str = "default") -> None:
        await self._ensure_connected()
        key = f"{self._prefix}{channel}"
        data = json.dumps(message.to_dict(), default=str)
        if message.correlation_id and message.correlation_id in self._pending_requests:
            future = self._pending_requests.pop(message.correlation_id)
            future.set_result(message)
            return
        await self._redis.rpush(key, data)
        await self._redis.publish(key, data)

    async def subscribe(self, channel: str = "default") -> AsyncIterator[DistributedMessage]:
        await self._ensure_connected()
        key = f"{self._prefix}{channel}"
        await self._pubsub.subscribe(key)
        try:
            async for msg in self._pubsub.listen():
                if msg["type"] != "message":
                    continue
                try:
                    data = json.loads(msg["data"])
                    yield DistributedMessage.from_dict(data)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        finally:
            await self._pubsub.unsubscribe(key)

    async def request(
        self, message: DistributedMessage, channel: str = "default",
        timeout: float = 30.0,
    ) -> DistributedMessage | None:
        correlation_id = message.correlation_id or f"req_{id(message)}"
        message.correlation_id = correlation_id
        future: asyncio.Future[DistributedMessage] = asyncio.Future()
        self._pending_requests[correlation_id] = future
        await self._ensure_connected()
        key = f"{self._prefix}{channel}"
        data = json.dumps(message.to_dict(), default=str)
        await self._redis.rpush(key, data)
        await self._redis.publish(key, data)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError:
            self._pending_requests.pop(correlation_id, None)
            return None

    async def acknowledge(self, message: DistributedMessage) -> None:
        pass

    async def close(self) -> None:
        self._running = False
        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()
