from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from db.session import get_db
from excel.worker_service import WorkerService
from task.task_schema import TaskRequest


router = APIRouter(
    prefix="/internal/tasks",
    tags=["internal"],
)

worker_service = WorkerService()


@router.post(
    "/export",

)
def process_export(
    request: TaskRequest,
    db: Session = Depends(get_db),
):


    try:
        worker_service.process_job(
            db=db,
            job_id=request.job_id,
        )

    except ValueError as error:
        raise HTTPException(

        ) from error

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )