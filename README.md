# live-translate

운영자와 외국인 고객의 대화를 위한 **이중 파이프라인 실시간 텍스트 번역 시스템**.
타이핑 중에는 경량 모델이 즉시 **초벌**을 스트리밍하고, 문장이 확정되면 LLM이
**대화 맥락을 반영한 최종 번역**을 내놓는다. 번역이 맞는지 사용자가 눈으로 확인할 수
있도록 **검증 장치**를 함께 보여주고, 외부에서 품질을 확인할 수 있도록 **공개 API**를 연다.

- **초벌 (draft)** — 저지연. 타이핑 중 매 변경마다 갱신.
- **최종 (quality)** — 확정 문장을 직전 맥락 기반으로 재번역. 사용 LLM은 **설정으로 교체 가능**.
- **검증 (verification)** — 정렬 · 역번역 · 신뢰도(QE) · 확인(제3 언어)으로 번역을 교차 점검.

> **범위 제외:** 음성(STT/TTS). 텍스트 전용이다. 다만 입력은 "확정되지 않은 부분 텍스트
> 스트림"으로 추상화돼 있어, 후속 음성 프로젝트에서 STT의 partial hypothesis를 그대로 이을 수 있다.

이 README는 **고수준 개요**만 담는다. 자주 바뀌는 수치·모델·데이터 모델·프로토콜·측정값은
아래 문서를 소스로 한다.

| 문서 | 내용 |
|---|---|
| [`docs/design.md`](docs/design.md) | 상세 설계 — 데이터 모델 · 파이프라인 · 프로토콜 · 데모 UX |
| [`docs/backend-architecture.md`](docs/backend-architecture.md) | BE 아키텍처 — 레이어 · 포트/어댑터 · 동시성 |
| [`docs/frontend-architecture.md`](docs/frontend-architecture.md) | FE 아키텍처 — 컴포넌트 · 상태 · WS/SSE 클라이언트 |
| [`docs/decisions.md`](docs/decisions.md) | 설계 결정 이력 — 왜 이 설계인가(모델 선정·실측 결론) |
| [`docs/serving.md`](docs/serving.md) | 서빙/운영 — GPU 배치 · 기동 · 환경 플래그 |
| [`CHANGELOG.md`](CHANGELOG.md) | 변경 이력 |

---

## 아키텍처

```
┌────────────┐   WS  초벌(부분 텍스트 → draft)
│  Console   │   SSE 최종(확정 문장 → quality)
│   (Web)    │   REST 세션·대화·무상태 번역·키 관리
└─────┬──────┘
      ▼
┌─────────────────────────────────────────────┐
│  Gateway (FastAPI)                           │
│   세션 · 라우팅 · 맥락 프롬프트 · 검증 · 인증  │
└───┬───────────────┬───────────────┬─────────┘
    │ OpenAI 호환    │ OpenAI 호환    │ HTTP
    ▼               ▼               ▼
 draft 모델      quality 모델      정렬(align)
  서버            서버              서비스
```

- **모델은 OpenAI 호환 서버(vLLM) 뒤**에 둔다 — 게이트웨이는 엔진 구현에 의존하지 않는다.
- **초벌·최종은 별도 모델 인스턴스.** 같은 엔진이면 초벌이 최종 뒤에 큐잉돼 저지연을 못 맞춘다.
- **초벌 안정화** — 디바운스 · single-flight · IME 조합 처리로 타이핑 중 flicker/백로그를 억제.
- **최종 맥락** — 직전 턴들의 원문을 프롬프트에 주입해 대명사·생략·격식을 복원(맥락 기반 번역).
- **엔진·모델은 교체 가능**하도록 설계 — 고정 요소와 교체 요소는 [`docs/decisions.md`](docs/decisions.md).

---

## API

공개 **REST + 스트리밍**(초벌 WS · 최종 SSE) + **무상태 단발 번역**을 제공한다. 외부 소비자가
번역 품질을 확인하는 채널로, 무상태 번역은 요청 시 검증 데이터(초벌·역번역·신뢰도·정렬·확인)를
함께 반환한다.

| 표면 | 용도 |
|---|---|
| 세션 · 초벌(WS) · 최종(SSE) | 실시간 번역 파이프라인 |
| 무상태 번역 | 세션 없이 한 번의 번역(+검증) |
| 대화 저장소 | 확정 대화의 영속·목록·복원 |
| 언어 카탈로그 | 지원 언어·검증된 쌍 |
| 키 관리(Admin) | API 키 발급·폐기·조회 |

- **인증** — `/health`를 제외한 전 API가 **API 키**를 요구한다(REST는 헤더, WS는 쿼리). 키는
  **DB에서 관리**(해시 저장)하며 외부 기업 키는 **Admin API로 런타임 발급·폐기**한다. 부트스트랩·
  키 관리 절차는 [`.env.example`](.env.example)와 [`docs/serving.md`](docs/serving.md).
- **전체 스펙**은 서비스 기동 후 Swagger `/docs`(OpenAPI). RESTful 규약·스키마는
  [`docs/design.md`](docs/design.md)·[`docs/backend-architecture.md`](docs/backend-architecture.md).

---

## 실행

전 스택(모델 서버 · 정렬 · 게이트웨이 · 콘솔)을 docker compose로 띄운다. 환경 변수는
`.env`로 관리한다([`.env.example`](.env.example) 복사).

```bash
cp .env.example .env      # 키·모델·프로파일 설정
./run.sh -d               # GPU 자동감지 → 있으면 GPU, 없으면 CPU 프로파일
```

> 모델 서버는 실행 **프로파일**(gpu/cpu)로 묶여 있어, 프로파일 없이 `docker compose up`만
> 쓰면 모델이 안 뜬다. `./run.sh`(자동 감지)를 쓰거나 `.env`에 실행 프로파일을 지정한다.
> GPU 요구사항·배치·기동 옵션은 [`docs/serving.md`](docs/serving.md).

---

## 설정 (env)

`.env` 한 곳에서 관리한다([`.env.example`](.env.example)에 전 항목 문서화):

- **모델** — 최종 LLM의 로드 소스(HuggingFace repo id 또는 로컬 경로)와 컨텍스트·GPU 예산.
  초벌 모델은 고정, 최종 LLM은 교체 가능.
- **인증** — 부트스트랩 API 키(시작 시 DB에 seed) · 콘솔(FE) 키 · Admin 키 · 실행 프로파일.
- **엔드포인트** — 모델/정렬 서비스 주소(기본값은 compose 내부 네트워크).

---

## 프로젝트 구조

```
app/       FastAPI 게이트웨이 (라우터 · 엔진 클라이언트 · 프롬프트 · 서비스 · 저장소)
web/       콘솔 프론트엔드
aligner/   정렬(단어 대응) 서비스
bench/     측정 하네스 + 결과
deploy/    nginx · 컨테이너 정의
docs/      설계 · 결정 이력 · 서빙 가이드
```

---

## 참고

- Pombal et al. (2026). *A Context-aware Framework for Translation-mediated Conversations.* TACL. — arXiv:2412.04205
- Tencent Hunyuan (2026). *HY-MT1.5 Technical Report.* — arXiv:2512.24092
- Zheng et al. (2025). *Hunyuan-MT Technical Report.* — arXiv:2509.05209
