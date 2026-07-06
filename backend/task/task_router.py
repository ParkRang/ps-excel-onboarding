from fastapi import APIRouter, HTTPException

from excel.worker_service import WorkerBusyError, WorkerService
from task.task_request import TaskRequest


router = APIRouter(prefix="/tasks", tags=["tasks"])
worker = WorkerService()


@router.post("/excel")
def export_task(request: TaskRequest):
    try:
        processed_job_id = worker.process_queued_job(request.job_id)
    except WorkerBusyError as error:
        # A non-2xx response asks Cloud Tasks to retry this wake-up signal.
        raise HTTPException(status_code=503, detail=str(error)) from error

    # Verify the chain in a fresh DB session after the worker transaction.
    # This also repairs a DONE Job whose queue row survived an interrupted request.
    worker.queue.recover_and_dispatch()

    return {
        "status": "ok",
        "requested_job_id": request.job_id,
        "processed_job_id": processed_job_id,
    }
