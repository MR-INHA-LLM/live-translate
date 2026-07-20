# 서빙 / 운영 가이드

두 tier(draft·quality)를 vLLM OpenAI 호환 서버로 띄우는 방법. 게이트웨이는 이
엔드포인트들 뒤에 붙는다. 설계 배경은 [`decisions.md`](decisions.md), 레이턴시·
메모리 실측 원본은 [`../bench/RESULTS_M0.md`](../bench/RESULTS_M0.md).

## 요구사항

- Python 3.11+, vLLM 0.25.x, CUDA 12.x
- GPU: **초벌/최종 GPU 2장 분리가 이상적.** 단, 아래 FP8 조합이면 단일 24GB(RTX 4090)에도 2-tier가 들어간다(M0 실측).

## 단일 24GB GPU 배치 (권장 · M0 실측)

`gemma-4-E4B`는 가중치만 16GB라 draft와 공존하면 KV 캐시 여유가 없다. 동일 계보
FP8 조합을 쓴다 — 가중치 합 ~10GB, 나머지 ~13GB를 두 KV 캐시/CUDA graph에 배분.

```bash
# Draft tier — 2.0GB(FP8)
vllm serve tencent/HY-MT1.5-1.8B-FP8 \
  --port 8001 \
  --served-model-name hy-mt1.5-1.8b \
  --enable-prefix-caching \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.30

# Quality tier — 8.0GB(FP8), 동일 계보라 용어개입·맥락·서식 기능 공유
vllm serve tencent/HY-MT1.5-7B-FP8 \
  --port 8002 \
  --served-model-name hy-mt1.5-7b \
  --enable-prefix-caching \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.55
```

호스트 런처는 저장소 루트의 [`../serve_draft.sh`](../serve_draft.sh)·
[`../serve_quality.sh`](../serve_quality.sh)에 있다(bf16 원본 모델 + 아래 WSL2 플래그 포함).
도커로 띄우려면 `docker compose --profile gpu up`.

## CPU 배포 (GPU 없음)

vLLM CUDA 이미지는 CPU 서빙이 안 되므로, GPU-less 환경에서는 초벌(draft)만 경량
transformers 서버(`cpu_server/`)로 CPU에서 돌리고 quality tier는 끈다.

```bash
QUALITY_ENABLED=false DRAFT_URL=http://draft-cpu:8000/v1 docker compose --profile cpu up
```

quality가 꺼지면 최종 번역은 draft로 degrade하고(`degraded=True`) UI 버블은 단일
"번역" 줄로 접힌다. 초벌 CPU 지연은 짧은 문장 ~1.5s(실측 [`../bench/draft_cpu_gpu.py`](../bench/draft_cpu_gpu.py),
GPU 대비 ~6-7배). 도커 없이 호스트에서 돌리려면 `serve_draft_cpu.sh`(:8001) +
게이트웨이 `QUALITY_ENABLED=false`.

## GPU 2장 배치

각 tier를 전용 GPU에 둔다. quality tier를 bf16 원본으로 올릴 수 있다 —
`gemma-4-E4B`(16GB) 또는 `HY-MT1.5-7B`(16GB). tier별 교체 후보는 README §1.2 참고.

## 운영 주의

- **Prefix caching 필수.** 타이핑 중 요청은 접두어가 계속 겹쳐 KV 캐시 재사용이 곧 지연시간이다. 두 tier 모두 `--enable-prefix-caching`.
- **세션 시작 시 워밍업 요청 1회.** 콜드 첫 요청만 TTFT가 튄다(실측 222ms, 이후 ~12ms). 세션 오픈 시 더미 번역 1회로 CUDA graph/토크나이저를 데운다.
- **Graceful degradation.** quality tier 실패 시 draft 결과를 최종으로 승격.

## WSL2 필수 플래그

WSL2 + CUDA 툴킷(nvcc) 미설치 환경에서는 아래가 없으면 엔진 초기화 단계에서 죽는다
(M0에서 확인). `serve_draft.sh`·`serve_quality.sh`에 반영되어 있다.

```bash
export VLLM_WSL2_ENABLE_PIN_MEMORY=1   # 없으면 "UVA is not available"로 종료
export VLLM_USE_FLASHINFER_SAMPLER=0   # nvcc 부재 → flashinfer JIT 불가, native sampler로 우회
export VLLM_ATTENTION_BACKEND=FLASH_ATTN
```

- vLLM 0.25.x는 `--disable-log-requests` 플래그가 제거됨.

## 게이트웨이 / 데모 (로컬)

```bash
# Gateway
cp .env.example .env
uv sync
uv run uvicorn app.main:app --port 8000

# Demo (채팅 FE) — Node 필요
cd web && npm install && npm run dev   # http://localhost:5173
# 게이트웨이 주소가 다르면 VITE_API_BASE=http://host:8000 로 지정
```

FE 브라우저 스모크: `node web/e2e-smoke.mjs` (게이트웨이 :8000 + preview :5173 필요).

## Docker Compose 배포 (nginx 리버스 프록시)

**한 명령**으로 채팅앱(FE) + API가 뜬다. nginx가 빌드된 FE를 정적 서빙 + `/api`·WS·SSE를
게이트웨이로 프록시. 기본은 호스트 vLLM(:8001) 사용.

```bash
docker compose up -d --build          # FE + gateway + nginx → http://localhost:18090
docker compose --profile gpu up -d    # vLLM(GPU)까지 자체완결 (DRAFT_URL을 vllm-draft로)
```

- **접속**: `http://localhost:18090`(채팅앱). API·health 동일 오리진(`/api/v1/...`, `/health`).
- **nginx**(`deploy/Dockerfile.nginx` + `deploy/nginx.conf`): FE 정적 + WS 업그레이드 +
  SSE(`proxy_buffering off`) 프록시.
- **안정성**: gateway healthcheck(`/health`) + `restart: unless-stopped`, nginx는
  `depends_on: gateway(service_healthy)`로 준비 후 기동.
- **gateway** env: `DRAFT_URL`·`QUALITY_URL`·`DRAFT_MODEL`·`DB_URL`·`CORS_ORIGINS`.
- E2E: `uv run pytest tests/e2e`(REST·WS·SSE) · FE 스모크 `SMOKE_URL=http://localhost:18090 node web/e2e-smoke.mjs`.
