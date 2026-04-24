#!/bin/bash

# 에러 발생 시 즉시 중단
set -e

IMAGE_NAME="stt-action-engine"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "============================================"
echo "  STT-NLU Action Engine Build Script"
echo "============================================"

# 1. 의존성 최신화 (uv.lock 업데이트)
if command -v uv >/dev/null 2>&1; then
    echo "[1/3] Syncing uv.lock..."
    uv lock
else
    echo "[1/3] Skip: uv command not found, using existing uv.lock"
fi

# 2. Docker 이미지 빌드
echo "[2/3] Building Docker image: $IMAGE_NAME:latest"
# --no-cache 옵션은 필요에 따라 제거하거나 추가할 수 있습니다.
docker compose build --pull

# 3. 불필요한 이미지 정리 (dangling images)
echo "[3/3] Cleaning up dangling images..."
docker image prune -f

echo "============================================"
echo "  Build Completed Successfully!"
echo "  Image: $IMAGE_NAME:latest"
echo "  Time: $(date)"
echo "============================================"

# 실행 방법 안내
echo "To start the container, run:"
echo "  docker compose up -d"
