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

### D6. Quality tier 모델은 **고정하지 않는다** (OpenAI 호환 뒤 교체 가능)

Quality tier 모델은 의도적으로 확정하지 않는다. tier가 OpenAI 호환 API 뒤에 있어
어떤 LLM이든 붙일 수 있고, 실측으로 하나를 못 박기보다 **교체 가능성**을 유지한다.
기준(placeholder)은 Gemma 4 계열 소형 `gemma-4-E2B`(실측: `Gemma4ForConditionalGeneration`
멀티모달, 텍스트측 128K, bf16 10.25GB). 대안 `HY-MT1.5-7B-FP8`(계보·기능).

- **맥락 개선(TMC)은 논문 근거로 갈음한다.** 직전 N턴 이중언어 컨텍스트가 대명사·
  격식·생략을 복원한다는 주장은 Pombal et al.(TACL 2026)에 근거한다 — 모델이 고정
  안 됐으니 우리 자체 측정은 하지 않고, **데모는 "논문 방법으로 맥락 번역한다"고
  주장**한다(over-claim 금지: 우리 측정 수치가 아니라 방법의 근거를 제시).
- 모델을 하나로 고정하는 시점에 vLLM 서빙 여부·레이턴시·`--max-model-len`(128K는
  과하니 8K~32K)만 확인한다. 지금은 설계 블로커가 아니다.

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

### D11. lay user에게 품질 전달 — 시각·상호작용 장치 (구문 트리 배제)

일반 사용자는 벤치마크 점수를 해석하지 못하고 유창한 출력이면 틀려도 믿는다
(automation bias). MT UX 연구를 조사해(아래 출처) 품질 전달을 **숫자가 아니라 시각·
상호작용**으로 설계한다. 채택:
- **구 정렬 hover**(소스↔타겟↔witness 대응 강조 — 커버리지를 눈으로), **witness 언어**,
  **단어 수준 QE 색상**(불확실 구간만 — CometKiwi 파생), **역번역 검증 버튼**(보조).
- 숫자 COMET/QE는 전문가·디버그 패널에만.
- **정직성**: 불확실성을 드러낸다. 다 초록으로 칠하면 거짓 신뢰(연구가 automation
  bias·"interpretability가 오히려 과신 유발"을 경고).

**배제 — 구문(syntax) 트리로 품질 증명**: (a) ko(SOV)↔id/en(SVO)은 M0에서 접두어
생존율 ≈0%(D3)로, 좋은 번역일수록 트리가 다르다 → 트리 유사도가 품질과 역행. (b)
구문 기반 MT 메트릭은 신경망 메트릭(COMET/CometKiwi)으로 대체됨. (c) lay user에게
파스 트리는 witness 텍스트보다 덜 직관적. 좁은 용도(타겟 파싱 가능성=약한 유창성
프록시, under-the-hood 교육 패널)만 있고 품질 증명은 못 함.

출처:
- Translation in the Hands of Many: MT as a (Lay) User-Facing Technology — arXiv:2502.13780
- User Strategies for Mistranslations in MT-Mediated Chat — CHI, ACM 10.1145/3531146.3534638
- Beyond General Purpose MT: Designing for Appropriate User Trust — arXiv:2205.06920
- Revisiting Round-Trip Translation for Quality Estimation — arXiv:2004.13937
- QE4PE: Word-level Quality Estimation for Human Post-Editing — arXiv:2503.03044

### D12. BE 하드닝 — open 항목을 결정으로 확정

자체 점검에서 남겼던 항목들을 데모 기준으로 결정한다(과설계 없이).

- **백프레셔/동시성 상한**: tier별 `asyncio.Semaphore(N)`로 게이트웨이→vLLM 동시
  요청을 제한(N은 vLLM 최대 배치에 맞춰 설정, 기본 8). 초과분은 큐잉. WS 초벌은
  연결당 single-flight로 이미 중복을 접으므로 폭주를 이중 방어. openai 클라이언트에
  요청 타임아웃 설정.
- **턴 멱등성**: `POST …/turns`에 클라이언트 생성 `idempotency_key`(확정 draft의
  revision 기반 UUID). 세션 내 동일 키가 있으면 기존 턴 결과를 반환. 턴 행에 유니크
  제약(session_id, idempotency_key).
