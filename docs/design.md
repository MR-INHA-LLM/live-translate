# 상세 설계서 (design)

이 문서는 M0 실측을 근거로 M1~M5 구현이 그대로 따라갈 **설계 명세**다. 개요는
[README](../README.md), 결정 근거는 [`decisions.md`](decisions.md), 서빙은
[`serving.md`](serving.md), 측정 원본은 [`../bench/RESULTS_M0.md`](../bench/RESULTS_M0.md).

> **설계를 지배하는 실측 사실 (근거: decisions.md)**
> - 초벌 추론 TTFT p50 **12.5ms** → 추론은 병목이 아니다. **디바운스(150~250ms)가
>   레이턴시 예산을 지배**하고, 다중 타겟 병렬 번역을 감당할 여유가 크다. (D4)
> - ko(SOV)↔id(SVO) 접두어 생존율 **≈0%** → **목표문 접두어 확정(hold-k)은
>   flicker 해법이 아니다.** 전체 tentative 렌더 + revision 순서제어로 간다. (D3)
> - temp=0 **완전 결정적** → 동일 소스는 동일 출력. 캐시·중복요청 제거 가능. (D3)
> - 초벌 6방향 평균 **COMET 88.59**, `ko↔id` 직접 87.8~87.9 = `ko↔en`급. en은
>   신뢰 가능한 **witness(증인) 언어**로 쓸 수 있다. (D1·D2)

---

## 1. 컴포넌트 아키텍처

```mermaid
flowchart TB
  FE["Demo FE (Vite/React)"]
  subgraph GW["Gateway (FastAPI :8000)"]
    LANG["LanguageCatalog<br/>지원 언어·검증 쌍"]
    SESS["SessionStore (Redis)<br/>세션·대화이력·설정"]
    DRAFT["DraftRouter<br/>디바운스·revision·abort·fan-out"]
    QUAL["QualityRouter<br/>TMC 컨텍스트 조립·degradation"]
    RER["Reranker (opt, M4)<br/>CometKiwi QAD"]
    ENG["EngineClient<br/>OpenAI 호환 async 클라이언트"]
    MET["Metrics/Health"]
  end
  DVLLM["vLLM :8001<br/>HY-MT1.5-1.8B-FP8 (draft)"]
  QVLLM["vLLM :8002<br/>gemma-4-E2B (quality)"]

  FE -- "WS /v1/stream (초벌)" --> DRAFT
  FE -- "SSE /v1/turn (최종)" --> QUAL
  FE -- "REST /v1/sessions, /v1/languages" --> SESS
  FE -- "REST /v1/languages" --> LANG
  DRAFT --> ENG --> DVLLM
  QUAL --> ENG --> QVLLM
  QUAL -.-> RER
  DRAFT & QUAL --> SESS
  GW --> MET
```

**책임 분리**
| 컴포넌트 | 책임 | 상태성 |
|---|---|---|
| `LanguageCatalog` | 지원 언어·언어명·검증된 쌍(+COMET) 제공 | 정적(설정) |
| `SessionStore` | 세션 설정·대화 이력·턴 로그. TTL. | Redis |
| `DraftRouter` | WS 수신 → 디바운스·revision 순서·이전요청 abort·다중 타겟 fan-out | 세션별 in-memory task |
| `QualityRouter` | 확정 문장 → TMC 컨텍스트 프롬프트 조립 → 스트리밍. 실패 시 degradation | stateless(세션 조회) |
| `EngineClient` | tier별 vLLM(OpenAI 호환)로 async 스트리밍/취소 | 커넥션 풀 |
| `Reranker` | (M4) 후보 N개 → CometKiwi 스코어 | optional |

---

## 2. 데이터 모델 (Pydantic v2)

