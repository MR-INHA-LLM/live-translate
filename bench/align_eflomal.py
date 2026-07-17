"""eflomal 정렬 실현성 — 순수 통계 정렬(신경망 0)이 데모에 그럴듯한가.

학습데이터: OpenSubtitles v2018 ko-en / ko-id(대화체) 서브셋. 데모 문장(실제 HY-MT
출력)을 코퍼스 끝에 붙여 함께 학습·정렬 → 마지막 N줄이 데모 정렬.
검증(골드 정렬 부재): (a) 데모 문장 육안, (b) 소스 내용어 정렬 커버리지.

사용: uv run python bench/align_eflomal.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPUS = ROOT / "data" / "opus"
WORK = ROOT / "data" / "eflomal"
BIN = Path(sys.executable).parent / "eflomal-align"
N_TRAIN = 150_000

# 데모 쌍 (실제 HY-MT 출력, SimAlign 검증과 동일 문장)
DEMO = {
    "en": [
        ("내일 오후 회의를 취소하고 금요일로 옮겨 주세요.",
         "Please cancel the meeting scheduled for tomorrow afternoon and move it to Friday instead."),
        ("그거 오늘 안에 처리해 주시면 정말 감사하겠습니다.",
         "I would be very grateful if you could handle that by today's deadline."),
    ],
    "id": [
        ("내일 오후 회의를 취소하고 금요일로 옮겨 주세요.",
         "Mohon membatalkan rapat yang akan berlangsung besok sore, dan menggantinya ke hari Jumat."),
        ("안녕하세요, 지난주에 주문한 헤드폰이 아직 도착하지 않았어요.",
         "Halo, headphone yang saya pesan minggu lalu masih belum sampai ke tangan saya."),
    ],
}

_STRIP = re.compile(r"^[^\w]+|[^\w]+$")


def tok(s: str) -> list[str]:
    out = []
    for w in s.strip().lower().split():
        w = _STRIP.sub("", w)
        if w:
            out.append(w)
    return out


NEI = [(-1, 0), (0, -1), (1, 0), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]


def gdfa(fwd: set, rev: set, n: int, m: int) -> set:
    """grow-diag-final-and 대칭화."""
    union = fwd | rev
    a = set(fwd & rev)
    while True:
        added = False
        sa = {i for i, _ in a}
        ta = {j for _, j in a}
        for i, j in list(a):
            for di, dj in NEI:
                ni, nj = i + di, j + dj
                if 0 <= ni < n and 0 <= nj < m and (ni, nj) in union and (ni, nj) not in a:
                    if ni not in sa or nj not in ta:
                        a.add((ni, nj)); sa.add(ni); ta.add(nj); added = True
        if not added:
            break
    sa = {i for i, _ in a}; ta = {j for _, j in a}
    for i, j in union:
        if i not in sa and j not in ta:
            a.add((i, j)); sa.add(i); ta.add(j)
    return a


def parse(line: str) -> set:
    return {(int(a), int(b)) for a, b in (p.split("-") for p in line.split())} if line.strip() else set()


def build_corpus(lang: str) -> tuple[list[list[str]], list[list[str]], int]:
    """OpenSubtitles 서브셋 + 데모 → (src 토큰들, tgt 토큰들, 데모 개수)."""
    ko = (OPUS / f"{'idko' if lang == 'id' else 'enko'}" /
          f"OpenSubtitles.{'id-ko' if lang == 'id' else 'en-ko'}.ko").read_text(encoding="utf-8").splitlines()
    tg = (OPUS / f"{'idko' if lang == 'id' else 'enko'}" /
          f"OpenSubtitles.{'id-ko' if lang == 'id' else 'en-ko'}.{lang}").read_text(encoding="utf-8").splitlines()
    src, tgt = [], []
    for k, t in zip(ko, tg):
        ks, ts = tok(k), tok(t)
        if 1 <= len(ks) <= 40 and 1 <= len(ts) <= 40:
            src.append(ks); tgt.append(ts)
        if len(src) >= N_TRAIN:
            break
    n_demo = len(DEMO[lang])
    for ks, ts in DEMO[lang]:
        src.append(tok(ks)); tgt.append(tok(ts))
    return src, tgt, n_demo


def run(lang: str) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    src, tgt, n_demo = build_corpus(lang)
    sp, tp = WORK / f"src.{lang}", WORK / f"tgt.{lang}"
    fp, rp = WORK / f"fwd.{lang}", WORK / f"rev.{lang}"
    sp.write_text("\n".join(" ".join(s) for s in src) + "\n", encoding="utf-8")
    tp.write_text("\n".join(" ".join(t) for t in tgt) + "\n", encoding="utf-8")

    print(f"\n{'='*72}\nko → {lang}   학습 {len(src)-n_demo:,}쌍 + 데모 {n_demo}")
    subprocess.run([str(BIN), "-s", str(sp), "-t", str(tp), "-f", str(fp),
                    "-r", str(rp), "-m", "3", "--overwrite"], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    fwd = [parse(x) for x in fp.read_text().splitlines()]
    rev = [parse(x) for x in rp.read_text().splitlines()]
    total_content, covered = 0, 0
    for d in range(n_demo):
        idx = len(src) - n_demo + d
        s_w, t_w = src[idx], tgt[idx]
        a = gdfa(fwd[idx], rev[idx], len(s_w), len(t_w))
        by_src: dict[int, list[str]] = {}
        for i, j in sorted(a):
            by_src.setdefault(i, []).append(t_w[j])
        print(f"\n  [{d+1}]  {' '.join(s_w)}")
        print(f"       {' '.join(t_w)}")
        for i, w in enumerate(s_w):
            mapped = " · ".join(by_src.get(i, ["—"]))
            print(f"       {w:<14} → {mapped}")
            if len(w) >= 2:  # 내용어 근사
                total_content += 1
                covered += 1 if i in by_src else 0
    print(f"\n  내용어 정렬 커버리지: {covered}/{total_content} "
          f"({100*covered/max(1,total_content):.0f}%)")


if __name__ == "__main__":
    for lang in ("en", "id"):
        run(lang)
