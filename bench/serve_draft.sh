#!/usr/bin/env bash
set -euo pipefail
cd /home/max/live-translate
# WSL2 kernel 6.x supports pinned memory, but vLLM gates it behind this flag.
# Required or the V1 GPU runner aborts with "UVA is not available".
export VLLM_WSL2_ENABLE_PIN_MEMORY=1
# No CUDA toolkit (nvcc) in this WSL2 env, so flashinfer cannot JIT-compile its
# sampling kernel. Fall back to the native PyTorch sampler + prebuilt FlashAttn.
export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_ATTENTION_BACKEND=FLASH_ATTN
exec .venv/bin/vllm serve models/HY-MT1.5-1.8B \
  --port 8001 \
  --served-model-name hy-mt1.5-1.8b \
  --enable-prefix-caching \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.5
