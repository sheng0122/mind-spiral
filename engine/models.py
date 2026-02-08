"""五層思維模型 — Pydantic v2 Models（對應 schemas/*.json）"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


# ─── Layer 1: Signal ───

class SignalContent(BaseModel):
    text: str = Field(max_length=300)
    type: Literal[
        "idea", "belief", "decision", "action", "framework", "story",
        "quote", "question", "observation", "reaction", "instruction",
        "hook_pattern", "narrative_pattern", "key_message",
    ]
    reasoning: str | None = Field(None, max_length=200)
    confidence: Literal["strong_opinion", "exploring", "tentative", "quoting_others"] | None = None
    emotion: Literal[
        "focused", "excited", "frustrated", "reflective", "neutral",
        "stressed", "playful", "passionate", "doubtful",
    ] | None = None


class SignalSource(BaseModel):
    date: str  # YYYY-MM-DD
    context: Literal[
        "solo_thinking", "team_meeting", "one_on_one", "phone_call",
        "brainstorm", "client_meeting", "presentation", "casual_chat",
        "commute", "short_video", "social_post", "interview_guest",
        "host_interview", "line_private", "line_group", "email",
        "book_reading", "article_reading", "podcast_listening",
        "course_learning", "other",
    ]
    participants: list[str] | None = None
    timestamp: str | None = None
    source_file: str | None = None
    book_title: str | None = None
    book_author: str | None = None
    chapter: str | None = None


class SignalAudience(BaseModel):
    directed_to: list[str] | None = None
    visibility: Literal[
        "public", "team_internal", "management_only", "one_on_one_private", "self_only",
    ] | None = None
    relationship_context: Literal[
        "boss_to_team", "peer_to_peer", "to_client", "to_investor",
        "to_partner", "self_reflection", "public_facing", "content_creator",
        "teacher_to_student",
    ] | None = None


class SignalLifecycle(BaseModel):
    active: bool
    created_at: str | None = None
    deactivated_at: str | None = None
    deactivated_reason: str | None = None
    superseded_by: str | None = None


class Signal(BaseModel):
    owner_id: str
    signal_id: str
    direction: Literal["input", "output"]
    modality: Literal[
        "spoken_spontaneous", "spoken_scripted", "spoken_interview",
        "written_casual", "written_deliberate", "written_structured",
        "highlighted", "consumed", "received", "decided", "acted",
    ]
    authority: Literal["own_voice", "endorsed", "referenced", "received"] | None = None
    content: SignalContent
    source: SignalSource
    audience: SignalAudience | None = None
    topics: list[str] | None = None
    lifecycle: SignalLifecycle


# ─── Layer 2: Conviction ───

class StatementVariant(BaseModel):
    text: str = Field(max_length=200)
    context: str = Field(max_length=50)
    signal_id: str | None = None


class ConvictionStrength(BaseModel):
    score: float = Field(ge=0, le=1)
    level: Literal["emerging", "developing", "established", "core"]
    trend: Literal["strengthening", "stable", "weakening", "fluctuating"] | None = None
    last_computed: str | None = None


class InputOutputConvergence(BaseModel):
    input_signal: str
    output_signal: str
    similarity: float | None = Field(None, ge=0, le=1)
    detected_at: str


class TemporalPersistence(BaseModel):
    signal_ids: list[str]
    time_span_days: int
    first_date: str | None = None
    last_date: str | None = None


class CrossContextConsistency(BaseModel):
    signal_ids: list[str]
    contexts: list[str]


class SpontaneousMention(BaseModel):
    signal_id: str
    was_prompted: bool | None = None


class ActionAlignment(BaseModel):
    statement_signal: str
    action_signal: str
    aligned: bool | None = None


class ResonanceEvidence(BaseModel):
    input_output_convergence: list[InputOutputConvergence] | None = None
    temporal_persistence: list[TemporalPersistence] | None = None
    cross_context_consistency: list[CrossContextConsistency] | None = None
    spontaneous_mentions: list[SpontaneousMention] | None = None
    action_alignment: list[ActionAlignment] | None = None


class ConvictionTension(BaseModel):
    opposing_conviction: str
    relationship: Literal["contradiction", "creative_tension", "context_dependent", "evolving"]
    note: str | None = Field(None, max_length=100)


class ConvictionLifecycle(BaseModel):
    status: Literal["active", "weakening", "superseded", "dormant"]
    first_detected: str
    last_reinforced: str | None = None
    superseded_by: str | None = None
    evolution_chain: list[str] | None = None


class Conviction(BaseModel):
    owner_id: str
    conviction_id: str
    statement: str = Field(max_length=200)
    statement_variants: list[StatementVariant] | None = None
    strength: ConvictionStrength
    domains: list[str]
    resonance_evidence: ResonanceEvidence
    tensions: list[ConvictionTension] | None = None
    lifecycle: ConvictionLifecycle


# ─── Layer 3: Reasoning Trace ───

class TraceTrigger(BaseModel):
    situation: str = Field(max_length=200)
    stimulus_type: Literal[
        "question_received", "problem_encountered", "decision_required",
        "opinion_challenged", "opportunity_spotted", "conflict_to_resolve",
        "teaching_moment", "self_reflection",
    ]
    from_signal: str | None = None


class ActivatedConviction(BaseModel):
    conviction_id: str
    role: Literal["premise", "framework", "evidence", "constraint", "value_anchor", "counterpoint"]
    activation_note: str | None = Field(None, max_length=100)


class ReasoningStep(BaseModel):
    action: Literal[
        "empathize", "reframe", "analyze", "compare", "recall_experience",
        "apply_framework", "challenge_assumption", "weigh_tradeoff",
        "synthesize", "decide",
    ]
    description: str = Field(max_length=150)
    uses_conviction: str | None = None


class ReasoningPath(BaseModel):
    steps: list[ReasoningStep]
    style: Literal[
        "analytical", "intuitive", "storytelling", "socratic",
        "first_principles", "pattern_matching", "empathy_driven",
    ]


class TraceConclusion(BaseModel):
    decision: str = Field(max_length=200)
    confidence: Literal["high", "medium", "low", "uncertain"]
    alternative_considered: str | None = Field(None, max_length=200)
    output_signal: str | None = None


class ConvictionImpact(BaseModel):
    conviction_id: str
    effect: Literal["reinforced", "weakened", "unchanged"]


class TraceOutcome(BaseModel):
    result: Literal["positive", "negative", "mixed", "unknown", "pending"] | None = None
    feedback_note: str | None = Field(None, max_length=200)
    conviction_impact: list[ConvictionImpact] | None = None
    recorded_at: str | None = None


class TraceSource(BaseModel):
    date: str
    context: str | None = None
    source_file: str | None = None
    participants: list[str] | None = None


class ReasoningTrace(BaseModel):
    owner_id: str
    trace_id: str
    trigger: TraceTrigger
    activated_convictions: list[ActivatedConviction]
    reasoning_path: ReasoningPath
    conclusion: TraceConclusion
    outcome: TraceOutcome | None = None
    context_frame_id: str | None = None
    source: TraceSource


# ─── Layer 4: Context Frame ───

class TriggerPattern(BaseModel):
    pattern: str = Field(max_length=100)
    keywords: list[str] | None = None
    audience_type: list[Literal[
        "client", "team", "partner", "investor", "public", "self", "student", "peer",
    ]] | None = None


class ConvictionActivation(BaseModel):
    conviction_id: str
    activation_weight: float = Field(ge=0, le=1)
    typical_role: Literal[
        "premise", "framework", "evidence", "constraint", "value_anchor", "counterpoint",
    ] | None = None


class SuppressedConviction(BaseModel):
    conviction_id: str
    reason: str = Field(max_length=100)


class ConvictionProfile(BaseModel):
    primary_convictions: list[ConvictionActivation]
    suppressed_convictions: list[SuppressedConviction] | None = None


class FrameReasoningPatterns(BaseModel):
    preferred_style: Literal[
        "analytical", "intuitive", "storytelling", "socratic",
        "first_principles", "pattern_matching", "empathy_driven",
    ] | None = None
    typical_steps: list[str] | None = None
    historical_traces: list[str] | None = None


class FrameVoice(BaseModel):
    tone: Literal[
        "professional", "warm", "direct", "patient",
        "passionate", "casual", "authoritative",
    ] | None = None
    typical_phrases: list[str] | None = None
    avoids: list[str] | None = None


class FrameEffectiveness(BaseModel):
    success_rate: float | None = Field(None, ge=0, le=1)
    total_traces: int | None = None
    positive_traces: int | None = None
    negative_traces: int | None = None
    learning_note: str | None = Field(None, max_length=200)


class FrameLifecycle(BaseModel):
    status: Literal["active", "evolving", "deprecated"]
    first_observed: str | None = None
    last_activated: str | None = None
    evolved_from: str | None = None


class ContextFrame(BaseModel):
    owner_id: str
    frame_id: str
    name: str = Field(max_length=50)
    description: str = Field(max_length=300)
    trigger_patterns: list[TriggerPattern]
    conviction_profile: ConvictionProfile
    reasoning_patterns: FrameReasoningPatterns
    voice: FrameVoice | None = None
    effectiveness: FrameEffectiveness | None = None
    lifecycle: FrameLifecycle | None = None


# ─── Layer 5: Identity Core ───

class IdentityUniversality(BaseModel):
    active_in_frames: list[str]
    total_active_frames: int
    coverage: float = Field(ge=0, le=1)


class IdentityExpression(BaseModel):
    frame_id: str
    how_it_manifests: str = Field(max_length=200)


class KeyReinforcingEvent(BaseModel):
    signal_id: str | None = None
    event_description: str | None = Field(None, max_length=100)


class IdentityOriginStory(BaseModel):
    earliest_signal: str | None = None
    formation_narrative: str | None = Field(None, max_length=300)
    key_reinforcing_events: list[KeyReinforcingEvent] | None = None


class IdentityStability(BaseModel):
    held_since: str
    consistency_score: float = Field(ge=0, le=1)
    last_challenged: str | None = None
    survived_challenges: int | None = None


class IdentityCore(BaseModel):
    owner_id: str
    identity_id: str
    core_belief: str = Field(max_length=150)
    conviction_id: str
    universality: IdentityUniversality
    expressions: list[IdentityExpression]
    origin_story: IdentityOriginStory | None = None
    non_negotiable: bool | None = None
    stability: IdentityStability | None = None
