# CLAUDE.md

이 문서는 Claude Code(claude.ai/code)와 새 개발자가 이 저장소에서 작업할 때 참고하는
가이드입니다. **한국어로 작성**되어 있으며, 실제 코드 동작과 일치하도록 유지합니다.

## 개요

비동기 Excel export 서비스입니다. PostgreSQL의 `orders` 행을 읽어 `.xlsx`로 **스트리밍**
생성하고, 파일을 저장한 뒤, 진행률을 **SSE**로 브라우저에 실시간 전송합니다. React
프론트엔드가 job을 트리거하고 상태를 실시간 표시하며, 완료/실패 시 **Discord 웹훅**으로
알립니다.

---

## 아키텍처 — INFRA_MODE가 중심 추상화

거의 모든 백엔드 동작이 `Settings.INFRA_MODE`(`local` | `cloud`)로 분기합니다.
`Settings.is_local` / `Settings.is_cloud`로 판별하며, `excel/`·`services/`·`db/`를
건드리기 전에 반드시 이 표를 이해해야 합니다.

| 관심사 | `local` | `cloud` |
| --- | --- | --- |
| 작업 큐 | 인프로세스 `asyncio.PriorityQueue` + 백그라운드 `worker_loop`(`main.lifespan`에서 시작) | Google Cloud Tasks → `POST /tasks/excel` HTTP 콜백 |
| 파일 저장 | `LocalStorageClient` → 로컬 볼륨, `GET /files/{job_id}`로 서빙 | `GCSClient` → GCS 업로드 + v4 서명 다운로드 URL |
| DB 연결 | TCP host:port | `DB_HOST`가 `/cloudsql/`로 시작하면 Cloud SQL 유닉스 소켓 |
| Excel 임시 dir | `EXCEL_STORAGE_DIR` | 시스템 temp, 업로드 후 삭제 |

디스패치 지점은 두 곳: `get_storage_client()`(`services/storage_service.py`)와
`ExcelService.enqueue_job`(`excel/excel_service.py`). **기능을 추가할 때는 두 모드를 모두
구현**해야 다른 환경이 조용히 깨지지 않습니다.

### 동시성 모델
- `create_excel`은 CPU+DB 무거운 작업이라 **항상 `asyncio.to_thread`로 워커 스레드에서**
  실행합니다(이벤트 루프를 막지 않기 위함). 조회 엔드포인트는 sync `def`라 FastAPI
  스레드풀에서 처리되어, export 중에도 조회가 멈추지 않습니다(동시성).
- 단, GIL/코어 한계로 **CPU 병렬은 아닙니다.** 인스턴스당 export는 1개
  (local: 단일 `worker_loop`, cloud: `task_router`의 `asyncio.Semaphore(1)`).
  처리량이 필요하면 Cloud Tasks가 여러 인스턴스로 분배하는 **수평 확장**이 답입니다.

---

## 프로젝트 구조

```
backend/
  main.py                  # FastAPI 앱, lifespan(worker/SSE 허브 기동), create_all
  core/
    config.py              # Settings — 모든 env 설정(INFRA_MODE, DB, GCP, 인증 등)
    auth.py                # require_api_key(/create), verify_cloud_task_oidc(/tasks)
    logging.py             # 로거 설정 및 단계별 로거
  db/
    database.py            # engine(하드닝 적용), SessionLocal, Base
    session.py             # get_db 의존성(요청 스코프 세션)
  excel/
    excel_router.py        # POST /create, GET /files/{job_id}
    excel_service.py       # 핵심: _claim_job, create_excel, enqueue_job, worker_loop
    worker_service.py      # cloud 콜백에서 create_excel 호출 래퍼
  job/
    job.py                 # Job 모델
    job_router.py          # GET /jobs, /jobs/page, /jobs/{id}, /{id}/download, /events
    job_service.py         # create_export, 조회/페이지네이션
    job_response.py        # JobResponse, JobPageResponse (응답 스키마)
    job_events.py          # JobEventHub (SSE 팬아웃)
  order/order.py           # Order 모델(export 원본)
  task/
    task_router.py         # POST /tasks/excel (Cloud Tasks 콜백)
    task_service.py        # CloudTaskService (Cloud Tasks 등록)
    task_request.py        # TaskRequest 스키마
  webhook/webhook_service.py  # Discord 성공/실패 알림
  services/storage_service.py # LocalStorageClient / GCSClient
  common/
    enums/job_status.py    # PENDING/PROCESSING/DONE/FAILED
    utils/now.py           # now() — 타임스탬프는 반드시 이걸 사용
  tests/                   # pytest 스위트(상태기계/create_excel/인증/다운로드/스트리밍)

frontend/src/
  main.jsx                 # 엔트리
  App.jsx                  # SPA 전체(컴포넌트 Progress / DownloadLink / App)
  api/jobs.js              # REST 클라이언트(request 래퍼, X-API-Key 주입)
```

