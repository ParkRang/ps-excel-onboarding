import tempfile, asyncio, logging
from math import ceil
from itertools import count
from pathlib import Path
from time import perf_counter

from openpyxl import Workbook
from sqlalchemy import func, select

from job.job import Job
from common.enums.job_status import JobStatus
from core.config import Settings
from order.order import Order
from db.database import SessionLocal
from services.storage_service import get_storage_client
from task.task_service import CloudTaskService
from core.logging import complete_logger, fail_logger, start_logger

from job.job_events import publish_job_event
from common.utils.now import now

logger = logging.getLogger(__name__)
settings = Settings()
cloud_task_service = CloudTaskService()

job_queue:asyncio.PriorityQueue = asyncio.PriorityQueue()
queued_job_ids: set[int] = set()
queue_lock = asyncio.Lock()
sequence = count()

class ExcelService:
    MAX_CHUNK_SIZE = 5000

    def create_excel(self, job_id: int):
        # ===== [IMPORTANT]
        # 이 함수는 asyncio.to_thread() 안에서 실행됨.
        # 그래서 DB Session을 외부에서 넘기면 안 되고,
        # 반드시 이 thread 안에서 새로 만들어야 함.
        db = SessionLocal()
        file_path: Path | None = None

        try:
            logger.info("엑셀 생성 작업을 시작합니다. job_id=%s infra_mode=%s", job_id, settings.INFRA_MODE)
            total_started_at = perf_counter()
            read_elapsed = 0.0
            write_elapsed = 0.0
            save_elapsed = 0.0

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
            start_logger(job_id=job.id, started_at=job.started_at)

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

                    read_started_at = perf_counter()
                    orders = db.scalars(
                        select(Order)
                        .order_by(Order.id)
                        .offset(offset)
                        .limit(self.MAX_CHUNK_SIZE)
                    ).all()
                    read_elapsed += perf_counter() - read_started_at

                    write_started_at = perf_counter()
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
                    write_elapsed += perf_counter() - write_started_at

                    processed_rows += len(orders)
                    progress = int((processed_rows / total_rows) * 100)
                    
                    logger.info(f'{job_id}번 작업 실행률 : {progress}%')
                    
                    # ===== [ADD] 진행률 저장 =====
                    job.processed_rows = processed_rows
                    job.progress = min(progress, 99)

                    db.commit()
                    db.refresh(job)

                    # ===== [ADD] 진행률 변경 즉시 SSE 발행 =====
                    publish_job_event(job)

            output_dir = Path(settings.EXCEL_STORAGE_DIR)
            if settings.is_cloud:
                output_dir = Path(tempfile.gettempdir())
            else:
                output_dir.mkdir(parents=True, exist_ok=True)

            file_path = output_dir / f"{job.id}.xlsx"
            save_started_at = perf_counter()
            workbook.save(file_path)
            save_elapsed += perf_counter() - save_started_at
            storage = get_storage_client()
            if settings.is_cloud:
                save_started_at = perf_counter()
                storage_result = storage.upload(str(file_path), job.id)
                save_elapsed += perf_counter() - save_started_at
            else:
                save_started_at = perf_counter()
                storage_result = storage.save(str(file_path), job.id)
                save_elapsed += perf_counter() - save_started_at

            # ===== [ADD] 작업 완료 상태 저장 =====
            job.status = JobStatus.DONE
            job.progress = 100
            job.processed_rows = total_rows
            job.completed_at = now()
            job.download_url = storage_result["download_url"]
            job.gcs_object_name = storage_result.get("object_name")
            job.gcs_url = storage_result.get("gcs_url")

            if job.started_at is not None:
                job.duration_seconds = int((job.completed_at - job.started_at).total_seconds())

            db.commit()
            db.refresh(job)

            # ===== [ADD] 완료 상태 SSE 발행 =====
            publish_job_event(job)
            complete_logger(
                job_id=job.id,
                completed_at=job.completed_at,
                duration_seconds=job.duration_seconds,
            )
            logger.info(
                "엑셀 생성 작업이 완료되었습니다. job_id=%s total_rows=%s download_url=%s",
                job.id,
                total_rows,
                job.download_url,
            )
            logger.info(
                (
                    "엑셀 생성 단계별 소요시간. "
                    "job_id=%s total_rows=%s read_seconds=%.3f "
                    "write_seconds=%.3f save_seconds=%.3f total_seconds=%.3f"
                ),
                job.id,
                total_rows,
                read_elapsed,
                write_elapsed,
                save_elapsed,
                perf_counter() - total_started_at,
            )

        except Exception as exc:
            db.rollback()
            logger.exception("엑셀 생성 작업이 실패했습니다. job_id=%s", job_id)

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
                fail_logger(
                    job_id=job.id,
                    failed_at=job.failed_at,
                    error_message=job.error_message,
                )

            raise

        finally:
            if settings.is_cloud and file_path is not None:
                file_path.unlink(missing_ok=True)
            db.close()

    async def enqueue_job(self, job: Job) -> None:
        logger.info("enqueue 실행")
        job_id = job.id

        if settings.is_cloud:
            task_name = cloud_task_service.enqueue(job_id)
            job.task_name = task_name
            logger.info("Cloud Tasks에 엑셀 작업을 등록했습니다. job_id=%s task_name=%s", job_id, task_name)
            return

        async with queue_lock:
            if job_id in queued_job_ids:
                logger.info("엑셀 작업이 이미 큐에 있습니다. job_id=%s", job_id)
                return

            queued_job_ids.add(job_id)
            await job_queue.put((job_id, next(sequence), job_id))

        logger.info("엑셀 생성 작업이 큐에 입력되었습니다. job_id=%s", job_id) 

    async def worker_loop(self):
        logger.info("worker_loop 동작")
        while True:
            job_id, _, _ = await job_queue.get()

            try:
                async with queue_lock:
                    queued_job_ids.discard(job_id)

                logger.info("worker_loop 내부에서 create_excel 실행")
                await asyncio.to_thread(self.create_excel, job_id)

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception("Worker failed while processing job_id=%s", job_id)

            finally:
                job_queue.task_done()

    @staticmethod
    def _format_datetime(value) -> str:
        return "" if value is None else value.strftime("%Y-%m-%d %H:%M:%S")

excel_service = ExcelService()
