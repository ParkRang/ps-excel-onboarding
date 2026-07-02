import os
import tempfile

from openpyxl import Workbook
from sqlalchemy.orm import Session

from job.job import Job
from order.order import Order
from job.job_repository import JobRepository
from services.storage_service import GCSClient

class ExcelService:

    def __init__(self):
        self.job_repository = JobRepository()
        self.gcs_client = GCSClient()

    def create_excel(
        self,
        db: Session,
        job: Job,
        orders: list[Order],
    ) -> str:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Orders"

        sheet.append([
            "주문번호",
            "주문자",
            "상품명",
            "카테고리",
            "금액",
            "상태",
            "주문일",
        ])

        total = len(orders)
        last_progress = 0

        job.total_rows = total
        job.processed_rows = 0
        job.progress = 0
        self.job_repository.save(db, job)

        # raise Exception("Webhook 테스트용 강제 실패")

        for index, order in enumerate(orders, start=1):
            sheet.append([
                order.id,
                order.user_name,
                order.product_name,
                order.category,
                order.amount,
                order.status,
                order.order_date.strftime("%Y-%m-%d %H:%M:%S"),
            ])

            progress = int(index / total * 100) if total > 0 else 100

            if progress > last_progress:
                job.processed_rows = index
                job.progress = progress
                self.job_repository.save(db, job)
                last_progress = progress

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
            temp_file_path = temp_file.name

        workbook.save(temp_file_path)

        return temp_file_path