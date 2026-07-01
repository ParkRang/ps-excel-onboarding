from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

from sqlalchemy.orm import sessionmaker

from core.config import Settings

settings = Settings()

DATABASE_URL = (
    f"postgresql+psycopg://"
    f"{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

engine = create_engine(
    DATABASE_URL,
    echo=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

class Base(DeclarativeBase):

    pass