```python
# 언어 (LanguageCatalog)
class LanguagePair(BaseModel):
    src: str; tgt: str
    validated: bool = False           # M0에서 측정했나
    comet: float | None = None        # FLORES-200 devtest COMET (검증된 쌍만)

class LanguageInfo(BaseModel):
    code: str                         # "ko"
    name_en: str                      # "Korean"
    name_native: str                  # "한국어"
    is_dialect: bool = False

# 세션 설정
class RerankConfig(BaseModel):
    enabled: bool = False
    n_candidates: int = Field(4, ge=2, le=8)
    metric: Literal["cometkiwi"] = "cometkiwi"

class StabilityConfig(BaseModel):
    debounce_ms: int = Field(200, ge=0, le=1000)
    commit_prefix: bool = False       # D3: 어순 유사 쌍에서만 켠다. 기본 off.

class SessionConfig(BaseModel):
    src_lang: str
    tgt_lang: str                     # primary target
    witness_langs: list[str] = ["en"] # D8: 동시 렌더링할 증인 언어(데모)
    domain: str = "general"
    formality: Literal["polite", "casual", "neutral"] = "neutral"
    draft_model: str = "hy-mt1.5-1.8b"
    quality_model: str = "gemma-4-e2b"
    rerank: RerankConfig = RerankConfig()
    stability: StabilityConfig = StabilityConfig()

class Turn(BaseModel):
    turn_id: int
    source: str
    draft: dict[str, str]             # {lang: 최종 draft 번역}
    final: str | None                 # primary target quality 결과
    candidates_scored: int = 0
    latency_ms: dict[str, float]      # {"draft_ttft","draft_total","final_ttft","final_total"}
```

`SessionConfig` 검증: `src_lang`·`tgt_lang`·`witness_langs`는 모두
`LanguageCatalog`에 존재해야 하고 서로 달라야 한다(witness에 tgt/src 중복 시 제거).

---

## 3. 지원 언어 & 언어 능력 노출

draft 모델(HY-MT1.5)이 지원하는 **33개 언어(+방언/소수민족 변형)**를 카탈로그로
제공한다. FE는 이 목록으로 언어 선택기와 "지원 언어" 패널을 그린다.

### `GET /v1/languages`
```jsonc
{
  "languages": [
    { "code": "ko", "name_en": "Korean",    "name_native": "한국어" },
    { "code": "id", "name_en": "Indonesian","name_native": "Bahasa Indonesia" },
    { "code": "en", "name_en": "English",   "name_native": "English" }
    // … zh, ja, vi, th, ms, tl, hi, fr, de, es, pt, it, ru, ar, tr, pl, cs, nl,
    //    km, my, fa, gu, ur, te, mr, he, bn, ta, uk, bo, kk, mn, ug
  ],
  "validated_pairs": [                      // M0에서 실측한 쌍만 COMET 노출
    { "src": "ko", "tgt": "id", "comet": 87.90 },
    { "src": "id", "tgt": "ko", "comet": 87.80 },
    { "src": "ko", "tgt": "en", "comet": 87.12 },
    { "src": "en", "tgt": "ko", "comet": 90.25 },
    { "src": "en", "tgt": "id", "comet": 90.67 },
    { "src": "id", "tgt": "en", "comet": 87.81 }
  ],
  "default_witness": "en"
}
```

- **미검증 쌍도 지원은 됨** — `validated`는 "M0에서 COMET을 쟀나"일 뿐. FE는 검증된
  쌍에 품질 배지(예: `COMET 87.9`)를, 그 외엔 "지원(미측정)"으로 표시.
- 카탈로그 소스는 draft 모델 카드의 언어 태그. 모델 교체 시 카탈로그만 갱신.

---

## 4. 초벌(draft) 파이프라인

### 4.1 클라이언트 입력 상태기 (FE)

```mermaid
stateDiagram-v2
  [*] --> Idle
  Idle --> Composing: compositionstart (IME)
  Composing --> Composing: compositionupdate (버퍼만, 미전송)
  Composing --> Settled: compositionend
  Idle --> Settled: 일반 keydown
  Settled --> Debounce: 입력 변화
  Debounce --> Sending: debounce_ms 경과 & 어절 경계
  Sending --> Settled: DraftResponse 수신(tentative 렌더)
  Settled --> Final: Enter (문장 확정)
  Final --> [*]: /v1/turn 트리거
```

