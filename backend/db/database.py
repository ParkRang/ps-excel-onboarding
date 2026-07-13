from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

from sqlalchemy.orm import sessionmaker

from core.config import Settings

settings = Settings()

# Cloud SQL Or Local
if settings.DB_HOST.startswith("/cloudsql/"):
    DATABASE_URL = (
        f"postgresql+psycopg://"
        f"{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@/{settings.DB_NAME}"
        f"?host={settings.DB_HOST}"
    )
else:
    DATABASE_URL = (
        f"postgresql+psycopg://"
        f"{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )

# ===== DB 하드닝 =====
# connect_timeout: 연결 수립이 매달리지 않게. statement_timeout(ms): 옵트인 시
# 서버측에서 폭주 쿼리를 중단. 둘 다 libpq 파라미터로 psycopg에 전달된다.
connect_args = {"connect_timeout": settings.DB_CONNECT_TIMEOUT_SECONDS}
if settings.DB_STATEMENT_TIMEOUT_MS > 0:
    connect_args["options"] = f"-c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    # 사용 직전 커넥션 유효성 검사 → Cloud SQL이 끊은 stale 커넥션 재사용 방지
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

class Base(DeclarativeBase):

    pass