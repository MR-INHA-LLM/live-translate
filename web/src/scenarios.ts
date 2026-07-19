// 시연용 대화 시드 — 발표자가 "무엇을 칠지" 막힐 때 쓰는 편집 가능한 예시.
// 시드는 '입력 원문'일 뿐이고 번역은 항상 실시간으로 수행된다(미리 번역된 게 아님).
// 자유 칩 풀: 순서 강제 없이 아무거나 골라 입력창을 채우고(자동 전송 X) 수정해 전송.

export interface Scenario {
  id: string;
  title: string;
  mine: string[]; // 운영자(한국어) 시드
  theirs: string[]; // 고객(영어) 시드
}

export const SCENARIOS: Scenario[] = [
  {
    id: "meeting",
    title: "회의 일정 변경",
    mine: [
      "네, 내일 회의를 옮겨 드릴까요?",
      "금요일 오후로 잡아 드릴게요.",
      "확정되면 초대장을 다시 보내 드리겠습니다.",
    ],
    theirs: [
      "Hi, can we move tomorrow's meeting?",
      "Friday afternoon works for me.",
      "Great, thanks for arranging it.",
    ],
  },
  {
    id: "refund",
    title: "환불 문의",
    mine: [
      "주문번호 확인해 드리겠습니다.",
      "불편을 드려 죄송합니다. 환불 도와드릴게요.",
      "환불은 영업일 기준 3~5일 소요됩니다.",
    ],
    theirs: [
      "I'd like a refund for order A-2231.",
      "The item arrived damaged.",
      "How long will the refund take?",
    ],
  },
  {
    id: "shipping",
    title: "배송 지연",
    mine: [
      "배송 상태를 조회해 보겠습니다.",
      "물류 지연이 있었던 것 같습니다.",
      "오늘 중으로 재발송 처리해 드리겠습니다.",
    ],
    theirs: [
      "My package hasn't arrived yet.",
      "It's been over a week now.",
      "Can you check the tracking for me?",
    ],
  },
];
