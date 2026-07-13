from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from job.job_events import publish_job_event

from common.enums.job_status import JobStatus
from common.utils.now import now
from core.logging import complete_logger, fail_logger, start_logger
from job.job import Job
from webhook.webhook_service import WebhookService

class JobService:
    """Job persistence and state transitions in one place."""

    def __init__(self):
        self.webhook = WebhookService()

    def create_export(self, db: Session, user_id: int) -> Job:
        job = Job(status=JobStatus.PENDING, progress=0, user_id=user_id)
        try:
            db.add(job)
            db.flush()
            db.commit()
            db.refresh(job)

            publish_job_event(job)
            return job
        except Exception:
            db.rollback()
            raise

    def get_job(self, db: Session, job_id: int, user_id: int) -> Job | None:
        # 소유자 본인의 job만 반환(다른 사용자 job은 없는 것처럼 취급).
        job = db.get(Job, job_id)
        if job is None or job.user_id != user_id:
            return None
        return job

    def get_jobs(self, db: Session, user_id: int) -> list[Job]:
        return list(
            db.scalars(
                select(Job).where(Job.user_id == user_id).order_by(Job.id.desc())
            ).all()
        )

    def get_jobs_page(self, db: Session, page: int, size: int, user_id: int) -> dict:
        owned = Job.user_id == user_id
        total = db.scalar(select(func.count()).select_from(Job).where(owned)) or 0
        status_counts = dict(
            db.execute(
                select(Job.status, func.count()).where(owned).group_by(Job.status)
            ).all()
        )
        statement = (
            select(Job)
            .where(owned)
            .order_by(Job.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        return {
            "items": list(db.scalars(statement).all()),
            "total": total,
            "active": (
                status_counts.get(JobStatus.PENDING, 0)
                + status_counts.get(JobStatus.PROCESSING, 0)
            ),
            "done": status_counts.get(JobStatus.DONE, 0),
            "failed": status_counts.get(JobStatus.FAILED, 0),
            "page": page,
            "size": size,
            "pages": ceil(total / size) if total else 1,
        }

    def start_job(self, db: Session, job: Job) -> Job:
        job.status = JobStatus.PROCESSING
        job.started_at = now()
        job.attempt_count += 1
        job.progress = 0
        job.error_message = None

        saved_job = self._save(db, job)
        publish_job_event(saved_job)

        start_logger(job_id=job.id, started_at=job.started_at)
        return self._save(db, job)

    def complete_job(self, db: Session, job: Job) -> Job:
        job.status = JobStatus.DONE
        job.progress = 100
        job.completed_at = now()
        if job.started_at:
            job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
        # job.gcs_object_name = upload["object_name"]
        # job.gcs_url = upload["gcs_url"]

        saved_job = self._save(db, job)
        publish_job_event(saved_job)

        complete_logger(job_id=job.id, completed_at=job.completed_at,
                        duration_seconds=job.duration_seconds)
        self.webhook.send_success_message(job.id, job.completed_at, job.download_url)
        return saved_job

    def fail_job(self, db: Session, job: Job, error: Exception) -> Job:
        job.status = JobStatus.FAILED
        job.failed_at = now()
        job.error_message = str(error)[:4000]
        saved_job = self._save(db, job)
        publish_job_event(saved_job)
        
        fail_logger(job_id=job.id, failed_at=job.failed_at, error_message=job.error_message)
        self.webhook.send_failure_message(job.id, job.error_message)
        return saved_job

    @staticmethod
    def _save(db: Session, job: Job) -> Job:
        db.add(job)
        db.flush()
        db.commit()
        db.refresh(job)
        return job

# job_service = JobService()
