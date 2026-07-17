"""대화 저장소 라우터 — `/api/v1/conversations`.

UI가 보여준 대화 이력의 저장·목록·복원. 번역 스트리밍은 sessions/turns가
담당하고, 여기서는 확정된 메시지를 영속·조회한다(decisions.md D14).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_conversation_service
from app.domain import StoredMessage
from app.schemas.conversation import (
    ConversationCreate,
    ConversationCreated,
    ConversationDetailRead,
    ConversationSummaryRead,
    MessageCreate,
    MessageRead,
)
from app.services.conversation import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _to_message_read(m: StoredMessage) -> MessageRead:
    return MessageRead(
        seq=m.seq, side=m.side, source=m.source,  # type: ignore[arg-type]
        translation=m.translation, witness=m.witness,
    )


@router.post("", response_model=ConversationCreated, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    svc: ConversationService = Depends(get_conversation_service),
) -> ConversationCreated:
    """빈 대화를 생성한다."""
    conv_id = await svc.create(body.src_lang, body.tgt_lang, body.witness_lang)
    return ConversationCreated(conversation_id=conv_id)


@router.get("", response_model=list[ConversationSummaryRead])
async def list_conversations(
    svc: ConversationService = Depends(get_conversation_service),
) -> list[ConversationSummaryRead]:
    """최근 활동 순 대화 목록."""
    summaries = await svc.list()
    return [
        ConversationSummaryRead(
            conversation_id=s.id, src_lang=s.src_lang, tgt_lang=s.tgt_lang,
            witness_lang=s.witness_lang, title=s.title,
            message_count=s.message_count, updated_at=s.updated_at,
        )
        for s in summaries
    ]


@router.get("/{conversation_id}", response_model=ConversationDetailRead)
async def get_conversation(
    conversation_id: str,
    svc: ConversationService = Depends(get_conversation_service),
) -> ConversationDetailRead:
    """대화 상세(메시지 포함)를 반환한다."""
    detail = await svc.get(conversation_id)  # 없으면 ConversationNotFoundError → 404
    return ConversationDetailRead(
        conversation_id=detail.id, src_lang=detail.src_lang, tgt_lang=detail.tgt_lang,
        witness_lang=detail.witness_lang,
        messages=[_to_message_read(m) for m in detail.messages],
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    svc: ConversationService = Depends(get_conversation_service),
) -> None:
    """대화를 삭제한다(메시지 포함)."""
    await svc.delete(conversation_id)  # 없으면 ConversationNotFoundError → 404


@router.post("/{conversation_id}/messages", response_model=MessageRead, status_code=201)
async def add_message(
    conversation_id: str,
    body: MessageCreate,
    svc: ConversationService = Depends(get_conversation_service),
) -> MessageRead:
    """대화에 확정 메시지를 추가한다."""
    stored = await svc.add_message(
        conversation_id,
        StoredMessage(side=body.side, source=body.source,
                      translation=body.translation, witness=body.witness),
    )
    return _to_message_read(stored)
