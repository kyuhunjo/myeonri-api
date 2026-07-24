#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════
# myeonri-api 마스터 빌드/푸시/k3s 통합 배포 스크립트 (v2)
# ════════════════════════════════════════════════════════════════════════
#
# 워크플로우 (2 hop):
#   로컬(WSL) → 마스터(192.168.35.13, scp)
#                 → 마스터 docker build + push
#                 → k3s imagePullSecrets pull → rollout
#
# 참고:
#   - BE는 런타임 env (DB, SECRET_KEY 등)를 k8s에서 주입 (env: / envFrom:)
#   - 빌드 시점에는 .env 불필요 (Dockerfile이 requirements.txt만 사용)
#   - .env / .env.example은 tar exclude
#
# 사용법:
#   ./deploy-master.sh                  # 설명 없이 기본 빌드
#   ./deploy-master.sh bugfix           # 태그에 설명 추가
# ════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── 설정 ──
readonly MASTER="root@192.168.35.13"
readonly BUILD_DIR="/root/build-contexts/myeonri-api"
readonly IMAGE_REPO="docker.io/kyuhunjo/myeonri-api"
readonly DEPLOYMENT="myeonri-api"       # api.imjoe24.com 라우팅
readonly NAMESPACE="default"
readonly LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 인자 처리 ──
DESCRIPTION="${1:-deploy}"
DESCRIPTION=$(echo "$DESCRIPTION" | tr -cd '[:alnum:]-_')
[ -z "$DESCRIPTION" ] && DESCRIPTION="deploy"

TAG="$(date +%Y%m%d-%H%M%S)-${DESCRIPTION}"
IMAGE_TAG="${IMAGE_REPO}:${TAG}"
TARBALL_NAME="api-${TAG}.tar.gz"

# ── 사전 검증 ──
cd "$LOCAL_DIR"
if [ ! -f "Dockerfile" ]; then
  echo "❌ Dockerfile 없음: $LOCAL_DIR" >&2
  exit 1
fi

echo "═══════════════════════════════════════════════════════"
echo "🔌 myeonri-api 통합 배포 (마스터 빌드/푸시)"
echo "═══════════════════════════════════════════════════════"
echo "  • 로컬:    $LOCAL_DIR"
echo "  • 마스터:  $MASTER"
echo "  • 빌드디렉토리: $BUILD_DIR"
echo "  • 이미지:  $IMAGE_TAG"
echo "  • 배포:    $NAMESPACE/$DEPLOYMENT (api.imjoe24.com)"
echo "═══════════════════════════════════════════════════════"

# ── 1) 로컬 → 마스터 전송 ──
echo ""
echo "── [1/4] 소스 전송 (로컬 → 마스터) ──"
TMP_TARBALL="/tmp/${TARBALL_NAME}"
tar czf "$TMP_TARBALL" \
  --exclude='__pycache__' --exclude='.git' --exclude='venv' --exclude='.venv' \
  --exclude='.env' --exclude='.env.example' --exclude='.pytest_cache' \
  --exclude='.DS_Store' --exclude='*.pyc' --exclude='*.log' \
  .
ls -lh "$TMP_TARBALL" | awk '{print "  ✓ tar.gz 생성:", $5, $9}'

scp -q -o StrictHostKeyChecking=accept-new "$TMP_TARBALL" "${MASTER}:/tmp/${TARBALL_NAME}"

ssh -o StrictHostKeyChecking=accept-new "$MASTER" "
  set -e
  rm -rf '$BUILD_DIR'
  mkdir -p '$BUILD_DIR'
  tar xzf '/tmp/${TARBALL_NAME}' -C '$BUILD_DIR'
  rm -f '/tmp/${TARBALL_NAME}'
" </dev/null
echo "  ✓ 마스터 소스 추출 완료: $BUILD_DIR"

rm -f "$TMP_TARBALL"

# ── 2) 마스터에서 Docker 빌드 ──
echo ""
echo "── [2/4] Docker 빌드 (마스터) ──"
ssh -o StrictHostKeyChecking=accept-new "$MASTER" \
  "cd '$BUILD_DIR' && docker build --no-cache -t '$IMAGE_TAG' ." 2>&1 | tail -10
echo "  ✓ 이미지 빌드 완료: $IMAGE_TAG"

# ── 3) Docker Hub 푸시 ──
echo ""
echo "── [3/4] Docker Hub 푸시 (마스터) ──"
ssh -o StrictHostKeyChecking=accept-new "$MASTER" \
  "docker push '$IMAGE_TAG'" 2>&1 | tail -6
echo "  ✓ 푸시 완료"

# ── 4) k3s rollout ──
echo ""
echo "── [4/4] k3s rollout (마스터) ──"
ssh -o StrictHostKeyChecking=accept-new "$MASTER" \
  "kubectl -n '$NAMESPACE' patch deployment '$DEPLOYMENT' --type=json \
    -p '[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/image\",\"value\":\"$IMAGE_TAG\"}]'" 2>&1 | tail -3
ssh -o StrictHostKeyChecking=accept-new "$MASTER" \
  "kubectl -n '$NAMESPACE' rollout status deployment/'$DEPLOYMENT' --timeout=180s" 2>&1 | tail -5

echo ""
echo "═══════════════════════════════════════════════════════"
echo "✅ 배포 완료: $IMAGE_TAG"
echo "═══════════════════════════════════════════════════════"
