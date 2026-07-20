import { useState, type ReactNode } from "react";
import type { AlignmentSpan, ConfidenceSpan } from "./api";
import type { ChatMessage } from "./useChat";
import type { T } from "./i18n";

const secs = (ms: number) => `${(ms / 1000).toFixed(2)}s`;

interface Mark {
  start: number;
  end: number;
  link?: number; // 정렬 링크 인덱스
  low?: boolean; // 신뢰도 저조
}
interface Seg {
  text: string;
  links: number[];
  low: boolean;
}

// 텍스트를 마크 경계로 잘라 각 구간이 어떤 정렬 링크·신뢰도에 걸치는지 계산.
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

function renderSegs(segs: Seg[], active: number[], setActive: (l: number[]) => void): ReactNode {
  return segs.map((s, i) => {
    if (!s.links.length && !s.low) return s.text;
    const isActive = s.links.some((l) => active.includes(l));
    // 신뢰도 저조가 우선(주황). 아니면 정렬 색(쌍 인덱스 % 5).
    const cls = s.low
      ? "qe"
      : `al a${s.links[0] % 5}${isActive ? " on" : ""}`;
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
  t,
}: {
  m: ChatMessage;
  src: string;
  tgt: string;
  witnessLang: string;
  t: T;
}) {
  const [active, setActive] = useState<number[]>([]);
  const transLang = m.side === "mine" ? tgt : src; // 초벌·최종 언어
  const rtLang = m.side === "mine" ? src : tgt; // 역번역 언어(원래 원문 언어)
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
      <div className="rec">
        <div className="src">{align.length ? renderSegs(srcSegs, active, setActive) : m.source}</div>
        <div className="stack">
          {m.draft && !m.degraded && (
            <div className="lane draft">
              <div className="k">
                <span className="name">{t.draft} {transLang}</span>
                {m.draftMs != null && <span className="ms">{secs(m.draftMs)}</span>}
              </div>
              <div className="v">{m.draft}</div>
            </div>
          )}
          <div className="lane qlt">
            <div className="k">
              <span className="name">{t.final} {transLang}</span>
              {m.finalMs != null && <span className="ms">{secs(m.finalMs)}</span>}
            </div>
            <div className="v">
              {align.length || conf.length ? renderSegs(tgtSegs, active, setActive) : m.translation}
            </div>
          </div>
          {m.roundTrip && (
            <div className="lane rt">
              <div className="k">
                <span className="name">{t.backtr} {rtLang}</span>
                {m.roundTripMs != null && <span className="ms">{secs(m.roundTripMs)}</span>}
              </div>
              <div className="v">{m.roundTrip}</div>
            </div>
          )}
          {m.witness && (
            <div className="lane wit">
              <div className="k">
                <span className="name">{t.witness} {witnessLang}</span>
                {m.draftMs != null && <span className="ms">{secs(m.draftMs)}</span>}
              </div>
              <div className="v">{m.witness}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
