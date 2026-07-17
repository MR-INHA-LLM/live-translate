import { useEffect, useRef } from "react";
import { useChat } from "./useChat";

export default function App() {
  const c = useChat();
  const feedRef = useRef<HTMLDivElement>(null);
  const custRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight });
    custRef.current?.scrollTo({ top: custRef.current.scrollHeight });
  }, [c.messages, c.draft]);

  const targets = (c.catalog?.languages ?? []).filter((l) => l.code !== c.src);
  const draftTgt = c.draft[c.tgt];
  const draftWit = c.tgt !== c.witnessLang ? c.draft[c.witnessLang] : undefined;
  const lastMine = [...c.messages].reverse().find((m) => m.side === "mine");

  return (
    <div className="console">
      {/* ① 좌: 설정 · 검증 */}
      <aside className="col side">
        <div className="brand">실시간 번역 콘솔</div>

        <section>
          <h3>번역 방향</h3>
          <div className="pair">
            <span className="tag">{c.nameOf(c.src)}</span>
            <button className="swap" onClick={c.swap} title="방향 스왑">⇄</button>
            <select value={c.tgt} onChange={(e) => c.setTgt(e.target.value)}>
              {targets.map((l) => (
                <option key={l.code} value={l.code}>{l.name_native}</option>
              ))}
            </select>
          </div>
          <p className="hint">맥락 반영 최종 번역 · 확인용 {c.witnessLang}</p>
        </section>

        <section className="verify">
          <h3>번역 검증 (최근)</h3>
          {lastMine ? (
            <div className="vbox">
              <div className="vrow"><span className="vlab">원문</span>{lastMine.source}</div>
              <div className="vrow"><span className="vlab">번역</span>{lastMine.translation}</div>
              {lastMine.witness && (
                <div className="vrow wit">
                  <span className="vlab">확인용 {c.witnessLang}</span>{lastMine.witness}
                </div>
              )}
              <p className="note">구 정렬·단어 신뢰도(QE)는 백엔드 배선 후 여기 표시됩니다.</p>
            </div>
          ) : (
            <p className="empty">메시지를 보내면 검증이 여기 표시됩니다.</p>
          )}
        </section>
      </aside>

      {/* ② 중앙: 운영자 작업대 */}
      <main className="col work">
        <header className="whead">
          <span className="wtitle">{c.nameOf(c.src)} → {c.nameOf(c.tgt)}</span>
          {c.latency?.ttft_ms != null && (
            <span className="lat">초벌 {Math.round(c.latency.ttft_ms)}ms</span>
          )}
        </header>

        <div className="feed" ref={feedRef}>
          {c.messages.length === 0 && (
            <p className="empty center">아래에 입력하면 번역이 시작됩니다.</p>
          )}
          {c.messages.map((m) => (
            <div key={m.id} className={`row ${m.side}`}>
              <div className="meta">{m.side === "mine" ? "운영자(나)" : "고객"}</div>
              <div className="bubble">
                <div className="orig">{m.source}</div>
                <div className="trans">
                  <span className="lab">{m.side === "mine" ? `→ ${c.tgt}` : `→ ${c.src}`}</span>
                  {m.translation}
                </div>
                {m.witness && <div className="wit">↳ {c.witnessLang} · “{m.witness}”</div>}
              </div>
            </div>
          ))}
        </div>

        <div className="composer">
          {(draftTgt || draftWit) && (
            <div className="draftprev">
              {draftTgt && <span><span className="lab">초벌 {c.tgt}</span>{draftTgt}</span>}
              {draftWit && <span><span className="lab">초벌 {c.witnessLang}</span>{draftWit}</span>}
            </div>
          )}
          <div className="inrow">
            <textarea
              className="field"
              rows={1}
              placeholder={`${c.nameOf(c.src)}로 입력…`}
              value={c.text}
              disabled={!c.sessionId}
              onChange={(e) => c.onInput(e.target.value)}
              onCompositionStart={c.onCompositionStart}
              onCompositionEnd={(e) => c.onCompositionEnd(e.currentTarget.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  void c.send();
                }
              }}
            />
            <button className="send" onClick={() => void c.send()} disabled={c.sending || !c.text.trim()}>
              {c.sending ? "…" : "전송"}
            </button>
          </div>
        </div>
      </main>

      {/* ③ 우: 고객 화면 (고객이 실제 보는 것) */}
      <aside className="col customer">
        <header className="chead">고객 화면 · {c.nameOf(c.tgt)}</header>
        <div className="feed cust" ref={custRef}>
          {c.messages.length === 0 && <p className="empty center">—</p>}
          {c.messages.map((m) => (
            <div key={m.id} className={`crow ${m.side === "mine" ? "in" : "out"}`}>
              <div className="cbubble">{m.side === "mine" ? m.translation : m.source}</div>
            </div>
          ))}
        </div>
        <div className="cfoot">고객은 번역된 {c.nameOf(c.tgt)}만 봅니다.</div>
      </aside>
    </div>
  );
}
