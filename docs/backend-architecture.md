# 백엔드 아키텍처 (gateway)

게이트웨이(FastAPI)의 내부 구조를 정의한다. 기능 요구는 [`design.md`](design.md),
이 문서는 **그 요구를 어떤 구조·추상·의존성으로 구현하는가**를 다룬다. 이 문서가
`app/` 패키지 구조의 기준이며 design.md §1·§6의 개략 구조를 대체한다.

**준수 표준**: `fastapi-standards`(API 설계·프로젝트 구조·에러)·`python-standards`
(OOP·타입힌트·uv·로깅·보안). 이 문서의 구조·네이밍은 두 표준을 따른다.

## 0. 설계 목표

- **교체 가능성**: 모델(draft/quality)·엔진·저장소를 코드 수정 없이 갈아끼운다.
  두 tier가 OpenAI 호환 뒤에 있고(design.md) 모델은 언제든 바뀐다는 전제(D6)에서 나온 제약이다.
- **테스트 가능성**: 네트워크(vLLM)·DB 없이 서비스 로직을 단위 테스트한다.
- **표준 구조**: 처음 여는 사람이 표준 FastAPI 레이아웃(`api·schemas·services·
  repositories`)으로 흐름을 읽을 수 있다.

## 1. 프로젝트 구조 (fastapi-standards §1.4 + §4.2)

표준 `app/` 레이아웃을 따른다. Repository 패턴(§4.2)으로 저장을 분리하고, 번역
도메인 특화 어댑터(`engines`·`prompts`)를 별 패키지로 둔다.

```
app/
├── main.py                     # 진입점 + lifespan(컴포지션 루트)
├── core/
│   ├── config.py               # Settings (pydantic-settings) — 시크릿은 .env
│   └── logging.py              # logging 설정 (print 금지)
├── api/
│   ├── deps.py                 # Depends 프로바이더 (서비스 주입)
│   ├── errors.py               # 예외 핸들러 (도메인 예외 → HTTP)
│   └── v1/
│       ├── sessions.py         # /api/v1/sessions
│       ├── languages.py        # /api/v1/languages
│       ├── turns.py            # /api/v1/sessions/{id}/turns (SSE)
│       └── stream.py           # WS /api/v1/sessions/{id}/stream
├── schemas/                    # Pydantic 요청/응답 (경계 검증)
│   ├── session.py, turn.py, language.py, stream.py, errors.py
├── services/                   # 비즈니스 로직
│   ├── draft.py                # DraftService
│   ├── quality.py              # QualityService (+ degradation)
│   ├── session.py              # SessionService (+ 워밍업)
│   ├── language.py             # LanguageService
│   ├── coordinator.py          # DraftSessionCoordinator (single-flight)
│   ├── stability.py            # StabilityPolicy (순수)
│   └── context.py              # ContextAssembler (TMC, 순수)
├── repositories/               # 저장 (Repository 패턴 §4.2)
│   ├── base.py                 # SessionRepository Protocol
│   ├── sql.py                  # SqlSessionRepository (SQLAlchemy async)
│   └── cache.py                # RenderingCache Protocol + 인메모리 LRU 구현 (D3)
├── engines/                    # 번역 엔진 어댑터
│   ├── base.py                 # TranslationEngine Protocol
│   ├── openai.py               # VllmEngine (OpenAI 호환)
│   └── registry.py             # ModelRegistry
├── prompts/                    # 프롬프트 전략
│   ├── base.py                 # PromptBuilder Protocol
│   ├── hy_mt.py                # HyMtPromptBuilder (언어쌍 분기)
│   └── gemma.py                # GemmaPromptBuilder
├── models/                     # SQLAlchemy ORM 모델 (Alembic 대상)
│   └── session.py, turn.py
└── domain.py                   # @dataclass 내부 값객체 (TranslationTask 등)
```

**의존성 방향**: `api → services → (repositories·engines·prompts)`. 라우터는 서비스만,
서비스는 Protocol(포트)만 안다. 구체 구현은 `main.py`에서만 조립·주입한다(DIP).

## 2. API 설계 (fastapi-standards §1)

`/api/v1` 프리픽스 · 복수 명사 · kebab-case · 계층으로 소속 표현.

