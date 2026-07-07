import asyncio

from fastapi import APIRouter, HTTPException

from core.logging import event_logger
from excel.worker_service import WorkerBusyError, WorkerService
from task.task_request import TaskRequest


router = APIRouter(prefix="/tasks", tags=["tasks"])
worker = WorkerService()
excel_semaphore = asyncio.Semaphore(1)


@router.post("/excel")
async def export_task(request: TaskRequest):
    event_logger("Cloud Task callback received", requested_job_id=request.job_id)
    try:
        # Keep CPU-heavy Excel work off the event loop and allow only one
        # in-process export at a time. The DB claim remains the cross-instance
        # duplicate-execution guard.
        async with excel_semaphore:
            processed_job_id = await asyncio.to_thread(
                worker.process_queued_job,
                request.job_id,
            )
    except WorkerBusyError as error:
        # A non-2xx response asks Cloud Tasks to retry this wake-up signal.
        raise HTTPException(status_code=503, detail=str(error)) from error

    # Verify the chain in a fresh DB session after the worker transaction.
    # This also repairs a DONE Job whose queue row survived an interrupted request.
    await asyncio.to_thread(worker.queue.recover_and_dispatch)
    event_logger(
        "Cloud Task callback completed",
        requested_job_id=request.job_id,
        processed_job_id=processed_job_id,
    )

    return {
        "status": "ok",
        "requested_job_id": request.job_id,
        "processed_job_id": processed_job_id,
    }
