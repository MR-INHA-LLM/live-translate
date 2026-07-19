#!/usr/bin/env bash
# Draft tier — HY-MT1.5-1.8B (초벌, 저지연). WSL2 vLLM 0.25.x 플래그 포함.
# Quality(Qwen3-4B)와 단일 GPU를 공유하므로 util을 0.30으로 낮춰 여유를 남긴다.
set -euo pipefail
cd "$(dirname "$0")"
export VLLM_WSL2_ENABLE_PIN_MEMORY=1
export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_ATTENTION_BACKEND=FLASH_ATTN
exec .venv/bin/vllm serve models/HY-MT1.5-1.8B \
  --port 8001 --served-model-name hy-mt1.5-1.8b \
  --enable-prefix-caching --max-model-len 4096 \
  --gpu-memory-utilization 0.30