| 메서드·경로 | 용도 | 비고 |
|---|---|---|
| `POST /api/v1/sessions` | 세션 생성 | 201, `SessionCreate` → `SessionCreated` |
| `GET /api/v1/sessions/{session_id}` | 세션 조회 | |
| `GET /api/v1/languages` | 지원 언어·검증쌍 | |
| `WS /api/v1/sessions/{session_id}/stream` | 초벌 스트리밍 | 세션은 경로에(계층). body에 session_id 없음 |
| `POST /api/v1/sessions/{session_id}/turns` | 최종 번역(턴 생성) | `text/event-stream`(SSE) |
| `GET /api/v1/sessions/{session_id}/turns` | 턴 이력 | |
| `GET /health`, `GET /metrics` | 헬스·메트릭 | 운영 엔드포인트라 버전 프리픽스 예외 |

- `turn`을 세션 하위 복수 리소스(`sessions/{id}/turns`)로 둬서 "턴 생성 = POST"가
  RESTful하게 성립(자작 `POST /v1/turn` 폐기).
- 초벌 WS도 세션 하위 경로로 소속을 드러낸다.
- 모든 요청/응답은 `schemas/`의 Pydantic 모델. 200 OK에 `{"error": …}` 금지, 실패는
  `HTTPException`/예외 핸들러(§7).

## 3. 스키마 vs 내부 값객체 (python-standards §7.3, §9)

- **경계(API)**: Pydantic 모델(`schemas/`). 외부 입력 검증은 Pydantic으로(§11.2).
  전송 관심사(`latency_ms`·`committed_prefix_len`)는 여기 둔다.
- **내부 값객체**: `@dataclass(frozen=True)`(`domain.py`). 직렬화가 필요 없는 순수
  객체(`TranslationTask`·`EngineRequest`·`TokenChunk`·`Rendering`)는 dataclass로.
- 이유: 도메인 로직이 wire 포맷을 따라 흔들리지 않게. 변환은 라우터에서 명시적으로.

```python
# domain.py
@dataclass(frozen=True)
class TranslationTask:
    src_lang: str
    tgt_lang: str
    source: str

@dataclass(frozen=True)
class TokenChunk:
    text: str
    ttft_ms: float | None   # 첫 청크만 채움
```

## 4. 서비스 계층 (fastapi-standards §1.4, python-standards §7)

라우터는 얇게, 로직은 서비스에(SRP). 서비스는 Protocol만 의존한다(DIP). 상속보다
합성(§7.2).

```python
class DraftService:
    """타이핑 중 소스를 다중 타겟으로 번역한다."""

    def __init__(self, registry: ModelRegistry, cache: RenderingCache,
                 metrics: MetricsSink) -> None:
        self._registry = registry
        self._cache = cache
        self._metrics = metrics

    async def render(self, session: Session, rev: Revision
                     ) -> AsyncIterator[RevisionUpdate]:
        """revision 하나를 tgt + witness 언어로 병렬 번역해 스트리밍한다.

        Args:
            session: 언어쌍·모델 설정을 담은 세션.
            rev: 정규화 전 부분 입력.
        Yields:
            타겟별 부분 번역 업데이트.
        """
        ...   # 결정성 캐시(D3) → 미스 시 tgt+witness fan-out(D8)
```

- **QualityService**: `ContextAssembler`로 직전 N턴 이중언어 컨텍스트 조립 →
  quality 엔진 스트리밍. `UpstreamEngineError`를 **잡아** draft로 승격(degradation)하고
  `degraded=True`로 알린다. degradation은 유스케이스 정책이지 전역 미들웨어가 아니다.
- **SessionService**: 생성 시 `LanguageService`로 언어쌍 검증(`UnsupportedLanguageError`)
  후 워밍업 1회(콜드 TTFT 제거 D4)를 백그라운드로 발사.
- **순수 도메인 서비스**(I/O 없음, 표 기반 단위 테스트):
  `StabilityPolicy.should_commit(pair) -> bool`(어순 유사 쌍만 접두어 커밋 D3),
  `ContextAssembler.build(turns, config, budget) -> Conversation`.

## 5. 엔진·프롬프트 어댑터 (OCP·Strategy·Adapter)

Protocol을 두고(python-standards §7.3) 구현체를 갈아끼운다.

```python
# engines/base.py
class TranslationEngine(Protocol):
    def stream(self, req: EngineRequest) -> AsyncIterator[TokenChunk]: ...
    async def health(self) -> EngineHealth: ...

# prompts/base.py
class PromptBuilder(Protocol):
    def build(self, task: TranslationTask) -> list[ChatMessage]: ...
    def build_contextual(self, task: TranslationTask,
                         ctx: Conversation) -> list[ChatMessage]: ...
```

