#!/usr/bin/env bash
# GPU 있으면 --profile gpu, 없으면 --profile cpu 로 전체 스택을 띄운다.
# API 키(API_KEYS/VITE_API_KEY)는 .env 에서 compose 가 자동으로 읽는다.
#   사용: ./run.sh -d        (백그라운드)
#         ./run.sh           (포그라운드)
set -euo pipefail
cd "$(dirname "$0")"

if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
  echo "▶ GPU 감지 — profile: gpu"
  exec docker compose --profile gpu up "$@"
else
  echo "▶ GPU 없음 — profile: cpu (quality 끔, draft만 CPU)"
  export QUALITY_ENABLED=false
  export DRAFT_URL=http://draft-cpu:8000/v1
  exec docker compose --profile cpu up "$@"
fi
