from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.session import get_db
from job.job_response import JobResponse
from job.job_service import JobService


router = APIRouter()
job_service = JobService()


@router.post(
    "/export",
    response_model=JobResponse
)
def create_export(
    db: Session = Depends(get_db),
):
    """
    엑셀 생성 작업을 요청합니다.

    실제 엑셀 생성은 여기서 실행하지 않고,
    JobService가 Cloud Tasks에 작업을 등록합니다.
    """
    try:
        return job_service.create_export(db)

    except Exception as error:
        raise HTTPException(


        ) from error


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