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
    modality: Literal[
        "spoken_spontaneous", "spoken_scripted", "spoken_interview",
        "written_casual", "written_deliberate", "written_structured",
        "highlighted", "consumed", "received", "decided", "acted",
    ]
    authority: Literal["own_voice", "endorsed", "referenced", "received"] | None = None
    text: str
    content_type: Literal[
        "idea", "belief", "decision", "action", "framework", "story",
        "quote", "question", "observation", "reaction", "instruction",
        "hook_pattern", "narrative_pattern", "key_message",
    ] = "idea"
    reasoning: str | None = None
    confidence: Literal["strong_opinion", "exploring", "tentative", "quoting_others"] | None = None
    emotion: Literal[
        "focused", "excited", "frustrated", "reflective", "neutral",
        "stressed", "playful", "passionate", "doubtful",
    ] | None = None
    date: str
    context: Literal[
        "solo_thinking", "team_meeting", "one_on_one", "phone_call",
        "brainstorm", "client_meeting", "presentation", "casual_chat",
        "commute", "short_video", "social_post", "interview_guest",
        "host_interview", "line_private", "line_group", "email",
        "book_reading", "article_reading", "podcast_listening",
        "course_learning", "other",
    ] = "other"
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


class ContextRequest(BaseModel):
    owner_id: str
    question: str
    caller_id: str | None = None
    conviction_limit: int = 7
    trace_limit: int = 8


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
