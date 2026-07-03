from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_db, SessionLocal
from job.job_response import JobResponse
from job.job_service import JobService
from excel.worker_service import WorkerService
from core.logging import request_logger

router = APIRouter()

job_service = JobService()
worker_service = WorkerService()

@router.post("/create")
def create_job(
    # background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    job = job_service.create_export(db)

    # background_tasks.add_task(
    #     worker_service.process_job,
    #     job.id,
    # )
    request_logger(job_id=job.id, requested_at=job.requested_at)

    return {
        "status": "accepted",
        "message": "Cloud Tasks에서 엑셀 생성을 시작했습니다.",
        "job_id": job.id,
    }


