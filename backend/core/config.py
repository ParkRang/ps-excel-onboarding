import os
from dotenv import load_dotenv

load_dotenv() # .env 파일 로드

class Settings:
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = os.getenv('DB_PORT')
    DB_NAME = os.getenv('DB_NAME')
    
    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
    GCP_LOCATION = os.getenv(
        "GCP_LOCATION"
    )
    GCP_TASKS_QUEUE_NAME = os.getenv(
        "GCP_TASKS_QUEUE_NAME"
    )

    BACKEND_URL = os.getenv("BACKEND_URL")

    TASKS_SERVICE_ACCOUNT_EMAIL = os.getenv(
        "TASKS_SERVICE_ACCOUNT_EMAIL"
    )

    GCP_STORAGE_BUCKET_NAME = os.getenv(
        "GCP_STORAGE_BUCKET_NAME"
    )

    TASKS_SERVICE_ACCOUNT_EMAIL = os.getenv(
        "TASKS_SERVICE_ACCOUNT_EMAIL"
    )

    DISCORD_WEBHOOK_URL = os.getenv(
        "DISCORD_WEBHOOK_URL"
    )
