"""API Request/Response Pydantic Models"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── Request Models ───


class AskRequest(BaseModel):
    owner_id: str
    text: str
    caller_id: str | None = None


class QueryRequest(BaseModel):
    owner_id: str
    question: str
    caller_id: str | None = None


class GenerateRequest(BaseModel):
    owner_id: str
    text: str
    output_type: Literal["article", "post", "decision", "script"] = "article"
    caller_id: str | None = None


class SignalInput(BaseModel):
    """簡化的 signal 輸入格式，對應 Signal model 的必要欄位。"""
    signal_id: str
    direction: Literal["input", "output"]
    modality: str
    authority: str | None = None
    text: str
    content_type: str = "idea"
    reasoning: str | None = None
    confidence: str | None = None
    emotion: str | None = None
    date: str
    context: str = "other"
    participants: list[str] | None = None
    source_file: str | None = None
    topics: list[str] | None = None


class IngestRequest(BaseModel):
    owner_id: str
    signals: list[SignalInput]


class RecallRequest(BaseModel):
    owner_id: str
    text: str
    context: str | None = None
    direction: Literal["input", "output"] | None = None
    date_from: str | None = None
    date_to: str | None = None
    limit: int = 20


class ExploreRequest(BaseModel):
    owner_id: str
    topic: str
    depth: Literal["lite", "full"] = "full"


class EvolutionRequest(BaseModel):
    owner_id: str
    topic: str


class ConnectionsRequest(BaseModel):
    owner_id: str
    topic_a: str
    topic_b: str


class SimulateRequest(BaseModel):
    owner_id: str
    scenario: str
    context: str | None = None


# ─── Response Models ───


class APIResponse(BaseModel):
    status: Literal["ok", "error"] = "ok"
    data: Any = None
    meta: dict[str, Any] | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    error: ErrorDetail
