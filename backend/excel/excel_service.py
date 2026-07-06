import tempfile, asyncio

from openpyxl import Workbook
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from job.job import Job
from order.order import Order
from job.job_repository import JobRepository
# from core.sse_manager import sse_manager
from services.storage_service import GCSClient


from db.database import SessionLocal

class ExcelService:

    # background_tasks: BackgroundTasks
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

        # workbook.save(temp_file_path)

        return temp_file_path

    def _format_datetime(self, value) -> str:
        if value is None:
            return ""

        return value.strftime("%Y-%m-%d %H:%M:%S")
    

    # 비동기

    # async def create_excel_async(self, job_id: int) -> str:
    #     workbook = Workbook(write_only=True)
    #     sheet = workbook.create_sheet("Orders")

    #     sheet.append([
    #         "주문번호",
    #         "주문자",
    #         "상품명",
    #         "카테고리",
    #         "금액",
    #         "상태",
    #         "주문일",
    #     ])

    #     with SessionLocal() as db:
    #         total_rows = db.query(Order).count()

    #         job = db.get(Job, job_id)
    #         job.total_rows = total_rows
    #         job.processed_rows = 0
    #         job.progress = 0
    #         db.commit()

    #     last_id = 0
    #     processed_rows = 0
    #     last_progress = 0
    #     chunk_size = 1000

    #     while True:
    #         orders = await asyncio.to_thread(
    #             self._load_order_chunk,
    #             last_id,
    #             chunk_size,
    #         )

    #         if not orders:
    #             break

    #         await asyncio.to_thread(
    #             self._append_orders,
    #             sheet,
    #             orders,
    #         )

    #         processed_rows += len(orders)
    #         last_id = orders[-1]["id"]

    #         progress = (
    #             int(processed_rows / total_rows * 100)
    #             if total_rows > 0
    #             else 100
    #         )

    #         if progress > last_progress:
    #             await asyncio.to_thread(
    #                 self._save_progress,
    #                 job_id,
    #                 processed_rows,
    #                 progress,
    #             )
    #             last_progress = progress

    #         # FastAPI 이벤트 루프에 다른 요청을 처리할 기회를 줌
    #         await asyncio.sleep(0)

    #     file_path = tempfile.mktemp(suffix=".xlsx")

    #     # workbook.save()도 오래 걸리는 동기 작업
    #     await asyncio.to_thread(
    #         workbook.save,
    #         file_path,
    #     )

    #     await asyncio.to_thread(
    #         self._save_progress,
    #         job_id,
    #         processed_rows,
    #         100,
    #     )

    #     return file_path
    
    # def _load_order_chunk(
    #     self,
    #     last_id: int,
    #     chunk_size: int,
    # ) -> list[dict]:
    #     with SessionLocal() as db:
    #         orders = (
    #             db.query(Order)
    #             .filter(Order.id > last_id)
    #             .order_by(Order.id)
    #             .limit(chunk_size)
    #             .all()
    #         )

    #         return [
    #             {
    #                 "id": order.id,
    #                 "user_name": order.user_name,
    #                 "product_name": order.product_name,
    #                 "category": order.category,
    #                 "amount": order.amount,
    #                 "status": order.status,
    #                 "order_date": order.order_date,
    #             }
    #             for order in orders
    #         ]
        
    # def _append_orders(
    #     self,
    #     sheet,
    #     orders: list[dict],
    # ) -> None:
    #     for order in orders:
    #         sheet.append([
    #             order["id"],
    #             order["user_name"],
    #             order["product_name"],
    #             order["category"],
    #             order["amount"],
    #             order["status"],
    #             self._format_datetime(order["order_date"]),
    #         ])

    # def _save_progress(
    #     self,
    #     job_id: int,
    #     processed_rows: int,
    #     progress: int,
    # ) -> None:
    #     with SessionLocal() as db:
    #         job = db.get(Job, job_id)

    #         if job is None:
    #             return

    #         job.processed_rows = processed_rows
    #         job.progress = progress
    #         db.commit()