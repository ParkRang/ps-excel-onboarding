from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_db, SessionLocal
from job.job_response import JobResponse
from job.job_service import JobService
from excel.excel_service import ExcelService

router = APIRouter()

@router.post("/create")
def create(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # 백그라운드 대기열에 서비스 실행 명령을 등록
    background_tasks.add_task(ExcelService().create_excel, db=db)
    
    return {"status": "accepted", "message": "백그라운드에서 엑셀 생성을 시작했습니다."}