- **인증**: 데모는 무인증. `session_id`는 추측 불가한 UUIDv4로, 세션 스코프 접근의
  capability 토큰 역할. 공개 배포 시 fastapi-standards §2(OAuth2/JWT)로 승격.
- **취소→vLLM abort**: vLLM은 클라이언트 disconnect 시 생성을 abort하는 문서화된
  동작에 의존한다(스트림 close로 유도). M1 배선 시 통합 테스트로 확인만, 설계
  블로커 아님.
- **컨텍스트 예산**: 최근 N턴 유지 + 토큰 예산 초과 시 **오래된 턴부터 절단**. 요약은
  도입하지 않는다(데모 YAGNI). `ContextAssembler(max_turns, token_budget)`가 담당.
- **방향 스왑 컨텍스트**: `ko⇄en` 스왑은 방향을 뒤집고 **활성 컨텍스트를 리셋**한다
  (새 방향 = 새 대화 스레드). 이전 턴은 이력 조회로 남되 방향이 바뀐 컨텍스트로는
  주입하지 않는다.

### D13. 품질증명 장치 — 데모 기준은 "설득력 있는 시각화" (정렬 하이라이팅 센터피스)

데모의 기준을 명확히 한다: **엄밀한 품질 증명이 아니라 설득력 있는 시각화**(단,
값은 실제 계산 — fake 금지). 이 기준에서 우선순위:

- **센터피스: 구 정렬 하이라이팅.** 소스 구 ↔ 대응 번역 구를 같은 색으로 잇는다 —
  데모에서 가장 설득력 있는 비주얼("조각조각 정확히 옮겼다"가 한눈에). SimAlign
  (mBERT/XLM-R 임베딩, zero-shot, 학습 불필요)으로 (소스, 최종) 쌍에서 **턴 확정 시
  1회** 계산 → 타이핑 지연과 무관, 캐시. 실제 정렬이라 뜯어봐도 성립.
- **주력**: 단어 QE 색상(초록빛 안심, CometKiwi 파생) · witness 언어 · 역번역(가장 직관적).
- 숫자 점수는 디버그 패널만. 구문 트리·LLM 첨언은 안 씀(트리는 어순 비대응으로 무의미).
- 정직성 가드(design §8.5)는 유지: 모든 표시는 실제 계산값. "그럴듯"을 fake로 하지 않는다.

> D13 개정: 초기엔 정렬을 deferred로 뒀으나(엄밀 증명 기준), 데모 기준이 "설득력"으로
> 명확해져 정렬 하이라이팅을 센터피스로 승격. 실현성은 SimAlign로 해결됨(실측 불필요).

**SimAlign 실측 검증 (`bench/align_simalign.py`, mBERT zero-shot, 실제 HY-MT 출력):**
- 내용어(명사·동사) 대응이 그럴듯하게 나온다 — 예: `회의를→rapat/meeting`,
  `취소하고→membatalkan/cancel`, `금요일로→Jumat/Friday`, `옮겨→menggantinya/move`,
  `오후→sore/afternoon`. ko→en·ko→id 모두 데모 설득력 충분.
- **속도**: 쌍당 26~115ms(턴 확정 시 1회), mBERT 로드 24s 1회. 타이핑과 무관.
- 약점: 조사/기능어 노이즈, `그거→that` 같은 대명사는 놓침(그거→I 오정렬). 데모
  하이라이팅에는 내용어 대응이면 충분 — 구현 시 구두점·저신뢰 정렬 제거 + 구 단위 병합.
- **환경 분리(D7 확장)**: simalign(transformers 필요)은 vLLM·COMET과 transformers/torch
  버전이 충돌한다(측정 중 torch 2.13↔2.11 재설치 확인). 정렬은 **서빙과 별도 컨테이너**
  (reranker처럼)로 둔다. `pyproject`의 `bench` optional은 이 도구들을 나열만 하며
  동일 env 공존 불가.

