# M0 — 실측 결과 (draft tier)

측정 환경: **RTX 4090 24GB · WSL2(kernel 6.18) · vLLM 0.25.1 · bf16**
모델: `tencent/HY-MT1.5-1.8B` (bf16 원본, FP8 아님)
측정일: 2026-07-17 · 재현: `bench/serve_draft.sh` 기동 후 `bench/*.py` 실행

> 범위: draft tier 단독. (a) FLORES-200 devtest COMET 정량 점수, (b) 방향별 번역
> 정확성 육안 검증, (c) 실제 하드웨어 레이턴시, (d) 단일 GPU 메모리 실현성,
> (e) 안정화(flicker) 실측.

---

## 0. 번역 품질 — FLORES-200 devtest COMET (정량)

`bench/flores.py` · 1012 n-way 병렬 문장 · greedy(temp=0) · 채점기
`Unbabel/wmt22-comet-da`(reference-based, 참조 있음).

데이터 출처: **Meta 공식 FLORES-200 devtest**(ungated 공개 tarball). FLORES+는
유지보수 후속판이나 gated(HF gate 승인 필요)라 이번엔 FLORES-200을 사용. FLORES+
재측정으로 원문 데이터셋 parity를 맞추는 것은 미완(§0 하단·M1 항목).

| 방향 | COMET | | 방향 | COMET |
|---|---|---|---|---|
| ko→en | 87.12 | | en→ko | 90.25 |
| **ko→id** | **87.90** | | **id→ko** | **87.80** |
| en→id | 90.67 | | id→en | 87.81 |
| | | | **6방향 평균** | **88.59** |

- `ko↔id` 직접 번역이 87.8~87.9로 `ko↔en`(87.1)과 비슷. 영어 경유(ko→en→id)의 중간
  단계 en 점수가 더 높지 않으므로 피벗의 품질 이점이 없다(육안 검증과 일치).
- 6방향 평균 88.59. en이 target인 방향(en→ko 90.25, en→id 90.67)이 나머지보다
  2~3점 높음.

## 1. 번역 품질 — 방향별 (육안 검증)

`bench/quality_spotcheck.py` · greedy(temp=0) · XX↔XX 영어 지시 템플릿.

- 6방향(ko/en/id) 모두 문법·의미 오류 없이 번역됨. 고객지원 도메인에서 경어(존댓말,
  `Mohon`/`Bisakah Anda`)가 유지됨.
- ko↔id 직접 번역의 COMET(§0)과 육안 결과가 일치 → *열린 이슈 #1(영어 피벗
  ko→en→id 도입 여부) 해소: 피벗 불필요.* 지연 2배 대비 품질 이점이 없음.
- 관찰된 미세 드리프트(품질 tier가 개선할 지점):
  - `faktur`(청구서) → id→ko에서 "영수증"으로 번역되는 경우 있음(invoice≠receipt).
  - `그거`(지시대명사) → 맥락 없이 "hal tersebut/that"으로 일반화 → **맥락 tier의
    대명사 복원 데모 포인트로 적합.**
  - id→ko에서 "…하겠습니다"처럼 원문에 없는 1인칭 의지 추가되는 경우 → 경미한 agency 삽입.

## 2. 레이턴시 — 실측 (목표 대비)

`bench/latency.py` · 스트리밍 TTFT/총시간.

| 시나리오 | TTFT p50 | TTFT p95 | Total p50 | Total p95 | 목표 |
|---|---|---|---|---|---|
| 타이핑 시뮬(콜드 포함) | 14 ms | 223 ms | 181 ms | 384 ms | TTFT≤150 / Total≤400 |
| Steady-state(핫 프리픽스, 30회) | **12.5 ms** | 14.1 ms | **90.7 ms** | 93.8 ms | 〃 |

- TTFT p50 12.5ms로 목표(150ms) 미만. 목표를 넘은 것은 첫 콜드 요청(TTFT 222ms)뿐 —
  CUDA graph/토크나이저 워밍업 1회. 세션 시작 시 워밍업 요청 1회로 제거 가능.
- 추론 지연(~12ms)이 디바운스(150~250ms)보다 작으므로 레이턴시 예산의 대부분은
  디바운스가 차지한다. 튜닝 레버는 모델 속도가 아니라 안정화 정책 쪽.

## 3. 단일 GPU 2-tier 메모리 실현성 — 실측

