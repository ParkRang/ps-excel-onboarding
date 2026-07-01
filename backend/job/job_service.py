from sqlalchemy.orm import Session

from common.enums.job_status import JobStatus
from common.utils.now import now
from job.job import Job
from job.job_repository import JobRepository
from services.cloud_task_service import CloudTaskService


class JobService:

    def __init__(self):
        self.job_repository = JobRepository()
        self.cloud_task_service = CloudTaskService()

    def create_export(self, db: Session) -> Job:
        """
        Job을 생성하고 Cloud Tasks에 작업을 등록합니다.
        """
        job = Job(
            status=JobStatus.PENDING,
            progress=0,
        )

        job = self.job_repository.save(db, job)

        try:
            self.cloud_task_service.enqueue(job.id)

        except Exception as error:
            job.status = JobStatus.FAILED
            job.completed_at = now()
            job.error_message = f"Cloud Tasks 등록 실패: {error}"

            self.job_repository.update(db, job)

            raise

        return job

    def get_job(
        self,
        db: Session,
        job_id: int,
    ) -> Job | None:
        return self.job_repository.find_by_id(db, job_id)

    def get_jobs(
        self,
        db: Session,
    ) -> list[Job]:
        return self.job_repository.find_all(db)

    def start_job(
        self,
        db: Session,
        job: Job,
    ) -> Job:
        job.status = JobStatus.PROCESSING
        job.started_at = now()
        job.progress = 0
        job.error_message = None

        return self.job_repository.update(db, job)

    def update_progress(
        self,
        db: Session,
        job: Job,
        progress: int,
    ) -> Job:
        job.progress = min(progress, 99)

        return self.job_repository.update(db, job)

    def complete_job(
        self,
        db: Session,
        job: Job,
        file_path: str,
    ) -> Job:
        job.status = JobStatus.DONE
        job.progress = 100
        job.completed_at = now()
        job.file_path = file_path
        job.error_message = None

        return self.job_repository.update(db, job)

    def fail_job(
        self,
        db: Session,
        job: Job,
        error: Exception,
    ) -> Job:
        job.status = JobStatus.FAILED
        job.completed_at = now()
        job.error_message = str(error)

        return self.job_repository.update(db, job)