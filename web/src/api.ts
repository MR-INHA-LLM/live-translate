// 게이트웨이 API 클라이언트 — REST · WS(초벌) · SSE(최종).
// 타입은 백엔드 app/schemas 와 1:1.

// 기본은 same-origin("") — nginx가 FE 정적 서빙 + /api 프록시(배포), dev는 vite 프록시.
// 별도 게이트웨이 주소를 쓰려면 VITE_API_BASE=http://host:8000.
export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export interface LanguageInfo {
  code: string;
  name_en: string;
  name_native: string;
}
export interface LanguagePair {
  src: string;
  tgt: string;
  comet: number | null;
}
export interface LanguageCatalog {
  languages: LanguageInfo[];
  validated_pairs: LanguagePair[];
  default_witness: string;
}
export interface SessionConfig {
  src_lang: string;
  tgt_lang: string;
  witness_langs: string[];
}
export interface DraftResponse {
  revision_id: number;
  renderings: Record<string, string>;
  latency: { ttft_ms: number | null; total_ms: number | null };
}
export interface ConfidenceSpan {
  tgt_start: number;
  tgt_end: number;
  prob: number;
  low: boolean;
}
export interface AlignmentSpan {
  src_start: number;
  src_end: number;
  tgt_start: number;
  tgt_end: number;
}
export interface TurnDone {
  turn_id: number;
  translation: string;
  degraded: boolean;
  latency: { ttft_ms: number | null; total_ms: number | null };
  confidence: ConfidenceSpan[];
  alignment: AlignmentSpan[];
  round_trip: string | null;
  round_trip_ms: number | null;
}

// --- 대화 저장소 (DB 영구 저장 이력) ---
export interface ConversationSummary {
  conversation_id: string;
  src_lang: string;
  tgt_lang: string;
  witness_lang: string | null;
  title: string | null;
  message_count: number;
  updated_at: string;
}
export interface StoredMessage {
  seq: number;
  side: "mine" | "theirs";
  source: string;
  translation: string;
  draft: string | null;
  witness: string | null;
  round_trip: string | null;
  confidence: ConfidenceSpan[] | null;
  alignment: AlignmentSpan[] | null;
  draft_ms: number | null;
  final_ms: number | null;
  round_trip_ms: number | null;
}
export interface MessageInput {
  side: "mine" | "theirs";
  source: string;
  translation: string;
  draft: string | null;
  witness: string | null;
  round_trip: string | null;
  confidence: ConfidenceSpan[] | null;
  alignment: AlignmentSpan[] | null;
  draft_ms: number | null;
  final_ms: number | null;
  round_trip_ms: number | null;
}
export interface ConversationDetail {
  conversation_id: string;
  src_lang: string;
  tgt_lang: string;
  witness_lang: string | null;
  messages: StoredMessage[];
}

export async function createConversation(body: {
  src_lang: string;
  tgt_lang: string;
  witness_lang: string | null;
}): Promise<string> {
  const r = await fetch(`${API_BASE}/api/v1/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`create conversation ${r.status}`);
  return (await r.json()).conversation_id as string;
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const r = await fetch(`${API_BASE}/api/v1/conversations`);
  if (!r.ok) throw new Error(`list conversations ${r.status}`);
  return r.json();
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const r = await fetch(`${API_BASE}/api/v1/conversations/${id}`);
  if (!r.ok) throw new Error(`get conversation ${r.status}`);
  return r.json();
}

export async function addMessage(id: string, body: MessageInput): Promise<void> {
  const r = await fetch(`${API_BASE}/api/v1/conversations/${id}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`add message ${r.status}`);
}

export async function deleteConversation(id: string): Promise<void> {
  const r = await fetch(`${API_BASE}/api/v1/conversations/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`delete conversation ${r.status}`);
}

export async function getLanguages(): Promise<LanguageCatalog> {
  const r = await fetch(`${API_BASE}/api/v1/languages`);
  if (!r.ok) throw new Error(`languages ${r.status}`);
  return r.json();
}

export async function createSession(config: SessionConfig): Promise<string> {
  const r = await fetch(`${API_BASE}/api/v1/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!r.ok) throw new Error(`create session ${r.status}`);
  return (await r.json()).session_id as string;
}

export function openDraftSocket(sessionId: string): WebSocket {
  const httpBase = API_BASE || `${location.protocol}//${location.host}`;
  const url = httpBase.replace(/^http/, "ws") + `/api/v1/sessions/${sessionId}/stream`;
  return new WebSocket(url);
}

// 최종 번역(SSE). onToken/onDone 콜백. AbortController로 취소 가능.
export async function streamTurn(
  sessionId: string,
  text: string,
  handlers: { onToken?: (d: string) => void; onDone?: (d: TurnDone) => void },
  context: string[] = [], // 직전 턴 원문열(Pombal 컨텍스트)
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}/turns`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, context }),
    signal,
  });
  if (!r.ok || !r.body) throw new Error(`turn ${r.status}`);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let event = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const chunk of parts) {
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) {
          const data = JSON.parse(line.slice(6));
          if (event === "token") handlers.onToken?.(data.delta);
          else if (event === "done") handlers.onDone?.(data);
        }
      }
    }
  }
}
