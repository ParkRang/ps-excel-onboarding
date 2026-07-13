"""공용 pytest 픽스처.

실제 Postgres 없이도 상태 기계/엑셀 생성 흐름을 검증할 수 있도록 SQLite
인메모리 DB에 실제 모델 메타데이터를 그대로 올린다.

주의: SQLite와 Postgres는 락/격리수준이 달라, 진짜 동시성(경합) 검증은
Postgres(testcontainers)로 별도 확인이 필요하다. 여기서는 상태 전이 로직을
검증한다.
"""
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from common.enums.job_status import JobStatus
from common.utils.now import now
from db.database import Base
import job.job  # noqa: F401 - 테이블 메타데이터 등록
import order.order  # noqa: F401 - 테이블 메타데이터 등록
import user.user  # noqa: F401 - 테이블 메타데이터 등록(Job.user_id FK 대상)
from job.job import Job
from order.order import Order


@pytest.fixture
def engine():
    # StaticPool + 단일 커넥션으로 인메모리 DB를 여러 세션이 공유하게 한다.
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def SessionFactory(engine):
    return sessionmaker(bind=engine, autoflush=False)


@pytest.fixture
def db(SessionFactory):
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


# ---- job 생성 헬퍼 ----

@pytest.fixture
def make_job(db):
    def _make(status=JobStatus.PENDING, attempt_count=0, started_age_seconds=None,
              progress=0):
        started_at = None
        if started_age_seconds is not None:
            started_at = now() - timedelta(seconds=started_age_seconds)
        job = Job(
            status=status,
            progress=progress,
            attempt_count=attempt_count,
            started_at=started_at,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    return _make


@pytest.fixture
def seed_orders(db):
    def _seed(n):
        db.add_all([
            Order(
                user_name=f"user{i}",
                product_name="product",
                category="cat",
                amount=100,
                status="PAID",
            )
            for i in range(1, n + 1)
        ])
        db.commit()
    return _seed