- **VllmEngine(TranslationEngine)** — 모델은 vLLM의 OpenAI 호환 서버로 뜨고, 이
  어댑터가 그 API의 **클라이언트**다(게이트웨이는 모델을 직접 안 돌림). 공식 `openai`
  async SDK(`AsyncOpenAI`)를 tier별 `base_url`에 물려 `/chat/completions` 스트림을
  `TokenChunk`로 변환한다. 실패는 `UpstreamEngineError`로 감싼다.
- **HyMtPromptBuilder / GemmaPromptBuilder(PromptBuilder)** — 프롬프트 규약이 계열별로
  다르다(HY-MT는 언어쌍별 중문/영문 지시 분기, D0). 계열 추가 = Strategy 추가로 끝,
  서비스 불변(OCP).
- **ModelRegistry** — `served-model-name → (engine, prompt_builder, tier)` 해석.
  draft·quality 두 바인딩을 컴포지션 루트에서 등록. 모델 교체 = 등록 변경뿐.

## 6. 저장소·캐시 (fastapi-standards §4)

**SQLite(영속) + 인메모리 캐시.** 데모는 단일 노드라 외부 캐시 서버(Redis)를 두지
않는다(D10).

- **SqlSessionRepository(SQLAlchemy async + aiosqlite)** — 세션·턴 영속. 라우트를
  얇게, DB 연산은 Repository로(§4.2). ORM 모델은 `models/`, 스키마 변경은 Alembic
  (SQLite ALTER 제약은 `render_as_batch=True`). WAL + `busy_timeout`으로 동시 쓰기 대기.
- **RenderingCache(Protocol) + InProcessRenderingCache** — 결정성 캐시(D3). 키는
  `(draft_model, src_lang, tgt_lang, 정규화_소스)` — 결정성은 (모델, 프롬프트)에
  묶이고 프롬프트가 언어쌍에 따라 갈리므로 키에 모델·쌍을 포함한다. 휘발성이라
  프로세스 내 bounded LRU면 충분. 미스 비용은 초벌 추론 12ms뿐(D4)이라 캐시는 GPU
  중복 호출을 줄이는 효율 장치다.
- **라이브 세션 상태**는 별도 저장 없이 `DraftSessionCoordinator`가 프로세스 내
  `asyncio.Task`로 소유(§8).

두 저장은 Protocol 뒤라 **스케일 시 어댑터 교체뿐**: DB는 URL(`sqlite+aiosqlite` →
`postgresql+asyncpg`) 교체로 Postgres 승격(D9), 캐시는 다중 노드 필요 시
`RedisRenderingCache` 구현 추가(D10). 서비스 코드 불변.

```python
# repositories/base.py
class SessionRepository(Protocol):
    async def create(self, cfg: SessionConfig) -> Session: ...
    async def get(self, session_id: str) -> Session | None: ...
    async def append_turn(self, session_id: str, turn: Turn) -> None: ...
    async def recent_turns(self, session_id: str, n: int) -> list[Turn]: ...
```

세션이 `Turn`의 애그리거트 루트다. 턴 추가는 `append_turn`으로만 → 이력 일관성을
한 곳에서 강제.

## 7. 에러 처리 (fastapi-standards §3, python-standards §10)

```python
# schemas/errors.py
class ErrorResponse(BaseModel):
    detail: str
    error_code: str | None = None
```

| 종류 | 예 | 처리 |
|---|---|---|
| 도메인 예외 | `SessionNotFoundError`(404)·`UnsupportedLanguageError`(422) | `api/errors.py` 핸들러가 `ErrorResponse`로 매핑 |
| 인프라 예외 | `UpstreamEngineError`·타임아웃 | quality: 서비스가 잡아 degradation / draft: revision 오류 이벤트 |

- 도메인은 HTTP 상태코드를 모른다. 매핑은 예외 핸들러 한 곳에만 둔다.
- `except`는 구체 타입만, `logger.exception()`으로 로깅(§10). bare `except` 금지.

## 8. 동시성·취소 — DraftSessionCoordinator (SRP)

WS 연결 하나의 "현재 revision"을 소유하는 single-flight 객체. 취소 관심사를 여기
가둬 서비스·엔진을 순수하게 유지한다.

