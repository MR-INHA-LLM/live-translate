import { useCallback, useEffect, useRef, useState } from "react";
import {
  createSession,
  getLanguages,
  openDraftSocket,
  streamTurn,
  type DraftResponse,
  type LanguageCatalog,
} from "./api";

export interface ChatMessage {
  id: string;
  side: "mine" | "theirs";
  source: string;
  translation: string;
  witness?: string;
}

const DEBOUNCE_MS = 200; // 초벌 발사 전 대기 (StabilityConfig.debounce_ms 기본과 동일)
const DEFAULT_SRC = "ko";
const DEFAULT_TGT = "en"; // 기본 쌍 ko⇄en (design). 선택기로 변경.

export function useChat() {
  const [catalog, setCatalog] = useState<LanguageCatalog | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [revSessionId, setRevSessionId] = useState<string | null>(null); // 고객→운영자 역방향
  const [src, setSrc] = useState(DEFAULT_SRC);
  const [tgt, setTgt] = useState(DEFAULT_TGT);
  const [witnessLang, setWitnessLang] = useState("en");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [custText, setCustText] = useState("");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [latency, setLatency] = useState<DraftResponse["latency"] | null>(null);
  const [sending, setSending] = useState(false);
  const [custSending, setCustSending] = useState(false);

  const ws = useRef<WebSocket | null>(null);
  const revision = useRef(0);
  const latestRev = useRef(0);
  const composing = useRef(false);
  const debounce = useRef<number | undefined>(undefined);

  // 카탈로그 로드 → 세션 생성 → WS 연결 (언어쌍 바뀌면 재생성)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const cat = await getLanguages();
      if (cancelled) return;
      setCatalog(cat);
      const wit = cat.default_witness;
      setWitnessLang(wit);
      const witnessLangs = tgt === wit ? [] : [wit];
      const id = await createSession({ src_lang: src, tgt_lang: tgt, witness_langs: witnessLangs });
      if (cancelled) return;
      setSessionId(id);
      // 고객(외국인)이 자기 화면에서 입력 → 운영자 언어로 역번역하는 세션.
      const revId = await createSession({ src_lang: tgt, tgt_lang: src, witness_langs: [] });
      if (cancelled) return;
      setRevSessionId(revId);
      const sock = openDraftSocket(id);
      sock.onmessage = (ev) => {
        const msg = JSON.parse(ev.data) as DraftResponse;
        if (msg.revision_id < latestRev.current) return; // stale
        latestRev.current = msg.revision_id;
        setDraft(msg.renderings);
        setLatency(msg.latency);
      };
      ws.current = sock;
    })().catch(() => {});
    return () => {
      cancelled = true;
      ws.current?.close();
      ws.current = null;
    };
  }, [src, tgt]);

  // 초벌 전송은 입력 핸들러에서 명시적으로 트리거한다(useEffect[text] 의존 X).
  // 한글 IME: 조합 중 onChange가 값을 미리 바꿔 compositionend에서 같은 값이 되면
  // effect가 안 도는 문제가 있어 — compositionend에서 직접 스케줄한다.
  const scheduleDraft = useCallback((value: string) => {
    window.clearTimeout(debounce.current);
    if (!value.trim() || !ws.current || ws.current.readyState !== WebSocket.OPEN) {
      setDraft({});
      return;
    }
    debounce.current = window.setTimeout(() => {
      revision.current += 1;
      ws.current?.send(
        JSON.stringify({ revision_id: revision.current, partial_text: value, is_final: false }),
      );
    }, DEBOUNCE_MS);
  }, []);

  const onInput = useCallback(
    (v: string) => {
      setText(v);
      if (!composing.current) scheduleDraft(v); // 조합 중이 아니면 즉시 스케줄
    },
    [scheduleDraft],
  );

  const onCompositionStart = useCallback(() => {
    composing.current = true;
  }, []);
  const onCompositionEnd = useCallback(
    (v: string) => {
      composing.current = false;
      setText(v);
      scheduleDraft(v); // 조합 확정 시 항상 스케줄 (IME 버그 회피)
    },
    [scheduleDraft],
  );

  const send = useCallback(async () => {
    const source = text.trim();
    if (!source || !sessionId || sending) return;
    const witness = draft[witnessLang];
    setSending(true);
    setText("");
    setDraft({});
    try {
      await streamTurn(sessionId, source, {
        onDone: (done) => {
          setMessages((m) => [
            ...m,
            {
              id: `m-${done.turn_id}-${Date.now()}`,
              side: "mine",
              source,
              translation: done.translation,
              witness: tgt === witnessLang ? undefined : witness,
            },
          ]);
        },
      });
    } finally {
      setSending(false);
    }
  }, [text, sessionId, sending, draft, tgt, witnessLang]);

  const sendFromCustomer = useCallback(async () => {
    const source = custText.trim();
    if (!source || !revSessionId || custSending) return;
    setCustSending(true);
    setCustText("");
    try {
      await streamTurn(revSessionId, source, {
        onDone: (done) => {
          setMessages((m) => [
            ...m,
            {
              id: `c-${done.turn_id}-${Date.now()}`,
              side: "theirs",
              source, // 고객이 입력한 원문(tgt 언어)
              translation: done.translation, // 운영자 언어(src)로 번역
            },
          ]);
        },
      });
    } finally {
      setCustSending(false);
    }
  }, [custText, revSessionId, custSending]);

  const swap = useCallback(() => {
    setMessages([]);
    setSrc(tgt);
    setTgt(src);
  }, [src, tgt]);

  const nameOf = useCallback(
    (code: string) => catalog?.languages.find((l) => l.code === code)?.name_native ?? code,
    [catalog],
  );

  return {
    catalog, sessionId, revSessionId, src, tgt, setTgt, swap, witnessLang, nameOf,
    messages, text, onInput, draft, latency, sending, send,
    custText, setCustText, custSending, sendFromCustomer,
    onCompositionStart, onCompositionEnd,
  };
}
