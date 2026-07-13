#!/usr/bin/env bash
#
# Cloud Run(백엔드) + Cloud Tasks 배포 스크립트
# ------------------------------------------------------------------
# 이 스크립트는 아래를 수행한다:
#   1. 필요한 GCP API 활성화
#   2. Cloud Tasks 큐 / GCS 버킷 생성(이미 있으면 건너뜀)
#   3. 서비스계정 IAM 롤 부여 (enqueuer / actAs / tokenCreator / storage)
#   4. 컨테이너 빌드 & Cloud Run 배포 (Cloud SQL 연결 + 환경변수 + 타임아웃)
#   5. 배포 URL을 BACKEND_URL로 반영해 재배포 (OIDC audience 일치)
#
# 전제:
#   - gcloud 로그인 및 프로젝트 권한 보유 (`gcloud auth login`)
#   - 아래 변수들을 실제 값으로 채울 것
#   - 하나의 서비스계정(SERVICE_ACCOUNT)을 백엔드 런타임 겸 Cloud Tasks OIDC
#     주체로 사용한다고 가정 (분리하려면 IAM 단계 주석 참고)
#
# 보안 모델:
#   - Cloud Run은 --allow-unauthenticated 로 배포한다(브라우저가 /create 호출).
#   - /create 는 API_KEY(X-API-Key 헤더)로 보호.
#   - /tasks/excel 콜백은 앱 레벨 OIDC 검증(VERIFY_TASK_OIDC=true)으로 보호.
#     → Cloud Run IAM(run.invoker)에 의존하지 않으므로 run.invoker 부여는 생략.
#
# 사용법:  deploy/deploy_backend.sh
set -euo pipefail

# ===== 1) 채워야 하는 변수 =========================================
PROJECT_ID="your-project-id"
REGION="asia-northeast3"                       # Cloud Run / Tasks 리전 (동일해야 함)
SERVICE_NAME="ps-onboarding-backend"           # Cloud Run 서비스 이름
SERVICE_ACCOUNT="ps-tasks@${PROJECT_ID}.iam.gserviceaccount.com"

QUEUE_NAME="excel-job-queue"                   # Cloud Tasks 큐 이름
BUCKET_NAME="ps-onboarding-excel-bucket"       # GCS 버킷 이름 (전역 유일)

CLOUDSQL_INSTANCE="${PROJECT_ID}:${REGION}:excel-onboarding"  # Cloud SQL 연결 이름
DB_USER="excel"
DB_PASSWORD="change_me_strong_password"
DB_NAME="excel_onboarding"

API_KEY="set-a-strong-random-key"              # /create 보호용 (프론트 VITE_API_KEY와 동일)
DISCORD_WEBHOOK_URL=""                         # 선택
RUN_TIMEOUT="1800"                             # 초. 코드의 dispatch_deadline(1800)과 정합
# ==================================================================

gcloud config set project "${PROJECT_ID}"

echo "==> [1/5] API 활성화"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudtasks.googleapis.com \
  storage.googleapis.com \
  sqladmin.googleapis.com \
  iamcredentials.googleapis.com

echo "==> [2/5] Cloud Tasks 큐 / GCS 버킷 (없으면 생성)"
gcloud tasks queues describe "${QUEUE_NAME}" --location="${REGION}" >/dev/null 2>&1 \
  || gcloud tasks queues create "${QUEUE_NAME}" --location="${REGION}"

gcloud storage buckets describe "gs://${BUCKET_NAME}" >/dev/null 2>&1 \
  || gcloud storage buckets create "gs://${BUCKET_NAME}" --location="${REGION}"

echo "==> [3/5] 서비스계정 IAM 롤"
# 태스크 생성 권한
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/cloudtasks.enqueuer" --condition=None

# 태스크에 OIDC 토큰을 실으려면 대상 SA를 actAs 할 수 있어야 함(여기선 자기 자신).
# v4 서명 URL(signBlob)에는 tokenCreator 권한이 필요.
gcloud iam service-accounts add-iam-policy-binding "${SERVICE_ACCOUNT}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/iam.serviceAccountUser"
gcloud iam service-accounts add-iam-policy-binding "${SERVICE_ACCOUNT}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/iam.serviceAccountTokenCreator"

# 버킷 업로드/서명 권한
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/storage.objectAdmin"

# (SA를 분리한다면: 런타임 SA에 위 4개를 주고, 콜백 OIDC용 SA는 TASKS_SERVICE_ACCOUNT_EMAIL로
#  지정하되 런타임 SA가 그 SA에 대해 serviceAccountUser/tokenCreator 를 갖게 하면 된다.)

# 공통 환경변수 (INFRA_MODE=cloud). BACKEND_URL은 1차 배포 후 채운다.
ENV_VARS="INFRA_MODE=cloud"
ENV_VARS="${ENV_VARS},DB_HOST=/cloudsql/${CLOUDSQL_INSTANCE}"
ENV_VARS="${ENV_VARS},DB_USER=${DB_USER},DB_PASSWORD=${DB_PASSWORD},DB_NAME=${DB_NAME}"
ENV_VARS="${ENV_VARS},GCP_PROJECT_ID=${PROJECT_ID},GCP_LOCATION=${REGION}"
ENV_VARS="${ENV_VARS},GCP_TASKS_QUEUE_NAME=${QUEUE_NAME}"
ENV_VARS="${ENV_VARS},GCP_STORAGE_BUCKET_NAME=${BUCKET_NAME}"
ENV_VARS="${ENV_VARS},TASKS_SERVICE_ACCOUNT_EMAIL=${SERVICE_ACCOUNT}"
ENV_VARS="${ENV_VARS},API_KEY=${API_KEY},VERIFY_TASK_OIDC=true"
ENV_VARS="${ENV_VARS},DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL}"

echo "==> [4/5] 빌드 & 1차 배포"
gcloud run deploy "${SERVICE_NAME}" \
  --source=backend \
  --region="${REGION}" \
  --service-account="${SERVICE_ACCOUNT}" \
  --add-cloudsql-instances="${CLOUDSQL_INSTANCE}" \
  --timeout="${RUN_TIMEOUT}" \
  --allow-unauthenticated \
  --set-env-vars="${ENV_VARS}"

echo "==> [5/5] BACKEND_URL 반영 후 재배포 (OIDC audience 일치)"
BACKEND_URL="$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" --format='value(status.url)')"
echo "    BACKEND_URL=${BACKEND_URL}"

gcloud run services update "${SERVICE_NAME}" \
  --region="${REGION}" \
  --update-env-vars="BACKEND_URL=${BACKEND_URL}"

echo "완료: ${BACKEND_URL}"
echo "확인: curl -X POST ${BACKEND_URL}/create -H \"X-API-Key: ${API_KEY}\""
