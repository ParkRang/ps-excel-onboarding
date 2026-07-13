import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
from pathlib import Path

from core.auth import require_api_key
from core.config import Settings
from core.logging import request_logger
from db.session import get_db
from job.job_service import JobService
from excel.excel_service import excel_service
from services.storage_service import EXCEL_MIME_TYPE

router = APIRouter(tags=["exports"])
job_service = JobService()
settings = Settings()
logger = logging.getLogger(__name__)

@router.post("/create", dependencies=[Depends(require_api_key)])
async def create_job(db: Session = Depends(get_db)):
    try:

        logger.info("(/create) create_job -> create_export 실행")
        job = job_service.create_export(db)
        logger.info("(/create) create_job -> enqueue_job 실행")
        await excel_service.enqueue_job(job)
        db.add(job)
        db.commit()
        db.refresh(job)
    except Exception as error:
        raise HTTPException(status_code=502, detail="Could not enqueue export job") from error
    request_logger(job_id=job.id, requested_at=job.requested_at)
    return {"status": "accepted", "message": "Excel export job was queued.", "job_id": job.id}

@router.get(f"{settings.EXCEL_DOWNLOAD_PREFIX}" + "/{job_id}")
async def download_file(job_id: int):
    path = (Path(settings.EXCEL_STORAGE_DIR) / f"{job_id}.xlsx").resolve()
    storage_dir = Path(settings.EXCEL_STORAGE_DIR).resolve()

    if storage_dir not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Excel file not found")

    logger.info("엑셀 다운로드를 처리합니다. job_id=%s path=%s", job_id, path)
    return FileResponse(
        path,
        filename=f"{job_id}.xlsx",
        media_type=EXCEL_MIME_TYPE,
    )
