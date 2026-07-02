import json, logging
from datetime import datetime

logger = logging.getLogger(__name__)
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
            json.dumps({
                "message": "Request received",
                "job_id": job_id,
                "requested_at": requested_at,
            },
            ensure_ascii=False,
            default=str
        ))

def start_logger(
        job_id: int,
        started_at: datetime
    ) :
    logger.info(
        json.dumps({
            "message": "Job started",
            "job_id": job_id,
        "started_at": started_at,
        },
        ensure_ascii=False,
        default=str
    ))

def complete_logger(
        job_id: int,
        completed_at: datetime,
        duration_seconds: float,
        gcs_url: str
    ) :
    logger.info(
        json.dumps({
            "message": "Job completed",
            "job_id": job_id,
            "completed_at": completed_at,
            "duration_seconds": duration_seconds,
            "gcs_url": gcs_url
        },
            ensure_ascii=False,
            default=str
        )
    )

def fail_logger(
        job_id: int,
        failed_at: datetime,
        error_message: str
    ) :
    logger.error(
        json.dumps({
            "message": "Job failed",
            "job_id": job_id,
            "failed_at": failed_at,
            "error_message": error_message
        },
            ensure_ascii=False,
            default=str
        )
    )