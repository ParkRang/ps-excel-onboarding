import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
from itertools import count
from typing import Any

from job.job import Job


logger = logging.getLogger(__name__)


class JobEventHub:
    """
    단일 FastAPI 프로세스 안에서 Job 이벤트를 구독자에게 전달한다.

    DB를 조회하거나 주기적으로 상태를 확인하지 않는다.
    worker가 publish()를 호출했을 때만 이벤트가 발생한다.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._event_sequence = count(1)

    async def start(self) -> None:
        """
        FastAPI가 실행되는 메인 asyncio event loop를 저장한다.

        Excel 작업은 worker thread에서 실행되므로 publish()가 다른
        thread에서 호출될 수 있다. 저장한 loop를 통해 안전하게 이벤트를
        메인 loop로 전달한다.
        """
        self._loop = asyncio.get_running_loop()
        logger.info("Job SSE event hub started")

    async def stop(self) -> None:
        """
        서버 종료 시 연결된 subscriber를 정리한다.
        """
        self._loop = None
        self._subscribers.clear()
        logger.info("Job SSE event hub stopped")

    def subscribe(self) -> asyncio.Queue[str]:
        """
        SSE 클라이언트 하나당 전용 Queue를 생성한다.

        이 함수는 /jobs/events를 처리하는 메인 event loop에서 호출된다.
        """
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)

        logger.info(
            "SSE subscriber connected. subscribers=%s",
            len(self._subscribers),
        )
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        """
        브라우저 연결이 끊기면 해당 클라이언트의 Queue를 제거한다.
        """
        self._subscribers.discard(queue)

        logger.info(
            "SSE subscriber disconnected. subscribers=%s",
            len(self._subscribers),
        )

    def publish(self, job: Job) -> None:
        """
        Job의 현재 상태를 이벤트로 발행한다.

        이 메서드는 메인 event loop 또는 Excel worker thread에서
        호출될 수 있다. ORM 객체는 호출 thread에서 즉시 JSON 문자열로
        변환하고, 문자열만 메인 loop로 전달한다.
        """
        payload = json.dumps(
            job_to_payload(job),
            ensure_ascii=False,
            separators=(",", ":"),
        )

        loop = self._loop
        if loop is None or loop.is_closed():
            logger.warning(
                "SSE event hub is not running. job_id=%s",
                job.id,
            )
            return

        loop.call_soon_threadsafe(self._broadcast, payload)

    def _broadcast(self, payload: str) -> None:
        """
        메인 event loop에서 모든 subscriber Queue에 이벤트를 삽입한다.
        """
        event_id = next(self._event_sequence)
        message = encode_sse(
            event="job",
            event_id=str(event_id),
            data=payload,
        )

        for queue in tuple(self._subscribers):
            self._offer(queue, message)

    @staticmethod
    def _offer(queue: asyncio.Queue[str], message: str) -> None:
        """
        느린 클라이언트 때문에 worker가 멈추지 않도록 non-blocking으로 넣는다.

        Queue가 가득 찼다면 가장 오래된 이벤트를 제거한다.
        브라우저는 재연결 또는 상태 전환 시 REST API로 최신 상태를
        동기화하므로 오래된 진행률 이벤트를 보존할 필요가 없다.
        """
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("Could not enqueue SSE event for slow subscriber")


def encode_sse(
    *,
    event: str,
    data: str,
    event_id: str | None = None,
    retry: int | None = None,
) -> str:
    """
    SSE 표준 형식으로 메시지를 만든다.

    각 이벤트는 반드시 빈 줄, 즉 \\n\\n으로 끝나야 한다.
    """
    lines: list[str] = []

    if event_id is not None:
        lines.append(f"id: {event_id}")

    if event:
        lines.append(f"event: {event}")

    if retry is not None:
        lines.append(f"retry: {retry}")

    for line in data.splitlines() or [""]:
        lines.append(f"data: {line}")

    return "\n".join(lines) + "\n\n"


def job_to_payload(job: Job) -> dict[str, Any]:
    """
    프론트엔드 JobResponse와 동일한 이름으로 payload를 만든다.

    종료된 GCS 필드는 포함하지 않는다.
    """
    return {
        "job_id": job.id,
        "status": json_value(job.status),
        "progress": job.progress,
        "processed_rows": job.processed_rows,
        "total_rows": job.total_rows,
        "requested_at": json_value(job.requested_at),
        "started_at": json_value(job.started_at),
        "completed_at": json_value(job.completed_at),
        "failed_at": json_value(job.failed_at),
        "duration_seconds": job.duration_seconds,
        "download_url": job.download_url,
        "error_message": job.error_message,
        "task_name": job.task_name,
        "attempt_count": job.attempt_count,
    }


def json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value

    if isinstance(value, datetime):
        return value.isoformat()

    return value


def publish_job_event(job: Job) -> None:
    job_event_hub.publish(job)


job_event_hub = JobEventHub()