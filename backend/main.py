import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import Settings
from core.logging import setup_logger
from db.database import Base, engine
from auth.auth_router import router as auth_router
from excel.excel_router import router as excel_router
from job.job import Job # noqa: F401 - registers table metadata
from job.job_router import router as job_router
from order.order import Order  # noqa: F401 - registers table metadata
from task.task_router import router as task_router
from user.user import User  # noqa: F401 - registers table metadata
from excel.excel_service import excel_service
# from db.database import SessionLocal
from job.job_service import JobService

from job.job_events import job_event_hub

job_service = JobService()
settings = Settings()
setup_logger()
logger = logging.getLogger(__name__)
settings.validate_infra_mode()
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # worker_task = asyncio.create_task(
    #     excel_service.worker_loop(job_service)
    # )
    # try:
    #     yield
    # finally:
    #     worker_task.cancel()
    await job_event_hub.start()

    # worker_task = asyncio.create_task(
    #     excel_service.worker_loop(job_service),
    #     name="excel-worker",
    # )
    worker_task = None
    logger.info("애플리케이션을 시작합니다. infra_mode=%s", settings.INFRA_MODE)
    if not settings.API_KEY:
        logger.warning(
            "API_KEY가 설정되지 않아 POST /create가 인증 없이 열려 있습니다. "
            "운영 환경에서는 API_KEY를 설정하세요."
        )
    if settings.is_local:
        logger.info("local 모드이므로 내부 백그라운드 엑셀 worker를 시작합니다.")
        worker_task = asyncio.create_task(excel_service.worker_loop())
    else:
        logger.info("cloud 모드이므로 내부 worker를 시작하지 않고 Cloud Tasks 콜백을 사용합니다.")

    try:
        yield
    finally:
        if worker_task is not None:
            logger.info("내부 백그라운드 엑셀 worker를 종료합니다.")
            worker_task.cancel()

            with suppress(asyncio.CancelledError):
                await worker_task

        await job_event_hub.stop()
    


app = FastAPI(title="Excel onboarding backend", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(job_router)
app.include_router(excel_router)
app.include_router(task_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://ps-onboarding-frontend-1038097021464.asia-northeast3.run.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "excel onboarding backend"}
