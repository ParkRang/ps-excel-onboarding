#!/usr/bin/env bash
#
# Cloud Run(프론트엔드) 배포 스크립트
# ------------------------------------------------------------------
# 정적 SPA를 nginx로 서빙하고 /api 를 백엔드 Cloud Run으로 프록시한다.
#
# 이 스크립트는:
#   1. 배포된 백엔드 Cloud Run URL을 조회 (nginx 프록시 대상 / Host 헤더용)
#   2. Artifact Registry 저장소 확보
#   3. Cloud Build로 이미지 빌드 (VITE_API_KEY 를 빌드타임 주입)
#   4. Cloud Run 배포 (BACKEND_UPSTREAM / BACKEND_HOST 환경변수 주입)
#   5. CORS 안내 출력
#
# 전제: deploy/deploy_backend.sh 로 백엔드가 먼저 배포되어 있어야 한다.
# 사용법:  deploy/deploy_frontend.sh
set -euo pipefail

# ===== 채워야 하는 변수 ============================================
PROJECT_ID="your-project-id"
REGION="asia-northeast3"
BACKEND_SERVICE="ps-onboarding-backend"        # deploy_backend.sh 의 SERVICE_NAME
FRONTEND_SERVICE="ps-onboarding-frontend"
AR_REPO="containers"                           # Artifact Registry 저장소 이름
VITE_API_KEY="set-a-strong-random-key"         # 백엔드 API_KEY 와 동일해야 함
# ==================================================================

gcloud config set project "${PROJECT_ID}"

echo "==> [1/5] 백엔드 URL 조회"
BACKEND_URL="$(gcloud run services describe "${BACKEND_SERVICE}" \
  --region="${REGION}" --format='value(status.url)')"
BACKEND_HOST="${BACKEND_URL#https://}"         # https:// 제거 → Host 헤더/SNI 용
echo "    BACKEND_URL=${BACKEND_URL}"
echo "    BACKEND_HOST=${BACKEND_HOST}"

echo "==> [2/5] Artifact Registry 저장소 (없으면 생성)"
gcloud artifacts repositories describe "${AR_REPO}" --location="${REGION}" >/dev/null 2>&1 \
  || gcloud artifacts repositories create "${AR_REPO}" \
       --repository-format=docker --location="${REGION}"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/frontend:latest"

echo "==> [3/5] Cloud Build (VITE_API_KEY 빌드타임 주입)"
gcloud builds submit frontend \
  --config=frontend/cloudbuild.yaml \
  --substitutions="_IMAGE=${IMAGE},_VITE_API_KEY=${VITE_API_KEY},_VITE_API_BASE_URL=/api"

echo "==> [4/5] Cloud Run 배포"
# 프론트는 /api 를 BACKEND_UPSTREAM 으로 프록시한다. Cloud Run 라우팅을 위해
# nginx가 Host=${BACKEND_HOST}, SNI on 으로 요청을 보낸다(Dockerfile/nginx.conf.template).
gcloud run deploy "${FRONTEND_SERVICE}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --allow-unauthenticated \
  --set-env-vars="BACKEND_UPSTREAM=${BACKEND_URL},BACKEND_HOST=${BACKEND_HOST}"

FRONTEND_URL="$(gcloud run services describe "${FRONTEND_SERVICE}" \
  --region="${REGION}" --format='value(status.url)')"

echo "==> [5/5] 완료: ${FRONTEND_URL}"
echo
echo "확인 사항:"
echo "  - 백엔드 CORS 허용 목록(main.py)에 프론트 URL이 포함되어야 브라우저 직접 호출도 안전:"
echo "      ${FRONTEND_URL}"
echo "    (nginx /api 프록시만 쓰면 same-origin이라 CORS는 불필요하지만, 목록에 넣어두길 권장)"
