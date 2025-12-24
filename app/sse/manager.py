import asyncio
from collections import defaultdict
from typing import Any


class SSEManager:
    def __init__(self) -> None:
        self._queues: dict[str, set[asyncio.Queue[str]]] = defaultdict(set)

    def register(self, serial_number: str) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._queues[serial_number].add(queue)
        return queue

    def unregister(self, serial_number: str, queue: asyncio.Queue[str]) -> None:
        queues = self._queues.get(serial_number)
        if not queues:
            return
        queues.discard(queue)
        if not queues:
            self._queues.pop(serial_number, None)

    def broadcast(self, serial_number: str, data: str) -> None:
        for queue in self._queues.get(serial_number, set()):
            queue.put_nowait(data)