**eflomal(순수 통계) 실측 (`bench/align_eflomal.py`):** "AI 아님"으로 스켑틱을
설득하려 통계 정렬을 검증. 학습데이터 OpenSubtitles v2018 ko-en(139만)·ko-id(59만)
서브셋 15만쌍, IBM1+HMM+fertility, ~10초/30만쌍(신경망·transformers 0, 의존성 충돌 없음).
- **결과: SimAlign보다 품질 낮음.** 내용어 일부는 맞지만(오후→afternoon, 회의를→rapat,
  금요일로→jumat) 명확한 오류가 남음(회의를→move, 취소하고→menggantinya, 헤드폰이→lalu).
  커버리지 71~79%지만 틀린 링크 혼재.
- **원인**: 한국어 교착어(조사 붙은 어절 희소 → 통계 정렬 취약, SimAlign은 subword로 강함),
  도메인 불일치(자막↔지원), HMM 위치 편향.
- **판정**: 신뢰 데모엔 틀린 링크가 치명적(정렬 없음보다 나쁨). eflomal로 가려면 한국어
  형태소 토크나이저(mecab/khaiii)로 조사 분리 + 데이터 증량 필요(→ mecab 의존성 재발생).
  → eflomal은 형태소 분석 붙일 때만 후보.

**awesome-align(사전학습 정렬 모델) 실측 — 정렬 센터피스 확정:** 직접 학습 대신
정렬용으로 fine-tune된 `aneuraz/awesome-align-with-co`(mBERT 기반) 다운로드·검증
(`bench/align_simalign.py <model>`).
- **셋 중 최고 품질.** 데모 문장 내용어가 ko→en·ko→id 모두 정확 정렬. 특히 **`그거→that`을
  맞춤** — eflomal·vanilla SimAlign이 놓친 대명사를 사전학습 모델은 잡음. 26~151ms(로드 19s).
- **의존성 충돌 회피 경로**: 같은 모델의 ONNX 버전 `cstr/awesome-align-onnx`를
  onnxruntime로 실행하면 torch/transformers 불필요 → vLLM·COMET과 충돌 없음.
- **결정**: 정렬 센터피스 = **awesome-align(사전학습)**. 학습 불필요. 배포는 transformers
  (별도 컨테이너, D7) 또는 ONNX(충돌 없음). eflomal(직접학습)·vanilla SimAlign보다 우수.

### D14. 대화 저장소(conversations/messages) = 번역 파이프라인과 분리된 뷰 모델

FE 좌측 패널을 "번역 세션 저장소"로 만들며(대화 목록·클릭 복원), 저장 계층을
**엔진용 `sessions`/`turns`와 분리**한다.

- **왜 분리했나**: `sessions`/`turns`는 번역 스트리밍(초벌 WS·최종 SSE·컨텍스트 조립)용이고,
  한 대화는 방향이 다른 **두 엔진 세션**(운영자 src→tgt, 고객 tgt→src)으로 구성된다.
  이를 하나의 사용자 대화로 되돌리려면 순서·측면(mine/theirs)을 가진 별도 뷰가 필요하다.
  엔진 세션 모델을 양방향으로 바꾸는 대규모 리팩터 대신, **UI가 렌더한 최종 메시지를 그대로
  담는 append-only 뷰 모델**(`conversations` + `messages`)을 추가한다(additive, 저위험).
- **스키마**: `conversations`(id·src·tgt·witness·title·created_at) + `messages`(seq·side·
  source·translation·witness·created_at). title=첫 메시지 원문(60자). 목록은 마지막 메시지
  시각 desc. `create_all`로 추가 생성(기존 테이블 불변, 마이그레이션 불필요).
- **FE 흐름**: 첫 메시지에서 대화 **지연 생성** → 이후 append. 클릭 시 상세를 받아 언어쌍
  복원(엔진 세션 재생성 트리거) + 메시지 복원. "새 대화"·스왑은 대화 컨텍스트 초기화.
- **알려진 한계**: 저장된 대화를 다시 열어 이어가면 **엔진 컨텍스트는 새로 시작**한다(엔진
  세션은 신규). 이력 열람·재개 UX가 목표이므로 수용. 완전한 문맥 승계는 세션 시드가 필요(후속).
