import json
from typing import Awaitable, Callable

import redis.asyncio as aioredis

from .constants import CHAT_EVENTS_CHANNEL
from .events import ChatEvent


class EventBus:
    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None

    async def connect(self) -> None:
        self._redis = aioredis.from_url(self.redis_url, decode_responses=True)

    async def close(self) -> None:
        if self._pubsub is not None:
            await self._pubsub.unsubscribe(CHAT_EVENTS_CHANNEL)
            await self._pubsub.close()
            self._pubsub = None
        if self._redis is not None:
            await self._redis.close()
            self._redis = None

    async def publish(self, event: ChatEvent) -> None:
        if self._redis is None:
            await self.connect()
        assert self._redis is not None
        await self._redis.publish(CHAT_EVENTS_CHANNEL, event.model_dump_json())

    async def subscribe(
        self,
        handler: Callable[[ChatEvent], Awaitable[None]],
    ) -> None:
        if self._redis is None:
            await self.connect()
        assert self._redis is not None
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(CHAT_EVENTS_CHANNEL)
        assert self._pubsub is not None
        async for message in self._pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if not data:
                continue
            try:
                event = ChatEvent.model_validate(json.loads(data))
            except Exception:
                continue
            await handler(event)
