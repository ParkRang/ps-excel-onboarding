from datetime import datetime

from pydantic import BaseModel, ConfigDict

from common.enums.job_status import JobStatus


class JobResponse(BaseModel):

    id: int

    status: JobStatus

    progress: int

    requested_at: datetime

    started_at: datetime | None

    completed_at: datetime | None

    file_path: str | None

    error_message: str | None

    model_config = ConfigDict(
        from_attributes=True
    )