| 모델 | 가중치 크기 | 비고 |
|---|---|---|
| HY-MT1.5-1.8B (bf16) | ~4.0 GB | 이번 측정 대상 |
| HY-MT1.5-1.8B-FP8 | **2.0 GB** | draft 권장 |
| HY-MT1.5-7B-FP8 | **8.0 GB** | quality 후보(동일 계보) |
| gemma-4-E4B (bf16) | **16.0 GB** | 공개 FP8 없음(E4B-FP8 401) |
| gemma-4-E2B (bf16) | 10.25 GB | 멀티모달(Gemma4), 텍스트측 128K |

- draft(bf16) 단독 실측 점유: **14.6 GB**(util=0.5 상한, KV 131K tokens 예약 포함).
  실제 가중치는 4GB이므로 util을 낮추면 축소됨.
- `gemma-4-E4B`는 가중치 16GB로, draft 가중치(bf16 4GB)와 합치면 20GB → 24GB에서
  두 tier의 KV 캐시·CUDA graph에 남는 여유가 부족하다. 단일 4090에서 gemma-4-E4B를
  quality로 두는 배치는 어렵다(README의 "별도 GPU 2장" 전제가 이 하드웨어엔 없음).
- **실측 기반 단일 GPU 권장 배치:**
  `draft = HY-MT1.5-1.8B-FP8 (2GB)` + `quality = HY-MT1.5-7B-FP8 (8GB)`
  = 가중치 10GB → 나머지 ~13GB를 두 KV 캐시/CUDA graph에 배분 가능.
  두 모델이 **동일 계보**라 프롬프트 인프라·용어개입·맥락·서식 기능을 공유.
  (gemma-4-E4B는 별도 GPU가 확보될 때의 옵션으로 강등.)

## 4. 안정화(flicker) — 실측

`bench/prefix_stability.py`.

- **결정성:** temp=0에서 동일 프롬프트 5/5 동일 → hold-k/local-agreement의
  전제(반복 재현성)는 성립.
- **접두어 생존율(ko→id):** 소스가 한 어절 늘 때 이전 번역문의 접두어가
  대부분 0% 생존(rev8은 rev7과 0자 공유). ko(SOV)↔id(SVO) 어순 차이로
  목표문이 매 리비전 전면 재작성됨.

**설계 수정 함의(README §2.1):**
- 목표문 접두어 확정(local agreement / hold-k)은 ko↔id처럼 어순이 다른 쌍에서
  확정할 접두어가 생기지 않는다.
- flicker 완화는 접두어 freeze가 아니라 (a) 디바운스(어절 경계) + (b) 전체
  draft를 "tentative"로 흐리게 렌더 + (c) revision_id 순서제어/이전요청 abort로
  간다. 접두어 커밋은 어순이 유사한 쌍에 한해 선택적으로만 켠다.
- IME 조합 제거·디바운스는 여전히 유효(입력 측).

---

## 재현 방법

```bash
uv venv --python 3.12 && uv pip install "huggingface-hub[hf-transfer]" vllm "unbabel-comet>=2.2"
hf download tencent/HY-MT1.5-1.8B --local-dir models/HY-MT1.5-1.8B
bash bench/serve_draft.sh          # 백그라운드로 기동, :8001
.venv/bin/python bench/quality_spotcheck.py
.venv/bin/python bench/latency.py
.venv/bin/python bench/prefix_stability.py

# FLORES-200 devtest COMET (정량). COMET 채점기는 HF 토큰 필요(gate 승인됨).
curl -o data/flores200.tar.gz https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz
tar xzf data/flores200.tar.gz -C data ./flores200_dataset/devtest/{kor_Hang,eng_Latn,ind_Latn}.devtest
HF_TOKEN=$HF_API_KEY .venv/bin/python bench/flores.py all    # translate + score
```

### WSL2 환경 필수 플래그 (실측 중 확인)
- `VLLM_WSL2_ENABLE_PIN_MEMORY=1` — 없으면 V1 GPU 러너가 `UVA is not available`로 죽음.
- `VLLM_USE_FLASHINFER_SAMPLER=0` + `VLLM_ATTENTION_BACKEND=FLASH_ATTN` — 이 환경에
  nvcc(CUDA 툴킷) 부재 → flashinfer JIT 컴파일 불가. native sampler로 우회.
- vLLM 0.25.1은 `--disable-log-requests` 플래그 제거됨.
