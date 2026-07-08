import logging
import os

from sqlalchemy import select, update

from core.logging import event_logger
from db.database import SessionLocal
from excel.excel_service import ExcelService
from job.job import Job
# from job.job_queue import JobQueue, QueueStatus
# from job.job_queue_service import JobQueueService
from job.job_service import JobService
# from services.storage_service import GCSClient


class WorkerBusyError(Exception):
    pass


class WorkerService:
    """Process the queue head, then dispatch exactly one next Cloud Task."""

    def __init__(self):
        self.jobs = JobService()
        # self.queue = JobQueueService()
        self.excel = ExcelService()
        self.storage = None

    # def process_queued_job(self, requested_job_id: int) -> int | None:
    #     db = SessionLocal()
    #     queue_item = None
    #     job = None
    #     local_file_path = None
    #     processing_completed = False

    #     try:
    #         event_logger("Worker request received", requested_job_id=requested_job_id)
    #         queue_item = db.scalar(select(JobQueue).order_by(JobQueue.job_id).limit(1))
    #         if queue_item is None:
    #             event_logger("Queue is empty", requested_job_id=requested_job_id)
    #             return None

    #         event_logger(
    #             "Queue head selected",
    #             requested_job_id=requested_job_id,
    #             queue_job_id=queue_item.job_id,
    #             queue_status=queue_item.status,
    #         )

    #         if queue_item.job_id != requested_job_id:
    #             event_logger(
    #                 "Stale task ignored",
    #                 level=logging.WARNING,
    #                 requested_job_id=requested_job_id,
    #                 queue_job_id=queue_item.job_id,
    #             )
    #             if queue_item.status == QueueStatus.WAITING:
    #                 self.queue.dispatch_head(db)
    #             return None

    #         claim_result = db.execute(
    #             update(JobQueue)
    #             .where(
    #                 JobQueue.id == queue_item.id,
    #                 JobQueue.status == QueueStatus.DISPATCHED,
    #             )
    #             .values(status=QueueStatus.PROCESSING)
    #             .execution_options(synchronize_session=False)
    #         )
    #         db.commit()
    #         if claim_result.rowcount != 1:
    #             event_logger(
    #                 "Queue item claim busy",
    #                 level=logging.WARNING,
    #                 requested_job_id=requested_job_id,
    #                 queue_job_id=queue_item.job_id,
    #             )
    #             raise WorkerBusyError("Queue head is already being processed")
    #         db.refresh(queue_item)
    #         event_logger("Queue item claimed", job_id=queue_item.job_id)

    #         job = db.get(Job, queue_item.job_id)
    #         if job is None:
    #             db.delete(queue_item)
    #             db.commit()
    #             self.queue.dispatch_head(db)
    #             return None

    #         self.jobs.start_job(db, job)
    #         event_logger("Excel generation started", job_id=job.id)
    #         local_file_path = self.excel.create_excel(db, job)
    #         event_logger("Excel file created", job_id=job.id, local_file_path=local_file_path)

    #         if self.storage is None:
    #             self.storage = GCSClient()
    #         event_logger("GCS upload started", job_id=job.id)
    #         upload = self.storage.upload(local_file_path, job.id)
    #         event_logger("GCS upload completed", job_id=job.id, object_name=upload["object_name"])

    #         # Job DONE and queue removal must succeed in the same commit.
    #         db.delete(queue_item)
    #         self.jobs.complete_job(db, job, upload)
    #         processing_completed = True
    #         event_logger("Job and queue committed", job_id=job.id)

    #         # Only after the current queue row is gone can the next Task exist.
    #         next_job_id = self.queue.dispatch_head(db)
    #         event_logger("Next queue dispatch checked", job_id=job.id, next_job_id=next_job_id)
    #         return job.id
    #     except WorkerBusyError:
    #         raise
    #     except Exception as error:
    #         event_logger(
    #             "Worker processing failed",
    #             level=logging.ERROR,
    #             requested_job_id=requested_job_id,
    #             job_id=job.id if job is not None else None,
    #             error=str(error),
    #         )
    #         db.rollback()
    #         if not processing_completed and queue_item is not None:
    #             queue_item = db.get(JobQueue, queue_item.id)
    #             if queue_item is not None:
    #                 queue_item.status = QueueStatus.DISPATCHED
    #             if job is not None:
    #                 self.jobs.fail_job(db, job, error)
    #             else:
    #                 db.commit()
    #         raise
    #     finally:
    #         if local_file_path and os.path.exists(local_file_path):
    #             os.remove(local_file_path)
    #         db.close()
