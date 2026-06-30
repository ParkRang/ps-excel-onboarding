from sqlalchemy.orm import Session

from backend.common.enums.job_status import JobStatus
from backend.job.job import Job
from backend.job.job_repository import JobRepository


class JobService:

    def __init__(self):
        self.job_repository = JobRepository()

    def create_job(self, db: Session) -> Job:

        job = Job(
            status=JobStatus.PENDING,
            progress=0
        )

        return self.job_repository.save(db, job)
    
    def starting_job(self, db: Session) -> Job:
        job = Job(
            status=JobStatus.PROCESSING,
            
        )

    def get_job(self, db: Session, job_id: int) -> Job | None:
        return self.job_repository.find_by_id(db, job_id)

    def get_jobs(self, db: Session) -> list[Job]:
        return self.job_repository.find_all(db)