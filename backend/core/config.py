import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(PROJECT_ROOT / ".env")

class Settings:
    INFRA_MODE = os.getenv("INFRA_MODE", "local").strip().lower()

    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = os.getenv('DB_PORT')
    DB_NAME = os.getenv('DB_NAME')
    
    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
    GCP_LOCATION = os.getenv("GCP_LOCATION")
    GCP_TASKS_QUEUE_NAME = os.getenv("GCP_TASKS_QUEUE_NAME")
    BACKEND_URL = os.getenv("BACKEND_URL")
    TASKS_SERVICE_ACCOUNT_EMAIL = os.getenv("TASKS_SERVICE_ACCOUNT_EMAIL")
    GCP_STORAGE_BUCKET_NAME = os.getenv("GCP_STORAGE_BUCKET_NAME")

    DISCORD_WEBHOOK_URL = os.getenv(
        "DISCORD_WEBHOOK_URL"
    )
    EXCEL_STORAGE_DIR = os.getenv("EXCEL_STORAGE_DIR", "files")
    EXCEL_DOWNLOAD_PREFIX = os.getenv("EXCEL_DOWNLOAD_PREFIX", "/files")

    @property
    def is_cloud(self) -> bool:
        return self.INFRA_MODE == "cloud"

    @property
    def is_local(self) -> bool:
        return self.INFRA_MODE == "local"

    def validate_infra_mode(self) -> None:
        if self.INFRA_MODE not in {"cloud", "local"}:
            raise RuntimeError(
                "INFRA_MODE must be either 'cloud' or 'local'. "
                f"current={self.INFRA_MODE!r}"
            )
