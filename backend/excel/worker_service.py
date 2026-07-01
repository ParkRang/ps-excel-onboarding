import logging
import os
from time import perf_counter

from sqlalchemy.orm import Session

from common.enums.job_status import JobStatus
from excel.excel_service import ExcelService
from job.job_service import JobService
from order.order_repository import OrderRepository
from services.storage_service import StorageService


logger = logging.getLogger(__name__)


class WorkerService:

    def __init__(self):
        self.job_service = JobService()
        self.order_repository = OrderRepository()
        self.excel_service = ExcelService()
        self.storage_service = StorageService()

    def process_job(
        self,
        db: Session,
        job_id: int,
    ):
        job = self.job_service.get_job(
            db=db,
            job_id=job_id,
        )

        if job is None:
            raise ValueError(
                f"Job({job_id})을 찾을 수 없습니다."
            )

        # 완료된 Job은 다시 처리하지 않음
        if job.status == JobStatus.DONE:
            return

        started_time = perf_counter()
        local_file_path = None

        try:
            # 1. 작업 시작
            self.job_service.start_job(
                db=db,
                job=job,
            )

            logger.info(
                "excel_processing_started",
                extra={
                    "job_id": job.id,
                    "started_at": job.started_at,
                },
            )

            # 2. 전체 주문 개수 조회
            total_count = (
                self.order_repository.count(db)
            )

            # 3. Excel 생성
            local_file_path = (
                self.excel_service.create_excel(
                    db=db,
                    job=job,
                    total_count=total_count,
                )
            )

            # 4. GCS 업로드
            gcs_file_path = (
                self.storage_service.upload(
                    local_file_path=local_file_path,
                    job_id=job.id,
                )
            )

            # 5. 작업 완료
            self.job_service.complete_job(
                db=db,
                job=job,
                file_path=gcs_file_path,
            )

            elapsed_seconds = round(
                perf_counter() - started_time,
                2,
            )

            logger.info(
                "excel_processing_completed",
                extra={
                    "job_id": job.id,
                    "completed_at": job.completed_at,
                    "elapsed_seconds": elapsed_seconds,
                    "gcs_file_path": gcs_file_path,
                },
            )

        except Exception as error:
            db.rollback()

            self.job_service.fail_job(
                db=db,
                job=job,
                error=error,
            )

            logger.exception(
                "excel_processing_failed",
                extra={
                    "job_id": job.id,
                    "error_message": str(error),
                },
            )

            # Cloud Tasks 재시도를 위해 예외 전달
            raise

        finally:
            # GCS 업로드 후 임시 파일 삭제
            if (
                local_file_path
                and os.path.exists(local_file_path)
            ):
                os.remove(local_file_path)