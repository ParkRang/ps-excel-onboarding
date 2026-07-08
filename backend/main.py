import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.logging import setup_logger
from db.database import Base, engine
from excel.excel_router import router as excel_router
from job.job import Job # noqa: F401 - registers table metadata
from job.job_router import router as job_router
from order.order import Order  # noqa: F401 - registers table metadata
# from task.task_router import router as task_router
from excel.excel_service import excel_service
# from db.database import SessionLocal
from job.job_service import JobService

from job.job_events import job_event_hub

job_service = JobService()
setup_logger()
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
    worker_task = asyncio.create_task(excel_service.worker_loop())

    try:
        yield
    finally:
        worker_task.cancel()

        with suppress(asyncio.CancelledError):
            await worker_task

        await job_event_hub.stop()
    


app = FastAPI(title="Excel onboarding backend", lifespan=lifespan)
app.include_router(job_router)
app.include_router(excel_router)
# app.include_router(task_router)
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

