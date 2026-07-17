"""Probe the #1 design challenge (section 2.1): draft-tier flicker.

Two questions the stabilization design depends on:

  1. DETERMINISM — with temperature=0, is the same prompt reproducible? The
     hold-k / local-agreement scheme assumes repeated identical prefixes are
     stable, not noisy.
  2. PREFIX GROWTH — as the source grows one 어절 at a time, how much of the
     PREVIOUS translation survives as a prefix of the next? This is the real
     flicker magnitude the UI must hide.
"""

from __future__ import annotations

import sys
from os import path

sys.path.insert(0, path.dirname(__file__))
from _client import translate, wait_until_ready  # noqa: E402
from prompts import build_user_prompt  # noqa: E402

SENTENCE = "내일 오후 회의를 취소하고 금요일 아침으로 옮겨 주시겠어요"


def common_prefix_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def determinism(tgt: str = "id", reps: int = 5) -> None:
    print("=" * 78)
    print(f"1) DETERMINISM  (temp=0, same prompt x{reps})")
    print("=" * 78)
    prompt = build_user_prompt("ko", tgt, SENTENCE)
    outs = [translate(prompt) for _ in range(reps)]
    same = all(o == outs[0] for o in outs)
    print(f"  all identical: {same}")
    for i, o in enumerate(outs):
        print(f"  [{i}] {o}")


def prefix_growth(tgt: str = "id") -> None:
    print("\n" + "=" * 78)
    print(f"2) PREFIX GROWTH  ko -> {tgt}  (how much survives revision to revision)")
    print("=" * 78)
    words = SENTENCE.split()
    prev = ""
    for i in range(1, len(words) + 1):
        cur = translate(build_user_prompt("ko", tgt, " ".join(words[:i])))
        cpl = common_prefix_len(prev, cur)
        frac = (cpl / len(prev) * 100) if prev else 0.0
        print(f"  rev{i}: kept {cpl:>3}/{len(prev):>3} chars ({frac:4.0f}%) of prev prefix")
        print(f"        {cur}")
        prev = cur


if __name__ == "__main__":
    if not wait_until_ready():
        sys.exit("vLLM draft server not reachable on :8001")
    determinism("id")
    prefix_growth("id")
