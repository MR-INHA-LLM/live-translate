#!/usr/bin/env bash
# CPU draft 서버 (GPU 없는 환경) — transformers로 :8001 에 OpenAI 호환 서빙.
# 도커 없이 호스트에서 쓸 때. 게이트웨이는 QUALITY_ENABLED=false 로 띄운다.
set -euo pipefail
cd "$(dirname "$0")"
export DRAFT_MODEL_PATH="${DRAFT_MODEL_PATH:-models/HY-MT1.5-1.8B}"
export SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-hy-mt1.5-1.8b}"
exec .venv/bin/uvicorn cpu_server.app:app --host 0.0.0.0 --port 8001 --log-level warning
