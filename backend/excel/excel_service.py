import tempfile, asyncio, logging
from itertools import count
from pathlib import Path
from time import perf_counter
from datetime import timedelta

import xlsxwriter
from sqlalchemy import and_, func, or_, select, update

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
from webhook.webhook_service import WebhookService

logger = logging.getLogger(__name__)
settings = Settings()
cloud_task_service = CloudTaskService()
webhook_service = WebhookService()

job_queue:asyncio.PriorityQueue = asyncio.PriorityQueue()
queued_job_ids: set[int] = set()
queue_lock = asyncio.Lock()
sequence = count()

class ExcelService:
    MAX_CHUNK_SIZE = 5000
    # 진행률을 몇 페이지마다 DB에 커밋할지 (commit 왕복 비용 절감)
    PROGRESS_COMMIT_EVERY = 4

    def _claim_job(self, db, job_id: int) -> int:
        """job을 원자적으로 PROCESSING으로 선점한다. 선점 rowcount(1 또는 0)를 반환.

        선점 대상:
          - PENDING / FAILED (정상 시작 또는 재시도), 또는
          - 리스(PROCESSING_LEASE_SECONDS)가 만료된 PROCESSING(죽은 워커가 남긴 좀비)
        단, attempt_count < MAX_ATTEMPTS 인 경우만.

        - 중복 실행 방어: Cloud Tasks는 at-least-once라 같은 job이 중복 도착할 수
          있다. 이미 다른 워커가 선점(리스 유효)했다면 rowcount=0 → 건너뛴다.
        - stale 리클레임: 인스턴스가 export 도중 죽으면 job이 PROCESSING에 묶인다.
          started_at이 리스를 넘긴 PROCESSING을 재선점 대상에 포함해 복구한다.
          리스는 정상 실행이 도중에 탈취되지 않도록 dispatch_deadline 이상으로 둔다.
        - 재시도 상한: attempt_count가 MAX_ATTEMPTS에 도달하면 선점하지 않아
          영구 실패로 고정되고, 콜백은 정상 응답하여 Cloud Tasks 재시도를 멈춘다.
        """
        lease_cutoff = now() - timedelta(seconds=settings.PROCESSING_LEASE_SECONDS)
        result = db.execute(
            update(Job)
            .where(Job.id == job_id)
            .where(
                or_(
                    Job.status.in_([JobStatus.PENDING, JobStatus.FAILED]),
                    and_(
                        Job.status == JobStatus.PROCESSING,
                        Job.started_at.is_not(None),
                        Job.started_at < lease_cutoff,
                    ),
                )
            )
            .where(Job.attempt_count < settings.MAX_ATTEMPTS)
            .values(
                status=JobStatus.PROCESSING,
                started_at=now(),
                failed_at=None,
                completed_at=None,
                error_message=None,
                progress=0,
                processed_rows=0,
                attempt_count=Job.attempt_count + 1,
            )
        )
        db.commit()
        return result.rowcount

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

            claimed = self._claim_job(db, job_id)
            db.refresh(job)

            if claimed == 0:
                # rowcount=0 원인은 세 가지다:
                # (1) 다른 워커가 이미 선점하고 리스가 살아있음(최근 started_at의 PROCESSING)
                # (2) 이미 완료됨(DONE)
                # (3) 재시도 상한 도달(attempt_count >= MAX_ATTEMPTS) → 영구 실패
                logger.info(
                    "claim에 실패하여 job을 건너뜁니다. "
                    "job_id=%s status=%s attempt_count=%s max_attempts=%s",
                    job_id,
                    job.status,
                    job.attempt_count,
                    settings.MAX_ATTEMPTS,
                )
                return

            # ===== [ADD] 상태 변경 즉시 SSE 발행 =====
            publish_job_event(job)
            start_logger(job_id=job.id, started_at=job.started_at)

            # ===== [PERF] xlsxwriter 스트리밍 workbook =====
            # constant_memory=True 는 write된 행을 순차적으로 디스크에 흘려보내
            # 메모리를 상수로 유지한다(openpyxl write_only와 동일). 순수 파이썬
            # 쓰기 속도가 openpyxl보다 ~1.5배 빨라 대용량에서 전체 작업시간이 크게 준다.
            # xlsxwriter는 생성 시점에 파일을 열므로 출력 경로를 먼저 결정한다.
            output_dir = Path(settings.EXCEL_STORAGE_DIR)
            if settings.is_cloud:
                output_dir = Path(tempfile.gettempdir())
            else:
                output_dir.mkdir(parents=True, exist_ok=True)
            file_path = output_dir / f"{job.id}.xlsx"

            workbook = xlsxwriter.Workbook(str(file_path), {"constant_memory": True})
            sheet = workbook.add_worksheet("Orders")
            sheet.write_row(0, 0, [
                "ID",
                "User Name",
                "Product Name",
                "Category",
                "Amount",
                "Status",
                "Order date",
            ])
            row_index = 1

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
                # ===== [PERF] keyset(seek) 페이징 + 컬럼만 select =====
                # OFFSET은 페이지가 뒤로 갈수록 앞 행을 매번 스캔해 총 시간이 제곱으로
                # 증가한다. `WHERE id > last_id`(keyset)는 인덱스로 바로 점프해 선형이며
                # 동시 insert/delete에도 행 누락/중복이 없다. 또한 ORM 객체 대신 필요한
                # 컬럼만 읽어(Core Row) 인스턴스화 오버헤드를 없앤다.
                columns = select(
                    Order.id,
                    Order.user_name,
                    Order.product_name,
                    Order.category,
                    Order.amount,
                    Order.status,
                    Order.order_date,
                )
                processed_rows = 0
                last_id = 0
                page = 0

                while True:
                    read_started_at = perf_counter()
                    rows = db.execute(
                        columns
                        .where(Order.id > last_id)
                        .order_by(Order.id)
                        .limit(self.MAX_CHUNK_SIZE)
                    ).all()
                    read_elapsed += perf_counter() - read_started_at

                    if not rows:
                        break

                    write_started_at = perf_counter()
                    for r in rows:
                        sheet.write_row(row_index, 0, [
                            r.id,
                            r.user_name,
                            r.product_name,
                            r.category,
                            r.amount,
                            r.status,
                            self._format_datetime(r.order_date),
                        ])
                        row_index += 1
                    write_elapsed += perf_counter() - write_started_at

                    processed_rows += len(rows)
                    last_id = rows[-1].id
                    page += 1
                    progress = int((processed_rows / total_rows) * 100)

                    logger.info(f'{job_id}번 작업 실행률 : {progress}%')

                    job.processed_rows = processed_rows
                    job.progress = min(progress, 99)

                    # ===== [PERF] 진행률 commit 스로틀링 =====
                    # 페이지마다 commit하면 (특히 Cloud SQL에선) 매번 왕복 비용이 든다.
                    # N페이지마다만 영속화한다. SSE도 이때 함께 발행(REST가 authoritative).
                    if page % self.PROGRESS_COMMIT_EVERY == 0:
                        db.commit()
                        publish_job_event(job)

                # 스로틀로 아직 커밋되지 않은 마지막 진행률을 반영한다.
                db.commit()
                publish_job_event(job)

            # xlsxwriter는 close() 시점에 파일을 최종화한다(openpyxl save 대체).
            save_started_at = perf_counter()
            workbook.close()
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
                job.duration_seconds = round((job.completed_at - job.started_at).total_seconds(), 2)

            db.commit()
            db.refresh(job)

            # ===== [ADD] 완료 상태 SSE 발행 =====
            publish_job_event(job)
            complete_logger(
                job_id=job.id,
                completed_at=job.completed_at,
                duration_seconds=job.duration_seconds,
            )
            webhook_service.send_success_message(
                job.id,
                job.completed_at,
                job.download_url,
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
                    job.duration_seconds = round((job.failed_at - job.started_at).total_seconds(), 2)

                db.commit()
                db.refresh(job)

                # ===== [ADD] 실패 상태 SSE 발행 =====
                publish_job_event(job)
                fail_logger(
                    job_id=job.id,
                    failed_at=job.failed_at,
                    error_message=job.error_message,
                )
                webhook_service.send_failure_message(
                    job.id,
                    job.error_message,
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
            # task_name은 호출측(excel_router.create_job)이 enqueue 직후 db.commit()
            # 하면서 함께 영속된다. 여기서 별도 commit하지 않는다.
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
