from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base
from common.enums.job_status import JobStatus
from common.utils.now import now


class Job(Base):
    __tablename__ = "jobs"

    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_jobs_progress"),
        CheckConstraint("processed_rows >= 0", name="ck_jobs_processed_rows"),
        CheckConstraint("total_rows >= 0", name="ck_jobs_total_rows"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=20),
        nullable=False,
        default=JobStatus.PENDING,
        index=True,
    )

    progress: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    processed_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    total_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=now,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )

    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )

    duration_seconds: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    gcs_object_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    gcs_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    task_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        unique=True,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    download_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
