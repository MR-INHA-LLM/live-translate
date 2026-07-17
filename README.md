# live-translate

타이핑 중에는 경량 번역 모델이 즉시 초벌 번역을 스트리밍하고 입력이 확정되면 LLM이 대화 맥락을 반영해 자연스럽게 재번역하는 **이중 파이프라인 텍스트 번역 시스템**.

- **Draft tier** — 저지연 초벌 번역. 타이핑 중 매 변경마다 갱신.
- **Quality tier** — 확정 문장을 대화 맥락 기반으로 재번역. context-aware reranking(QAD) 선택 가능.

> **범위 제외:** STT / ASR / TTS / 음성 입출력. 본 프로젝트는 텍스트 전용입니다.
> 다만 입력 인터페이스는 "확정되지 않은 부분 텍스트(partial text) 스트림"으로 추상화되어 있어, 후속 음성 프로젝트에서 STT의 partial hypothesis를 그대로 연결할 수 있습니다.

이 README는 **고수준 개요**만 담습니다. 구체 수치·데이터 모델·프로토콜·측정값 등 자주 바뀌는 내용은 아래 문서에 있습니다.

| 문서 | 내용 |
|---|---|
| [`docs/design.md`](docs/design.md) | **상세 설계서** — 데이터 모델 · 파이프라인 · 프로토콜 · 데모 UX (구현 기준) |
| [`docs/user-scenario.md`](docs/user-scenario.md) | **사용자 시나리오** — 데모를 사용자 눈높이에서 걸어보기 |
| [`docs/backend-architecture.md`](docs/backend-architecture.md) | **BE 아키텍처** — 레이어 · 포트/어댑터 · SOLID · 동시성 (게이트웨이 구조 기준) |
| [`docs/decisions.md`](docs/decisions.md) | 설계 결정 이력 — 왜 이 설계인가 (모델 선정 근거 · 실측 결론) |
| [`docs/serving.md`](docs/serving.md) | 서빙/운영 — GPU 배치 · 기동 · 환경 플래그 |
| [`bench/RESULTS_M0.md`](bench/RESULTS_M0.md) | M0 실측 원본 데이터 |

---

## 1. 모델 선정

- **Draft tier — `tencent/HY-MT1.5-1.8B`.** 소형·실시간 지향 번역 전용 모델. M0에서 6방향(ko/en/id) 실측 검증 후 확정. 후보 비교·측정 결과는 [`docs/decisions.md`](docs/decisions.md).
- **Quality tier — Gemma 4 계열 소형 모델(기준 `gemma-4-E2B`).** vLLM OpenAI 호환 API 뒤라 **언제든 교체 가능**. 서빙 가능 여부·배치는 M1에서 확정.
- **Reranker (QAD, 선택)** — reference-free 품질 추정(CometKiwi)으로 후보 리랭킹. 지연이 후보 수에 비례 → API 토글.

---

## 2. 아키텍처

```
┌──────────────┐
│  Demo (Web)  │
└──────┬───────┘
       │ WS  /api/v1/sessions/{id}/stream   (초벌: partial text → draft)
       │ SSE /api/v1/sessions/{id}/turns    (최종: 확정 문장 → quality)
       ▼
┌──────────────────────────────────────────────┐
│  Gateway (FastAPI, :8000)                    │
│   ├─ SessionStore   대화 이력 / 언어쌍 / 도메인 │
│   ├─ DraftRouter    디바운스·취소·다중 타겟     │
│   ├─ QualityRouter  컨텍스트 프롬프트 구성      │
│   └─ Reranker       (optional) CometKiwi      │
└───────┬──────────────────────┬───────────────┘
        │ OpenAI-compatible    │ OpenAI-compatible
        ▼                      ▼
┌───────────────────┐  ┌───────────────────┐
│ vLLM :8001        │  │ vLLM :8002        │
│ draft             │  │ quality           │
└───────────────────┘  └───────────────────┘
```

**두 tier는 반드시 별도 vLLM 인스턴스.** 같은 엔진이면 초벌이 최종 뒤에 큐잉되어 저지연 목표를 못 맞춥니다. GPU 배치(단일/듀얼)는 [`docs/serving.md`](docs/serving.md).

- **초벌 안정화** — 타이핑마다 번역 전체가 바뀌는 flicker를 억제. 디바운스 · IME 조합 제거 · tentative 렌더 · revision 순서제어로 처리. 상세·실측 근거는 [`docs/design.md`](docs/design.md) §4.
- **최종 컨텍스트 (TMC)** — 직전 N턴의 이중언어 원문/번역을 프롬프트에 포함해 대명사·격식·생략을 복원. Pombal et al. (TACL 2026) 기반. 상세는 [`docs/design.md`](docs/design.md) §5.

---

## 3. API

