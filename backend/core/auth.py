import hmac
import logging

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from core.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()

# Google 공개 인증서로 ID 토큰을 검증할 때 쓰는 전송 객체(재사용).
_google_request = google_requests.Request()

API_KEY_HEADER_NAME = "X-API-Key"

# auto_error=False: 헤더가 없어도 여기서 바로 403을 던지지 않고,
# API_KEY 미설정 시 인증을 건너뛸 수 있도록 판단을 dependency 안에서 한다.
_api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def require_api_key(provided: str | None = Security(_api_key_header)) -> None:
    """API_KEY가 설정된 경우에만 X-API-Key 헤더를 검증한다.

    - API_KEY 미설정: 인증 비활성화(로컬/온보딩 편의). 통과.
    - API_KEY 설정:   헤더 값이 정확히 일치해야 통과, 아니면 401.
    타이밍 공격을 피하기 위해 상수시간 비교(hmac.compare_digest)를 쓴다.
    """
    expected = settings.API_KEY
    if not expected:
        return

    if provided is None or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": API_KEY_HEADER_NAME},
        )


def verify_cloud_task_oidc(request: Request) -> None:
    """Cloud Tasks 콜백(POST /tasks/excel)의 OIDC ID 토큰을 검증한다.

    Cloud Tasks는 task 생성 시 넣어둔 service_account_email로 서명된 ID 토큰을
    Authorization: Bearer 헤더에 담아 콜백을 보낸다. 이 함수는
      1) 토큰이 Google이 서명한 유효한 ID 토큰인지
      2) audience 가 우리 BACKEND_URL 과 일치하는지
      3) 발급 주체(email)가 기대한 서비스계정과 일치하고 검증되었는지
    를 확인한다. 검증 실패 시 401/403 → Cloud Tasks가 재시도한다.

    - local 모드에서는 이 엔드포인트를 쓰지 않으므로 통과시킨다.
    - VERIFY_TASK_OIDC=false 로 잠시 끌 수 있다(디버깅용).
    """
    if not settings.is_cloud or not settings.VERIFY_TASK_OIDC:
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    token = auth_header.split(" ", 1)[1].strip()

    try:
        claims = google_id_token.verify_oauth2_token(
            token,
            _google_request,
            audience=settings.BACKEND_URL,
        )
    except Exception as error:  # 서명/만료/audience 불일치 등
        logger.warning("Cloud Tasks OIDC 검증 실패: %s", error)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OIDC token",
        ) from error

    expected_sa = settings.TASKS_SERVICE_ACCOUNT_EMAIL
    if expected_sa and claims.get("email") != expected_sa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unexpected token issuer",
        )
    if not claims.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token email not verified",
        )
