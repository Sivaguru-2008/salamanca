from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# --- Council chat ---
class ChatRequest(BaseModel):
    agent: str = Field(default="advisor", max_length=50)
    message: str = Field(..., min_length=1, max_length=8000)
    conversation_id: str = Field(default="default", max_length=100)
    context: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    id: str
    agent: str
    conversation_id: str
    text: str
    reasoning_steps: list[str]
    provider: str
    model: str
    latency_ms: int


class ChatHistoryMessage(BaseModel):
    role: str
    content: str


class ChatHistoryRead(BaseModel):
    agent: str
    conversation_id: str
    messages: list[ChatHistoryMessage]


class DecisionLogEntry(BaseModel):
    id: str
    agent: str
    agent_name: str
    action: str
    question: str
    answer_preview: str
    provider: str
    model: str
    latency_ms: int
    timestamp: str


# --- Loan analysis ---
class LoanAnalysisRequest(BaseModel):
    text: str = Field(..., min_length=20, max_length=100_000)


class LoanFlag(BaseModel):
    level: str
    title: str
    desc: str


class LoanAnalysisResponse(BaseModel):
    apr: float
    term: str
    cost: str
    flags: list[LoanFlag]
    recommendation: str
    engine: str


# --- Document retrieval ---
class ChunkSearchResult(BaseModel):
    index: int
    text: str
    score: float


class DocumentSearchResponse(BaseModel):
    document_id: str
    document_name: str
    query: str
    results: list[ChunkSearchResult]
