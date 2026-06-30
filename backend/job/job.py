from zoneinfo import ZoneInfo
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.database import Base
from backend.common.enums.job_status import JobStatus
from backend.common.utils.now import now


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus),
        nullable=False,
        default=JobStatus.PENDING
    )

    progress: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=now
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    file_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    error_message: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True
    )