- **IME 조합 제거:** `compositionupdate` 중인 자모(`안녕하세ㅇ`)는 절대 전송하지
  않는다. `compositionend` 확정 문자열만 대상. (한글 기준 우선 테스트 — README §2.1)
- **디바운스:** `debounce_ms`(기본 200) + 어절 경계 도달 시에만 revision 발사.
  추론이 12ms이므로 이 값이 flicker↔반응성의 실질 튜닝 손잡이. (D4)
- revision마다 `revision_id`를 단조 증가시켜 전송.

### 4.2 게이트웨이 초벌 처리 (BE)

```mermaid
sequenceDiagram
  participant FE
  participant DR as DraftRouter
  participant EC as EngineClient
  participant V as vLLM draft
  FE->>DR: {revision_id:n, partial_text, is_final:false}
  Note over DR: revision_id < last_seen ? → drop(stale)
  DR->>DR: 진행 중 task 있으면 cancel(abort)
  Note over DR: 정규화 소스 == 직전 == ? → 캐시 반환(D3 결정성)
  par 타겟별 병렬 fan-out (tgt + witness)
    DR->>EC: translate(src→id) stream
    DR->>EC: translate(src→en) stream
  end
  EC->>V: /chat/completions (stream, temp=0)
  V-->>EC: tokens…
  EC-->>DR: 렌더 조각
  Note over DR: revision_id == last_seen ? (아니면 폐기)
  DR-->>FE: {revision_id:n, renderings:{id,en}, latency_ms}
```

**핵심 규칙 (실측 근거)**
1. **다중 타겟 fan-out (D8):** `[tgt_lang] + witness_langs`를 `asyncio.gather`로 병렬
   번역. 각 타겟은 프롬프트가 달라 KV 접두어는 분리되지만, 타이핑 리비전 간
   접두어 재사용은 타겟별로 유효 → prefix caching 이득 유지.
2. **revision 순서 제어 (D3):** 응답이 역전 도착해도 `revision_id`가 현재 최신일
   때만 FE로 전달. 새 입력 도착 시 이전 task를 `cancel()` → vLLM은 클라이언트
   중단 시 생성을 abort하므로 GPU 낭비 없음.
3. **결정성 캐시 (D3):** 정규화 소스가 직전과 동일하면(백스페이스 후 복원 등)
   재요청 없이 캐시 렌더 반환.
4. **tentative 렌더 (D3):** 응답은 목표문 전체를 담고, FE는 **미확정 = 흐리게**
   렌더. `commit_prefix=false`가 기본. 어순 유사 쌍에서 켜면 응답에
   `committed_prefix_len`(타겟별)을 실어 보낸다.
5. **greedy·타이트:** `temperature=0`, `max_tokens` 소스 길이에 비례한 상한.

### 4.3 파라미터 (초벌)
`temperature=0`, prefix caching on, `max_tokens ≈ len(src_tokens)*2 + 16`.
세션 생성 시 **워밍업 요청 1회**로 콜드 TTFT(222ms) 제거. (D4)

---

## 5. 최종(quality) 파이프라인

### 5.1 컨텍스트 조립 (TMC)

Pombal et al. (TACL 2026)를 따른다. `is_final` 문장이 오면:

1. SessionStore에서 **직전 N턴의 이중언어(원문/번역) 쌍**을 가져온다(기본 N=5,
   토큰 예산 초과 시 오래된 턴부터 절단 — 요약은 후속 과제).
2. HY-MT 계열이면 **contextual template**(모델 카드의 중국어 지시형)에 컨텍스트를
   주입; Gemma 계열이면 system+few-shot 형태로 대화 맥락을 구성.
