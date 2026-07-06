import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from db.session import get_db
from job.job_events import job_event_hub
from job.job_response import JobResponse
from job.job_service import JobService


router = APIRouter(prefix="/jobs", tags=["jobs"])
job_service = JobService()


@router.get("", response_model=list[JobResponse])
def get_jobs(db: Session = Depends(get_db)):
    return job_service.get_jobs(db)


@router.get("/events", include_in_schema=False)
async def job_events(request: Request):
    async def event_stream():
        queue = job_event_hub.subscribe()

        try:
            while not await request.is_disconnected():
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"event: job\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            job_event_hub.unsubscribe(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
