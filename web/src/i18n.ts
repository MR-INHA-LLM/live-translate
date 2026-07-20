// 콘솔 UI 언어(KO/EN). 번역 "방향"(한국어⇄외국어)과는 별개 — 이건 인터페이스 언어다.
export type Lang = "ko" | "en";

export interface T {
  appTitle: string;
  sessions: string;
  newConv: string;
  noSessions: string;
  ctxMt: string;
  feedEmpty: string;
  draft: string;
  final: string;
  backtr: string;
  witness: string;
  send: string;
  custView: string;
  convo: string;
  retranslating: string;
  pending: string;
  calc: string;
  delTitle: string;
  swapTitle: string;
  apiDocs: string;
  inputPh: (l: string) => string;
  count: (n: number) => string;
}

export const STRINGS: Record<Lang, T> = {
  ko: {
    appTitle: "실시간 번역",
    sessions: "번역 세션",
    newConv: "+ 새 대화",
    noSessions: "저장된 대화가 없습니다.\n메시지를 보내면 여기에 쌓입니다.",
    ctxMt: "문맥 기반 번역",
    feedEmpty: "아래에 입력하면 번역이 시작됩니다.",
    draft: "초벌",
    final: "최종",
    backtr: "역번역",
    witness: "확인",
    send: "전송",
    custView: "고객이 보는 화면",
    convo: "번역 대화",
    retranslating: "언어 변경 · 재번역 중…",
    pending: "번역 중…",
    calc: "계산 중",
    delTitle: "세션 삭제",
    swapTitle: "방향 스왑",
    apiDocs: "API Docs",
    inputPh: (l: string) => `${l}로 입력…`,
    count: (n: number) => `${n}개`,
  },
  en: {
    appTitle: "Live Translate",
    sessions: "Sessions",
    newConv: "+ New",
    noSessions: "No saved conversations yet.\nThey pile up here as you chat.",
    ctxMt: "Context-aware MT",
    feedEmpty: "Start typing below to translate.",
    draft: "Draft",
    final: "Final",
    backtr: "Back-trans",
    witness: "Witness",
    send: "Send",
    custView: "Customer view",
    convo: "Translation",
    retranslating: "Changing language · retranslating…",
    pending: "Translating…",
    calc: "computing",
    delTitle: "Delete session",
    swapTitle: "Swap direction",
    apiDocs: "API Docs",
    inputPh: (l: string) => `Type in ${l}…`,
    count: (n: number) => `${n} msgs`,
  },
};
