import tempfile, asyncio, logging
from math import ceil
from fastapi import BackgroundTasks
from itertools import count
from typing import Any
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from job.job import Job
from common.enums.job_status import JobStatus
# from job.job_events import publish_job_event
from core.logging import event_logger
from order.order import Order
from db.database import SessionLocal

logger = logging.getLogger(__name__)

job_queue:asyncio.PriorityQueue = asyncio.PriorityQueue()
queued_job_ids: set[int] = set()
queue_lock = asyncio.Lock()
sequence = count()

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
        last_logged_progress = 0

        event_logger(
            f"job_id={job.id}, 엑셀 생성 작업이 시작되었습니다.",
        )

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
                if progress >= last_logged_progress + 10 or progress == 100:
                    event_logger(
                        f"{job.id}번 파일 생성이 진행중입니다. {progress}"
                    )
                    last_logged_progress = progress

        # with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
        #     file_path = temp_file.name
        # workbook.save(file_path)

        output_dir = Path("files")
        output_dir.mkdir(parents=True, exist_ok=True)

        file_path = output_dir / f"{job.id}.xlsx"
        workbook.save(file_path)


        event_logger(f"{job.id}엑셀 파일이 생성되었습니다, {file_path}")
        return str(file_path)

    async def enqueue_job(self, job: Job) -> None:
        print("enqueue 실행")
        job_id = job.id

        async with queue_lock:
            if job_id in queued_job_ids:
                logger.info("엑셀 작업이 이미 큐에 있습니다. job_id=%s", job_id)
                return

            queued_job_ids.add(job_id)
            await job_queue.put((job_id, next(sequence), job_id))

        logger.info("엑셀 생성 작업이 큐에 입력되었습니다. job_id=%s", job_id) 

    async def worker_loop(self, job_service) -> None:
        logger.info("엑셀 worker_loop 시작")

        while True:
            job_id, _, _ = await job_queue.get()
            logger.info("큐에서 엑셀 작업을 꺼냈습니다. job_id=%s", job_id)

            async with queue_lock:
                queued_job_ids.discard(job_id)

            with SessionLocal() as db:
                job = db.get(Job, job_id)

                try:
                    if job is None:
                        logger.warning("엑셀 작업을 찾을 수 없습니다. job_id=%s", job_id)
                        continue

                    logger.info("엑셀 작업이 시작되었습니다. job_id=%s", job_id)

                    job_service.start_job(db, job)
                    db.commit()
                    db.refresh(job)

                    file_path = self.create_excel(db, job)

                    job.download_url = f"/files/{job.id}"
                    job_service.complete_job(db, job)

                    db.commit()

                    logger.info(
                        "엑셀 생성이 완료되었습니다. job_id=%s file_path=%s",
                        job_id,
                        file_path,
                    )

                except Exception as error:
                    logger.exception("엑셀 작업이 실패하였습니다. job_id=%s", job_id)

                    if job is not None:
                        job.status = JobStatus.FAILED
                        job.error_message = str(error)
                        db.commit()

                finally:
                    job_queue.task_done()
    # async def worker_loop(excel_servce, session_factory):
    #     while True:
    #         job_id, _, _ = await job_queue.get()

    #         try:
    #             with session_factory() as db:
    #                 job = db.get(Job, job_id)
    #                 if job is None:
    #                     continue

    #                 job.status =JobStatus.PROCESSING
    #                 db.commit()

    #                 url = excel_servce.create_excel(db, job)

    #                 job.status = JobStatus.DONE
    #                 job.download_url = url
    #                 db.commit()

    #         except Exception:
    #             logger.exception("엑셀 작업이 실패하였습니다. job_id=%s", job_id)

    #         finally:
    #             job_queue.task_done()




    @staticmethod
    def _save_progress(db: Session, job: Job, processed_rows: int, total_rows: int) -> None:
        job.processed_rows = processed_rows
        job.total_rows = total_rows
        job.progress = 100 if total_rows == 0 else int(processed_rows * 100 / total_rows)
        db.commit()
        db.refresh(job)

    @staticmethod
    def _format_datetime(value) -> str:
        return "" if value is None else value.strftime("%Y-%m-%d %H:%M:%S")

excel_service = ExcelService()