"""Curated probe set for M0 draft-model measurement.

NOT full FLORES+ (that dataset is gated — needs an HF token to accept terms,
plus a COMET model for scoring; deferred to a later iteration). This is a
transparent, human-inspectable probe set targeting exactly the design's open
questions:

  * GENERAL   — is direct ko<->id even coherent, or do we need an en pivot?
                (README open issue #1)
  * DIALOGUE  — the phenomena the quality tier is supposed to fix: pronoun
                reference, formality (존댓말/반말), and Korean subject omission.
                Used to check whether the *draft* tier already handles them
                (if it does, the quality tier has less to prove).

Each item: (id, src_lang, tgt_lang, source_text, note).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Probe:
    id: str
    src: str
    tgt: str
    text: str
    note: str


# --- General single-sentence probes (all 6 directions over ko/en/id) --------
_GENERAL_SENTENCES = [
    ("g1", "ko", "내일 오후 회의를 취소하고 금요일로 옮겨 주세요."),
    ("g2", "ko", "이 제품은 무상 보증 기간이 2년이며, 영수증이 있어야 교환이 가능합니다."),
    ("g3", "en", "The shipment was delayed because the warehouse ran out of packaging."),
    ("g4", "en", "Could you confirm whether the invoice was already sent to the client?"),
    ("id", "id", "Mohon kirimkan ulang faktur karena lampiran sebelumnya tidak bisa dibuka."),
    ("g6", "id", "Pertemuan besok dipindahkan ke sore hari agar semua tim bisa hadir."),
]

# Directions to translate each source into (skip identity).
_TARGETS = {"ko": ["en", "id"], "en": ["ko", "id"], "id": ["ko", "en"]}


def general_probes() -> list[Probe]:
    out: list[Probe] = []
    for sid, src, text in _GENERAL_SENTENCES:
        for tgt in _TARGETS[src]:
            out.append(Probe(f"{sid}-{src}2{tgt}", src, tgt, text, "general"))
    return out


# --- Multi-turn customer-support dialogue (ko source) -----------------------
# Designed so context matters: turn 3 omits the subject, turn 4 uses an
# ambiguous pronoun ("그거"), formality is polite throughout.
DIALOGUE_KO = [
    "안녕하세요, 지난주에 주문한 헤드폰이 아직 도착하지 않았어요.",
    "주문 번호는 A-2231이고, 원래 화요일 도착 예정이었습니다.",
    "확인해 보니 아직 발송도 안 됐네요. 언제쯤 받을 수 있을까요?",
    "그거 오늘 안에 처리해 주시면 정말 감사하겠습니다.",
]


def dialogue_probes(tgt: str = "id") -> list[Probe]:
    """Each turn as an isolated draft-tier translation (no context) — this is
    what the draft tier actually sees. The quality tier will later get context."""
    return [
        Probe(f"d{i+1}-ko2{tgt}", "ko", tgt, turn, "dialogue-turn")
        for i, turn in enumerate(DIALOGUE_KO)
    ]


if __name__ == "__main__":
    g = general_probes()
    d = dialogue_probes("id")
    print(f"general probes: {len(g)}  | dialogue probes: {len(d)}")
    for p in g + d:
        print(f"  {p.id:12s} {p.src}->{p.tgt}  {p.text[:40]}")
