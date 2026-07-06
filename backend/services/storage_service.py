from google.cloud import storage

from core.config import Settings


class GCSClient:

    def __init__(self):
        self.settings = Settings()

        self.client = storage.Client()

        self.bucket_name = self.settings.GCP_STORAGE_BUCKET_NAME
        self.bucket = self.client.bucket(self.bucket_name)

    def upload(self, local_file_path: str, job_id: int) -> dict:
        object_name = f"excels/job_{job_id}.xlsx"

        blob = self.bucket.blob(object_name)
        blob.upload_from_filename(
            local_file_path,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        gcs_url = f"gs://{self.bucket_name}/{object_name}"

        download_url = blob.public_url
        # download_url = blob.generate_signed_url(
        #     version="v4",
        #     expiration=timedelta(hours=1),
        #     method="GET",
        # )

        return {
            "object_name": object_name,
            "gcs_url": gcs_url,
            "download_url": download_url,
        }
