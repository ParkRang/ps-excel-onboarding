import os

from openpyxl import Workbook
from sqlalchemy.orm import Session

from backend.job.job import Job
from backend.order.order import Order
from backend.job.job_repository import JobRepository


class ExcelService:

    def __init__(self):
        self.job_repository = JobRepository()

    def create_excel(
        self,
        db: Session,
        job: Job,
        orders: list[Order]
    ) -> str:

        workbook = Workbook()

        sheet = workbook.active
        sheet.title = "Orders"

        # Header
        sheet.append([
            "주문번호",
            "주문자",
            "상품명",
            "카테고리",
            "금액",
            "상태",
            "주문일"
        ])

        total = len(orders)

        if total == 0:
            os.makedirs("exports", exist_ok=True)

            file_path = f"exports/job_{job.id}.xlsx"

            workbook.save(file_path)

            return file_path

        last_progress = 0

        for index, order in enumerate(orders, start=1):

            sheet.append([
                order.id,
                order.user_name,
                order.product_name,
                order.category,
                order.amount,
                order.status,
                order.order_date.strftime("%Y-%m-%d %H:%M:%S")
            ])

            progress = int(index / total * 100)

            # 같은 progress는 업데이트하지 않음
            if progress > last_progress:
                job.progress = progress
                self.job_repository.update(db, job)
                last_progress = progress

        os.makedirs("exports", exist_ok=True)

        file_path = f"exports/job_{job.id}.xlsx"

        workbook.save(file_path)

        return file_path