3. `domain`·`formality`를 지시에 반영(예: `formality=polite` → 존댓말/`Anda`).

```mermaid
sequenceDiagram
  participant FE
  participant QR as QualityRouter
  participant EC as EngineClient
  participant Q as vLLM quality
  FE->>QR: POST /v1/turn {text, rerank?}
  QR->>QR: 직전 N턴 이중언어 컨텍스트 조립 + domain/formality
  QR->>EC: (rerank off) stream 1회
  EC->>Q: /chat/completions (stream)
  Q-->>FE: SSE event: token …
  alt rerank on (M4)
    QR->>EC: n_candidates 생성 → CometKiwi 스코어 → best
  end
  QR->>FE: SSE event: done {turn_id, translation, latency, candidates_scored}
  QR->>QR: Turn 저장(source, draft, final, latency)
```

### 5.2 Graceful degradation
quality tier 오류/타임아웃 시 해당 턴의 **primary target draft 결과를 최종으로
승격**하고 `degraded:true`로 done 이벤트를 보낸다. 데모가 멈추지 않는다.

### 5.3 witness 언어(최종)
비용 관리: **primary target만 quality tier**를 태우고 witness(en)는 draft 결과를
유지(증인의 역할은 신뢰 신호이지 최상 품질이 아님). 설정으로 witness도 quality로
올릴 수 있게 둔다.

### 5.4 Quality 모델 교체 후보
tier가 OpenAI 호환 뒤라 모델 교체 자유. 기준 `gemma-4-E2B`(D6) 외:
- `HY-MT1.5-7B(-FP8)` — 용어개입·문맥번역·서식유지 native, 단일 GPU FP8 배치 유리(D5).
- `MiLMMT-46-12B` — 46개 언어 범위에서 Tower-Plus-9B / Seed-X-7B / TranslateGemma 상회 보고.
- `gemma-4-26B-A4B` — MoE, 처리량 유리(GPU 여유 시).
- Gemma 4 MTP(Multi-Token Prediction) drafter 별도 배포 → 최종 tier TTFT 개선 검토.

---

## 6. 프로토콜 계약

### `POST /v1/sessions` → `201`
Body = `SessionConfig`. 응답 `{ "session_id": "..." }`. 생성 시 워밍업 수행.

### `GET /v1/languages` → `200`
§3 참조.

### `WS /v1/stream` — 초벌
```jsonc
// client → server
{ "session_id":"…", "revision_id":17, "partial_text":"내일 회의를 오후로", "is_final":false }

// server → client  (revision마다; 다중 렌더)
{
  "revision_id":17,
  "renderings": { "id":"Rapat besok ke sore", "en":"the meeting to the afternoon" },
  "committed_prefix_len": { "id":0, "en":0 },   // commit_prefix=false면 항상 0
  "latency_ms": { "ttft":12, "total":88 }
}
```
- `is_final:true` 수신 → 초벌 마무리 + 서버가 자동으로 최종 파이프라인을 큐잉(또는
  FE가 명시적으로 `/v1/turn` 호출; 데모는 후자로 프롬프트/후보를 노출).
- **오류 처리:** stale revision은 조용히 drop. 업스트림 오류는
  `{ "revision_id":n, "error":"upstream_draft_error" }`.

### `POST /v1/turn` (SSE) — 최종
```jsonc
// request
{ "session_id":"…", "text":"내일 회의를 오후로 옮겨도 될까요?", "rerank":true }
// events
event: token  data: {"delta":"Bisa"}
event: done   data: {"turn_id":5,"translation":"…","candidates_scored":4,
                     "degraded":false,"latency_ms":{"ttft":340,"total":1180}}
event: error  data: {"code":"upstream_quality_error","degraded_to_draft":true}
```

### `GET /v1/sessions/{id}/turns` → 턴별 원문/초벌/최종/레이턴시 이력
### `GET /health` → tier별 모델 로드 상태 · `GET /metrics` → §9

