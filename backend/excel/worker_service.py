from datetime import datetime

from sqlalchemy.orm import Session

from common.enums.job_status import JobStatus
from job.job import Job
from job.job_repository import JobRepository
from order.order_repository import OrderRepository
from excel.excel_service import ExcelService


class WorkerService:

    def __init__(self):
        self.job_repository = JobRepository()
        self.order_repository = OrderRepository()
        self.excel_service = ExcelService()

    def process_job(self, db: Session, job_id: int):

        job = self.job_repository.find_by_id(db, job_id)

        if job is None:
            raise ValueError(f"Job({job_id})을 찾을 수 없습니다.")

        try:

            # 작업 시작
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now()
            self.job_repository.update(db, job)

            # 주문 데이터 조회
            orders = self.order_repository.find_all(db)

            # 엑셀 생성
            file_path = self.excel_service.create_excel(
                db=db,
                job=job,
                orders=orders
            )

            # 작업 완료
            job.status = JobStatus.DONE
            job.completed_at = datetime.now()
            job.file_path = file_path
            job.progress = 100

            self.job_repository.update(db, job)

        except Exception as e:

            job.status = JobStatus.FAILED
            job.completed_at = datetime.now()
            job.error_message = str(e)

            self.job_repository.update(db, job)

            raise