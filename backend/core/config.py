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

    # 한 job이 최대 몇 번까지 처리(claim)를 시도할지 상한.
    # Cloud Tasks는 at-least-once 재시도라, 영구적으로 실패하는 job이
    # 무한 재시도되는 것을 막는 앱 레벨 안전장치다. (local 모드에서도 동일 적용)
    MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))

    # PROCESSING 상태가 이 시간(초)을 넘도록 갱신되지 않으면 죽은 작업으로 보고
    # 다른 워커가 재선점(리클레임)할 수 있게 한다. 정상 실행이 도중에 탈취되지
    # 않도록 Cloud Tasks dispatch_deadline(1800s) 이상으로 둔다.
    PROCESSING_LEASE_SECONDS = int(os.getenv("PROCESSING_LEASE_SECONDS", "1800"))

    # ===== DB 커넥션 풀/견고성 =====
    # 인스턴스당 풀 크기. 인스턴스 수 × (POOL_SIZE+MAX_OVERFLOW)가 Cloud SQL의
    # max_connections를 넘지 않도록 작게 유지한다.
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "5"))
    # 이 초를 넘긴 커넥션은 폐기(서버측 유휴 타임아웃보다 짧게).
    DB_POOL_RECYCLE_SECONDS = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800"))
    # 연결 수립 자체가 매달리지 않도록 하는 상한(초).
    DB_CONNECT_TIMEOUT_SECONDS = int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "10"))
    # 서버측 statement_timeout(ms). 0이면 비활성(대용량 count 등을 죽이지 않도록
    # 기본 off, 필요 시 옵트인). 켜면 폭주 쿼리가 인스턴스를 무한정 잡는 걸 막는다.
    DB_STATEMENT_TIMEOUT_MS = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "0"))

    # POST /create(export 트리거) 보호용 API 키.
    # 설정되면 요청은 X-API-Key 헤더에 이 값을 담아야 한다.
    # 비어 있으면 인증이 비활성화된다(로컬/온보딩 편의, 시작 시 경고). local/cloud 공통.
    API_KEY = os.getenv("API_KEY") or None

    # Cloud Tasks 콜백(POST /tasks/excel)의 OIDC 토큰을 앱 레벨에서 검증할지 여부.
    # cloud 모드에서만 동작하며, 기본 활성화. Cloud Run을 --no-allow-unauthenticated로
    # 배포했더라도 방어적으로 한 번 더 검증한다. OIDC 셋업 디버깅 시 잠시 끌 수 있게 토글.
    VERIFY_TASK_OIDC = os.getenv("VERIFY_TASK_OIDC", "true").strip().lower() == "true"

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
