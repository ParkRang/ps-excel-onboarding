
from core.config import Settings
from webhook.webhook_response import WebhookResponse
from datetime import datetime

import requests
import logging

logger = logging.getLogger(__name__)

class WebhookService:
    def __init__(self):
        self.settings = Settings()

        self.webhook_url = self.settings.DISCORD_WEBHOOK_URL

    def send_success_message(
        self,
        job_id: int,
        completed_at: datetime,
        download_url: str,
    ):
        payload = {"content": (
            f"Excel 생성 완료\n"
            f"Job ID: {job_id}\n"
            f"Completed At: {completed_at}\n"
            f"Download URL: {download_url}"
        )
    }
    
        response = requests.post(
            self.webhook_url,
            json=payload,
        )

        logger.info(f"Webhook response: {response.status_code}")
        response.raise_for_status()
    
    def send_failure_message(
        self,
        job_id: int,
        error_message: str,
    ):
        payload = {"content": (
            f"Excel 생성 실패\n"
            f"Job ID: {job_id}\n"
            f"Error Message: {error_message}"
        )
    }
    
        response = requests.post(
            self.webhook_url,
            json=payload,
        )

        logger.info(f"Webhook response: {response.status_code}")
        response.raise_for_status()