```python
class DraftSessionCoordinator:
    """WS 연결 1개의 초벌 revision 순서·취소를 관리한다."""

    def __init__(self, service: DraftService, session: Session) -> None:
        self._svc = service
        self._session = session
        self._task: asyncio.Task[None] | None = None
        self._latest = -1

    async def submit(self, rev: Revision, sink: UpdateSink) -> None:
        """새 revision을 받는다. 이전 진행 요청은 취소한다."""
        if rev.id <= self._latest:            # 순서 역전/중복 → 폐기
            return
        self._latest = rev.id
        if self._task and not self._task.done():
            self._task.cancel()               # 이전 요청 abort → vLLM 생성 중단
        self._task = asyncio.create_task(self._run(rev, sink))
```

라우터(`stream.py`)는 연결당 코디네이터 1개를 만들고 수신 메시지를 `submit`으로
넘긴다. 라우터=파싱·전송 / 코디네이터=순서·취소 / 서비스=번역으로 책임이 겹치지 않는다.

## 9. 의존성 주입 / 컴포지션 루트 (fastapi-standards §1.5)

`Depends()`를 명시적으로 쓰고 전역 상태를 피한다. 구체 어댑터는 lifespan에서 한 번만
생성해 주입한다.

```python
# main.py (발췌)
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()                          # .env 바인딩
    draft = VllmEngine(settings.draft_url)
    quality = VllmEngine(settings.quality_url)
    registry = ModelRegistry()
    registry.register(settings.draft_model, draft, HyMtPromptBuilder(), tier="draft")
    registry.register(settings.quality_model, quality, GemmaPromptBuilder(), tier="quality")
    app.state.container = Container(registry, ...)
    yield
    await draft.aclose(); await quality.aclose()
```

라우터는 `Depends`로 서비스를 받고, 서비스 생성자는 Protocol만 받으므로 테스트에서
가짜로 대체된다.

## 10. 설정·로깅·보안 (python-standards §10~11)

- **Settings**: `pydantic-settings`로 env 바인딩. 시크릿 하드코딩 금지, `.env`.
- **로깅**: `logging` 모듈(`getLogger(__name__)`), `print()` 금지. `except`에서
  `logger.exception()`.
- **입력 검증**: 모든 외부 입력은 Pydantic 스키마로(§11.2).

## 11. 테스트 (fastapi-standards §5)

- `tests/conftest.py` 공용 픽스처, `tests/api/` 엔드포인트 테스트.
- `httpx.AsyncClient`(ASGITransport)로 async 테스트, `app.dependency_overrides`로
  서비스 대체.
- **서비스 단위**: `FakeEngine`(스크립트 토큰)·`InMemorySessionRepository` 주입 →
  fan-out·degradation·캐시·순서제어를 네트워크 없이 검증.
- **순수 도메인**: `StabilityPolicy`·`ContextAssembler`·`LanguageCatalog` 표 기반.
- **E2E**: 데모 시나리오(대화 프로브)를 회귀 기대값으로(design.md §8.7).

## 12. 표준 준수 체크리스트

fastapi-standards:
- [x] `/api/v1` 프리픽스 · 복수 명사 · kebab-case · 계층(`sessions/{id}/turns`)
- [x] 요청/응답 Pydantic · 실패는 `HTTPException`/핸들러
- [x] `app/{api,schemas,services}` 구조 + Repository 패턴
- [x] 예외 핸들러가 `ErrorResponse{detail, error_code}` 일관 반환
- [x] 시크릿은 env(`pydantic-settings`)

python-standards:
- [x] Protocol 인터페이스 + `@dataclass` 값객체
- [x] 타입힌트(모던 문법)·공개 함수 docstring
- [x] `uv add`/`uv run`, `logging`(print 금지), 구체 예외 처리
- [x] SOLID·합성 우선·DRY

**의도적으로 뺀 것 (YAGNI)**: 이벤트 소싱·CQRS·메시지 브로커·범용 DI 컨테이너.
현재 요구(2 tier·세션 상태·스트리밍)에 과하다. 필요해지면 Protocol 뒤에서 추가한다.

## 13. design.md와의 관계

- 데이터 모델·프로토콜·파이프라인의 **무엇**은 design.md, **어떤 구조로**는 이 문서.
- 실측 근거(D3 캐시·D4 워밍업·D6 모델 교체·D8 fan-out)는 [`decisions.md`](decisions.md).
