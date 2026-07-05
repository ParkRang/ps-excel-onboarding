from sqlalchemy.orm import Session

from common.enums.job_status import JobStatus
from common.utils.now import now
from job.job import Job
from job.job_repository import JobRepository
from job.job_response import JobResponse
from task.task_service import CloudTaskService
from webhook.webhook_service import WebhookService
from core.logging import start_logger
from core.logging import complete_logger
from core.logging import fail_logger


class JobService:

    def __init__(self):
        self.job_repository = JobRepository()
        self.cloud_task_service = CloudTaskService()
        self.webhook_service = WebhookService()

    def create_export(self, db: Session) -> Job:
        """
        Job을 생성하고 Cloud Tasks에 작업을 등록합니다.
        """
        job = Job(
            status=JobStatus.PENDING,
            progress=0,
        )

        job = self.job_repository.save(db, job)

        task_name = self.cloud_task_service.enqueue(job.id)
        job.task_name = task_name

        return job

    def get_job(
        self,
        db: Session,
        job_id: int,
    ) -> Job | None:
        return self.job_repository.find_by_id(db, job_id)

    # def get_jobs(
    #     self,
    #     db: Session,
    # ) -> list[Job]:
    #     return self.job_repository.find_all(db)

    def get_jobs(
        self,
        db: Session,
    ) -> list[JobResponse]:

        jobs = self.job_repository.find_all(db)

        return [
            JobResponse(
                job_id=job.id,
                status=job.status,
                progress=job.progress,
                processed_rows=job.processed_rows,
                total_rows=job.total_rows,
                requested_at=job.requested_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                failed_at=job.failed_at,
                duration_seconds=job.duration_seconds,
                gcs_object_name=job.gcs_object_name,
                gcs_url=job.gcs_url,
                download_url=job.download_url,
                error_message=job.error_message,
                task_name=job.task_name,
                attempt_count=job.attempt_count,
            )
            for job in jobs
        ]

    def start_job(
        self,
        db: Session,
        job: Job,
    ) -> Job:
        job.status = JobStatus.PROCESSING
        job.started_at = now()
        job.attempt_count += 1
        job.progress = 0
        job.error_message = None

        start_logger(job_id=job.id, started_at=job.started_at)

        return self.job_repository.save(db, job)

    def update_progress(
        self,
        db: Session,
        job: Job,
        progress: int,
    ) -> Job:
        job.progress = min(progress, 99)

        return self.job_repository.save(db, job)

    def complete_job(
        self,
        db: Session,
        job: Job,
        gcs_object_name: str,
        gcs_url: str,
        download_url: str,
    ) -> Job:
        job.status = JobStatus.DONE
        job.progress = 100
        job.completed_at = now()
        if job.started_at:
            job.duration_seconds = (
            job.completed_at - job.started_at
        ).total_seconds()
        job.gcs_object_name = gcs_object_name
        job.gcs_url = gcs_url
        job.download_url = download_url
        
        complete_logger(
            job_id=job.id,
            completed_at=job.completed_at,
            duration_seconds=job.duration_seconds,
            gcs_url=job.gcs_url,
            
        )

        WebhookService.send_success_message(
            self.webhook_service,
            job_id=job.id,
            completed_at=job.completed_at,
            download_url=job.download_url,
        )

        return self.job_repository.save(db, job)

    def fail_job(
        self,
        db: Session,
        job: Job,
        error: Exception,
    ) -> Job:
        job.status = JobStatus.FAILED
        job.failed_at = now()
        job.error_message = str(error)

        fail_logger(
            job_id=job.id,
            failed_at=job.failed_at,
            error_message=job.error_message,
        )

        WebhookService.send_failure_message(
            self.webhook_service,
            job_id=job.id,
            error_message=job.error_message,
        )

        return self.job_repository.save(db, job)