**에러 코드**: `session_not_found`(404) · `unsupported_language`(422) ·
`stale_revision`(silent) · `upstream_draft_error` · `upstream_quality_error`(→degrade) · `rate_limited`(429).

---

## 7. 동시성 / 취소 모델

- 초벌은 **세션당 하나의 활성 revision**만 유효. `DraftRouter`가 세션별
  `asyncio.Task`를 들고 있다가 새 revision 도착 시 `task.cancel()`.
- `EngineClient`는 `httpx.AsyncClient` 스트리밍. 취소 시 응답 스트림을 닫아 vLLM
  업스트림 생성을 중단(클라이언트 disconnect → vLLM abort).
- 타겟 fan-out은 하나의 revision task 안에서 `asyncio.gather(*targets)`; 일부 타겟
  실패해도 `return_exceptions=True`로 나머지는 렌더.
- 초벌·최종은 **반드시 별도 vLLM 인스턴스**(같은 엔진이면 초벌이 최종 뒤에 큐잉).
  GPU 배치는 [`serving.md`](serving.md).

---

## 8. 데모 UX 설계 (FE)

### 8.1 데모의 역할 — 무엇을 증명하는가

데모는 기능 나열이 아니라 **하나의 논증**이다. 주장별 난이도가 다르다:

| 주장 | 증명 장치 | 난이도 |
|---|---|---|
| ① 빠르다 | 레이턴시 오버레이(실측 TTFT 12ms) | 쉬움 |
| ② target을 몰라도 믿을 수 있다 | witness 언어(en) 동시 렌더 | 쉬움 |
| ③ 지원 범위가 넓다 | `/v1/languages` 33종 | 쉬움 |
| ④ **quality tier가 지연을 정당화한다** | **아래 8.3** | **어려움 — 데모의 승부처** |

④가 핵심이다. 짧은 문장은 draft==final이라 quality tier가 무의미해 보인다(README
§7이 경고한 함정). 데모의 설계 전체가 **④를 id를 모르는 사람에게도 보이게** 하는 데
집중한다.

### 8.2 화면 레이아웃
```
┌──────────────────────────────────────────────────────────────────┐
│ 모드 [시나리오 ▾ | 자유]  언어 [ko ▸ id]  witness [en]  맥락 [on]  │  ← /v1/languages
├───────────────┬────────────────────────────┬─────────────────────┤
│  입력 (ko)     │  PRIMARY  id               │  WITNESS  en        │
│  그거 오늘…    │  draft:(흐림) hal itu…      │  draft: handle that │  ← 초벌(맥락 없음)
│                │  final:      pengirimannya… │  final: the shipment│  ← 최종(맥락)
├───────────────┴────────────────────────────┴─────────────────────┤
│ 왜 바뀌었나: 대명사 '그거' → 이전 턴의 '배송'으로 복원 (맥락)      │  ← diff 주석
│ 레이턴시  draft 12ms/88ms · final 340/1180ms   | 콜드·degraded 표시 │
│ 대화 로그 (턴별 원문·초벌·최종)                                    │
└──────────────────────────────────────────────────────────────────┘
```

### 8.3 quality tier를 "보이게" 한다 (④ — 데모의 승부처)

- **witness로 개선을 읽는다 (핵심 재설계):** witness-en을 primary(id)의 **draft와
  final 양쪽**에 렌더한다. id를 모르는 사용자가 영어로 *개선 자체*를 읽는다 —
  draft en `"handle that"` → final en `"process the shipment"`(`그거`가 맥락으로
  복원). 즉 witness는 "id가 맞나"를 넘어 **맥락 tier가 무슨 일을 하는지**를 비-화자에게
  전달하는 렌즈다. (COMET 87~90이라 en 신호는 정직하다 — D1)
- **counterfactual 토글(맥락 on/off):** 같은 문장을 맥락 없이/있이 나란히 →
  quality tier의 기여를 격리해 보여준다.
