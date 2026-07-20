# Changelog

이 프로젝트의 모든 주목할 변경을 기록한다. 형식은 [Keep a Changelog](https://keepachangelog.com),
버전 규칙은 [Semantic Versioning](https://semver.org)을 따른다.

## [Unreleased]

### ✨ Features
- **web/console**: 시연용 **대화 시나리오(자유 칩 풀)** — 발표자가 무엇을 칠지 막힐 때 쓰는 편집 가능한 시드 칩. 시나리오(회의 일정/환불/배송) 선택 후 운영자 작성창엔 한국어 시드, 고객 태블릿엔 영어 시드가 칩으로 뜨고, 클릭하면 입력창을 채운다(자동 전송 X, 수정 후 전송). **번역은 항상 실시간** 수행이라 "미리 번역된 것처럼" 보이지 않는다.
- **검증(정렬)**: 구 정렬 하이라이트(awesome-align, 센터피스 D13) 배선 완료. `aligner/`(simalign, `aneuraz/awesome-align-with-co`)를 별도 호스트 프로세스(:8003)로 서빙(`serve_aligner.sh`), 게이트웨이 `HttpAligner`가 턴 확정 시 1회 호출(도달 불가 시 graceful degrade). 버블에서 **소스 구에 hover하면 대응 번역 구가 함께 강조**. QE(amber 밑줄)와 정렬(hover 배경)은 다른 시각 채널로 공존. → 검증 4종(witness·QE·역번역·정렬) 완성.
- **검증(QE·역번역)**: 최종 턴에 두 검증 장치를 함께 계산·표시(D11/D13). **단어 QE**는 최종 스트림의 토큰 logprob를 단어 단위로 묶어 신뢰도를 내고 저신뢰 단어만 amber로 표시(다 초록으로 칠하지 않는 정직성). **역번역(round-trip)**은 최종 번역을 draft 엔진으로 원문 언어로 되돌려(tgt→src) 운영자가 의미 보존을 눈으로 확인. 버블에 초벌·LLM·역번역·확인(witness)이 각 소요시간과 함께 나란히. 값은 모두 저장·복원.
- **quality tier**: 최종 번역을 실제 경량 LLM **Qwen3-4B-Instruct-2507** 로 서빙(단일 GPU를 draft와 공유). 더 이상 draft로 degrade하지 않아 초벌과 LLM 결과가 실제로 달라진다(예: 초벌 "move the meeting" vs LLM "reschedule the meeting"). 엔진 도달 불가 시에만 draft로 graceful degrade. 서빙은 `serve_draft.sh`·`serve_quality.sh`로 코드화.
- **quality tier**: **Pombal et al.(TACL 2026)** 문맥 기반 번역 프레임워크 적용 — 직전 턴들의 **원문**(양측, 순서대로)을 컨텍스트로 주입해 대명사·생략·모호성을 해소. FE가 대화 원문열을 턴 요청 `context`로 전달, `QwenPromptBuilder`가 context-augmented 프롬프트 구성.
- **web/console**: 좌측 세션 저장소 하단에 근거 논문 각주("문맥 기반 번역" · Pombal et al., TACL 2026 링크) 추가.
- **web/console**: 운영자 채팅 버블에 **초벌·LLM 번역을 함께** 표시 — LLM 최종 번역이 완료되면 빠른 초벌(draft)과 LLM(quality) 결과를 한 버블에 나란히 보여준다. 검증(확인용 언어 back-check)도 같은 버블 안에 포함하고, 하단 검증바는 제거.
- **web/console**: 각 단계의 **소요 시간(초)** 을 버블에 표시(초벌·LLM·검증). 캐시 히트 초벌도 실제 소요(≈0초)를 보고하도록 draft 서비스 보정.
- **api/conversations**: 메시지에 `draft`·`witness`·`round_trip`·`confidence`·`alignment`와 `draft_ms`·`final_ms`·`round_trip_ms` 필드 추가 — 초벌/검증 데이터와 각 단계 소요 시간을 저장·복원까지 보존.
- **web**: 제공된 `favicon.ico`를 `web/public/`로 이동해 적용, 문서 제목을 "실시간 번역 콘솔", `lang="ko"`로 정리.
- **api/conversations**: 대화 저장소 API 신설(`POST/GET /api/v1/conversations`, `GET /{id}`, `POST /{id}/messages`) — UI가 확정한 대화를 DB(SQLite)에 영구 저장하고 목록·복원한다. 번역 파이프라인(sessions/turns)과 분리된 뷰 모델(decisions.md D14).
- **web/console**: 좌측 패널을 **번역 세션 저장소**로 재편 — 역할이 불명확하던 "실시간 번역 콘솔"을 대신해 저장된 대화 목록(제목·언어쌍·개수)을 보여주고, 클릭하면 언어쌍과 메시지를 그대로 복원한다. "+ 새 대화"로 새 세션 시작.
- **api/conversations**: 대화 삭제 `DELETE /api/v1/conversations/{id}` — 좌측 목록의 각 세션을 호버 시 나타나는 ✕로 삭제(메시지까지 함께 삭제).
- **web/console**: 번역 방향 선택·스왑과 검증 요약을 중앙 작업대(헤더·검증바)로 이동해 좌측을 저장소 전용으로 비움.
- **web/console**: 운영자(관리자) UI 전반 확대 — 좌측 목록·중앙 말풍선(원문/번역)·방향 선택·검증바·입력창 글자와 여백을 키워 가독성 강화. 좌측 컬럼 폭 확대(262→310px).
- **web/console**: 고객 화면을 태블릿 규격(580px)으로 키우고 본문 폰트를 확대해 데모에서 "실제 고객 기기" 느낌을 강화. 빈 스테이지 위에 부양하도록 우측 패널만 배경 분리.
- **web/console**: 고객 화면에 입력창 추가 — 외국인 고객이 자기 언어로 입력하면 역방향 세션으로 운영자 언어로 번역돼 작업대에 수신된다(양방향 대화 데모).

### ✨ Features (cont.)
- **web/console (초벌 anti-jank)**: 초벌 WS를 **single-flight**로 재설계 — in-flight 요청은 항상 1개, 그 사이 입력은 **최신값만 대기**시켜 큐잉·"우다다"(밀렸다 몰아치는 현상)를 없앴다. **적응형 디바운스**(최근 지연에 맞춰 150~1000ms 자동 조절)로 느린 환경에서도 매끄럽게. 백엔드 속도에 자동으로 맞춰지므로 CPU·GPU 공통 이득.
- **web/console**: "번역 중…" 표시를 **기존 초벌을 지우지 않게** 개선 — 이미 초벌이 떠 있으면 유지하고 작은 진행점(…)만 덧붙이고, 첫 번역(아직 없을 때)만 "번역 중…"을 단독 표시.
- **web/console (CPU 모드 대비)**: quality 미가용(`degraded`)이면 초벌==최종이라 버블을 **단일 "번역" 줄**로 접는다(초벌/LLM 이중 표기 제거). GPU가 있으면 기존대로 초벌·LLM 분리.

### 🔧 Infra / Ops
- **compose**: vLLM 두 tier(draft·quality)를 **도커화** — `vllm/vllm-openai` 이미지로 `vllm-draft`·`vllm-quality` 서비스 추가, 로컬 `./models`를 마운트해 재다운로드 없이 로드, GPU 예약(`deploy.resources … nvidia`), healthcheck 포함. 이제 **`docker compose --profile gpu up` 한 번**으로 vLLM+gateway+nginx 전체 기동(정렬은 호스트 :8003 유지). gateway `DRAFT_URL`/`QUALITY_URL` 기본값을 컨테이너 서비스명으로 변경(호스트 vLLM은 env override). 전제: `nvidia-container-toolkit` 설치.

### ♻️ Refactor
- **web/console**: 3분할 콘솔에서 전체를 카드로 띄우던 처리를 걷어내고 풀 레이아웃으로 복귀. 부양 효과는 고객 화면 한 곳에만 남겨 시선을 집중.

### ✅ Tests
- **tests/e2e**: 대화 저장소 CRUD(생성·추가·목록·복원·404) pytest 추가(vLLM 불필요, 순수 DB). `web/e2e-smoke.mjs`에 목록 적재·새 대화·복원 시나리오 추가.

---
**배포 노트**: **전체 스택 = `docker compose --profile gpu up`** (vLLM draft·quality + gateway + nginx). 전제: `nvidia-container-toolkit`. 정렬은 호스트 프로세스 `bash serve_aligner.sh`(:8003) — 미기동 시 정렬 생략(graceful). 호스트 vLLM 방식으로 되돌리려면 `DRAFT_URL`/`QUALITY_URL`을 `host.docker.internal:8001/8002`로 override하고 `serve_draft.sh`·`serve_quality.sh` 사용. `QUALITY_MODEL=qwen3-4b-instruct`. 새 테이블 `conversations`/`messages`는 기동 시 `create_all`로 자동 생성. ⚠️ `messages`에 컬럼(`draft`/`draft_ms`/`final_ms`)이 추가되어, **미리 배포된 개발 DB가 있으면 `gateway-data` 볼륨을 재생성**해야 한다(`docker compose down && docker volume rm live-translate_gateway-data`). Alembic 미도입(create_all 모드) 상태의 데모 한정 조치. env 변경 없음.
