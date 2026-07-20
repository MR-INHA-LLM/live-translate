import { useEffect, useRef, useState } from "react";
import { useChat } from "./useChat";
import { Bubble } from "./Bubble";
import { STRINGS, type Lang } from "./i18n";

// 언어 코드 → 국기 파일(design-handoff). 없으면 국기 생략.
const FLAG: Record<string, string> = { ko: "KR", en: "US", id: "ID", ja: "JP", th: "TH", ru: "RU" };
const flagSrc = (code: string) => (FLAG[code] ? `/flags/${FLAG[code]}.svg` : undefined);

export default function App() {
  const c = useChat();
  const feedRef = useRef<HTMLDivElement>(null);
  const custRef = useRef<HTMLDivElement>(null);

  const [uiLang, setUiLang] = useState<Lang>(() => (localStorage.getItem("ui-lang") as Lang) || "ko");
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const s = localStorage.getItem("theme");
    if (s === "light" || s === "dark") return s;
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);
  useEffect(() => {
    localStorage.setItem("ui-lang", uiLang);
    document.documentElement.lang = uiLang;
  }, [uiLang]);
  const t = STRINGS[uiLang];

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight });
    custRef.current?.scrollTo({ top: custRef.current.scrollHeight });
  }, [c.messages, c.draft]);

  const targets = (c.catalog?.languages ?? []).filter((l) => l.code !== c.src);
  const draftTgt = c.draft[c.tgt];
  const draftWit = c.tgt !== c.witnessLang ? c.draft[c.witnessLang] : undefined;

  return (
    <div className="app">
      {/* 상단 바(단일): 실시간 번역 · 번역 방향 · Docs · UI 언어 · 테마 */}
      <div className="statusbar">
        <div className="wordmark"><span className="dot" />{t.appTitle}</div>
        <span className="sb-div" />
        <div className="pair">
          <span className="tag">
            {flagSrc(c.src) && <img className="fl" alt="" src={flagSrc(c.src)} />}
            {c.nameOf(c.src)}
          </span>
          <button className="swap" onClick={c.swap} title={t.swapTitle}>⇄</button>
          <span className="selwrap">
            {flagSrc(c.tgt) && <img className="fl" alt="" src={flagSrc(c.tgt)} />}
            <select className="sel" value={c.tgt} onChange={(e) => c.setTgt(e.target.value)}>
              {targets.map((l) => (
                <option key={l.code} value={l.code}>{l.name_native}</option>
              ))}
            </select>
          </span>
        </div>
        <div className="spacer" />
        <a className="docsbtn" href="/docs" target="_blank" rel="noreferrer">
          {t.apiDocs}<span className="ext">↗</span>
        </a>
        <div className="uilang">
          <button className={uiLang === "ko" ? "on" : ""} onClick={() => setUiLang("ko")}>KO</button>
          <button className={uiLang === "en" ? "on" : ""} onClick={() => setUiLang("en")}>EN</button>
        </div>
        <button className="themebtn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} title="theme">◐</button>
      </div>

      <div className="console">
        {/* ① 세션 저장소 */}
        <aside className="col store">
          <div className="storehead">
            <div className="brand">{t.sessions}</div>
            <button className="newconv" onClick={c.newConversation}>{t.newConv}</button>
          </div>
          <div className="convlist">
            {c.conversations.length === 0 && <p className="empty">{t.noSessions}</p>}
            {c.conversations.map((cv) => (
              <div key={cv.conversation_id} className={`convitem ${cv.conversation_id === c.activeConvId ? "active" : ""}`}>
                <button className="convopen" onClick={() => void c.loadConversation(cv.conversation_id)}>
                  <span className="convtitle">{cv.title ?? t.newConv.replace("+ ", "")}</span>
                  <span className="convmeta">
                    {c.nameOf(cv.src_lang)} → {c.nameOf(cv.tgt_lang)} · <span className="cnt">{t.count(cv.message_count)}</span>
                  </span>
                </button>
                <button className="convdel" title={t.delTitle} onClick={() => void c.removeConversation(cv.conversation_id)}>✕</button>
              </div>
            ))}
          </div>
          <footer className="storefoot">
            <a href="https://aclanthology.org/2026.tacl-1.26/" target="_blank" rel="noreferrer">{t.ctxMt}</a>
            <span> · Pombal et al., TACL 2026</span>
          </footer>
        </aside>

        {/* ② 작업대 */}
        <main className="col work">
          <div className="feed" ref={feedRef}>
            {c.messages.length === 0 && <p className="empty center">{t.feedEmpty}</p>}
            {c.messages.map((m) => (
              <Bubble key={m.id} m={m} src={c.src} tgt={c.tgt} witnessLang={c.witnessLang} t={t} />
            ))}
          </div>

          <div className="composer">
            {c.retranslating && (
              <div className="retrans"><span className="dot" />{t.retranslating}</div>
            )}
            {(draftTgt || draftWit || c.draftPending) && (
              <div className="draftprev">
                {draftTgt && (
                  <span>
                    <span className="lab">{t.draft} {c.tgt}</span> {draftTgt}
                    {c.draftPending && <span className="pdot">● {t.calc}</span>}
                  </span>
                )}
                {draftWit && <span><span className="lab">{t.draft} {c.witnessLang}</span> {draftWit}</span>}
                {!draftTgt && !draftWit && c.draftPending && <span className="pendingline">{t.pending}</span>}
              </div>
            )}
            <div className="inrow">
              <textarea
                className="field"
                rows={1}
                placeholder={t.inputPh(c.nameOf(c.src))}
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
                {c.sending ? "…" : t.send}
              </button>
            </div>
          </div>
        </main>

        {/* ③ 고객 화면 — 스테이지 위 태블릿, 상담원 메시지에 프로필(카톡식) */}
        <aside className="col customer">
          <div className="stagelabel">{t.custView} · {c.nameOf(c.tgt)}</div>
          <div className="device">
            <header className="dhead"><span className="glyph" />{t.convo}</header>
            <div className="cfeed" ref={custRef}>
              {c.messages.length === 0 && <p className="empty center">—</p>}
              {c.messages.map((m, i) => {
                const side = m.side === "mine" ? "in" : "out";
                const firstOfGroup = i === 0 || c.messages[i - 1].side !== m.side;
                return (
                  <div key={m.id} className={`crow ${side} ${firstOfGroup ? "grp" : ""}`}>
                    {side === "in" &&
                      (firstOfGroup ? (
                        <img className="avatar" alt="" src="/avatar/doctor.png" />
                      ) : (
                        <div className="avspace" />
                      ))}
                    <div className="cbubble">{m.side === "mine" ? m.translation : m.source}</div>
                  </div>
                );
              })}
            </div>
            <div className="dcompose">
              <input
                className="dfield"
                placeholder={t.inputPh(c.nameOf(c.tgt))}
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
              <button className="dsend" onClick={() => void c.sendFromCustomer()} disabled={c.custSending || !c.custText.trim()}>
                {c.custSending ? "…" : "↑"}
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
