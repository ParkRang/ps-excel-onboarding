from pydantic import BaseModel, Field


class TaskRequest(BaseModel):

    job_id: int