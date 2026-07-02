from sqlalchemy import select, func, update
from sqlalchemy.orm import Session

from job.job import Job
from common.enums.job_status import JobStatus
from common.utils.now import now


class JobRepository:
    def save(self, db: Session, job: Job) -> Job:
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def find_by_id(self, db: Session, job_id: int) -> Job | None:
        return db.get(Job, job_id)

    def find_all(self, db: Session) -> list[Job]:
        stmt = (
            select(Job)
            .order_by(Job.id.desc())
        )

        return list(
            db.execute(stmt).scalars().all()
        )

    def find_page(self, db: Session, page: int, size: int) -> tuple[list[Job], int]:
        total = db.scalar(select(func.count()).select_from(Job)) or 0

        stmt = (
            select(Job)
            .order_by(Job.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )

        return list(db.scalars(stmt)), total

    def set_task_name(self, db: Session, job: Job, task_name: str) -> Job:
        job.task_name = task_name
        db.commit()
        db.refresh(job)
        return job

    def mark_enqueue_failed(self, db: Session, job: Job, message: str) -> None:
        job.status = JobStatus.FAILED
        job.completed_at = now
        job.error_message = message
        db.commit()

    def claim_for_processing(
        self,
        db: Session,
        job_id: int,
        allow_processing_retry: bool = False,
    ) -> Job | None:
        claimable = [JobStatus.PENDING, JobStatus.FAILED]

        if allow_processing_retry:
            claimable.append(JobStatus.PROCESSING)

        stmt = (
            update(Job)
            .where(Job.id == job_id, Job.status.in_(claimable))
            .values(
                status=JobStatus.PROCESSING,
                started_at=now,
                completed_at=None,
                error_message=None,
                progress=0,
                processed_rows=0,
                attempt_count=Job.attempt_count + 1,
            )
        )

        result = db.execute(stmt)
        db.commit()

        if result.rowcount != 1:
            return None

        return db.get(Job, job_id)

    def update_progress(
        self,
        db: Session,
        job_id: int,
        processed_rows: int,
        total_rows: int,
    ) -> None:
        progress = 100 if total_rows == 0 else min(
            99,
            int(processed_rows * 100 / total_rows),
        )

        db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == JobStatus.PROCESSING)
            .values(
                progress=progress,
                processed_rows=processed_rows,
                total_rows=total_rows,
            )
        )

        db.commit()

    def mark_done(
        self,
        db: Session,
        job_id: int,
        object_name: str,
        total_rows: int,
    ) -> Job:
        db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == JobStatus.PROCESSING)
            .values(
                status=JobStatus.DONE,
                progress=100,
                processed_rows=total_rows,
                total_rows=total_rows,
                completed_at=now,
                gcs_object_name=object_name,
                error_message=None,
            )
        )

        db.commit()

        return db.get(Job, job_id)

    def mark_failed(self, db: Session, job_id: int, message: str) -> None:
        db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=JobStatus.FAILED,
                completed_at=now,
                error_message=message[:4000],
            )
        )

        db.commit()