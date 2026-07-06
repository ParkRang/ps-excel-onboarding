from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from common.enums.job_status import JobStatus


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: int = Field(validation_alias="id")
    status: JobStatus
    progress: int
    processed_rows: int
    total_rows: int
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    duration_seconds: float | None = None
    gcs_object_name: str | None = None
    gcs_url: str | None = None
    download_url: str | None = None
    error_message: str | None = None
    task_name: str | None = None
    attempt_count: int


class JobPageResponse(BaseModel):
    items: list[JobResponse]
    total: int
    active: int
    done: int
    failed: int
    page: int
    size: int
    pages: int
