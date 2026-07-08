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

from job.job_events import publish_job_event
from common.utils.now import now

logger = logging.getLogger(__name__)

job_queue:asyncio.PriorityQueue = asyncio.PriorityQueue()
queued_job_ids: set[int] = set()
queue_lock = asyncio.Lock()
sequence = count()

class ExcelService:
    MAX_CHUNK_SIZE = 5000


    # def create_excel(self, db: Session, job: Job) -> str:
    #     workbook = Workbook(write_only=True)
    #     sheet = workbook.create_sheet("Orders")
    #     sheet.append(["주문번호", "주문자", "상품명", "카테고리", "금액", "상태", "주문일"])

    #     total_rows = db.scalar(select(func.count()).select_from(Order)) or 0
    #     chunk_size = max(1, min(self.MAX_CHUNK_SIZE, ceil(total_rows / 100)))
    #     self._save_progress(db, job, 0, total_rows)
    #     job.total_rows = total_rows
    
    #     last_id = 0
    #     processed_rows = 0
    #     last_progress = 0
    #     last_logged_progress = 0

    #     event_logger(
    #         f"job_id={job.id}, 엑셀 생성 작업이 시작되었습니다.",
    #     )

    #     while True:
    #         statement = (
    #             select(
    #                 Order.id,
    #                 Order.user_name,
    #                 Order.product_name,
    #                 Order.category,
    #                 Order.amount,
    #                 Order.status,
    #                 Order.order_date,
    #             )
    #             .where(Order.id > last_id)
    #             .order_by(Order.id)
    #             .limit(chunk_size)
    #         )
    #         orders = db.execute(statement).all()
    #         if not orders:
    #             break

    #         for order in orders:
    #             sheet.append([
    #                 order.id, order.user_name, order.product_name,
    #                 order.category, order.amount, order.status,
    #                 self._format_datetime(order.order_date),
    #             ])

    #         processed_rows += len(orders)
    #         last_id = orders[-1].id
    #         progress = 100 if total_rows == 0 else int(processed_rows * 100 / total_rows)
    #         if progress > last_progress:
    #             self._save_progress(db, job, processed_rows, total_rows)
    #             last_progress = progress
    #             if progress >= last_logged_progress + 10 or progress == 100:
    #                 event_logger(
    #                     f"{job.id}번 파일 생성이 진행중입니다. {progress}"
    #                 )
    #                 last_logged_progress = progress

    #     # with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
    #     #     file_path = temp_file.name
    #     # workbook.save(file_path)

    #     output_dir = Path("files")
    #     output_dir.mkdir(parents=True, exist_ok=True)

    #     file_path = output_dir / f"{job.id}.xlsx"
    #     workbook.save(file_path)


    #     event_logger(f"{job.id}엑셀 파일이 생성되었습니다, {file_path}")
    #     return str(file_path)

    def create_excel(self, job_id: int):
        # ===== [IMPORTANT]
        # 이 함수는 asyncio.to_thread() 안에서 실행됨.
        # 그래서 DB Session을 외부에서 넘기면 안 되고,
        # 반드시 이 thread 안에서 새로 만들어야 함.
        db = SessionLocal()

        try:
            job = db.get(Job, job_id)

            if job is None:
                logger.warning("Job not found: %s", job_id)
                return

            # ===== [ADD] 작업 시작 상태 저장 =====
            job.status = JobStatus.PROCESSING
            job.started_at = now()
            job.failed_at = None
            job.completed_at = None
            job.error_message = None
            job.progress = 0
            job.processed_rows = 0
            job.attempt_count += 1

            db.commit()
            db.refresh(job)

            # ===== [ADD] 상태 변경 즉시 SSE 발행 =====
            publish_job_event(job)

            # ===== [기존 코드 유지] 엑셀 workbook 생성 =====
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Orders"

            sheet.append([
                "ID",
                "User Name",
                "Product Name",
                "Category",
                "Amount",
                "Status",
                "Order date",
            ])

            # ===== [기존 코드 유지] 전체 row 수 조회 =====
            total_rows = db.scalar(select(func.count(Order.id))) or 0

            job.total_rows = total_rows
            job.processed_rows = 0
            job.progress = 0

            db.commit()
            db.refresh(job)

            # ===== [ADD] total_rows 반영된 상태 SSE 발행 =====
            publish_job_event(job)

            if total_rows > 0:
                total_pages = ceil(total_rows / self.MAX_CHUNK_SIZE)
                processed_rows = 0

                for page in range(total_pages):
                    offset = page * self.MAX_CHUNK_SIZE

                    orders = db.scalars(
                        select(Order)
                        .order_by(Order.id)
                        .offset(offset)
                        .limit(self.MAX_CHUNK_SIZE)
                    ).all()

                    for order in orders:
                        sheet.append([
                            order.id,
                            order.user_name,
                            order.product_name,
                            order.category,
                            order.amount,
                            order.status,
                            order.order_date,
                        ])

                    processed_rows += len(orders)
                    progress = int((processed_rows / total_rows) * 100)

                    # ===== [ADD] 진행률 저장 =====
                    job.processed_rows = processed_rows
                    job.progress = min(progress, 99)

                    db.commit()
                    db.refresh(job)

                    # ===== [ADD] 진행률 변경 즉시 SSE 발행 =====
                    publish_job_event(job)

            # ===== [기존 코드 유지] 파일 저장 =====
            output_dir = Path("files")
            output_dir.mkdir(parents=True, exist_ok=True)

            file_path = output_dir / f"{job.id}.xlsx"
            workbook.save(file_path)

            # ===== [ADD] 작업 완료 상태 저장 =====
            job.status = JobStatus.DONE
            job.progress = 100
            job.processed_rows = total_rows
            job.completed_at = now()
            job.download_url = f"/files/{job.id}"

            if job.started_at is not None:
                job.duration_seconds = int((job.completed_at - job.started_at).total_seconds())

            db.commit()
            db.refresh(job)

            # ===== [ADD] 완료 상태 SSE 발행 =====
            publish_job_event(job)

        except Exception as exc:
            db.rollback()

            job = db.get(Job, job_id)

            if job is not None:
                # ===== [ADD] 실패 상태 저장 =====
                job.status = JobStatus.FAILED
                job.failed_at = now()
                job.error_message = str(exc)

                if job.started_at is not None:
                    job.duration_seconds = int((job.failed_at - job.started_at).total_seconds())

                db.commit()
                db.refresh(job)

                # ===== [ADD] 실패 상태 SSE 발행 =====
                publish_job_event(job)

            raise

        finally:
            db.close()

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

    # async def worker_loop(self, job_service) -> None:
    #     logger.info("엑셀 worker_loop 시작")

    #     while True:
    #         job_id, _, _ = await job_queue.get()
    #         logger.info("큐에서 엑셀 작업을 꺼냈습니다. job_id=%s", job_id)

    #         async with queue_lock:
    #             queued_job_ids.discard(job_id)

    #         with SessionLocal() as db:
    #             job = db.get(Job, job_id)

    #             try:
    #                 if job is None:
    #                     logger.warning("엑셀 작업을 찾을 수 없습니다. job_id=%s", job_id)
    #                     continue

    #                 logger.info("엑셀 작업이 시작되었습니다. job_id=%s", job_id)

    #                 job_service.start_job(db, job)
    #                 db.commit()
    #                 db.refresh(job)

    #                 # file_path = self.create_excel(db, job)

    #                 ###########
    #                 file_path = await asyncio.to_thread(
    #                     self.create_excel,
    #                     job_id,
    #                 )

    #                 job.download_url = f"/files/{job.id}"
    #                 job_service.complete_job(db, job)

    #                 db.commit()

    #                 logger.info(
    #                     "엑셀 생성이 완료되었습니다. job_id=%s file_path=%s",
    #                     job_id,
    #                     file_path,
    #                 )

    #             except Exception as error:
    #                 logger.exception("엑셀 작업이 실패하였습니다. job_id=%s", job_id)

    #                 if job is not None:
    #                     job.status = JobStatus.FAILED
    #                     job.error_message = str(error)
    #                     db.commit()

    #             finally:
    #                 job_queue.task_done()

    async def worker_loop(self):
            while True:
                job_id, _, _ = await job_queue.get()

                try:
                    async with queue_lock:
                        queued_job_ids.discard(job_id)

                    # ===== [ADD] 핵심: sync create_excel을 별도 thread에서 실행 =====
                    # 이것 때문에 FastAPI 이벤트 루프가 막히지 않고,
                    # /jobs/events, /jobs/page 같은 요청을 동시에 처리할 수 있음.
                    await asyncio.to_thread(self.create_excel, job_id)

                except asyncio.CancelledError:
                    raise

                except Exception:
                    logger.exception("Worker failed while processing job_id=%s", job_id)

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