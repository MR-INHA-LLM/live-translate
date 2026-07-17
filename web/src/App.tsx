import { useEffect, useRef } from "react";
import { useChat } from "./useChat";

export default function App() {
  const c = useChat();
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight });
  }, [c.messages, c.draft]);

  const targets = (c.catalog?.languages ?? []).filter((l) => l.code !== c.src);
  const draftTgt = c.draft[c.tgt];
  const draftWit = c.tgt !== c.witnessLang ? c.draft[c.witnessLang] : undefined;

  return (
    <div className="app">
      <div className="phone">
        <header>
          <span className="who">인니 상담원</span>
          <span className="langs">
            한국어 <span className="swap" onClick={c.swap} title="방향 스왑">⇄</span>{" "}
            <select value={c.tgt} onChange={(e) => c.setTgt(e.target.value)}>
              {targets.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.name_native}
                </option>
              ))}
            </select>
          </span>
          <span className="ctx">
            {c.latency?.ttft_ms != null && (
              <span className="lat">draft {Math.round(c.latency.ttft_ms)}ms</span>
            )}
          </span>
        </header>

        <div className="feed" ref={feedRef}>
          {c.messages.map((m) => (
            <div key={m.id} className={`row ${m.side}`}>
              <div className="meta">
                {m.side === "mine" ? `나 · ${c.src} → ${c.tgt}` : `상대 · ${c.tgt} → ${c.src}`}
              </div>
              <div className="bubble">
                <div className="orig">{m.source}</div>
                <div className="trans">
                  <span className="lab">{m.side === "mine" ? "보냄" : "읽음"}</span>
                  {m.translation}
                </div>
                {m.witness && <div className="wit">↳ 확인용 en · “{m.witness}”</div>}
                {m.degraded && <span className="badge">간이(초벌) 결과</span>}
              </div>
            </div>
          ))}
        </div>

        <div className="composer">
          {(draftTgt || draftWit) && (
            <div className="draftprev">
              {draftTgt && (
                <span>
                  <span className="lab">초벌 {c.tgt}</span>
                  {draftTgt}
                </span>
              )}
              {draftWit && (
                <span>
                  <span className="lab">초벌 {c.witnessLang}</span>
                  {draftWit}
                </span>
              )}
            </div>
          )}
          <div className="inrow">
            <textarea
              className="field"
              rows={1}
              placeholder="한국어로 입력…"
              value={c.text}
              disabled={!c.sessionId}
              onChange={(e) => c.setText(e.target.value)}
              onCompositionStart={c.onCompositionStart}
              onCompositionEnd={(e) => c.onCompositionEnd(e.currentTarget.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  void c.send();
                }
              }}
            />
            <button
              className="send"
              onClick={() => void c.send()}
              disabled={c.sending || !c.text.trim()}
            >
              {c.sending ? "…" : "전송"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
