"""M0 quantitative eval — FLORES-200 devtest COMET, all 6 ko/en/id directions.

Source: official Meta FLORES-200 devtest (ungated public tarball), 1012 n-way
parallel sentences. FLORES+ is the maintained successor but is gated; for ko/en/id
direction quality the FLORES-200 devtest is the canonical, widely-reported set.

Pipeline:
  1. translate every source with the draft model via the vLLM endpoint (concurrent)
  2. score with reference-based COMET (Unbabel/wmt22-comet-da) using src/hyp/ref

Two stages so the (slow) translation pass is cached to disk and COMET scoring can
be re-run without re-translating:

  python bench/flores.py translate   # -> data/flores_hyps.jsonl
  python bench/flores.py score       # reads that file, prints COMET table
  python bench/flores.py all [N]     # both; optional N = sentences per direction
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from os import path

sys.path.insert(0, path.dirname(__file__))
from _client import translate, wait_until_ready  # noqa: E402
from prompts import build_user_prompt  # noqa: E402

DATA_DIR = path.join(path.dirname(__file__), "..", "data", "flores200_dataset", "devtest")
HYP_FILE = path.join(path.dirname(__file__), "..", "data", "flores_hyps.jsonl")

LANG_FILE = {"ko": "kor_Hang.devtest", "en": "eng_Latn.devtest", "id": "ind_Latn.devtest"}
DIRECTIONS = [("ko", "en"), ("en", "ko"), ("ko", "id"), ("id", "ko"), ("en", "id"), ("id", "en")]


def _load_lang(lang: str) -> list[str]:
    with open(path.join(DATA_DIR, LANG_FILE[lang]), encoding="utf-8") as f:
        return [ln.rstrip("\n") for ln in f]


def translate_all(limit: int | None = None) -> None:
    if not wait_until_ready():
        sys.exit("vLLM draft server not reachable on :8001")
    texts = {l: _load_lang(l) for l in LANG_FILE}
    n = len(next(iter(texts.values())))
    if limit:
        n = min(n, limit)
    print(f"translating {n} sentences x {len(DIRECTIONS)} directions "
          f"= {n * len(DIRECTIONS)} calls")

    rows: list[dict] = []
    for src, tgt in DIRECTIONS:
        srcs, refs = texts[src][:n], texts[tgt][:n]

        def _one(i: int) -> dict:
            hyp = translate(build_user_prompt(src, tgt, srcs[i]), max_tokens=512)
            return {"dir": f"{src}2{tgt}", "src": srcs[i], "ref": refs[i], "hyp": hyp}

        with ThreadPoolExecutor(max_workers=16) as ex:
            dir_rows = list(ex.map(_one, range(n)))
        rows.extend(dir_rows)
        print(f"  {src}->{tgt}: {len(dir_rows)} done")

    with open(HYP_FILE, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} rows -> {HYP_FILE}")


def score() -> None:
    import os

    from comet import download_model, load_from_checkpoint

    rows = [json.loads(ln) for ln in open(HYP_FILE, encoding="utf-8")]
    ckpt = download_model("Unbabel/wmt22-comet-da", saving_directory="models/comet")
    model = load_from_checkpoint(ckpt)

    print("\n" + "=" * 60)
    print("FLORES-200 devtest · COMET (wmt22-comet-da, reference-based)")
    print("=" * 60)
    print(f"{'direction':<10}{'COMET':>9}{'n':>7}")
    overall = []
    for src, tgt in DIRECTIONS:
        d = f"{src}2{tgt}"
        sub = [r for r in rows if r["dir"] == d]
        data = [{"src": r["src"], "mt": r["hyp"], "ref": r["ref"]} for r in sub]
        out = model.predict(data, batch_size=64, gpus=1, progress_bar=False)
        score = out["system_score"]
        overall.append(score)
        print(f"{d:<10}{score*100:>8.2f} {len(sub):>7}")
    print("-" * 26)
    print(f"{'avg':<10}{sum(overall)/len(overall)*100:>8.2f}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else None
    if cmd in ("translate", "all"):
        translate_all(lim)
    if cmd in ("score", "all"):
        score()
