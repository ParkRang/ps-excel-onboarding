from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.session import get_db
from job.job_response import JobResponse
from job.job_service import JobService


router = APIRouter()
job_service = JobService()


@router.get(
    "/jobs",
    response_model=list[JobResponse],
)
def get_jobs(
    db: Session = Depends(get_db),
):
    return job_service.get_jobs(db)


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
):
    job = job_service.get_job(db, job_id)

    if job is None:
        raise HTTPException(

        )

    return job