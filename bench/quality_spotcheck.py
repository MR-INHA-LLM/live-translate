"""M0 quality spot-check: translate every probe, print for human inspection.

Answers the design's open question #1 (is direct ko<->id good enough, or do we
need an English pivot?) and shows whether the draft tier alone handles the
dialogue phenomena the quality tier targets.
"""

from __future__ import annotations

import sys

from _client import translate, wait_until_ready
from eval_set import dialogue_probes, general_probes
from prompts import build_user_prompt


def run() -> None:
    if not wait_until_ready():
        sys.exit("vLLM draft server not reachable on :8001")

    print("=" * 78)
    print("GENERAL PROBES  (ko/en/id, all 6 directions)")
    print("=" * 78)
    for p in general_probes():
        hyp = translate(build_user_prompt(p.src, p.tgt, p.text))
        print(f"\n[{p.id}]  {p.src} -> {p.tgt}")
        print(f"  src: {p.text}")
        print(f"  out: {hyp}")

    print("\n" + "=" * 78)
    print("DIALOGUE PROBES  ko -> id  (draft tier = NO context; each turn alone)")
    print("=" * 78)
    for p in dialogue_probes("id"):
        hyp = translate(build_user_prompt(p.src, p.tgt, p.text))
        print(f"\n[{p.id}]")
        print(f"  src: {p.text}")
        print(f"  out: {hyp}")

    # Also ko->en for the dialogue so a non-Indonesian reader can judge fidelity.
    print("\n" + "-" * 78)
    print("DIALOGUE PROBES  ko -> en  (readability cross-check)")
    print("-" * 78)
    for p in dialogue_probes("en"):
        hyp = translate(build_user_prompt(p.src, p.tgt, p.text))
        print(f"\n[{p.id}]")
        print(f"  src: {p.text}")
        print(f"  out: {hyp}")


if __name__ == "__main__":
    run()
