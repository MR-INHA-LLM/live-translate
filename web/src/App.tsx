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
  const secs = (ms: number) => `${(ms / 1000).toFixed(2)}초`;

  return (
    <div className="console">
      {/* ① 좌: 번역 세션 저장소 */}
      <aside className="col store">
        <div className="storehead">
          <div className="brand">번역 세션</div>
          <button className="newconv" onClick={c.newConversation}>+ 새 대화</button>
        </div>
        <div className="convlist">
          {c.conversations.length === 0 && (
            <p className="empty">저장된 대화가 없습니다.<br />메시지를 보내면 여기에 쌓입니다.</p>
          )}
          {c.conversations.map((cv) => (
            <div
              key={cv.conversation_id}
              className={`convitem ${cv.conversation_id === c.activeConvId ? "active" : ""}`}
            >
              <button
                className="convopen"
                onClick={() => void c.loadConversation(cv.conversation_id)}
              >
                <span className="convtitle">{cv.title ?? "새 대화"}</span>
                <span className="convmeta">
                  {c.nameOf(cv.src_lang)} → {c.nameOf(cv.tgt_lang)} · {cv.message_count}개
                </span>
              </button>
              <button
                className="convdel"
                title="세션 삭제"
                onClick={() => void c.removeConversation(cv.conversation_id)}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* ② 중앙: 운영자 작업대 (방향 선택 · 검증 포함) */}
      <main className="col work">
        <header className="whead">
          <div className="pair">
            <span className="tag">{c.nameOf(c.src)}</span>
            <button className="swap" onClick={c.swap} title="방향 스왑">⇄</button>
            <select value={c.tgt} onChange={(e) => c.setTgt(e.target.value)}>
              {targets.map((l) => (
                <option key={l.code} value={l.code}>{l.name_native}</option>
              ))}
            </select>
          </div>
          {c.latency?.ttft_ms != null && (
            <span className="lat">초벌 {Math.round(c.latency.ttft_ms)}ms</span>
          )}
        </header>

        <div className="feed" ref={feedRef}>
          {c.messages.length === 0 && (
            <p className="empty center">아래에 입력하면 번역이 시작됩니다.</p>
          )}
          {c.messages.map((m) => {
            const transLang = m.side === "mine" ? c.tgt : c.src;
            return (
              <div key={m.id} className={`row ${m.side}`}>
                <div className="meta">{m.side === "mine" ? "운영자(나)" : "고객"}</div>
                <div className="bubble">
                  <div className="orig">{m.source}</div>
                  {m.draft && (
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
                      LLM {transLang}
                      {m.finalMs != null && <span className="ms">{secs(m.finalMs)}</span>}
                    </span>
                    {m.translation}
                  </div>
                  {m.witness && (
                    <div className="trans verify">
                      <span className="lab">
                        검증 {c.witnessLang}
                        {m.draftMs != null && <span className="ms">{secs(m.draftMs)}</span>}
                      </span>
                      {m.witness}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
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

      {/* ③ 우: 고객 화면 — 빈 스테이지 위에 태블릿처럼 부양 */}
      <aside className="col customer">
        <div className="stagelabel">고객이 보는 화면 · {c.nameOf(c.tgt)}</div>
        <div className="device">
          <header className="dhead">번역 대화</header>
          <div className="feed cust" ref={custRef}>
            {c.messages.length === 0 && <p className="empty center">—</p>}
            {c.messages.map((m) => (
              <div key={m.id} className={`crow ${m.side === "mine" ? "in" : "out"}`}>
                <div className="cbubble">{m.side === "mine" ? m.translation : m.source}</div>
              </div>
            ))}
          </div>
          <div className="dcompose">
            <input
              className="dfield"
              placeholder={`${c.nameOf(c.tgt)}로 입력…`}
              value={c.custText}
              disabled={!c.revSessionId}
              onChange={(e) => c.setCustText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  void c.sendFromCustomer();
                }
              }}
            />
            <button
              className="dsend"
              onClick={() => void c.sendFromCustomer()}
              disabled={c.custSending || !c.custText.trim()}
            >
              {c.custSending ? "…" : "↑"}
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}
