import tempfile

from openpyxl import Workbook
from sqlalchemy.orm import Session

from job.job import Job
from order.order import Order
from job.job_repository import JobRepository
# from core.sse_manager import sse_manager
from services.storage_service import GCSClient

class ExcelService:

    def __init__(self):
        self.job_repository = JobRepository()
        # self.sse_manager = sse_manager
        self.gcs_client = GCSClient()

    def create_excel(
        self,
        db: Session,
        job: Job,
    ) -> str:
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet("Orders")

        sheet.append([
            "주문번호",
            "주문자",
            "상품명",
            "카테고리",
            "금액",
            "상태",
            "주문일",
        ])

        total_rows = db.query(Order).count()

        job.total_rows = total_rows
        job.processed_rows = 0
        job.progress = 0
        self.job_repository.save(db, job)

        last_id = 0
        chunk_size = 1000
        processed_rows = 0
        last_progress = 0

        while True:
            orders = (
                db.query(Order)
                .filter(Order.id > last_id)
                .order_by(Order.id)
                .limit(chunk_size)
                .all()
            )

            if not orders:
                break

            for order in orders:
                sheet.append([
                    order.id,
                    order.user_name,
                    order.product_name,
                    order.category,
                    order.amount,
                    order.status,
                    self._format_datetime(order.order_date),
                ])

            processed_rows += len(orders)
            last_id = orders[-1].id

            progress = (
                int(processed_rows / total_rows * 100)
                if total_rows > 0
                else 100
            )

            if progress > last_progress:
                job.processed_rows = processed_rows
                job.progress = progress
                self.job_repository.save(db, job)

                # sse_manager.send(job.id, {
                #     "job_id": job.id,
                #     "status": (
                #         job.status.value
                #         if hasattr(job.status, "value")
                #         else str(job.status)
                #     ),
                #     "progress": progress,
                #     "processed_rows": processed_rows,
                #     "total_rows": total_rows,
                # })

                last_progress = progress

        job.processed_rows = processed_rows
        job.progress = 100
        self.job_repository.save(db, job)



        return self._save_workbook(workbook)

    def _save_workbook(self, workbook: Workbook) -> str:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
            temp_file_path = temp_file.name

        workbook.save(temp_file_path)

        return temp_file_path

    def _format_datetime(self, value) -> str:
        if value is None:
            return ""

        return value.strftime("%Y-%m-%d %H:%M:%S")