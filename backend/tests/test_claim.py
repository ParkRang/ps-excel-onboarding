"""job 상태 기계 = 이 서비스 안정성의 핵심.

atomic claim + 리스 리클레임 + 재시도 상한을 실제 프로덕션 코드
(ExcelService._claim_job)와 실제 claim SQL로 검증한다.
"""
import excel.excel_service as es
from common.enums.job_status import JobStatus

svc = es.ExcelService()
MAX = es.settings.MAX_ATTEMPTS
LEASE = es.settings.PROCESSING_LEASE_SECONDS


def test_pending_is_claimed(db, make_job):
    job = make_job(status=JobStatus.PENDING)
    assert svc._claim_job(db, job.id) == 1
    db.refresh(job)
    assert job.status == JobStatus.PROCESSING
    assert job.attempt_count == 1
    assert job.started_at is not None


def test_failed_is_reclaimed_for_retry(db, make_job):
    job = make_job(status=JobStatus.FAILED, attempt_count=1)
    assert svc._claim_job(db, job.id) == 1
    db.refresh(job)
    assert job.status == JobStatus.PROCESSING
    assert job.attempt_count == 2  # 재시도마다 증가


def test_processing_within_lease_is_not_stolen(db, make_job):
    # 방금 시작된(리스 유효) PROCESSING → 중복 전달로 와도 선점 실패
    job = make_job(status=JobStatus.PROCESSING, attempt_count=1, started_age_seconds=5)
    assert svc._claim_job(db, job.id) == 0
    db.refresh(job)
    assert job.attempt_count == 1  # 그대로


def test_stale_processing_is_reclaimed(db, make_job):
    # 리스를 넘긴 PROCESSING(죽은 워커가 남긴 좀비) → 재선점됨
    job = make_job(status=JobStatus.PROCESSING, attempt_count=1,
                   started_age_seconds=LEASE + 60)
    assert svc._claim_job(db, job.id) == 1
    db.refresh(job)
    assert job.attempt_count == 2
    # 재선점하면 started_at이 갱신되어 곧바로 다시 탈취되지 않는다
    assert svc._claim_job(db, job.id) == 0


def test_retry_cap_blocks_claim(db, make_job):
    # attempt_count가 상한이면 더 이상 선점하지 않음 → 영구 실패 고정
    job = make_job(status=JobStatus.FAILED, attempt_count=MAX)
    assert svc._claim_job(db, job.id) == 0
    db.refresh(job)
    assert job.status == JobStatus.FAILED


def test_stale_processing_at_cap_is_not_reclaimed(db, make_job):
    # 좀비이더라도 상한에 도달했으면 재선점 안 됨
    job = make_job(status=JobStatus.PROCESSING, attempt_count=MAX,
                   started_age_seconds=LEASE + 60)
    assert svc._claim_job(db, job.id) == 0


def test_done_is_never_claimed(db, make_job):
    job = make_job(status=JobStatus.DONE, attempt_count=1,
                   started_age_seconds=LEASE + 60, progress=100)
    assert svc._claim_job(db, job.id) == 0
    db.refresh(job)
    assert job.status == JobStatus.DONE
