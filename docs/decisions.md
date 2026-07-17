# 설계 결정 이력

설계를 바꾼 결정과 그 근거를 시간순으로 기록한다. README는 "현재 설계"를,
이 문서는 "왜 그 설계가 되었나"를 담는다. 측정 원본은
[`../bench/RESULTS_M0.md`](../bench/RESULTS_M0.md).

---

## 2026-07-17 · M0 draft-tier 실측

환경: RTX 4090 24GB · WSL2(kernel 6.x) · vLLM 0.25.1 · bf16.
대상: `tencent/HY-MT1.5-1.8B`. 하네스: `bench/*.py`.

### D0. Draft 후보 비교 (선정 배경, 측정 전)

`LMT-60-4B`·`TranslateGemma-4B` 대신 `HY-MT1.5-1.8B` 채택.

| 항목 | HY-MT1.5-1.8B | LMT-60-4B | TranslateGemma-4B |
|---|---|---|---|
| 파라미터 | **1.8B** | 4B | 4B |
| 지원 언어 | 33 (+5 방언/소수민족) | 60 | 55 |
| 계보 | WMT25 우승(Hunyuan-MT-7B) 후속 | Qwen3 CPT+SFT | Gemma 3 기반 |
| 실시간 타겟 | **명시적**(edge/real-time) | 아님 | 아님 |
| 양자화 | FP8 / GPTQ-Int4 / GGUF / 2bit | — | GGUF |

- 7B의 1/3 미만 파라미터로 준하는 품질 → 초벌 tier에 4B 불필요.
- 동남아 언어(vi/th/id) 강점 → `id` 요구에 유리.
- **번역 전용**(일반 QA/코드 불가), 기본 system prompt 없음, 프롬프트가 언어쌍별
  분기(zh↔ 중문 지시 / 그 외 영문 지시).
- 한계: 33개 언어로 LMT-60보다 커버리지 좁음 → 확장 요구 시 `TranslateGemma-4B` 스왑.

### D1. Draft 모델 `HY-MT1.5-1.8B` 확정

FLORES-200 devtest(1012문장) reference-based COMET(wmt22-comet-da)로 6방향 정량
측정 + 육안 검증. 6방향 평균 **COMET 88.59**, 전 방향 유창·정확. 중국어 중심
설계 우려는 실측에서 문제되지 않음. → **draft 모델 확정.**

| ko→en | en→ko | ko→id | id→ko | en→id | id→en | 평균 |
|---|---|---|---|---|---|---|
| 87.12 | 90.25 | 87.90 | 87.80 | 90.67 | 87.81 | **88.59** |

*남은 검증:* FLORES+(gated, HF gate 승인 필요) 재측정으로 README 원문 데이터셋과
parity, TranslateGemma-4B / LMT-60-4B 대조는 미완.

### D2. `ko↔id` 영어 피벗 폐기

열린 이슈였던 "ko↔id 품질 미달 시 ko→en→id 피벗 도입"을 폐기. **정량 근거:**
`ko↔id` 직접 COMET 87.8~87.9로 `ko↔en`(87.1)과 동급 — 영어가 더 나은 브릿지가
아니므로 피벗은 지연만 2배로 늘림. 육안으로도 직접 번역이 자연스러움.

### D3. flicker 안정화 — 목표문 접두어 확정(local agreement) 포기

`prefix_stability.py` 결과:
- temp=0 greedy는 결정적(동일 프롬프트 5/5 동일) → hold-k의 재현성 전제는 성립.
- 그러나 ko(SOV)→id(SVO)는 소스가 한 어절 늘 때마다 목표문이 전면 재작성되어
  이전 번역 대비 접두어 생존율이 대부분 0%. "연속 k회 동일 접두어 확정"으로는
  확정할 접두어가 생기지 않는다.

→ 접두어 freeze로는 flicker를 줄이지 못한다. 완화는 (a) 디바운스(어절 경계),
(b) 미확정 draft 전체를 tentative로 렌더, (c) revision_id 순서제어/이전요청 abort로
간다. 목표문 접두어 확정은 어순이 유사한 쌍에 한해 선택적으로만. (README §2.1)

### D4. 레이턴시 — 추론 지연은 디바운스보다 작다

초벌 TTFT p50 12.5ms / Total p50 91ms로 목표(150/400ms) 미만. 목표를 넘은 것은
콜드 첫 요청(TTFT 222ms)뿐 → 세션 워밍업 1회로 제거.
→ 추론 지연(~12ms)이 디바운스(150~250ms)보다 작으므로, 레이턴시 예산의 대부분은
디바운스가 차지한다. 튜닝 레버는 모델 속도가 아니라 안정화 정책. (README §2.1, §4)

### D5. 단일 GPU 2-tier 배치 — FP8 동일 계보 조합

`gemma-4-E4B`는 가중치만 16GB → 단일 4090에서 draft와 2-tier 공존 비현실적
(README의 "별도 GPU 2장" 전제가 이 하드웨어엔 없음). 실측 권장:
`HY-MT1.5-1.8B-FP8`(2GB) + `HY-MT1.5-7B-FP8`(8GB), 가중치 합 ~10GB.
동일 계보라 프롬프트 인프라·용어개입·맥락·서식 기능 공유. GPU 2장 확보 시
gemma-4-E4B bf16을 quality 전용 GPU에 두는 옵션 유지. ([`serving.md`](serving.md))

