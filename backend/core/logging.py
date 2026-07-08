import json, logging
from datetime import datetime

logger = logging.getLogger(__name__)


def event_logger(message: str, *, level: int = logging.INFO, **fields) -> None:
    logger.log(
        level,
        message
    )


def setup_logger() :

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)

def request_logger(
        job_id: int,
        requested_at: datetime
    ) :
        logger.info(
            f"job_id={job_id} request_log, 엑셀 생성이 요청되었습니다. at : {requested_at}"
        )

def start_logger(
        job_id: int,
        started_at: datetime
    ) :
    logger.info(
            f"job_id={job_id} start_log, 엑셀 작업이 시작되었습니다. at : {started_at}"
        )

def complete_logger(
        job_id: int,
        completed_at: datetime,
        duration_seconds: float,
    ) :
    logger.info(
        f"job_id={job_id} complete_log, 엑셀 생성이 완료되었습니다. at : {completed_at}, 소모시간 : {duration_seconds}" 
    )

def fail_logger(
        job_id: int,
        failed_at: datetime,
        error_message: str
    ) :
    logger.error(
        f"job_id={job_id} fail_log, 엑셀 생성이 실패하였습니다. at : {failed_at}, msg:{error_message}"
    )
