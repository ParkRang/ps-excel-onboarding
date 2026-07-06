from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from db.session import get_db
from job.job_response import JobResponse
from job.job_service import JobService

# from sse_starlette.sse import EventSourceResponse
from core.sse_manager import sse_manager

import asyncio

router = APIRouter()
job_service = JobService()


@router.get(
    "/jobs",
    response_model=list[JobResponse],
)
async def get_jobs(
    db: Session = Depends(get_db),
):
    return job_service.get_jobs(db)

# @router.get("/jobs")
# async def get_jobs(
#     db: AsyncSession = Depends(get_async_db),
# ):
#     return await job_service.get_jobs_async(db)


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

# @router.get(
#     "/jobs/{job_id}",
#     response_model=JobResponse,
# )
# async def get_job(
#     job_id: int,
#     db: AsyncSession = Depends(get_async_db),
# ):
#     job = await job_service.get_job_async(db, job_id)

#     if job is None:
#         raise HTTPException(
#             status_code=404,
#             detail="Job not found",
#         )

#     return job

@router.get("/jobs/{job_id}/events", include_in_schema=False)
async def job_events(
    job_id: int,
    request: Request,
):
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    connection = sse_manager.connect(
        job_id=job_id,
        queue=queue,
        loop=loop,
    )

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break

                message = await queue.get()
                yield message

        finally:
            sse_manager.disconnect(
                job_id=job_id,
                connection=connection,
            )

    return EventSourceResponse(event_generator())