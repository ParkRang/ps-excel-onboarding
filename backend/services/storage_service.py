from datetime import timedelta
import logging
from pathlib import Path

import google.auth
from google.auth.transport.requests import Request
from google.cloud import storage

from core.config import Settings

EXCEL_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
logger = logging.getLogger(__name__)


class LocalStorageClient:
    def __init__(self):
        self.settings = Settings()
        self.storage_dir = Path(self.settings.EXCEL_STORAGE_DIR)

    def save(self, local_file_path: str, job_id: int) -> dict:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        target_path = self.storage_dir / f"{job_id}.xlsx"

        if Path(local_file_path) != target_path:
            target_path.write_bytes(Path(local_file_path).read_bytes())

        logger.info("엑셀 파일을 로컬 볼륨에 저장했습니다. job_id=%s path=%s", job_id, target_path)
        return {
            "object_name": str(target_path),
            "download_url": f"{self.settings.EXCEL_DOWNLOAD_PREFIX}/{job_id}",
        }


class GCSClient:
    def __init__(self):
        self.settings = Settings()
        self._validate_settings()
        self.credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self.client = storage.Client(credentials=self.credentials)
        self.bucket_name = self.settings.GCP_STORAGE_BUCKET_NAME
        self.bucket = self.client.bucket(self.bucket_name)

    def upload(self, local_file_path: str, job_id: int) -> dict:
        object_name = f"excels/job_{job_id}.xlsx"
        blob = self.bucket.blob(object_name)
        blob.upload_from_filename(
            local_file_path,
            content_type=EXCEL_MIME_TYPE,
        )

        logger.info(
            "엑셀 파일을 GCS에 업로드했습니다. job_id=%s bucket=%s object=%s",
            job_id,
            self.bucket_name,
            object_name,
        )
        return {
            "object_name": object_name,
            "gcs_url": f"gs://{self.bucket_name}/{object_name}",
            "download_url": self.create_download_url(object_name),
        }

    def create_download_url(self, object_name: str) -> str:
        if not self.credentials.valid:
            self.credentials.refresh(Request())

        blob = self.bucket.blob(object_name)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),
            method="GET",
            service_account_email=self.settings.TASKS_SERVICE_ACCOUNT_EMAIL,
            access_token=self.credentials.token,
            response_disposition=(
                f'attachment; filename="{object_name.rsplit("/", 1)[-1]}"'
            ),
        )


    def _validate_settings(self) -> None:
        missing = [
            name
            for name in (
                "GCP_STORAGE_BUCKET_NAME",
                "TASKS_SERVICE_ACCOUNT_EMAIL",
            )
            if not getattr(self.settings, name)
        ]
        if missing:
            raise RuntimeError(
                "Missing GCS settings: "
                + ", ".join(missing)
            )


def get_storage_client():
    settings = Settings()
    if settings.is_cloud:
        return GCSClient()
    return LocalStorageClient()
