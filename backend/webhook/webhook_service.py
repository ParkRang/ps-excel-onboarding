import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests

from core.config import Settings


logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="discord-webhook")


class WebhookService:
    def __init__(self):
        self.webhook_url = Settings().DISCORD_WEBHOOK_URL

    def send_success_message(self, job_id: int, completed_at: datetime, download_url: str) -> None:
        executor.submit(
            self._send,
            f"Excel 생성 완료\nJob ID: {job_id}\nCompleted At: {completed_at}\nDownload URL: {download_url}",
        )

    def send_failure_message(self, job_id: int, error_message: str) -> None:
        executor.submit(
            self._send,
            f"Excel 생성 실패\nJob ID: {job_id}\nError Message: {error_message}",
        )

    def _send(self, content: str) -> None:
        if not self.webhook_url:
            return
        try:
            response = requests.post(self.webhook_url, json={"content": content}, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Discord webhook delivery failed")
