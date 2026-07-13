"""다운로드 서명 URL 재발급 분기 (job_router.get_job_download)."""
import pytest
from fastapi import HTTPException

import job.job_router as jr


class _FakeJob:
    def __init__(self, download_url="/files/5", gcs_object_name="excels/job_5.xlsx"):
        self.download_url = download_url
        self.gcs_object_name = gcs_object_name


class _FakeStorage:
    def create_download_url(self, object_name):
        return f"https://signed-FRESH/{object_name}"


@pytest.fixture
def stub_get_job(monkeypatch):
    def _set(job):
        monkeypatch.setattr(jr.job_service, "get_job", lambda db, jid: job)
    return _set


def test_local_returns_stored_url(monkeypatch, stub_get_job):
    monkeypatch.setattr(jr.settings, "INFRA_MODE", "local")
    stub_get_job(_FakeJob())
    assert jr.get_job_download(5, db=None)["download_url"] == "/files/5"


def test_cloud_regenerates_signed_url(monkeypatch, stub_get_job):
    monkeypatch.setattr(jr.settings, "INFRA_MODE", "cloud")
    monkeypatch.setattr(jr, "get_storage_client", lambda: _FakeStorage())
    stub_get_job(_FakeJob())
    url = jr.get_job_download(5, db=None)["download_url"]
    assert url == "https://signed-FRESH/excels/job_5.xlsx"


def test_cloud_without_object_name_falls_back(monkeypatch, stub_get_job):
    monkeypatch.setattr(jr.settings, "INFRA_MODE", "cloud")
    stub_get_job(_FakeJob(gcs_object_name=None))
    assert jr.get_job_download(5, db=None)["download_url"] == "/files/5"


def test_missing_job_returns_404(monkeypatch, stub_get_job):
    stub_get_job(None)
    with pytest.raises(HTTPException) as exc:
        jr.get_job_download(5, db=None)
    assert exc.value.status_code == 404


def test_not_ready_returns_409(monkeypatch, stub_get_job):
    stub_get_job(_FakeJob(download_url=None))
    with pytest.raises(HTTPException) as exc:
        jr.get_job_download(5, db=None)
    assert exc.value.status_code == 409