- 도메인별 패키지는 `_router`(HTTP) / `_service`(로직) / 모델로 분리합니다.
- 백엔드 import는 **`backend/` 루트 기준 절대경로**(`from job.job import Job`)라,
  프로세스를 반드시 `backend/`를 CWD로 실행해야 합니다.

---

## 요청 → export 흐름

1. `POST /create`(`excel/excel_router.py`) → `JobService.create_export`가 Job(`PENDING`)
   삽입 → `ExcelService.enqueue_job`이 라우팅(큐 vs Cloud Tasks). cloud면 `task_name`을
   세팅하고, 라우터가 이어서 commit해 영속화합니다.
2. 실제 작업은 `ExcelService.create_excel(job_id)` — `asyncio.to_thread`로 실행되며
   **자체 `SessionLocal()`**을 엽니다(요청 세션을 넘기면 안 됨).
3. 첫 단계는 **원자적 claim**(`ExcelService._claim_job`). 단일 UPDATE로 `PROCESSING`을
   선점하며, 아래 세 규칙이 합쳐져 있습니다 — **여기를 수정하면 `tests/test_claim.py`가
   회귀 안전망입니다.**
   - **중복 방지**: `status IN (PENDING, FAILED)`만 선점(Cloud Tasks at-least-once 대비).
     `rowcount=0`이면 다른 워커가 이미 처리 중 → 건너뜀.
   - **좀비 리클레임**: 리스(`PROCESSING_LEASE_SECONDS`)를 넘긴 `PROCESSING`도 선점 대상
     (인스턴스가 export 도중 죽어 묶인 job 복구).
   - **재시도 상한**: `attempt_count < MAX_ATTEMPTS`일 때만 선점(영구 실패 무한 재시도 방지).
4. `MAX_CHUNK_SIZE`(5000)씩 **keyset 페이징**(`WHERE id > last_id`, 컬럼만 select)으로
   읽습니다. OFFSET이 아니라 keyset이라 대용량에서 선형이고 정합성도 좋습니다. 진행률은
   `PROGRESS_COMMIT_EVERY`(4)페이지마다 저장·SSE 발행(99에서 캡).
5. 쓰기는 **xlsxwriter `constant_memory`**(상수 메모리 스트리밍). 성공 시 upload/save →
   `DONE`/`progress=100`/`download_url`/성공 웹훅. 예외 시 rollback → `FAILED`/에러 웹훅/re-raise.

`task/task_router.py`는 Cloud Tasks 콜백을 `Semaphore(1)`로 감싸 인스턴스당 1개 export만
돌리고, non-2xx 응답으로 Cloud Tasks 재시도를 유도합니다. 콜백은 **OIDC 토큰을 검증**합니다
(`verify_cloud_task_oidc`).

---

## SSE 진행률 (`job/job_events.py`)

`JobEventHub`는 단일 프로세스 push 팬아웃(DB 폴링 없음)입니다. `create_excel`이 워커
스레드에서 돌기 때문에, `publish`는 **호출 스레드에서 ORM 객체를 JSON 문자열로 직렬화**한 뒤
`loop.call_soon_threadsafe`로 메인 루프에 문자열만 넘깁니다. 느린 구독자는 오래된 이벤트를
버립니다. 프론트는 `EventSource('/jobs/events')`로 소비하고, **권위 있는 상태는 REST로
재동기화**합니다. 허브는 `main.lifespan`에서 시작/종료됩니다.

---

## 데이터 모델

- `Job`(`job/job.py`) — export 생명주기, 진행률, 타이밍, 저장 포인터, `attempt_count`.
  상태 enum은 `common/enums/job_status.py`(`PENDING/PROCESSING/DONE/FAILED`).
- `Order`(`order/order.py`) — export 원본 행.

테이블은 시작 시 `Base.metadata.create_all`로 생성합니다. Alembic은 의존성에 있지만
마이그레이션 스크립트는 아직 없어, 모델 변경은 재시작 시 반영됩니다(마이그레이션 아님).
**새 모델은 `main.py`에 import**(`# noqa: F401`)해야 create_all 전에 메타데이터가 등록됩니다.

---

## API 엔드포인트 & 응답 형식