- **"왜 바뀌었나" 주석:** draft↔final 차이에 언어학적 이유(대명사 지시·격식·주어
  생략 복원)를 태깅. 시나리오는 이 현상들이 걸리도록 설계.
- **확정/미확정 시각 구분:** 미확정 초벌은 흐리게, `is_final` 후 최종은 선명하게.
  `commit_prefix` on일 때만 접두어 확정 스타일.

### 8.4 두 가지 모드
- **시나리오 모드:** 준비된 다중 턴 대화(대명사 `그거`, 주어 생략, 존댓말)를 재생 →
  ④가 반드시 드러난다. 시나리오는 `bench/eval_set.py`의 대화 프로브 재사용.
- **자유 모드:** 사용자가 직접 타이핑 → 속도·IME·견고성·flicker 억제를 체감.
  (여기선 draft==final일 수 있음을 감수 — 속도 증명용.)
- (디버그) **역번역 검사:** primary(id)를 `id→en`으로 되번역해 witness와 비교 →
  id 출력을 직접 검증. 한 홉 추가라 옵션.

### 8.5 정직한 신호 (신뢰의 일부)
숨기지 않는다: **콜드 첫 요청**(TTFT 튐), **degradation**(quality 실패 → draft 승격
배지), **레이턴시 p95**. 실패 모드를 우아하게 보여주는 것이 데모의 신뢰를 높인다.

### 8.6 지원 언어 노출
언어 선택기는 `/v1/languages`로 채우고, 검증된 쌍엔 `COMET 87.9` 배지, 나머지엔
"지원(미측정)". "지원 언어 33종" 요약 뱃지 + 펼침 목록.

### 8.7 데모 시나리오 = 살아있는 명세
시나리오 대화는 **E2E 테스트 픽스처로 재사용**한다(Max 원칙 4). "이 대화에서 final은
`그거`를 이렇게 복원해야 한다"가 곧 회귀 테스트의 기대값이 된다 — 데모와 테스트가
같은 소스를 공유.

---

## 9. 관측성

`GET /metrics`(Prometheus 형식):
- tier별 **TTFT·total 히스토그램**(p50/p95/p99).
- **abort rate** — revision이 진행 중 요청을 취소한 비율(= flicker/낭비 신호, 튜닝 지표).
- **cache hit rate** — 결정성 캐시(D3) 적중률.
- **degradation count** — quality→draft 승격 횟수.
- 초벌 req/s, 타겟 fan-out 배수(witness 수).

`GET /health`: tier별 vLLM `/v1/models` 도달성 + 모델 로드 여부.

---

## 10. 배포 / 환경

- tier별 **별도 vLLM 인스턴스**, 단일 24GB 배치는 [`serving.md`](serving.md).
  quality 기준 모델 `gemma-4-E2B`(멀티모달 128K; `--max-model-len` 8K~32K 제한 권장).
- **venv 분리 (D7):** COMET(transformers v4)와 vLLM(v5)은 의존성 충돌 → 별도
  환경/컨테이너. reranker(CometKiwi, M4)는 quality 서버와 다른 컨테이너.
- 인프라는 Docker Compose로 코드화(게이트웨이·draft vLLM·quality vLLM·redis·nginx).

---

## 11. 미해결 / M1 검증 항목

- [ ] vLLM 0.25.x의 **Gemma4 아키텍처 서빙 여부** + 단일 GPU KV 실현성 측정(D6).
- [ ] 최종 tier TTFT/완료 실측(README §4 미측정 행).
- [ ] `commit_prefix`를 켤 만한 어순 유사 쌍 식별(예: ko↔ja) — 접두어 확정 실효 측정.
- [ ] 컨텍스트 길이 증가 시 절단 vs 요약 정책.
- [ ] rerank(CometKiwi)의 context-aware 변형 학습 여부(M4).
- [ ] FLORES+ gated 재측정으로 README 원문 데이터셋 parity(gate 승인 후).
