import asyncio
from collections import defaultdict
from typing import Any

from app.metrics import sse_subscribers


class SSEManager:
    def __init__(self) -> None:
        self._queues: dict[str, set[asyncio.Queue[str]]] = defaultdict(set)
        self._subscriber_count = 0

    def register(self, serial_number: str) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._queues[serial_number].add(queue)
        self._subscriber_count += 1
        sse_subscribers.set(self._subscriber_count)
        return queue

    def unregister(self, serial_number: str, queue: asyncio.Queue[str]) -> None:
        queues = self._queues.get(serial_number)
        if not queues:
            return
        if queue in queues:
            queues.discard(queue)
            self._subscriber_count = max(self._subscriber_count - 1, 0)
            sse_subscribers.set(self._subscriber_count)
        if not queues:
            self._queues.pop(serial_number, None)

    def broadcast(self, serial_number: str, data: str) -> None:
        for queue in self._queues.get(serial_number, set()):
            queue.put_nowait(data)
