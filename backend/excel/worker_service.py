from core.logging import event_logger
from excel.excel_service import ExcelService
from job.job_service import JobService


class WorkerBusyError(Exception):
    pass


class WorkerService:
    """Process the queue head, then dispatch exactly one next Cloud Task."""

    def __init__(self):
        self.jobs = JobService()
        self.excel = ExcelService()
        self.storage = None

    def process_queued_job(self, requested_job_id: int) -> int:
        event_logger("Cloud Task Excel processing started", job_id=requested_job_id)
        self.excel.create_excel(requested_job_id)
        event_logger("Cloud Task Excel processing completed", job_id=requested_job_id)
        return requested_job_id
