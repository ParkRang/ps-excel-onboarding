from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class WebhookResponse(BaseModel):
    job_id: int
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = None