### 환경 메모

WSL2 + nvcc 미설치에서 vLLM 기동에 필요한 플래그는 [`serving.md`](serving.md#wsl2-필수-플래그) 참고.

---

## 2026-07-17 · 상세 설계 라운드

### D6. Quality tier 기준 모델 = `gemma-4-E2B` (사용자 지정)

Gemma 4 계열 중 가장 작은 모델을 quality tier 기준으로 삼는다(사용자 지정: "vLLM로
구동만 되면"). 실측: `gemma-4-E2B`는 `Gemma4ForConditionalGeneration`(멀티모달 —
audio/vision config 포함, 텍스트측 `gemma4_text` 35층·**128K 컨텍스트**), bf16
가중치 **10.25GB**. 번역엔 텍스트 경로만 사용.

- **M1 검증 필수:** (a) vLLM 0.25.x가 Gemma4 아키텍처를 서빙하는지, (b) 단일
  24GB에서 draft(FP8 2GB)와 공존 시 KV 여유(128K는 과하니 `--max-model-len`을
  8K~32K로 제한). 안 되면 tier가 OpenAI 호환 뒤라 모델 교체로 대응.
- D5의 `HY-MT1.5-7B-FP8`은 계보·기능 관점 대안으로 유지(GPU 2장 또는 교체 시).

### D7. COMET ↔ vLLM 의존성 충돌 — venv 분리

`unbabel-comet`이 `transformers==4.57.6`(v4)를 설치 → vLLM 0.25.x는 transformers v5
요구라 import가 깨진다("Support for Transformers v4 ... removed in vLLM v0.24.0").
→ **채점(COMET)과 서빙(vLLM)은 별도 venv로 분리.** 이미 로드된 서버 프로세스는
영향 없으나, 재기동/신규 import는 충돌. 배포는 tier별 컨테이너로 자연 분리됨.

### D8. 데모 witness 언어(triangulation) — BE에 다중 타겟 fan-out 도입

데모 사용자가 target 언어(id)를 몰라도 번역 품질을 채감하도록, 소스를 **primary
target(id) + witness 언어(en)로 동시 번역**해 나란히 보여준다. en은 COMET 87~90으로
신뢰 가능한 "증인". → 게이트웨이가 초벌 요청을 target 목록으로 fan-out(병렬)하고
revision마다 `{lang: translation}` 다중 렌더를 반환. 초벌 TTFT 12ms·prefix caching
여유(D4)로 N=2~3 타겟 병렬은 저비용. 지원 언어는 `GET /api/v1/languages`로 노출. (design.md §3, §8)

### D9. 세션·턴 저장 = SQLite (Postgres는 스케일 승격 경로)

전역 표준은 PostgreSQL이나, 이 프로젝트 단계엔 SQLite를 쓴다. `bench/db_sqlite_probe.py`
실측(SQLAlchemy async + aiosqlite + WAL):

| 시나리오 | 처리량 | 쓰기 p50/p95 | lock 에러 |
|---|---|---|---|
| 10 세션 동시 | 1,342 w/s | 0.7 / 21.7ms | 0 |
| 50 세션 동시 | 1,372 w/s | 25.8 / 74.6ms | 0 |
| 50 세션 + 동시읽기 | 476 w/s | 92 / 200ms | 0 |
| 200 세션(현실 초과) + 읽기 | 487 w/s | 400 / 506ms | 0 |

근거:
- **전 시나리오 lock 에러 0** (WAL + busy_timeout). 실제 부하는 턴 확정 시에만 쓰기
  (키스트로크마다 아님) — 활성 100세션이 5초마다 확정해도 ~20 w/s로 측정치의 25배 이하.
- 턴 저장은 SSE 최종 경로 밖 → 사용자 대기와 무관.
- 핫패스(초벌 렌더)는 인메모리 캐시(D10), 라이브 상태는 프로세스 내. DB는 저빈도 세션·턴만.
- **`SessionRepository`가 Protocol 뒤라 DB 선택은 연결 URL 한 줄.** 다중 노드로 커지면
  `sqlite+aiosqlite` → `postgresql+asyncpg` URL 교체로 승격, 코드 불변(포트/어댑터 이점).
  SQLAlchemy·Alembic 동일 동작(SQLite ALTER 제약은 Alembic `render_as_batch=True`로 처리).

### D10. Redis 제거 — 데모는 인메모리 캐시

Redis를 빼고 결정성 캐시(D3)를 프로세스 내 bounded LRU로 둔다. 라이브 세션 상태는
`DraftSessionCoordinator`가 이미 프로세스 내 `asyncio.Task`로 소유(별도 저장 불필요).

근거:
- 캐시는 세션별·휘발성이고 미스 비용이 초벌 추론 12ms뿐(D4) → 공유 저장이 불필요.
  캐시의 목적은 지연 절감보다 동일 소스 재요청의 GPU 중복 호출 방지(효율 장치).
- 단일 노드 데모에서 Redis가 값을 하는 지점(다중 프로세스 캐시 공유·WS pub/sub·분산
  rate-limit)이 없다. "불필요한 패키지는 삭제"(Max 표준) + docker compose 단순화.
- `RenderingCache`가 Protocol 뒤라, 다중 노드로 커질 때 `RedisRenderingCache` 구현을
  추가하는 것으로 승격(코드 불변). SQLite→Postgres(D9)와 동일 패턴.
