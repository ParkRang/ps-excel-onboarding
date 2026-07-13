"""사용자 인증(JWT) + 사용자별 job 소유권 검증."""
import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from auth.auth_dependencies import get_current_user
from auth.auth_router import router as auth_router
from auth.auth_service import AuthService, EmailAlreadyRegistered, hash_password, verify_password
from common.enums.job_status import JobStatus
from core.config import Settings
from db.session import get_db
from job.job_service import JobService
from user.user import User

auth_service = AuthService()
job_service = JobService()


# ---- 비밀번호 해싱 ----

def test_hash_and_verify():
    h = hash_password("s3cret-password")
    assert h != "s3cret-password"
    assert verify_password("s3cret-password", h)
    assert not verify_password("wrong", h)


# ---- 회원가입 / 인증 (서비스 레벨, SQLite) ----

def test_register_and_duplicate(db):
    user = auth_service.register(db, "  A@Example.com ", "password123")
    assert user.id is not None
    assert user.email == "a@example.com"  # 정규화(trim+lower)
    with pytest.raises(EmailAlreadyRegistered):
        auth_service.register(db, "a@example.com", "password123")


def test_authenticate(db):
    auth_service.register(db, "b@example.com", "password123")
    assert auth_service.authenticate(db, "b@example.com", "password123") is not None
    assert auth_service.authenticate(db, "b@example.com", "wrong") is None
    assert auth_service.authenticate(db, "nobody@example.com", "password123") is None


def test_token_roundtrip(db):
    user = auth_service.register(db, "c@example.com", "password123")
    token = auth_service.create_access_token(user)
    payload = auth_service.decode_token(token)
    assert payload["sub"] == str(user.id)
    assert payload["email"] == "c@example.com"


def test_expired_token_rejected(db, monkeypatch):
    # 만료시간을 음수로 만들어 즉시 만료된 토큰 생성
    monkeypatch.setattr(Settings, "JWT_EXPIRE_MINUTES", -1)
    user = auth_service.register(db, "d@example.com", "password123")
    token = auth_service.create_access_token(user)
    with pytest.raises(jwt.ExpiredSignatureError):
        auth_service.decode_token(token)


# ---- 사용자별 job 소유권 (서비스 레벨) ----

def test_jobs_are_isolated_per_user(db):
    a = auth_service.register(db, "owner-a@example.com", "password123")
    b = auth_service.register(db, "owner-b@example.com", "password123")

    ja1 = job_service.create_export(db, a.id)
    ja2 = job_service.create_export(db, a.id)
    jb1 = job_service.create_export(db, b.id)

    # 목록은 소유자 것만
    a_jobs = {j.id for j in job_service.get_jobs(db, a.id)}
    assert a_jobs == {ja1.id, ja2.id}
    assert {j.id for j in job_service.get_jobs(db, b.id)} == {jb1.id}

    # 단건 조회: 남의 job은 None
    assert job_service.get_job(db, jb1.id, a.id) is None
    assert job_service.get_job(db, ja1.id, a.id) is not None

    # 페이지 요약도 소유자 기준
    page_a = job_service.get_jobs_page(db, 1, 20, a.id)
    assert page_a["total"] == 2
    assert len(page_a["items"]) == 2


# ---- 엔드포인트 (TestClient + get_db 오버라이드) ----

@pytest.fixture
def client(SessionFactory):
    app = FastAPI()
    app.include_router(auth_router)

    @app.get("/protected")
    def protected(current_user: User = Depends(get_current_user)):
        return {"email": current_user.email}

    def override_get_db():
        s = SessionFactory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_register_login_me_flow(client):
    # 회원가입
    r = client.post("/auth/register", json={"email": "flow@example.com", "password": "password123"})
    assert r.status_code == 201
    assert r.json()["email"] == "flow@example.com"

    # 중복 → 409
    assert client.post("/auth/register", json={"email": "flow@example.com", "password": "password123"}).status_code == 409

    # 로그인 → 토큰
    r = client.post("/auth/login", json={"email": "flow@example.com", "password": "password123"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    # 토큰 없이 보호 라우트 → 401
    assert client.get("/protected").status_code == 401

    # 잘못된 토큰 → 401
    assert client.get("/protected", headers={"Authorization": "Bearer bad"}).status_code == 401

    # 올바른 토큰 → 200
    r = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["email"] == "flow@example.com"


def test_login_wrong_password_401(client):
    client.post("/auth/register", json={"email": "wp@example.com", "password": "password123"})
    r = client.post("/auth/login", json={"email": "wp@example.com", "password": "nope"})
    assert r.status_code == 401
