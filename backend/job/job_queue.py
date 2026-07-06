from enum import Enum

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class QueueStatus(str, Enum):
    WAITING = "WAITING"
    DISPATCHED = "DISPATCHED"
    PROCESSING = "PROCESSING"


class JobQueue(Base):
    __tablename__ = "job_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[QueueStatus] = mapped_column(
        SqlEnum(QueueStatus, native_enum=False, length=20),
        nullable=False,
        default=QueueStatus.WAITING,
        index=True,
    )
