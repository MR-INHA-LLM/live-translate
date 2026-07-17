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
  degraded?: boolean;
}

const DEBOUNCE_MS = 200;
const WITNESS = "en";

// 데모용 상대(인니 상담원) 프리셋 — 실제 vLLM 번역값(id→ko).
const SEED: ChatMessage[] = [
  {
    id: "seed-1",
    side: "theirs",
    source: "Mohon maaf atas keterlambatannya. Boleh saya minta nomor pesanan Anda?",
    translation: "지연된 점에 대해 죄송합니다. 혹시 귀하의 주문 번호를 알려주실 수 있나요?",
  },
];

export function useChat() {
  const [catalog, setCatalog] = useState<LanguageCatalog | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [src, setSrc] = useState("ko");
  const [tgt, setTgt] = useState("id");
  const [messages, setMessages] = useState<ChatMessage[]>(SEED);
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [latency, setLatency] = useState<DraftResponse["latency"] | null>(null);
  const [sending, setSending] = useState(false);

  const ws = useRef<WebSocket | null>(null);
  const revision = useRef(0);
  const latestRev = useRef(0);
  const composing = useRef(false);
  const debounce = useRef<number | undefined>(undefined);
  const started = useRef(false);

  // 세션 생성 + WS 연결 (언어쌍 바뀌면 재생성)
  useEffect(() => {
    let cancelled = false;
    getLanguages().then((c) => !cancelled && setCatalog(c)).catch(() => {});
    (async () => {
      const witness = tgt === WITNESS ? [] : [WITNESS];
      const id = await createSession({ src_lang: src, tgt_lang: tgt, witness_langs: witness });
      if (cancelled) return;
      setSessionId(id);
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
    started.current = true;
    return () => {
      cancelled = true;
      ws.current?.close();
      ws.current = null;
    };
  }, [src, tgt]);

  // 초벌: text 변경 → 디바운스 후 revision 전송
  useEffect(() => {
    if (composing.current) return;
    window.clearTimeout(debounce.current);
    if (!text.trim() || !ws.current || ws.current.readyState !== WebSocket.OPEN) {
      setDraft({});
      return;
    }
    debounce.current = window.setTimeout(() => {
      revision.current += 1;
      ws.current?.send(
        JSON.stringify({ revision_id: revision.current, partial_text: text, is_final: false }),
      );
    }, DEBOUNCE_MS);
  }, [text]);

  const onCompositionStart = useCallback(() => {
    composing.current = true;
  }, []);
  const onCompositionEnd = useCallback((v: string) => {
    composing.current = false;
    setText(v); // 확정된 문자열로 트리거
  }, []);

  const send = useCallback(async () => {
    const source = text.trim();
    if (!source || !sessionId || sending) return;
    const witness = draft[WITNESS];
    setSending(true);
    setText("");
    setDraft({});
    let acc = "";
    try {
      await streamTurn(
        sessionId,
        source,
        {
          onToken: (d) => (acc += d),
          onDone: (done) => {
            setMessages((m) => [
              ...m,
              {
                id: `m-${done.turn_id}-${Date.now()}`,
                side: "mine",
                source,
                translation: done.translation,
                witness: tgt === WITNESS ? undefined : witness,
                degraded: done.degraded,
              },
            ]);
          },
        },
      );
    } finally {
      void acc;
      setSending(false);
    }
  }, [text, sessionId, sending, draft, tgt]);

  const swap = useCallback(() => {
    setMessages(SEED);
    setSrc(tgt);
    setTgt(src);
  }, [src, tgt]);

  return {
    catalog, sessionId, src, tgt, setTgt, swap,
    messages, text, setText, draft, latency, sending, send,
    onCompositionStart, onCompositionEnd, witnessLang: WITNESS,
  };
}
