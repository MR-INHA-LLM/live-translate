"""정렬 하이라이팅 실현성 확인 — SimAlign이 그럴듯한 구 대응을 내는가 (D13).

데모 센터피스(구 정렬 하이라이팅)가 실제로 설득력 있게 나오는지 눈으로 확인한다.
입력은 실제 HY-MT1.5-1.8B 출력(앞서 quality_spotcheck에서 나온 진짜 문장).
SimAlign(mBERT, zero-shot)로 (소스, 최종) 단어 정렬을 뽑아 사람이 읽게 출력.

사용: uv run python bench/align_simalign.py
"""

from __future__ import annotations

import time

from simalign import SentenceAligner

# (설명, 소스 ko, 타겟 lang, 타겟 문장) — 전부 실제 HY-MT 출력
PAIRS = [
    ("회의 일정", "내일 오후 회의를 취소하고 금요일로 옮겨 주세요.", "en",
     "Please cancel the meeting scheduled for tomorrow afternoon and move it to Friday instead."),
    ("회의 일정", "내일 오후 회의를 취소하고 금요일로 옮겨 주세요.", "id",
     "Mohon membatalkan rapat yang akan berlangsung besok sore, dan menggantinya ke hari Jumat."),
    ("그거(대명사)", "그거 오늘 안에 처리해 주시면 정말 감사하겠습니다.", "en",
     "I would be very grateful if you could handle that by today's deadline."),
    ("헤드폰 배송", "안녕하세요, 지난주에 주문한 헤드폰이 아직 도착하지 않았어요.", "id",
     "Halo, headphone yang saya pesan minggu lalu masih belum sampai ke tangan saya."),
]


def show(aligner: SentenceAligner, tag: str, src: str, tgt_lang: str, tgt: str) -> None:
    src_w = src.split()
    tgt_w = tgt.split()
    t0 = time.perf_counter()
    aligns = aligner.get_word_aligns(src_w, tgt_w)
    dt = (time.perf_counter() - t0) * 1000
    pairs = aligns.get("itermax", aligns[next(iter(aligns))])

    print(f"\n{'='*70}\n[{tag}]  ko → {tgt_lang}   ({dt:.0f}ms)")
    print(f"  KO: {src}")
    print(f"  {tgt_lang.upper()}: {tgt}")
    print("  정렬(어절 → 대응 단어):")
    by_src: dict[int, list[str]] = {}
    for i, j in pairs:
        by_src.setdefault(i, []).append(tgt_w[j])
    for i, w in enumerate(src_w):
        mapped = " · ".join(by_src.get(i, ["—"]))
        print(f"    {w:<12} → {mapped}")


def main() -> None:
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else "bert"
    print(f"SimAlign 로딩 (model={model})…")
    t0 = time.perf_counter()
    aligner = SentenceAligner(model=model, token_type="bpe", matching_methods="i")
    print(f"로드 {time.perf_counter()-t0:.1f}s")
    for tag, src, lang, tgt in PAIRS:
        show(aligner, tag, src, lang, tgt)


if __name__ == "__main__":
    main()
