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

engine = create_engine(
    DATABASE_URL,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

class Base(DeclarativeBase):

    pass