- **의도적 중복**: `messages`는 `turns`와 데이터가 겹치나 목적이 다르다(사용자 이력 뷰 vs
  엔진 컨텍스트 소스). 이벤트 로그↔뷰 모델 분리로 보고 drift로 취급하지 않는다.

### D15. Quality tier = Qwen3-4B-Instruct + Pombal 컨텍스트 프레임워크

M1까지 quality tier를 draft(HY-MT)로 degrade해 두었으나(초벌==최종으로 보임), 실제
경량 LLM을 서빙해 **문맥 반영 최종 번역**을 만든다.

- **모델 선정**: Gemma 3/4 계열은 HF gated(수동 승인)라 read-only 토큰으로 불안정 →
  **open 모델 `Qwen/Qwen3-4B-Instruct-2507`** 채택(다국어 우수, 경량). 단일 RTX 4090을
  draft와 공유: draft `--gpu-memory-utilization 0.30`(~7GB) + quality `0.50`(~12GB) = ~19/24GB.
  서빙은 docker compose(`vllm-draft`·`vllm-quality`)로 코드화(WSL2 플래그 포함).
- **컨텍스트 = Pombal et al.(TACL 2026)** *A Context-aware Framework for Translation-mediated
  Conversations*. 핵심: 컨텍스트로 직전 턴들의 **원문(x_<t)** 을 순서대로 주입한다(번역문
  아님). 화자 역할·메타데이터는 넣지 않는 미니멀 구성. 6~10턴이면 대부분 충분(§6.1).
  - 우리 구조: 엔진 세션이 방향별로 분리(운영자/고객)라 세션 턴만으론 한쪽만 보인다. 그래서
    **FE가 대화의 이전 원문열(양측, 순서대로)을 턴 요청 `context`에 담아 전달**하고, 서버는
    `ContextAssembler.trim`(최근 N턴·문자예산) 후 `QwenPromptBuilder.build_contextual`로
    context-augmented 프롬프트를 만든다. 결합도 낮고 양측 맥락을 모두 반영.
- **정직한 degrade**: quality 엔진 도달 불가/미등록 시 draft로 폴백하고 `degraded=True`.
- **실측**: `그거 금요일까지 보내주세요` → quality "Please send that by Friday"(정상) vs
  draft "Please keep that until Friday"(오역). 초벌 "move the meeting" vs LLM "reschedule
  the meeting"처럼 두 tier가 실제로 다른 출력을 낸다. 동음이의어 완전 해소는 4B 용량 한계.

### D16. 검증 스위트 완성 — 정렬 서비스 분리 (호스트 → 컨테이너)

D13에서 정렬 센터피스로 awesome-align을 확정했고, 이제 검증 4종(witness·QE·역번역·
정렬)을 모두 배선한다.

> **개정**: 처음엔 torch 이미지 빌드를 피하려 호스트 프로세스(:8003)로 뒀으나, 전 스택
> 도커화(전 스택 `docker compose --profile gpu up`) 방향에 맞춰 **`aligner/Dockerfile`로
> 컨테이너화**했다(호스트 HF 캐시 마운트로 모델 재사용). 호스트 런처 `serve_*.sh`는 제거.

- **정렬 서비스 분리**: transformers/torch가 vLLM·COMET과 충돌(D7)하므로 게이트웨이와
  별도 서비스로 띄운다. `aligner/app.py`(FastAPI) + `aligner/Dockerfile`(CPU, simalign).
  모델 `aneuraz/awesome-align-with-co`는 호스트 HF 캐시를 마운트해 재다운로드 없이 로드.
- **호출·정직성**: 게이트웨이 `HttpAligner`가 턴 확정 시 1회 호출(초벌 핫패스 아님).
  도달 불가/타임아웃이면 빈 목록으로 **graceful degrade** — 정렬은 보조 시각 장치라
  없어도 번역은 성립. 어절 단위 정렬 → 문자 오프셋 스팬, 구두점-only 대응은 제거.
- **QE + 정렬 공존**: 최종 번역 줄에서 QE(저신뢰 amber 밑줄)와 정렬(hover 배경 강조)을
  **다른 시각 채널**로 겹쳐 렌더(서로 간섭 없음). 소스 구에 hover하면 대응 번역 구가
  같이 강조된다.
