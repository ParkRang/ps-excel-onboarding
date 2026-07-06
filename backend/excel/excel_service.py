import tempfile
from math import ceil

from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from job.job import Job
from job.job_events import publish_job_event
from order.order import Order


class ExcelService:
    MAX_CHUNK_SIZE = 5000

    def create_excel(self, db: Session, job: Job) -> str:
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet("Orders")
        sheet.append(["주문번호", "주문자", "상품명", "카테고리", "금액", "상태", "주문일"])

        total_rows = db.scalar(select(func.count()).select_from(Order)) or 0
        chunk_size = max(1, min(self.MAX_CHUNK_SIZE, ceil(total_rows / 100)))
        self._save_progress(db, job, 0, total_rows)
        last_id = 0
        processed_rows = 0
        last_progress = 0

        while True:
            statement = (
                select(
                    Order.id,
                    Order.user_name,
                    Order.product_name,
                    Order.category,
                    Order.amount,
                    Order.status,
                    Order.order_date,
                )
                .where(Order.id > last_id)
                .order_by(Order.id)
                .limit(chunk_size)
            )
            orders = db.execute(statement).all()
            if not orders:
                break

            for order in orders:
                sheet.append([
                    order.id, order.user_name, order.product_name,
                    order.category, order.amount, order.status,
                    self._format_datetime(order.order_date),
                ])

            processed_rows += len(orders)
            last_id = orders[-1].id
            progress = 100 if total_rows == 0 else int(processed_rows * 100 / total_rows)
            if progress > last_progress:
                self._save_progress(db, job, processed_rows, total_rows)
                last_progress = progress

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
            file_path = temp_file.name
        workbook.save(file_path)
        return file_path

    @staticmethod
    def _save_progress(db: Session, job: Job, processed_rows: int, total_rows: int) -> None:
        job.processed_rows = processed_rows
        job.total_rows = total_rows
        job.progress = 100 if total_rows == 0 else int(processed_rows * 100 / total_rows)
        db.commit()
        db.refresh(job)
        publish_job_event(job)

    @staticmethod
    def _format_datetime(value) -> str:
        return "" if value is None else value.strftime("%Y-%m-%d %H:%M:%S")