| 메서드/경로 | 설명 | 응답(성공) |
| --- | --- | --- |
| `POST /create` | export job 생성·큐잉 (API 키 필요 시) | `{"status":"accepted","message":...,"job_id":int}` |
| `GET /jobs` | 전체 job 목록 | `JobResponse[]` |
| `GET /jobs/page?page&size` | 페이지네이션 + 요약 | `JobPageResponse` |
| `GET /jobs/{id}` | 단건 조회 | `JobResponse` |
| `GET /jobs/{id}/download` | 다운로드 URL(cloud는 매번 재발급) | `{"download_url":str}` |
| `GET /jobs/events` | SSE 스트림 | `text/event-stream` |
| `GET /files/{id}` | local 파일 서빙 | xlsx 파일 |
| `POST /tasks/excel` | Cloud Tasks 콜백(OIDC 검증) | `{"status":"ok","requested_job_id":...,"processed_job_id":...}` |

`JobResponse` 필드: `job_id`(모델 `id`의 alias), `status`, `progress`, `processed_rows`,
`total_rows`, `requested_at`, `started_at`, `completed_at`, `failed_at`,
`duration_seconds`(소수 2자리), `gcs_object_name`, `gcs_url`, `download_url`,
`error_message`, `task_name`, `attempt_count`.

`JobPageResponse`: `items`, `total`, `active`, `done`, `failed`, `page`, `size`, `pages`.

---

## 에러 처리

- 백엔드는 FastAPI `HTTPException`을 던지며, 응답 형식은 **`{"detail": "..."}`** 입니다.
  주요 코드: `401`(인증 실패), `404`(job/파일 없음), `409`(파일 아직 준비 안 됨),
  `502`(enqueue 실패), `503`(worker busy → Cloud Tasks 재시도).
- `create_excel`은 예외 시 rollback → `FAILED` 저장 → 에러 웹훅 → **re-raise**하여 cloud
  콜백이 non-2xx로 응답하게 합니다(재시도 유도). 단 재시도는 `MAX_ATTEMPTS`에서 멈춥니다.
- 프론트(`api/jobs.js`)는 에러 본문에서 `detail || message`를 꺼내 사용자 메시지로 씁니다.

---

## 인증

- `POST /create` → `require_api_key`(`core/auth.py`). `API_KEY`가 설정되면 요청은
  `X-API-Key` 헤더에 그 값을 보내야 합니다(상수시간 비교). 미설정 시 인증 비활성(시작 시 경고).
  프론트는 `VITE_API_KEY`가 있으면 헤더로 전송합니다.
- `POST /tasks/excel` → `verify_cloud_task_oidc`. cloud 모드에서 Cloud Tasks가 보낸 OIDC
  토큰을 검증(서명, audience=`BACKEND_URL`, 발급 SA=`TASKS_SERVICE_ACCOUNT_EMAIL`).
  `VERIFY_TASK_OIDC=false`로 잠시 끌 수 있음.

---

## 네이밍 & 컨벤션

- 파일: 도메인별 `xxx_router.py` / `xxx_service.py` / 모델(`xxx.py`).
- 인스턴스: 서비스는 모듈 하단에 싱글턴 인스턴스(`excel_service = ExcelService()`).
- 타임스탬프는 **`common/utils/now.py:now()`** 사용(직접 `datetime.now()` 금지).
- 프론트 API 함수는 동사+명사(`getJobs`, `createExportJob`, `getJobDownloadUrl`).
- 환경변수는 대문자 스네이크(`MAX_ATTEMPTS`), config 클래스 속성으로 노출.

---

## 프론트엔드: 컴포넌트 구조 & 상태 관리

Vite + React SPA이며 라우터 없이 `App.jsx` 하나에 컴포넌트 3개가 있습니다.

- **`App`** — 최상위. 목록/페이지네이션/요약/생성/SSE를 담당.
- **`Progress({ job })`** — 진행률 바(퍼센트, 처리 행 수).
- **`DownloadLink({ job })`** — 다운로드 버튼(자체 `downloading`/`downloadError` 상태 보유).

### 상태 관리
- 전역 상태 라이브러리 없이 **`useState` + `useRef`** 로컬 상태만 사용.
- `App`의 상태: `jobs`, `page`, `pages`, `summary{total,active,done,failed}`, `loading`,
  `error`, `requestingCount`.
- **`useRef`(`requestIdRef`, `jobsRef`, `pageRef`)** 는 SSE 핸들러의 stale closure를 피하기
  위해 최신 값을 참조하는 용도.
- **데이터 흐름**: 최초 `getJobs`(REST)로 로드 → `EventSource('/jobs/events')` SSE로
  실시간 갱신 → 권위 있는 상태는 REST로 재동기화. SSE는 최적화일 뿐, 진실의 원천은 REST.
