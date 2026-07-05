import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class SSEConnection:
    queue: asyncio.Queue
    loop: asyncio.AbstractEventLoop


class SSEManager:
    def __init__(self):
        self.connections: dict[int, list[SSEConnection]] = defaultdict(list)

    def connect(
        self,
        job_id: int,
        queue: asyncio.Queue,
        loop: asyncio.AbstractEventLoop,
    ) -> SSEConnection:
        connection = SSEConnection(
            queue=queue,
            loop=loop,
        )
        self.connections[job_id].append(connection)
        return connection

    def disconnect(
        self,
        job_id: int,
        connection: SSEConnection,
    ) -> None:
        connections = self.connections.get(job_id)

        if not connections:
            return

        if connection in connections:
            connections.remove(connection)

        if not connections:
            del self.connections[job_id]

    def send(self, job_id: int, data: dict) -> None:
        message = {
            "event": "job-progress",
            "data": json.dumps(data, ensure_ascii=False),
        }

        for connection in list(self.connections.get(job_id, [])):
            connection.loop.call_soon_threadsafe(
                connection.queue.put_nowait,
                message,
            )


sse_manager = SSEManager()