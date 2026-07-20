import { useState, type ReactNode } from "react";
import type { AlignmentSpan, ConfidenceSpan } from "./api";
import type { ChatMessage } from "./useChat";

const secs = (ms: number) => `${(ms / 1000).toFixed(2)}초`;

interface Mark {
  start: number;
  end: number;
  link?: number; // 정렬 링크 인덱스
  low?: boolean; // QE 저신뢰
}

interface Seg {
  text: string;
  links: number[];
  low: boolean;
}

// 텍스트를 마크 경계로 잘라 각 구간이 어떤 정렬 링크·QE에 걸치는지 계산.
function segmentize(text: string, marks: Mark[]): Seg[] {
  const bounds = new Set<number>([0, text.length]);
  for (const m of marks) {
    if (m.start >= 0 && m.start <= text.length) bounds.add(m.start);
    if (m.end >= 0 && m.end <= text.length) bounds.add(m.end);
  }
  const bs = [...bounds].sort((a, b) => a - b);
  const segs: Seg[] = [];
  for (let k = 0; k < bs.length - 1; k++) {
    const a = bs[k];
    const b = bs[k + 1];
    if (a >= b) continue;
    const links = marks.filter((m) => m.link != null && m.start <= a && m.end >= b).map((m) => m.link!);
    const low = marks.some((m) => m.low && m.start <= a && m.end >= b);
    segs.push({ text: text.slice(a, b), links, low });
  }
  return segs;
}

function renderSegs(
  segs: Seg[],
  active: number[],
  setActive: (l: number[]) => void,
): ReactNode {
  return segs.map((s, i) => {
    if (!s.links.length && !s.low) return s.text;
    const isActive = s.links.some((l) => active.includes(l));
    const cls = [
      s.low ? "qe low" : "",
      s.links.length ? "al" : "",
      isActive ? "active" : "",
    ]
      .filter(Boolean)
      .join(" ");
    return (
      <span
        key={i}
        className={cls}
        onMouseEnter={s.links.length ? () => setActive(s.links) : undefined}
        onMouseLeave={s.links.length ? () => setActive([]) : undefined}
      >
        {s.text}
      </span>
    );
  });
}

export function Bubble({
  m,
  src,
  tgt,
  witnessLang,
}: {
  m: ChatMessage;
  src: string;
  tgt: string;
  witnessLang: string;
}) {
  const [active, setActive] = useState<number[]>([]);
  const transLang = m.side === "mine" ? tgt : src;
  const align = m.alignment ?? [];
  const conf: ConfidenceSpan[] = m.confidence ?? [];

  const srcSegs = segmentize(
    m.source,
    align.map((a: AlignmentSpan, i) => ({ start: a.src_start, end: a.src_end, link: i })),
  );
  const tgtSegs = segmentize(m.translation, [
    ...align.map((a: AlignmentSpan, i) => ({ start: a.tgt_start, end: a.tgt_end, link: i })),
    ...conf.filter((c) => c.low).map((c) => ({ start: c.tgt_start, end: c.tgt_end, low: true })),
  ]);

  return (
    <div className={`row ${m.side}`}>
      <div className="meta">{m.side === "mine" ? "운영자(나)" : "고객"}</div>
      <div className="bubble">
        <div className="orig">{align.length ? renderSegs(srcSegs, active, setActive) : m.source}</div>
        {/* quality 미가용(degraded)이면 초벌==최종이라 별도 초벌 줄을 접는다. */}
        {m.draft && !m.degraded && (
          <div className="trans draft">
            <span className="lab">
              초벌 {transLang}
              {m.draftMs != null && <span className="ms">{secs(m.draftMs)}</span>}
            </span>
            {m.draft}
          </div>
        )}
        <div className="trans final">
          <span className="lab">
            {m.degraded ? "번역" : "LLM"} {transLang}
            {m.finalMs != null && <span className="ms">{secs(m.finalMs)}</span>}
          </span>
          {align.length || conf.length ? renderSegs(tgtSegs, active, setActive) : m.translation}
        </div>
        {m.roundTrip && (
          <div className="trans verify">
            <span className="lab">
              역번역 {m.side === "mine" ? src : tgt}
              {m.roundTripMs != null && <span className="ms">{secs(m.roundTripMs)}</span>}
            </span>
            {m.roundTrip}
          </div>
        )}
        {m.witness && (
          <div className="trans verify">
            <span className="lab">
              확인 {witnessLang}
              {m.draftMs != null && <span className="ms">{secs(m.draftMs)}</span>}
            </span>
            {m.witness}
          </div>
        )}
      </div>
    </div>
  );
}
