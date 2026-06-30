from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.job import Job
from backend.enums.job_status import JobStatus


class JobRepository:

    def save(self, db: Session, job: Job) -> Job:
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def find_by_id(self, db: Session, job_id: int) -> Job | None:
        stmt = select(Job).where(Job.id == job_id)
        return db.execute(stmt).scalar_one_or_none()

    def find_all(self, db: Session) -> list[Job]:
        stmt = select(Job).order_by(Job.id.desc())
        return list(db.execute(stmt).scalars().all())

    def update(self, db: Session, job: Job) -> Job:
        db.commit()
        db.refresh(job)
        return job

    def delete(self, db: Session, job: Job):
        db.delete(job)
        db.commit()