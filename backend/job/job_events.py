# import asyncio
# import json
# import logging
# from datetime import datetime
# from enum import Enum

# from sqlalchemy import select

# from db.database import SessionLocal
# from job.job import Job


# logger = logging.getLogger(__name__)


# class JobEventHub:
#     """Fan out committed Job changes inside the single FastAPI process."""

#     def __init__(self):
#         self._subscribers: dict[asyncio.Queue[str], asyncio.AbstractEventLoop] = {}
#         self._known_payloads: dict[int, str] = {}
#         self._loop: asyncio.AbstractEventLoop | None = None
#         self._monitor_task: asyncio.Task | None = None

#     async def start(self) -> None:
#         self._loop = asyncio.get_running_loop()
#         self._monitor_task = asyncio.create_task(self._monitor_database())

#     async def stop(self) -> None:
#         if self._monitor_task is not None:
#             self._monitor_task.cancel()
#             try:
#                 await self._monitor_task
#             except asyncio.CancelledError:
#                 pass
#         self._monitor_task = None
#         self._loop = None

#     def subscribe(self) -> asyncio.Queue[str]:
#         queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
#         self._subscribers[queue] = asyncio.get_running_loop()
#         return queue

#     def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
#         self._subscribers.pop(queue, None)

#     def publish(self, job: Job) -> None:
#         payload = json.dumps(_job_payload(job), ensure_ascii=False)
#         if self._loop is not None:
#             self._loop.call_soon_threadsafe(self._broadcast, job.id, payload)

#     async def _monitor_database(self) -> None:
#         while True:
#             try:
#                 jobs = await asyncio.to_thread(self._load_recent_jobs)
#                 for job_id, payload in jobs:
#                     if self._known_payloads.get(job_id) != payload:
#                         self._broadcast(job_id, payload)
#             except asyncio.CancelledError:
#                 raise
#             except Exception:
#                 logger.exception("Failed to monitor Job changes for SSE")
#             await asyncio.sleep(0.25)

#     @staticmethod
#     def _load_recent_jobs() -> list[tuple[int, str]]:
#         with SessionLocal() as db:
#             jobs = list(db.scalars(select(Job).order_by(Job.id.desc()).limit(200)).all())
#             return [
#                 (job.id, json.dumps(_job_payload(job), ensure_ascii=False))
#                 for job in jobs
#             ]

#     def _broadcast(self, job_id: int, payload: str) -> None:
#         self._known_payloads[job_id] = payload
#         for queue in tuple(self._subscribers):
#             self._offer(queue, payload)

#     @staticmethod
#     def _offer(queue: asyncio.Queue[str], payload: str) -> None:
#         if queue.full():
#             queue.get_nowait()
#         queue.put_nowait(payload)


# def publish_job_event(job: Job) -> None:
#     job_event_hub.publish(job)


# def _job_payload(job: Job) -> dict:
#     return {
#         "job_id": job.id,
#         "status": _json_value(job.status),
#         "progress": job.progress,
#         "processed_rows": job.processed_rows,
#         "total_rows": job.total_rows,
#         "requested_at": _json_value(job.requested_at),
#         "started_at": _json_value(job.started_at),
#         "completed_at": _json_value(job.completed_at),
#         "failed_at": _json_value(job.failed_at),
#         "duration_seconds": job.duration_seconds,
#         "gcs_object_name": job.gcs_object_name,
#         "gcs_url": job.gcs_url,
#         "download_url": job.download_url,
#         "error_message": job.error_message,
#         "task_name": job.task_name,
#         "attempt_count": job.attempt_count,
#     }


# def _json_value(value):
#     if isinstance(value, Enum):
#         return value.value
#     if isinstance(value, datetime):
#         return value.isoformat()
#     return value


# job_event_hub = JobEventHub()
