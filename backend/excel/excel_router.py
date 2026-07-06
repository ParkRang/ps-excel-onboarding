from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.logging import request_logger
from db.session import get_db
from job.job_service import JobService


router = APIRouter(tags=["exports"])
job_service = JobService()


@router.post("/create", status_code=status.HTTP_202_ACCEPTED)
def create_job(db: Session = Depends(get_db)):
    try:
        job = job_service.create_export(db)
    except Exception as error:
        raise HTTPException(status_code=502, detail="Could not enqueue export job") from error
    request_logger(job_id=job.id, requested_at=job.requested_at)
    return {"status": "accepted", "message": "Excel export job was queued.", "job_id": job.id}
