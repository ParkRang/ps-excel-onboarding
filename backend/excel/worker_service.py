import logging
import os
from time import perf_counter

from sqlalchemy.orm import Session

from db.session import SessionLocal
from job.job_service import JobService
# from order.order_repository import OrderRepository
from excel.excel_service import ExcelService
from services.storage_service import GCSClient

logger = logging.getLogger(__name__)


class WorkerService:

    def __init__(self):
        self.job_service = JobService()
        # self.order_repository = OrderRepository()
        self.excel_service = ExcelService()
        self.storage_service = GCSClient()

    def process_job(self, job_id: int):
        db = SessionLocal()

        try:
            job = self.job_service.get_job(db, job_id)

            self.job_service.start_job(db, job)
            
            local_file_path = self.excel_service.create_excel(
                db=db,
                job=job,
            )
            # gcs_object_name = self.storage_service.upload(
            #     local_file_path=local_file_path,
            #     job_id=job.id,
            # )

            upload_result = self.storage_service.upload(
                local_file_path=local_file_path,
                job_id=job.id,
            )

            self.job_service.complete_job(
                db=db,
                job=job,
                gcs_object_name=upload_result["object_name"],
                gcs_url=upload_result["gcs_url"],
                download_url=upload_result["download_url"]
            )

        except Exception as error:
            db.rollback()

            if "job" in locals() and job is not None:
                self.job_service.fail_job(
                    db=db,
                    job=job,
                    error=error,
                )

            raise

        finally:
            db.close()