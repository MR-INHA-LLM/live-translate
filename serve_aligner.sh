#!/usr/bin/env bash
# 정렬 서비스 — awesome-align(simalign) 기반 구 정렬 (:8003, 호스트 프로세스).
# vLLM/COMET과 transformers/torch 충돌 회피를 위해 게이트웨이와 분리(decisions.md D7).
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/uvicorn aligner.app:app --host 0.0.0.0 --port 8003 --log-level warning
