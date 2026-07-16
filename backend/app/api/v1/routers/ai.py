from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, RedisDep, SettingsDep
from app.api.v1.schemas.ai import (
    ChatHistoryMessage,
    ChatHistoryRead,
    ChatRequest,
    ChatResponse,
    DecisionLogEntry,
    LoanAnalysisRequest,
    LoanAnalysisResponse,
)
from app.api.v1.schemas.common import PROBLEM_RESPONSES
from app.domain.ai.service import ChatService, LoanAnalyzer

router = APIRouter(tags=["ai"], responses=PROBLEM_RESPONSES)


@router.post("/chat", response_model=ChatResponse, summary="Ask an AI council agent")
async def chat(
    payload: ChatRequest,
    user: CurrentUser,
    db: DbSession,
    redis: RedisDep,
    settings: SettingsDep,
) -> ChatResponse:
    result = await ChatService(db, redis, settings).send(
        user.id,
        agent=payload.agent,
        message=payload.message,
        conversation_id=payload.conversation_id,
        extra_context=payload.context,
    )
    return ChatResponse(**result)


@router.get(
    "/chat/{agent}/history",
    response_model=ChatHistoryRead,
    summary="Get council conversation history",
)
async def chat_history(
    agent: str,
    user: CurrentUser,
    db: DbSession,
    redis: RedisDep,
    settings: SettingsDep,
    conversation_id: str = "default",
) -> ChatHistoryRead:
    messages = await ChatService(db, redis, settings).history(user.id, agent, conversation_id)
    return ChatHistoryRead(
        agent=agent,
        conversation_id=conversation_id,
        messages=[ChatHistoryMessage(**m) for m in messages],
    )


@router.get(
    "/chat/decisions",
    response_model=list[DecisionLogEntry],
    summary="Recent council decision log (newest first)",
)
async def chat_decisions(
    user: CurrentUser,
    db: DbSession,
    redis: RedisDep,
    settings: SettingsDep,
) -> list[DecisionLogEntry]:
    entries = await ChatService(db, redis, settings).decisions(user.id)
    return [DecisionLogEntry(**entry) for entry in entries]


@router.post(
    "/loan-analysis/analyze",
    response_model=LoanAnalysisResponse,
    summary="Analyze a loan agreement text for risk clauses",
)
async def analyze_loan(
    payload: LoanAnalysisRequest,
    user: CurrentUser,
    settings: SettingsDep,
) -> LoanAnalysisResponse:
    result = await LoanAnalyzer(settings).analyze(payload.text)
    return LoanAnalysisResponse(**result)
