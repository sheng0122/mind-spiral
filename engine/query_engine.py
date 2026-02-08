"""Query Engine — 五層感知 RAG

流程：
1. Frame Matching — 反射匹配（關鍵字命中）或 embedding 匹配
2. Conviction Activation — 根據 frame 激活信念組合
3. Trace Retrieval — 找類似情境的推理路徑
4. Identity Check — 確認不違反身份核心
5. Response Generation — 用該 frame 的語氣和推理風格生成回應
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np

from engine.config import get_owner_dir
from engine.conviction_detector import _load_convictions
from engine.frame_clusterer import _load_frames
from engine.identity_scanner import _load_identity
from engine.llm import call_llm
from engine.models import (
    ContextFrame,
    Conviction,
    IdentityCore,
    ReasoningTrace,
)
from engine.signal_store import SignalStore
from engine.trace_extractor import _load_traces


@dataclass
class QueryContext:
    """查詢過程中累積的上下文。"""
    question: str
    caller: str | None = None
    matched_frame: ContextFrame | None = None
    match_method: str = ""  # "reflex" or "embedding"
    activated_convictions: list[Conviction] = field(default_factory=list)
    relevant_traces: list[ReasoningTrace] = field(default_factory=list)
    identity_constraints: list[IdentityCore] = field(default_factory=list)
    response: str = ""


def _reflex_match(question: str, frames: list[ContextFrame]) -> ContextFrame | None:
    """反射匹配：關鍵字直接命中 trigger_patterns → 跳過 embedding。"""
    question_lower = question.lower()
    best_frame: ContextFrame | None = None
    best_hits = 0

    for frame in frames:
        hits = 0
        for tp in frame.trigger_patterns:
            if tp.keywords:
                for kw in tp.keywords:
                    if kw.lower() in question_lower:
                        hits += 1
        if hits > best_hits:
            best_hits = hits
            best_frame = frame

    return best_frame if best_hits >= 1 else None


def _embedding_match(
    question: str,
    frames: list[ContextFrame],
    store: SignalStore,
) -> ContextFrame | None:
    """Embedding 匹配：計算問題與每個 frame 描述的 cosine similarity。"""
    if not frames:
        return None

    q_emb = np.array(store.compute_embedding(question))

    best_frame = None
    best_sim = -1.0

    for frame in frames:
        # 用 frame 的 name + description + trigger patterns 組成文本
        frame_text = f"{frame.name} {frame.description}"
        for tp in frame.trigger_patterns:
            frame_text += f" {tp.pattern}"
        f_emb = np.array(store.compute_embedding(frame_text))

        sim = float(np.dot(q_emb, f_emb) / (np.linalg.norm(q_emb) * np.linalg.norm(f_emb) + 1e-8))
        if sim > best_sim:
            best_sim = sim
            best_frame = frame

    return best_frame if best_sim > 0.3 else None


def _find_relevant_traces(
    question: str,
    frame: ContextFrame | None,
    traces: list[ReasoningTrace],
    store: SignalStore,
    limit: int = 5,
) -> list[ReasoningTrace]:
    """找與問題相關的推理軌跡。優先找同 frame 的。"""
    # 如果有 frame，先從 historical_traces 找
    if frame and frame.reasoning_patterns.historical_traces:
        frame_trace_ids = set(frame.reasoning_patterns.historical_traces)
        frame_traces = [t for t in traces if t.trace_id in frame_trace_ids]
        if len(frame_traces) >= limit:
            return frame_traces[:limit]

    # Embedding 搜尋
    if not traces:
        return []

    q_emb = np.array(store.compute_embedding(question))

    scored: list[tuple[float, ReasoningTrace]] = []
    for t in traces:
        t_text = f"{t.trigger.situation} {t.conclusion.decision}"
        t_emb = np.array(store.compute_embedding(t_text))
        sim = float(np.dot(q_emb, t_emb) / (np.linalg.norm(q_emb) * np.linalg.norm(t_emb) + 1e-8))
        scored.append((sim, t))

    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored[:limit]]


def _build_response_prompt(ctx: QueryContext) -> str:
    """組裝最終的回應生成 prompt。"""
    # 信念
    conviction_lines = []
    for c in ctx.activated_convictions:
        conviction_lines.append(f"- {c.statement}（strength: {c.strength.score}）")
    convictions_text = "\n".join(conviction_lines) if conviction_lines else "（無特定信念激活）"

    # 推理軌跡範例
    trace_lines = []
    for t in ctx.relevant_traces[:3]:
        steps = " → ".join(s.action for s in t.reasoning_path.steps)
        trace_lines.append(
            f"- 情境：{t.trigger.situation}\n"
            f"  推理：{steps}（{t.reasoning_path.style}）\n"
            f"  結論：{t.conclusion.decision}"
        )
    traces_text = "\n".join(trace_lines) if trace_lines else "（無相關推理軌跡）"

    # Identity 護欄
    identity_lines = [f"- {i.core_belief}" for i in ctx.identity_constraints]
    identity_text = "\n".join(identity_lines) if identity_lines else "（無 identity 約束）"

    # Frame 資訊
    frame_info = ""
    if ctx.matched_frame:
        f = ctx.matched_frame
        frame_info = f"情境框架：{f.name}\n描述：{f.description}\n"
        if f.voice and f.voice.tone:
            frame_info += f"語氣：{f.voice.tone}\n"
        if f.voice and f.voice.typical_phrases:
            frame_info += f"常用句式：{', '.join(f.voice.typical_phrases)}\n"
        if f.voice and f.voice.avoids:
            frame_info += f"避免：{', '.join(f.voice.avoids)}\n"
        if f.reasoning_patterns.preferred_style:
            frame_info += f"推理風格：{f.reasoning_patterns.preferred_style}\n"

    caller_info = f"提問者：{ctx.caller}" if ctx.caller else ""

    return f"""你現在要模擬一個人的思維方式來回答問題。

