from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from common.enums.job_status import JobStatus


class JobResponse(BaseModel):

    job_id: int

    status: JobStatus

    progress: int
    processed_rows: int
    total_rows: int

    requested_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    failed_at: Optional[datetime] = None

    duration_seconds: Optional[float] = None

    gcs_object_name: Optional[str] = None

    gcs_url : Optional[str] = None

    error_message: Optional[str] = None

    attempt_count: int

    class Config:
        from_attributes = True