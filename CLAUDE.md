# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Async Excel export service: reads `orders` rows from PostgreSQL, streams them into an
`.xlsx` workbook, stores the file, and reports progress to the browser in real time over
SSE. A React frontend triggers jobs and renders their live status. On completion/failure a
Discord webhook is sent.

## INFRA_MODE — the central abstraction

Almost every backend behavior branches on `Settings.INFRA_MODE` (`local` | `cloud`), read
from env. `Settings.is_local` / `Settings.is_cloud` gate the choice. Understand this before
changing anything in `excel/`, `services/`, or `db/`:

| Concern | `local` | `cloud` |
| --- | --- | --- |
| Job queue | in-process `asyncio.PriorityQueue` + background `worker_loop` (started in `main.lifespan`) | Google Cloud Tasks → HTTP callback to `POST /tasks/excel` |
| File storage | `LocalStorageClient` → local volume, served by `GET /files/{job_id}` | `GCSClient` → GCS upload + v4 signed download URL |
| DB connection | TCP host:port (`db` service) | Cloud SQL unix socket when `DB_HOST` starts with `/cloudsql/` |
| Excel temp dir | `EXCEL_STORAGE_DIR` | system temp, deleted after upload |

`get_storage_client()` (`services/storage_service.py`) and `ExcelService.enqueue_job`
(`excel/excel_service.py`) are the two dispatch points. When adding a feature, implement
**both** modes or the other environment breaks silently.

## Request → export flow

1. `POST /create` (`excel/excel_router.py`) → `JobService.create_export` inserts a `Job`
   (status `PENDING`), then `ExcelService.enqueue_job` routes it (queue vs Cloud Tasks).
2. Actual work is `ExcelService.create_excel(job_id)` — CPU-bound, always run via
   `asyncio.to_thread` (never on the event loop). It opens its **own** `SessionLocal()`;
   never pass a request-scoped DB session into it.
3. First step inside `create_excel` is an **atomic claim**: a single `UPDATE ... WHERE
   status IN (PENDING, FAILED)` flips to `PROCESSING`. `rowcount == 0` means another worker
   already took it → skip. This is the cross-instance duplicate guard, required because
   Cloud Tasks is at-least-once. Preserve this guard when editing `create_excel`.
4. Rows are read in `MAX_CHUNK_SIZE` (5000) pages; after each page `progress` is persisted
   (capped at 99 until done) and an SSE event is published.
5. On success: upload/save, set status `DONE`, `progress=100`, `download_url`, send success
   webhook. On exception: rollback, status `FAILED`, error webhook, re-raise.

`task/task_router.py` wraps the Cloud Tasks callback with an in-process
`asyncio.Semaphore(1)` so one export runs per instance; a non-2xx response tells Cloud Tasks
to retry.

## SSE progress (`job/job_events.py`)

`JobEventHub` is a single-process, push-only fan-out — no DB polling. `publish_job_event(job)`
is called at every state change. Because `create_excel` runs in a worker thread, `publish`
serializes the ORM object to JSON **in the calling thread** and hands only the string to the
main loop via `loop.call_soon_threadsafe`. Slow subscribers drop their oldest event rather
than blocking the worker. Frontend consumes it via `EventSource('/jobs/events')` and
resyncs authoritative state through the REST endpoints. The hub is started/stopped in
`main.lifespan`.

## Data model

- `Job` (`job/job.py`) — export lifecycle, progress, timing, storage pointers,
  `attempt_count`. Status enum in `common/enums/job_status.py`
  (`PENDING/PROCESSING/DONE/FAILED`).
- `Order` (`order/order.py`) — source rows exported to Excel.

Tables are created at startup via `Base.metadata.create_all` in `main.py`. Alembic is a
dependency but there are no migration scripts yet; model changes take effect on restart
against an empty/compatible schema, not via migration.

## Conventions

- Layout is per-domain packages (`excel/`, `job/`, `task/`, `order/`, `webhook/`) each split
  into `_router` / `_service` / model. Cross-cutting code lives in `core/`, `db/`,
  `services/`, `common/`.
- Backend imports are **absolute from the `backend/` root** (`from job.job import Job`), which
  only resolves when the process runs with CWD `backend/`. Run/launch from there.
- New SQLAlchemy models must be imported in `main.py` (even if unused —
  `# noqa: F401`) so their table metadata registers before `create_all`.
- Timestamps use `common/utils/now.py:now()`; don't call `datetime.now()` directly.

## Commands

Backend (run from `backend/`):
```bash
cd backend && pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload   # needs INFRA_MODE + DB env set
pytest                          # test suite in backend/tests (state machine, create_excel, auth, download)
```

Frontend (run from `frontend/`):
```bash
npm install
npm run dev        # Vite dev server on :5173, proxies /api → localhost:8000
npm run build
npm run lint       # eslint
```

Full stack (local mode, from repo root):
```bash
cp .env.local.example .env      # or .env.cloud.example for cloud mode
docker compose up --build       # db (postgres:16) + backend:8000 + frontend:8080
```

## Environment

Config is loaded (`core/config.py`) from `backend/.env` then repo-root `.env` via
`python-dotenv`. Start from `.env.local.example` / `.env.cloud.example`. `INFRA_MODE` is
validated at startup and must be exactly `local` or `cloud`. Cloud mode additionally requires
`GCP_PROJECT_ID`, `GCP_LOCATION`, `GCP_TASKS_QUEUE_NAME`, `BACKEND_URL`,
`TASKS_SERVICE_ACCOUNT_EMAIL`, `GCP_STORAGE_BUCKET_NAME` (validated lazily when the Cloud
Tasks / GCS clients are first used).

## Deployment

Both services deploy to Google Cloud Run (`asia-northeast3`); URLs are in `README.md`. The
frontend container serves the built SPA behind nginx (`frontend/nginx.conf.template`) and
proxies `/api` to the backend upstream.
