from datetime import datetime

from sqlalchemy.orm import Session

from backend.enums.job_status import JobStatus
from backend.repositories.job_repository import JobRepository
from backend.services.excel_service import ExcelService


class WorkerService:

    def __init__(self):
        self.job_repository = JobRepository()
        self.excel_service = ExcelService()

    def process_job(self, db: Session, job_id: int):

        job = self.job_repository.find_by_id(db, job_id)

        if job is None:
            return

        try:
            # 작업 시작
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now()

            self.job_repository.update(db, job)

            # 엑셀 생성
            file_path = self.excel_service.create_excel(
                db=db,
                job=job
            )

            # 완료
            job.progress = 100
            job.status = JobStatus.DONE
            job.completed_at = datetime.now()
            job.file_path = file_path

            self.job_repository.update(db, job)

        except Exception as e:

            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()

            self.job_repository.update(db, job)