- `api/jobs.js`의 `request()`가 공통 fetch 래퍼(베이스 URL, JSON, `X-API-Key` 주입, 에러 파싱).

---

## 환경변수 (`core/config.py`)

`backend/.env` → 저장소 루트 `.env` 순으로 로드. `INFRA_MODE`는 시작 시 검증되며 정확히
`local` 또는 `cloud`여야 합니다.

- **공통**: `INFRA_MODE`, `DB_USER/PASSWORD/HOST/PORT/NAME`, `DISCORD_WEBHOOK_URL`,
  `EXCEL_STORAGE_DIR`, `EXCEL_DOWNLOAD_PREFIX`
- **동작 튜닝**: `MAX_ATTEMPTS`(재시도 상한, 기본 3), `PROCESSING_LEASE_SECONDS`(좀비 리스,
  기본 1800), `API_KEY`(/create 보호), `VERIFY_TASK_OIDC`(콜백 검증, 기본 true)
- **DB 하드닝**: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE_SECONDS`,
  `DB_CONNECT_TIMEOUT_SECONDS`, `DB_STATEMENT_TIMEOUT_MS`(0=off).
  엔진은 항상 `pool_pre_ping=True`(Cloud SQL stale 커넥션 대비).
- **cloud 추가 필수**: `GCP_PROJECT_ID`, `GCP_LOCATION`, `GCP_TASKS_QUEUE_NAME`,
  `BACKEND_URL`, `TASKS_SERVICE_ACCOUNT_EMAIL`, `GCP_STORAGE_BUCKET_NAME`(지연 검증).

---

## 실행 & 테스트

백엔드(`backend/`에서):
```bash
cd backend && pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload   # INFRA_MODE + DB env 필요
pytest                                                  # tests/ (SQLite 기반, 외부 DB 불필요)
```

프론트엔드(`frontend/`에서):
```bash
npm install
npm run dev        # Vite :5173, /api → localhost:8000 프록시
npm run build
npm run lint       # eslint
```

로컬 실측(실제 export)은 로컬 Postgres 컨테이너에 붙여 확인하되, **`DISCORD_WEBHOOK_URL`은
실채널**이므로 스텁하거나 비우고, **테스트용 Job 행을 DB에 남기지 마세요.**

---

## Hook 기반 자동 검증 (권장 — 아직 미설정)

> 참고: Hook은 **CLAUDE.md가 아니라 `.claude/settings.json`** 에 설정합니다. CLAUDE.md에
> 적는다고 자동 실행되지 않습니다. 아래는 이 프로젝트에 걸면 좋은 권장안입니다.

- **편집 후 컴파일/테스트**: 백엔드 `.py`를 편집하면 `PostToolUse` 훅으로
  `cd backend && python -m pytest -q`(또는 최소 `py_compile`)를 자동 실행 → 회귀 즉시 감지.
- **커밋 전 리뷰**: 변경분에 `/code-review`를 돌려 정합성 이슈를 먼저 잡기(수동 관례로도 가능).

설정을 원하면 update-config(설정) 경로로 `settings.json`에 훅을 추가하면 됩니다.

---

## MCP 참조

이 프로젝트가 **필수로 요구하는 MCP 서버는 없습니다.** 외부 도구(예: 이슈 트래커, 클라우드
콘솔)를 MCP로 연결해 쓰는 경우, 여기에 서버 이름과 용도를 명시하세요. (MCP 연결 자체는
CLAUDE.md가 아니라 MCP 설정에서 합니다.)

---

## 배포

두 서비스 모두 Google Cloud Run(`asia-northeast3`)에 배포합니다. 스크립트는 `deploy/`:
- `deploy/deploy_backend.sh` — API 활성화, 큐/버킷/IAM, Cloud SQL 연결·env·타임아웃(1800s)
  으로 배포 후, 배포 URL을 `BACKEND_URL`로 반영해 재배포(OIDC audience 일치).
- `deploy/deploy_frontend.sh` + `frontend/cloudbuild.yaml` — `VITE_API_KEY`를 빌드타임
  주입, nginx가 `Host=<백엔드>` + SNI로 `/api`를 백엔드로 프록시.

보안 모델: Cloud Run은 `--allow-unauthenticated`(브라우저가 `/create` 호출), `/create`는
`API_KEY`로, `/tasks/excel` 콜백은 앱 레벨 **OIDC 검증**으로 보호합니다.
CI는 `.github/workflows/ci.yml`(backend pytest + frontend lint/build).
