import json

from google.cloud import tasks_v2
from google.protobuf import duration_pb2

from core.config import Settings


class CloudTaskService:
    REQUIRED_SETTINGS = (
        "GCP_PROJECT_ID",
        "GCP_LOCATION",
        "GCP_TASKS_QUEUE_NAME",
        "BACKEND_URL",
        "TASKS_SERVICE_ACCOUNT_EMAIL",
    )

    def __init__(self):
        self.settings = Settings()
        self.client = None

    def enqueue(self, job_id: int) -> str:
        self._validate_settings()

        if self.client is None:
            self.client = tasks_v2.CloudTasksClient()

        queue_path = self.client.queue_path(
            self.settings.GCP_PROJECT_ID,
            self.settings.GCP_LOCATION,
            self.settings.GCP_TASKS_QUEUE_NAME,
    
    )

        worker_url = (
            f"{self.settings.BACKEND_URL}"
            "/tasks/excel"
        )

        payload = {
            "job_id": job_id,
        }

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": worker_url,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": json.dumps(payload).encode("utf-8"),
                "oidc_token": {
                    "service_account_email": (
                        self.settings
                        .TASKS_SERVICE_ACCOUNT_EMAIL
                    ),
                    "audience": self.settings.BACKEND_URL,
                },
            },
            "dispatch_deadline": duration_pb2.Duration(
                seconds=1800,
            ),
        }

        created_task = self.client.create_task(
            parent=queue_path,
            task=task,
        )

        return created_task.name

    def _validate_settings(self) -> None:
        missing = [
            name
            for name in self.REQUIRED_SETTINGS
            if not getattr(self.settings, name)
        ]
        if missing:
            raise RuntimeError(
                "Missing cloud task settings: "
                + ", ".join(missing)
            )
