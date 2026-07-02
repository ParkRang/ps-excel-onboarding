import json

from google.cloud import tasks_v2
from google.protobuf import duration_pb2

from core.config import Settings


class CloudTaskService:

    def __init__(self):
        self.settings = Settings()

    def enqueue(self, job_id: int) -> str:

        # 메서드 실행 시점에 client를 생성합니다.
        client = tasks_v2.CloudTasksClient()

        queue_path = client.queue_path(
            self.settings.GCP_PROJECT_ID,
            self.settings.GCP_LOCATION,
            self.settings.GCP_TASKS_QUEUE,
    
    )

        worker_url = (
            f"{self.settings.BACKEND_URL}"
            "/internal/tasks/export"
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

        created_task = client.create_task(
            parent=queue_path,
            task=task,
        )

        return created_task.name
