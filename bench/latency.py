"""M0 latency measurement against the real vLLM draft endpoint on this GPU.

Two scenarios:

  A) TYPING SIMULATOR — a Korean sentence grows one 어절(word) at a time; each
     growth fires a fresh streaming request. This is exactly the draft-tier load
     and it exercises prefix-cache reuse (each prompt extends the previous one).
     We report TTFT + total per revision vs the design targets (TTFT<=150ms,
     total<=400ms).

  B) STEADY-STATE — repeat one representative sentence N times to get stable
     p50/p95/p99 once the prefix is hot.
"""

from __future__ import annotations

import statistics as stats
import sys

from _client import translate_streaming, wait_until_ready
from prompts import build_user_prompt

TYPING_SENTENCE_KO = "내일 오후 회의를 취소하고 금요일 아침으로 옮겨 주시겠어요"
STEADY_SENTENCE_KO = "이 제품은 무상 보증 기간이 2년입니다"


def _pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = max(0, min(len(xs) - 1, round((p / 100) * (len(xs) - 1))))
    return xs[k]


def typing_simulator(tgt: str = "id") -> None:
    words = TYPING_SENTENCE_KO.split()
    print("=" * 78)
    print(f"A) TYPING SIMULATOR  ko -> {tgt}  ({len(words)} revisions, growing prefix)")
    print("=" * 78)
    print(f"{'rev':>3} {'chars':>5} {'ttft_ms':>8} {'total_ms':>9} {'tok':>4}  translation")
    ttfts, totals = [], []
    for i in range(1, len(words) + 1):
        partial = " ".join(words[:i])
        t = translate_streaming(build_user_prompt("ko", tgt, partial), max_tokens=128)
        ttfts.append(t.ttft_ms or 0.0)
        totals.append(t.total_ms)
        print(f"{i:>3} {len(partial):>5} {t.ttft_ms:>8.1f} {t.total_ms:>9.1f} "
              f"{t.n_tokens:>4}  {t.text}")
    print(f"\n  TTFT  p50={_pct(ttfts,50):.0f}ms  p95={_pct(ttfts,95):.0f}ms  "
          f"max={max(ttfts):.0f}ms   (target <=150ms)")
    print(f"  TOTAL p50={_pct(totals,50):.0f}ms  p95={_pct(totals,95):.0f}ms  "
          f"max={max(totals):.0f}ms  (target <=400ms)")


def steady_state(tgt: str = "id", n: int = 30) -> None:
    print("\n" + "=" * 78)
    print(f"B) STEADY-STATE  ko -> {tgt}  ({n} reps, hot prefix)")
    print("=" * 78)
    prompt = build_user_prompt("ko", tgt, STEADY_SENTENCE_KO)
    ttfts, totals = [], []
    for _ in range(n):
        t = translate_streaming(prompt, max_tokens=128)
        ttfts.append(t.ttft_ms or 0.0)
        totals.append(t.total_ms)
    for name, xs, target in (("TTFT", ttfts, 150), ("TOTAL", totals, 400)):
        print(f"  {name:5s} p50={_pct(xs,50):6.1f}  p95={_pct(xs,95):6.1f}  "
              f"p99={_pct(xs,99):6.1f}  mean={stats.mean(xs):6.1f}ms  (target <={target}ms)")


if __name__ == "__main__":
    if not wait_until_ready():
        sys.exit("vLLM draft server not reachable on :8001")
    typing_simulator("id")
    steady_state("id", n=30)
