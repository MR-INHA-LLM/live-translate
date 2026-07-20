import { useCallback, useEffect, useRef, useState } from "react";
import {
  addMessage,
  createConversation,
  createSession,
  deleteConversation,
  getConversation,
  getLanguages,
  listConversations,
  openDraftSocket,
  streamTurn,
  type AlignmentSpan,
  type ConfidenceSpan,
  type ConversationSummary,
  type DraftResponse,
  type LanguageCatalog,
  type MessageInput,
} from "./api";

export interface ChatMessage {
  id: string;
  side: "mine" | "theirs";
  source: string;
  translation: string; // LLM(최종) 번역
  draft?: string; // 초벌(빠른) 번역
  witness?: string; // 검증(확인용 언어)
  roundTrip?: string; // 역번역(tgt→src)
  confidence?: ConfidenceSpan[]; // 단어 QE
  alignment?: AlignmentSpan[]; // 구 정렬
  draftMs?: number; // 초벌·검증 소요(ms)
  finalMs?: number; // LLM 소요(ms)
  roundTripMs?: number; // 역번역 소요(ms)
  degraded?: boolean; // quality 미가용 → draft로 최종 (초벌==최종, 버블 단일 줄)
}

// 적응형 디바운스: 최근 초벌 지연에 맞춰 자동 조절(GPU 빠르면 짧게, CPU 느리면 길게).
const DEBOUNCE_MIN = 150;
const DEBOUNCE_MAX = 1000;
function nextDebounce(lastMs: number | undefined): number {
  if (!lastMs) return 200;
  return Math.max(DEBOUNCE_MIN, Math.min(DEBOUNCE_MAX, Math.round(lastMs * 0.6)));
}
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
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [draftPending, setDraftPending] = useState(false); // 초벌 계산 대기(기존 초벌은 유지)

  const ws = useRef<WebSocket | null>(null);
  const revision = useRef(0);
  const latestRev = useRef(0);
  const composing = useRef(false);
  const debounce = useRef<number | undefined>(undefined);
  // 대화 id는 저장 사이 즉시 참조가 필요해 ref를 원본으로, state는 목록 하이라이트용.
  const convId = useRef<string | null>(null);
  // 초벌 소요(ms) — 전송 시점 캡처를 latency state 클로저 레이스 없이 하려고 ref로 둔다.
  const lastDraftMs = useRef<number | undefined>(undefined);
  // 단일 in-flight 코디네이션(anti-jank): 요청은 항상 1개만, 나머지는 최신값만 대기.
  const inflight = useRef(false);
  const pendingValue = useRef<string | null>(null);
  const sentRev = useRef(0);
  const sendDraftRef = useRef<(v: string) => void>(() => {}); // 효과 클로저에서 최신 sendDraft 참조

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
        setDraft(msg.renderings); // 새 초벌 도착 시에만 교체(그전까지 이전 초벌 유지)
        setLatency(msg.latency);
        lastDraftMs.current = msg.latency.total_ms ?? msg.latency.ttft_ms ?? undefined;
        // 이번 in-flight 요청의 응답이면 → 완료 처리 + 대기 중 최신값 발사(single-flight).
        if (msg.revision_id >= sentRev.current) {
          inflight.current = false;
          const next = pendingValue.current;
          pendingValue.current = null;
          if (next && next.trim()) sendDraftRef.current(next);
          else setDraftPending(false);
        }
      };
      ws.current = sock;
    })().catch(() => {});
    return () => {
      cancelled = true;
      ws.current?.close();
      ws.current = null;
    };
  }, [src, tgt]);

  // 대화 목록(저장소) 로드 — 마운트 시 1회.
  const refreshList = useCallback(async () => {
    setConversations(await listConversations());
  }, []);
  useEffect(() => {
    refreshList().catch(() => {});
  }, [refreshList]);

  // 확정 메시지를 대화에 영속(첫 메시지에서 대화를 지연 생성).
  const persistMessage = useCallback(
    async (msg: MessageInput) => {
      let id = convId.current;
      if (!id) {
        id = await createConversation({ src_lang: src, tgt_lang: tgt, witness_lang: witnessLang });
        convId.current = id;
        setActiveConvId(id);
      }
      await addMessage(id, msg);
      await refreshList();
    },
    [src, tgt, witnessLang, refreshList],
  );

  // 실제 발사(single-flight): 항상 in-flight 1개만. refs만 쓰므로 stable.
  const sendDraft = useCallback((value: string) => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) return;
    revision.current += 1;
    sentRev.current = revision.current;
    inflight.current = true;
    setDraftPending(true); // 기존 초벌은 유지한 채 "계산 중" 표시만
    ws.current.send(
      JSON.stringify({ revision_id: revision.current, partial_text: value, is_final: false }),
    );
  }, []);
  sendDraftRef.current = sendDraft;

  // 초벌 스케줄은 입력 핸들러에서 트리거(useEffect[text] 의존 X). 한글 IME: 조합 확정 시
  // 같은 값이면 effect가 안 도는 문제 회피용으로 직접 스케줄한다. 적응형 디바운스 후,
  // 이미 요청이 떠 있으면 보내지 않고 **최신값만** 대기시켜(single-flight) 큐잉/우다다 방지.
  const scheduleDraft = useCallback(
    (value: string) => {
      window.clearTimeout(debounce.current);
      if (!value.trim() || !ws.current || ws.current.readyState !== WebSocket.OPEN) {
        // revision 무효화 → 아직 오는 중인 초벌 응답을 stale로 드롭(빈 입력에 옛 초벌 방지).
        revision.current += 1;
        latestRev.current = revision.current;
        pendingValue.current = null;
        inflight.current = false;
        setDraftPending(false);
        setDraft({});
        return;
      }
      debounce.current = window.setTimeout(() => {
        if (inflight.current) pendingValue.current = value; // 대기(최신값만 유지)
        else sendDraft(value);
      }, nextDebounce(lastDraftMs.current));
    },
    [sendDraft],
  );

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
    // 전송 시점의 초벌(빠른) 번역·검증(확인용 언어)과 그 소요 시간을 함께 캡처한다.
    const draftText = draft[tgt];
    const witness = tgt === witnessLang ? undefined : draft[witnessLang];
    const draftMs = lastDraftMs.current;
    setSending(true);
    setText("");
    setDraft({});
    // single-flight 상태 초기화(대기 중이던 초벌 요청 버림 + in-flight 응답 stale 처리).
    window.clearTimeout(debounce.current);
    revision.current += 1;
    latestRev.current = revision.current;
    pendingValue.current = null;
    inflight.current = false;
    setDraftPending(false);
    // Pombal 컨텍스트: 직전 턴들의 원문(양측, 순서대로).
    const context = messages.map((m) => m.source);
    try {
      let translation = "";
      let finalMs: number | undefined;
      let done_: import("./api").TurnDone | undefined;
      await streamTurn(sessionId, source, {
        onDone: (done) => {
          done_ = done;
          translation = done.translation;
          finalMs = done.latency.total_ms ?? done.latency.ttft_ms ?? undefined;
          setMessages((m) => [
            ...m,
            {
              id: `m-${done.turn_id}-${Date.now()}`, side: "mine", source, translation,
              draft: draftText, witness, draftMs, finalMs, degraded: done.degraded,
              roundTrip: done.round_trip ?? undefined,
              confidence: done.confidence, alignment: done.alignment,
              roundTripMs: done.round_trip_ms ?? undefined,
            },
          ]);
        },
      }, context);
      if (translation) {
        await persistMessage({
          side: "mine", source, translation,
          draft: draftText ?? null, witness: witness ?? null,
          round_trip: done_?.round_trip ?? null,
          confidence: done_?.confidence ?? null, alignment: done_?.alignment ?? null,
          draft_ms: draftMs ?? null, final_ms: finalMs ?? null,
          round_trip_ms: done_?.round_trip_ms ?? null,
        });
      }
    } finally {
      setSending(false);
    }
  }, [text, sessionId, sending, draft, tgt, witnessLang, messages, persistMessage]);

  const sendFromCustomer = useCallback(async () => {
    const source = custText.trim();
    if (!source || !revSessionId || custSending) return;
    setCustSending(true);
    setCustText("");
    const context = messages.map((m) => m.source); // Pombal 컨텍스트(양측 원문)
    try {
      let translation = "";
      let finalMs: number | undefined;
      let done_: import("./api").TurnDone | undefined;
      await streamTurn(revSessionId, source, {
        onDone: (done) => {
          done_ = done;
          translation = done.translation; // 운영자 언어(src)로 번역
          finalMs = done.latency.total_ms ?? done.latency.ttft_ms ?? undefined;
          setMessages((m) => [
            ...m,
            {
              id: `c-${done.turn_id}-${Date.now()}`,
              side: "theirs",
              source, // 고객이 입력한 원문(tgt 언어)
              translation,
              finalMs,
              degraded: done.degraded,
              roundTrip: done.round_trip ?? undefined,
              confidence: done.confidence, alignment: done.alignment,
              roundTripMs: done.round_trip_ms ?? undefined,
            },
          ]);
        },
      }, context);
      if (translation) {
        await persistMessage({
          side: "theirs", source, translation,
          draft: null, witness: null,
          round_trip: done_?.round_trip ?? null,
          confidence: done_?.confidence ?? null, alignment: done_?.alignment ?? null,
          draft_ms: null, final_ms: finalMs ?? null,
          round_trip_ms: done_?.round_trip_ms ?? null,
        });
      }
    } finally {
      setCustSending(false);
    }
  }, [custText, revSessionId, custSending, messages, persistMessage]);

  const resetConversation = useCallback(() => {
    convId.current = null;
    setActiveConvId(null);
    setMessages([]);
    setText("");
    setCustText("");
    setDraft({});
  }, []);

  const newConversation = useCallback(() => {
    resetConversation();
  }, [resetConversation]);

  // 저장된 대화 열기 — 언어쌍 복원(세션 재생성 트리거) + 메시지 복원.
  const loadConversation = useCallback(
    async (id: string) => {
      const detail = await getConversation(id);
      convId.current = id;
      setActiveConvId(id);
      setText("");
      setCustText("");
      setDraft({});
      setMessages(
        detail.messages.map((m, i) => ({
          id: `s-${id}-${m.seq}-${i}`,
          side: m.side,
          source: m.source,
          translation: m.translation,
          draft: m.draft ?? undefined,
          witness: m.witness ?? undefined,
          roundTrip: m.round_trip ?? undefined,
          confidence: m.confidence ?? undefined,
          alignment: m.alignment ?? undefined,
          draftMs: m.draft_ms ?? undefined,
          finalMs: m.final_ms ?? undefined,
          roundTripMs: m.round_trip_ms ?? undefined,
        })),
      );
      setSrc(detail.src_lang);
      setTgt(detail.tgt_lang);
    },
    [],
  );

  const removeConversation = useCallback(
    async (id: string) => {
      await deleteConversation(id);
      if (convId.current === id) resetConversation();
      await refreshList();
    },
    [resetConversation, refreshList],
  );

  const swap = useCallback(() => {
    resetConversation();
    setSrc(tgt);
    setTgt(src);
  }, [src, tgt, resetConversation]);

  const nameOf = useCallback(
    (code: string) => catalog?.languages.find((l) => l.code === code)?.name_native ?? code,
    [catalog],
  );

  return {
    catalog, sessionId, revSessionId, src, tgt, setTgt, swap, witnessLang, nameOf,
    messages, text, onInput, draft, draftPending, latency, sending, send,
    custText, setCustText, custSending, sendFromCustomer,
    conversations, activeConvId, loadConversation, newConversation, removeConversation,
    onCompositionStart, onCompositionEnd,
  };
}