{frame_info}
{caller_info}

這個人的核心信念：
{convictions_text}

這個人不可違反的身份核心：
{identity_text}

這個人在類似情境下的推理範例：
{traces_text}

問題：{ctx.question}

請用這個人的思維方式、推理風格和語氣來回答。
要求：
- 用第一人稱「我」回答
- 回答要反映上述信念和推理風格
- 不能違反身份核心中的任何信念
- 語氣要符合情境框架的設定
- 長度適中（100-300 字）
- 可以引用自己過去的推理邏輯作為佐證"""


def query(
    owner_id: str,
    question: str,
    caller: str | None = None,
    config: dict | None = None,
) -> dict:
    """主入口：五層感知查詢。

    回傳包含 response 和查詢過程資訊的 dict。
    """
    from engine.config import load_config
    cfg = config or load_config()
    owner_dir = get_owner_dir(cfg, owner_id)
    store = SignalStore(cfg, owner_id)

    ctx = QueryContext(question=question, caller=caller)

    # 載入各層資料
    frames = _load_frames(owner_dir)
    active_frames = [f for f in frames if f.lifecycle and f.lifecycle.status == "active"]
    convictions = _load_convictions(owner_dir)
    conviction_map = {c.conviction_id: c for c in convictions}
    traces = _load_traces(owner_dir)
    identities = _load_identity(owner_dir)

    # Step 1: Frame Matching（反射優先）
    matched = _reflex_match(question, active_frames)
    if matched:
        ctx.matched_frame = matched
        ctx.match_method = "reflex"
    else:
        matched = _embedding_match(question, active_frames, store)
        if matched:
            ctx.matched_frame = matched
            ctx.match_method = "embedding"

    # Step 2: Conviction Activation
    if ctx.matched_frame:
        for ca in ctx.matched_frame.conviction_profile.primary_convictions:
            conv = conviction_map.get(ca.conviction_id)
            if conv:
                ctx.activated_convictions.append(conv)
    else:
        # 沒有 frame 時，用 strength 最高的 convictions
        sorted_convictions = sorted(convictions, key=lambda c: -c.strength.score)
        ctx.activated_convictions = sorted_convictions[:5]

    # Step 3: Trace Retrieval
    ctx.relevant_traces = _find_relevant_traces(
        question, ctx.matched_frame, traces, store,
    )

    # Step 4: Identity Check
    ctx.identity_constraints = identities

    # Step 5: Response Generation
    prompt = _build_response_prompt(ctx)
    ctx.response = call_llm(prompt, config=cfg)

    return {
        "response": ctx.response,
        "matched_frame": ctx.matched_frame.name if ctx.matched_frame else None,
        "match_method": ctx.match_method,
        "activated_convictions": [c.statement for c in ctx.activated_convictions],
        "relevant_traces": len(ctx.relevant_traces),
        "identity_constraints": [i.core_belief for i in ctx.identity_constraints],
    }
