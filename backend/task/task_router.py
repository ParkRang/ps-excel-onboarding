from fastapi import APIRouter

from excel.worker_service import WorkerService
from task.task_request import TaskRequest

router = APIRouter(prefix="/tasks", tags=["tasks"])

worker_service = WorkerService()

@router.post("/excel")
async def export_task(request: TaskRequest):
    worker_service.process_job(request.job_id)

    return {
        "status": "ok",
        "job_id": request.job_id,
    }

# @router.post("/excel")
# async def export_task(job_id: int,
#     excel_service: ExcelService = Depends(get_excel_service),):
#     awiworker_service.process_job(request.job_id)

#     return {
#         "status": "ok",
#         "job_id": request.job_id,
#     }