from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_db, SessionLocal
from job.job_response import JobResponse
from job.job_service import JobService
from excel.worker_service import WorkerService

router = APIRouter()

job_service = JobService()
worker_service = WorkerService()


def run_worker(job_id: int):
    """
    Background Task에서 사용할 Worker
    """

    db = SessionLocal()

    try:
        worker_service.process_job(db, job_id)

    finally:
        db.close()


@router.post(
    "/export",
    response_model=JobResponse
)
def export(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    job = job_service.create_job(db)

    background_tasks.add_task(
        run_worker,
        job.id
    )

    return job


@router.get(
    "/jobs",
    response_model=list[JobResponse]
)
def get_jobs(
    db: Session = Depends(get_db)
):
    return job_service.get_jobs(db)


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse
)
def get_job(
    job_id: int,
    db: Session = Depends(get_db)
):

    job = job_service.get_job(db, job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job을 찾을 수 없습니다."
        )

    return job