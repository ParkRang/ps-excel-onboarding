import csv
import logging
import tempfile
from math import ceil
from time import perf_counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.logging import event_logger
from job.job import Job
from job.job_events import publish_job_event
from order.order import Order


logger = logging.getLogger(__name__)


class ExcelService:
    MAX_CHUNK_SIZE = 5000

    def create_excel(
        self,
        db: Session,
        job: Job,
    ) -> str:
        total_start = perf_counter()
        db_query_seconds = 0.0
        csv_write_seconds = 0.0
        progress_save_seconds = 0.0

        total_rows = (
            db.scalar(
                select(func.count())
                .select_from(Order)
            )
            or 0
        )

        chunk_size = max(
            1,
            min(
                self.MAX_CHUNK_SIZE,
                ceil(total_rows / 100),
            ),
        )

        progress_start = perf_counter()
        self._save_progress(
            db,
            job,
            processed_rows=0,
            total_rows=total_rows,
        )
        progress_save_seconds += (
            perf_counter() - progress_start
        )

        last_id = 0
        processed_rows = 0
        last_progress = 0
        last_logged_progress = 0

        event_logger(
            "CSV rows processing initialized",
            job_id=job.id,
            total_rows=total_rows,
            chunk_size=chunk_size,
        )

        # utf-8-sig는 Excel에서 한글이 깨지지 않도록 BOM을 추가합니다.
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            encoding="utf-8-sig",
            newline="",
            delete=False,
        ) as temp_file:
            file_path = temp_file.name

            writer = csv.writer(
                temp_file,
                lineterminator="\n",
            )

            writer.writerow([
                "주문번호",
                "주문자",
                "상품명",
                "카테고리",
                "금액",
                "상태",
                "주문일",
            ])

            while True:
                query_start = perf_counter()

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

                db_query_seconds += (
                    perf_counter() - query_start
                )

                if not orders:
                    break

                write_start = perf_counter()

                writer.writerows([
                    [
                        order.id,
                        order.user_name,
                        order.product_name,
                        order.category,
                        order.amount,
                        order.status,
                        self._format_datetime(
                            order.order_date
                        ),
                    ]
                    for order in orders
                ])

                csv_write_seconds += (
                    perf_counter() - write_start
                )

                processed_rows += len(orders)
                last_id = orders[-1].id

                progress = (
                    100
                    if total_rows == 0
                    else int(
                        processed_rows
                        * 100
                        / total_rows
                    )
                )

                if progress > last_progress:
                    progress_start = perf_counter()

                    self._save_progress(
                        db,
                        job,
                        processed_rows,
                        total_rows,
                    )

                    progress_save_seconds += (
                        perf_counter()
                        - progress_start
                    )

                    last_progress = progress

                    if (
                        progress
                        >= last_logged_progress + 10
                        or progress == 100
                    ):
                        event_logger(
                            "CSV generation progress",
                            job_id=job.id,
                            progress=progress,
                            processed_rows=processed_rows,
                            total_rows=total_rows,
                        )

                        last_logged_progress = progress

        total_seconds = (
            perf_counter() - total_start
        )

        logger.info(
            "[Job %s] CSV timing | "
            "rows=%s | "
            "DB=%.3fs | "
            "write=%.3fs | "
            "progress-save=%.3fs | "
            "total=%.3fs",
            job.id,
            total_rows,
            db_query_seconds,
            csv_write_seconds,
            progress_save_seconds,
            total_seconds,
        )

        event_logger(
            "CSV file saved",
            job_id=job.id,
            file_path=file_path,
        )

        return file_path

    @staticmethod
    def _save_progress(
        db: Session,
        job: Job,
        processed_rows: int,
        total_rows: int,
    ) -> None:
        job.processed_rows = processed_rows
        job.total_rows = total_rows
        job.progress = (
            100
            if total_rows == 0
            else int(
                processed_rows
                * 100
                / total_rows
            )
        )

        db.commit()
        db.refresh(job)
        publish_job_event(job)

    @staticmethod
    def _format_datetime(value) -> str:
        if value is None:
            return ""

        return value.strftime(
            "%Y-%m-%d %H:%M:%S"
        )