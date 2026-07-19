#!/usr/bin/env bash
# Quality tier — Qwen3-4B-Instruct-2507 (context-aware 최종 번역, Pombal TACL 2026).
# Draft와 단일 RTX 4090을 공유. WSL2 vLLM 0.25.x 플래그 포함.
set -euo pipefail
cd "$(dirname "$0")"
export VLLM_WSL2_ENABLE_PIN_MEMORY=1
export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_ATTENTION_BACKEND=FLASH_ATTN
exec .venv/bin/vllm serve models/Qwen3-4B-Instruct-2507 \
  --port 8002 --served-model-name qwen3-4b-instruct \
  --enable-prefix-caching --max-model-len 8192 \
  --gpu-memory-utilization 0.50
