import os

from sqlalchemy import select, text

from db.database import SessionLocal
from excel.excel_service import ExcelService
from job.job import Job
from job.job_queue import JobQueue, QueueStatus
from job.job_queue_service import JobQueueService
from job.job_service import JobService
from services.storage_service import GCSClient


WORKER_LOCK_ID = 824_2026


class WorkerBusyError(Exception):
    pass


class WorkerService:
    """Process the queue head, then dispatch exactly one next Cloud Task."""

    def __init__(self):
        self.jobs = JobService()
        self.queue = JobQueueService()
        self.excel = ExcelService()
        self.storage = None

    def process_queued_job(self, requested_job_id: int) -> int | None:
        db = SessionLocal()
        queue_item = None
        job = None
        local_file_path = None
        lock_acquired = False
        processing_completed = False

        try:
            lock_acquired = bool(
                db.scalar(text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": WORKER_LOCK_ID})
            )
            if not lock_acquired:
                raise WorkerBusyError("Another Excel worker is already running")

            queue_item = db.scalar(select(JobQueue).order_by(JobQueue.job_id).limit(1))
            if queue_item is None:
                return None

            if queue_item.job_id != requested_job_id:
                if queue_item.status == QueueStatus.WAITING:
                    self.queue.dispatch_head(db)
                return None

            queue_item.status = QueueStatus.PROCESSING
            db.commit()

            job = db.get(Job, queue_item.job_id)
            if job is None:
                db.delete(queue_item)
                db.commit()
                self.queue.dispatch_head(db)
                return None

            self.jobs.start_job(db, job)
            local_file_path = self.excel.create_excel(db, job)
            if self.storage is None:
                self.storage = GCSClient()
            upload = self.storage.upload(local_file_path, job.id)
            # Job DONE and queue removal must succeed in the same commit.
            db.delete(queue_item)
            self.jobs.complete_job(db, job, upload)
            processing_completed = True

            # Only after the current queue row is gone can the next Task exist.
            self.queue.dispatch_head(db)
            return job.id
        except WorkerBusyError:
            raise
        except Exception as error:
            db.rollback()
            if not processing_completed and queue_item is not None:
                queue_item = db.get(JobQueue, queue_item.id)
                if queue_item is not None:
                    queue_item.status = QueueStatus.DISPATCHED
                if job is not None:
                    self.jobs.fail_job(db, job, error)
                else:
                    db.commit()
            raise
        finally:
            if local_file_path and os.path.exists(local_file_path):
                os.remove(local_file_path)
            if lock_acquired:
                try:
                    db.execute(
                        text("SELECT pg_advisory_unlock(:lock_id)"),
                        {"lock_id": WORKER_LOCK_ID},
                    )
                    db.commit()
                except Exception:
                    db.rollback()
            db.close()
