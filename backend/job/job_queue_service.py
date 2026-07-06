from sqlalchemy import select, text
from sqlalchemy.orm import Session

from common.enums.job_status import JobStatus
from db.database import SessionLocal
from job.job import Job
from job.job_events import publish_job_event
from job.job_queue import JobQueue, QueueStatus
from task.task_service import CloudTaskService


DISPATCH_LOCK_ID = 824_2027


class JobQueueService:
    def __init__(self):
        self.cloud_tasks = CloudTaskService()

    @staticmethod
    def add(db: Session, job_id: int) -> JobQueue:
        queue_item = JobQueue(job_id=job_id, status=QueueStatus.WAITING)
        db.add(queue_item)
        return queue_item

    def recover_and_dispatch(self) -> int | None:
        """Remove queue rows already completed before a crash, then resume the chain."""
        with SessionLocal() as db:
            completed_items = list(
                db.scalars(
                    select(JobQueue)
                    .join(Job, Job.id == JobQueue.job_id)
                    .where(Job.status == JobStatus.DONE)
                ).all()
            )
            for queue_item in completed_items:
                db.delete(queue_item)
            db.commit()
            return self.dispatch_head(db)

    def dispatch_head(self, db: Session) -> int | None:
        """Create a Cloud Task only when no queue item is already in flight."""
        try:
            db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": DISPATCH_LOCK_ID},
            )

            # A previous worker may have committed Job DONE immediately before
            # terminating. Clean those stale queue rows on every dispatch.
            completed_items = list(
                db.scalars(
                    select(JobQueue)
                    .join(Job, Job.id == JobQueue.job_id)
                    .where(Job.status == JobStatus.DONE)
                ).all()
            )
            for completed_item in completed_items:
                db.delete(completed_item)
            db.flush()

            active = db.scalar(
                select(JobQueue)
                .where(JobQueue.status.in_([QueueStatus.DISPATCHED, QueueStatus.PROCESSING]))
                .limit(1)
            )
            if active is not None:
                db.commit()
                return None

            queue_item = db.scalar(
                select(JobQueue)
                .where(JobQueue.status == QueueStatus.WAITING)
                .order_by(JobQueue.job_id)
                .limit(1)
                .with_for_update()
            )
            if queue_item is None:
                db.commit()
                return None

            task_name = self.cloud_tasks.enqueue(queue_item.job_id)
            queue_item.status = QueueStatus.DISPATCHED
            job = db.get(Job, queue_item.job_id)
            if job is not None:
                job.task_name = task_name

            db.commit()
            if job is not None:
                db.refresh(job)
                publish_job_event(job)
            return queue_item.job_id
        except Exception:
            db.rollback()
            raise
