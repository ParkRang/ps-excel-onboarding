"""인증: /create API 키 + /tasks/excel OIDC 게이팅."""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import core.auth as auth
from core.auth import require_api_key, verify_cloud_task_oidc


@pytest.fixture
def api_key_client():
    app = FastAPI()

    @app.post("/create")
    def create(_: None = Depends(require_api_key)):
        return {"ok": True}

    return TestClient(app)


def test_no_key_configured_allows(monkeypatch, api_key_client):
    monkeypatch.setattr(auth.settings, "API_KEY", None)
    assert api_key_client.post("/create").status_code == 200


def test_key_configured_requires_header(monkeypatch, api_key_client):
    monkeypatch.setattr(auth.settings, "API_KEY", "s3cr3t")
    assert api_key_client.post("/create").status_code == 401


def test_wrong_key_rejected(monkeypatch, api_key_client):
    monkeypatch.setattr(auth.settings, "API_KEY", "s3cr3t")
    r = api_key_client.post("/create", headers={"X-API-Key": "nope"})
    assert r.status_code == 401


def test_correct_key_accepted(monkeypatch, api_key_client):
    monkeypatch.setattr(auth.settings, "API_KEY", "s3cr3t")
    r = api_key_client.post("/create", headers={"X-API-Key": "s3cr3t"})
    assert r.status_code == 200


# ---- OIDC 콜백 ----

@pytest.fixture
def oidc_client():
    app = FastAPI()

    @app.post("/tasks/excel")
    def cb(_: None = Depends(verify_cloud_task_oidc)):
        return {"ok": True}

    return TestClient(app)


def test_local_mode_skips_oidc(monkeypatch, oidc_client):
    monkeypatch.setattr(auth.settings, "INFRA_MODE", "local")
    monkeypatch.setattr(auth.settings, "VERIFY_TASK_OIDC", True)
    assert oidc_client.post("/tasks/excel").status_code == 200


def test_cloud_missing_token_rejected(monkeypatch, oidc_client):
    monkeypatch.setattr(auth.settings, "INFRA_MODE", "cloud")
    monkeypatch.setattr(auth.settings, "VERIFY_TASK_OIDC", True)
    assert oidc_client.post("/tasks/excel").status_code == 401


def test_cloud_invalid_token_rejected(monkeypatch, oidc_client):
    monkeypatch.setattr(auth.settings, "INFRA_MODE", "cloud")
    monkeypatch.setattr(auth.settings, "VERIFY_TASK_OIDC", True)
    r = oidc_client.post("/tasks/excel", headers={"Authorization": "Bearer bad-token"})
    assert r.status_code == 401


def test_cloud_toggle_off_skips(monkeypatch, oidc_client):
    monkeypatch.setattr(auth.settings, "INFRA_MODE", "cloud")
    monkeypatch.setattr(auth.settings, "VERIFY_TASK_OIDC", False)
    assert oidc_client.post("/tasks/excel").status_code == 200
