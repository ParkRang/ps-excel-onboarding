from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse

from core.logging import request_logger
from db.session import get_db
from job.job_service import JobService


router = APIRouter(tags=["exports"])
job_service = JobService()


@router.post("/create")
def create_job(db: Session = Depends(get_db)):
    try:
        job = job_service.create_export(db)
    except Exception as error:
        raise HTTPException(status_code=502, detail="Could not enqueue export job") from error
    request_logger(job_id=job.id, requested_at=job.requested_at)
    return {"status": "accepted", "message": "Excel export job was queued.", "job_id": job.id}

@router.get('/files/{job_id}')
async def download_file(job_id: str) :
    path = f'/app/files/{job_id}.xlsx'
    return FileResponse(path, filename = f'{job_id}.xlsx')