| 엔드포인트 | 용도 |
|---|---|
| `POST /api/v1/sessions` | 세션 생성(언어쌍·도메인·격식·모델·rerank 설정) |
| `GET /api/v1/languages` | 지원 언어 · 검증된 쌍 |
| `WS /api/v1/sessions/{id}/stream` | 초벌 스트리밍(revision 단위, 다중 타겟 렌더) |
| `POST /api/v1/sessions/{id}/turns` (SSE) | 최종 번역(턴 생성) 스트리밍 |
| `GET /api/v1/sessions/{id}/turns` | 턴별 원문/초벌/최종/레이턴시 이력 |
| `GET /health`, `GET /metrics` | 모델 로드 상태 · tier별 레이턴시 히스토그램 |

> RESTful 네이밍·프로젝트 구조는 `fastapi-standards` 준수. 요청/응답 스키마·메시지 포맷·에러 코드는 [`docs/design.md`](docs/design.md) §6, BE 구조는 [`docs/backend-architecture.md`](docs/backend-architecture.md).

---

## 4. 성능 목표

| 지표 | 목표 |
|---|---|
| 초벌 TTFT | ≤ 150 ms |
| 초벌 완료 | ≤ 400 ms |
| 최종 TTFT | ≤ 1 s |
| 최종 완료 (rerank off) | ≤ 2 s |
| 최종 완료 (rerank on, N=4) | ≤ 5 s |

- **Prefix caching 필수.** 타이핑 중 요청은 접두어가 겹침 → KV 캐시 재사용이 곧 지연시간.
- 초벌은 greedy(`temperature=0`), `max_tokens` 타이트하게. 안정성 > 다양성.
- **Graceful degradation** — quality tier 실패 시 초벌 결과를 최종으로 승격.

> 초벌의 M0 실측 수치는 [`bench/RESULTS_M0.md`](bench/RESULTS_M0.md).

---

## 5. 실행

요구사항·GPU 배치·기동 명령·환경 플래그는 [`docs/serving.md`](docs/serving.md).

```bash
bash bench/serve_draft.sh          # draft tier (:8001)
# quality tier (:8002) — docs/serving.md
uv sync && uv run uvicorn app.main:app --port 8000
cd web && pnpm install && pnpm dev # 데모
```

---

## 6. 프로젝트 구조

```
app/     FastAPI 게이트웨이 (라우터 · 엔진 클라이언트 · 프롬프트 · 세션)
web/     데모 프론트엔드
bench/   측정 하네스 (M0~) + RESULTS_M0.md
docs/    설계서 · 결정 이력 · 서빙 가이드
```

---

## 7. 데모

데모가 증명하려는 주장은 "quality tier가 지연을 정당화한다"입니다. 짧은 문장에선 draft==final이라 효과가 드러나지 않으므로, **id를 모르는 사용자도 witness 언어(en)로 개선을 읽게** 하는 것을 목표로 합니다. 상세 UX는 [`docs/design.md`](docs/design.md) §8.

---

## 8. 마일스톤

- [x] **M0** — draft 모델 실측 → **`HY-MT1.5-1.8B` 확정**. 근거 [`docs/decisions.md`](docs/decisions.md).
- [ ] **M1** — vLLM 2-tier 서빙 + gateway 배선. 레이턴시 측정.
- [ ] **M2** — WS 초벌 스트리밍 + 안정화(IME, tentative 렌더). **flicker 없는 상태 확보.**
- [ ] **M3** — TMC 컨텍스트 프롬프트 + SSE 최종.
- [ ] **M4** — QAD 리랭킹 + API 토글.
- [ ] **M5** — 데모 프론트 + 시나리오.

---

## 9. 열린 이슈

- 리랭킹 metric을 context-aware 변형으로 학습할지, 표준 CometKiwi로 갈지.
- 대화 이력이 길어질 때 컨텍스트 절단 vs 요약.
- 언어 커버리지 요구가 draft 모델 지원 범위를 넘으면 재선정.

> 해소된 이슈(예: ko↔id 영어 피벗)는 [`docs/decisions.md`](docs/decisions.md)에 이력으로 남깁니다.

---

## 10. 참고

- Pombal et al. (2026). *A Context-aware Framework for Translation-mediated Conversations.* TACL. — arXiv:2412.04205
- Tencent Hunyuan (2026). *HY-MT1.5 Technical Report.* — arXiv:2512.24092
- Zheng et al. (2025). *Hunyuan-MT Technical Report.* — arXiv:2509.05209
- NiuTrans (2025). *NiuTrans.LMT.* — arXiv:2511.07003
- Finkelstein et al. (2026). *TranslateGemma Technical Report.*
- Gemma 4 model card — https://ai.google.dev/gemma/docs/core/model_card_4
