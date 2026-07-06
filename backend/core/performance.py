import logging
import time
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger("perform")

@contextmanager
def measure_time(operation:str, *, job_id : int | None = None,
                 **extra,) -> Iterator[None]:
    started_at = time.perf_counter()

    try:
        yield

    except Exception:
        elapsed_seconds = time.perf_counter() - started_at

        logger.exception(
            "[PERFORMANCE][FAILED] "
            "operation=%s job_id=%s elapsed=%.3fs extra=%s",
            operation,
            job_id,
            elapsed_seconds,
            extra,
        )
        raise

    else:
        elapsed_seconds = time.perf_counter() - started_at

        logger.info(
            "[PERFORMANCE] "
            "operation=%s job_id=%s elapsed=%.3fs extra=%s",
            operation,
            job_id,
            elapsed_seconds,
            extra,
        )