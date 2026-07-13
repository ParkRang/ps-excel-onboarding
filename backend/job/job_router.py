import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from auth.auth_dependencies import get_current_user
from core.config import Settings
from db.session import get_db
from job.job_events import job_event_hub
from job.job_response import JobPageResponse, JobResponse
from job.job_service import JobService
from services.storage_service import get_storage_client
from user.user import User


router = APIRouter(prefix="/jobs", tags=["jobs"])
job_service = JobService()
settings = Settings()

@router.get("/events")
async def stream_job_events(request: Request):
    # ===== [ADD] subscribe()는 async generator가 아니라 Queue를 반환함 =====
    queue = job_event_hub.subscribe()

    async def event_generator():
        try:
            # ===== [ADD] 브라우저 재연결 간격 안내 =====
            yield "retry: 3000\n\n"

            # ===== [ADD] 연결 확인용 SSE comment =====
            yield ": connected\n\n"

            while True:
                if await request.is_disconnected():
                    break

                try:
                    # ===== [IMPORTANT]
                    # Queue에 publish된 SSE 메시지가 들어올 때까지 await 대기하는 것.
                    message = await asyncio.wait_for(queue.get(), timeout=15)
                    yield message

                except asyncio.TimeoutError:
                    # ===== [ADD]
                    # 연결 유지용 heartbeat.
                    yield ": heartbeat\n\n"

        except asyncio.CancelledError:
            # Server shutdown or client disconnect while the SSE stream is open.
            return

        finally:
            # ===== [ADD] 브라우저 연결 종료 시 subscriber 제거 =====
            job_event_hub.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("", response_model=list[JobResponse])
def get_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return job_service.get_jobs(db, current_user.id)


@router.get("/page", response_model=JobPageResponse)
def get_jobs_page(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return job_service.get_jobs_page(db, page, size, current_user.id)




@router.get("/{job_id}/download")
def get_job_download(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = job_service.get_job(db, job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.download_url:
        raise HTTPException(status_code=409, detail="Excel file is not ready")

    # ===== [FIX] 서명 URL 재발급 =====
    # cloud 모드의 GCS 서명 URL은 1시간 만료라, DB에 저장해 둔 값을 그대로 주면
    # 생성 후 1시간 뒤 다운로드가 403으로 실패한다. 요청 시점에 object_name으로
    # 새 서명 URL을 발급해 항상 유효한 링크를 돌려준다.
    # (local 모드의 download_url은 만료 없는 정적 경로이므로 그대로 사용)
    if settings.is_cloud and job.gcs_object_name:
        download_url = get_storage_client().create_download_url(job.gcs_object_name)
    else:
        download_url = job.download_url

    return {
        "download_url": download_url,
    }


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = job_service.get_job(db, job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# @router.get(
#     "/events",
#     include_in_schema=False,
#     response_class=StreamingResponse,
# )
# async def job_events(request: Request) -> StreamingResponse:
#     """
#     브라우저와 장기 HTTP 연결을 맺고 Job 이벤트를 전달한다.
#     """

#     async def event_stream():
#         queue = job_event_hub.subscribe()

#         try:
#             # 브라우저의 재연결 간격을 3초로 설정한다.
#             yield "retry: 3000\n\n"

#             while True:
#                 if await request.is_disconnected():
#                     break

#                 try:
#                     # 이벤트가 없으면 coroutine은 잠들어 있는다.
#                     # queue를 반복 조회하는 polling이 아니다.
#                     message = await asyncio.wait_for(
#                         queue.get(),
#                         timeout=15,
#                     )
#                     yield message

#                 except asyncio.TimeoutError:
#                     # SSE comment다. 애플리케이션 상태를 조회하지 않는다.
#                     # 프록시가 유휴 연결을 종료하지 않게 하는 용도다.
#                     yield ": heartbeat\n\n"

#         except asyncio.CancelledError:
#             # 서버 종료 또는 클라이언트 연결 종료
#             raise

#         finally:
#             job_event_hub.unsubscribe(queue)

#     return StreamingResponse(
#         event_stream(),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache, no-transform",
#             "Connection": "keep-alive",
#             "X-Accel-Buffering": "no",
#         },
#     )
