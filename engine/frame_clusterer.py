"""Frame Clusterer — 從 traces 聚類出 Layer 4 情境框架

邏輯：
1. 載入所有 traces，按 source.context 分組
2. 每組統計：conviction 激活頻率、推理風格分佈、結論信心
3. 過濾：至少 N 個 traces 的組才建立 frame
4. 用 LLM 生成 frame 名稱、描述、trigger_patterns
5. 比對既有 frames，更新或新增
"""

from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

from engine.config import get_owner_dir
from engine.conviction_detector import _load_convictions
from engine.llm import batch_llm, call_llm
from engine.models import (
    ContextFrame,
    ConvictionActivation,
    ConvictionProfile,
    FrameEffectiveness,
    FrameLifecycle,
    FrameReasoningPatterns,
    FrameVoice,
    ReasoningTrace,
    TriggerPattern,
)
from engine.trace_extractor import _load_traces


def _load_frames(owner_dir: Path) -> list[ContextFrame]:
    path = owner_dir / "frames.jsonl"
    if not path.exists():
        return []
    frames = []
    with open(path) as f:
        for line in f:
            if line.strip():
                frames.append(ContextFrame.model_validate_json(line))
    return frames


def _save_frames(owner_dir: Path, frames: list[ContextFrame]) -> None:
    path = owner_dir / "frames.jsonl"
    with open(path, "w") as f:
        for frame in frames:
            f.write(frame.model_dump_json() + "\n")


def _group_traces_by_context(traces: list[ReasoningTrace]) -> dict[str, list[ReasoningTrace]]:
    """按 source.context 分組。context 為 None 的歸入 'other'。"""
    groups: dict[str, list[ReasoningTrace]] = defaultdict(list)
    for t in traces:
        ctx = t.source.context or "other"
        groups[ctx].append(t)
    return dict(groups)


def _analyze_group(traces: list[ReasoningTrace]) -> dict:
    """分析一組 traces 的統計特徵。"""
    # Conviction 激活頻率
    conviction_counts: Counter[str] = Counter()
    conviction_roles: dict[str, Counter[str]] = defaultdict(Counter)
    for t in traces:
        for ac in t.activated_convictions:
            conviction_counts[ac.conviction_id] += 1
            conviction_roles[ac.conviction_id][ac.role] += 1

    # 推理風格分佈
    style_counts = Counter(t.reasoning_path.style for t in traces)

    # 推理步驟頻率
    step_counts: Counter[str] = Counter()
    for t in traces:
        for step in t.reasoning_path.steps:
            step_counts[step.action] += 1

    # 觸發類型
    trigger_counts = Counter(t.trigger.stimulus_type for t in traces)

    # Outcome 統計
    positive = sum(1 for t in traces if t.outcome and t.outcome.result == "positive")
    negative = sum(1 for t in traces if t.outcome and t.outcome.result == "negative")
    total_with_outcome = sum(1 for t in traces if t.outcome and t.outcome.result not in (None, "pending"))

    # 日期範圍
    dates = sorted(t.source.date for t in traces)

    return {
        "trace_count": len(traces),
        "conviction_counts": conviction_counts,
        "conviction_roles": conviction_roles,
        "style_counts": style_counts,
        "step_counts": step_counts,
        "trigger_counts": trigger_counts,
        "positive": positive,
        "negative": negative,
        "total_with_outcome": total_with_outcome,
        "date_range": (dates[0], dates[-1]) if dates else None,
        "trace_ids": [t.trace_id for t in traces],
    }


def _build_conviction_activations(
    stats: dict,
    total_traces: int,
    conviction_map: dict[str, str],
) -> list[ConvictionActivation]:
    """從統計資料建構 conviction activation 列表。"""
    activations = []
    for cid, count in stats["conviction_counts"].most_common(7):
        weight = round(count / total_traces, 2)
        if weight < 0.1:
            continue
        # 找最常見的 role
        role_counter = stats["conviction_roles"].get(cid, Counter())
        typical_role = role_counter.most_common(1)[0][0] if role_counter else "framework"
        activations.append(ConvictionActivation(
            conviction_id=cid,
            activation_weight=weight,
            typical_role=typical_role,
        ))
    return activations


def _build_reasoning_patterns(stats: dict) -> FrameReasoningPatterns:
    """從統計資料建構推理模式。"""
    preferred = stats["style_counts"].most_common(1)
    preferred_style = preferred[0][0] if preferred else None

    # 典型步驟序列：取前 5 最常見的步驟
    typical_steps = [step for step, _ in stats["step_counts"].most_common(5)]

    return FrameReasoningPatterns(
        preferred_style=preferred_style,
        typical_steps=typical_steps,
        historical_traces=stats["trace_ids"][:20],
    )


def _build_effectiveness(stats: dict) -> FrameEffectiveness | None:
    if stats["total_with_outcome"] == 0:
        return None
    rate = stats["positive"] / stats["total_with_outcome"] if stats["total_with_outcome"] > 0 else None
    return FrameEffectiveness(
        success_rate=round(rate, 2) if rate is not None else None,
        total_traces=stats["trace_count"],
        positive_traces=stats["positive"],
        negative_traces=stats["negative"],
    )


def _generate_frame_metadata(
    context: str,
    stats: dict,
    conviction_map: dict[str, str],
    config: dict,
) -> dict | None:
    """用 LLM 生成 frame 的名稱、描述和 trigger patterns。"""
    # 組裝信念列表
    top_convictions = []
    for cid, count in stats["conviction_counts"].most_common(5):
        statement = conviction_map.get(cid, cid)
        top_convictions.append(f"- {statement}（出現 {count}/{stats['trace_count']} 次）")

    # 觸發類型
    triggers = [f"- {t}: {c} 次" for t, c in stats["trigger_counts"].most_common(5)]

    # 推理風格
    styles = [f"- {s}: {c} 次" for s, c in stats["style_counts"].most_common(3)]

    prompt = f"""以下是一個人在「{context}」情境下的推理行為統計：

推理次數：{stats['trace_count']}
主要信念：
{chr(10).join(top_convictions)}

觸發類型：
{chr(10).join(triggers)}

推理風格：
{chr(10).join(styles)}

請根據以上統計，為這個情境框架生成：
1. name：框架名稱（中文，最多 15 字，例如「高價銷售應對」「教學引導模式」）
2. description：描述這個人在此情境下的行為特徵（中文，最多 100 字）
3. trigger_patterns：2-4 個觸發模式，每個包含 pattern（描述）和 keywords（2-3 個關鍵詞）
4. tone：語氣（professional/warm/direct/patient/passionate/casual/authoritative 擇一）

輸出 JSON（不要加 markdown 標記）：
{{"name": "...", "description": "...", "trigger_patterns": [{{"pattern": "...", "keywords": ["...", "..."]}}], "tone": "..."}}"""

    result = call_llm(prompt, config=config).strip()
    # 清理 markdown
    if result.startswith("```"):
        result = result.split("\n", 1)[1] if "\n" in result else result[3:]
    if result.endswith("```"):
        result = result[:-3]
    result = result.strip()

    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return None


def cluster(owner_id: str, config: dict, min_traces: int = 3) -> list[ContextFrame]:
    """主入口：從 traces 聚類出 context frames。

    1. 載入 traces，按 source.context 分組
    2. 過濾：至少 min_traces 個 traces 的組
    3. 每組統計 conviction 激活、推理風格
    4. LLM 生成 frame metadata
    5. 比對既有 frames，更新或新增
    """
    owner_dir = get_owner_dir(config, owner_id)
    traces = _load_traces(owner_dir)
    if not traces:
        return []

    convictions = _load_convictions(owner_dir)
    conviction_map = {c.conviction_id: c.statement for c in convictions}

    # Step 1: 分組
    groups = _group_traces_by_context(traces)

    # Step 2: 過濾 + 分析
    candidates: list[tuple[str, dict]] = []
    for context, group_traces in groups.items():
        if len(group_traces) < min_traces:
            continue
        stats = _analyze_group(group_traces)
        candidates.append((context, stats))

    if not candidates:
        return []

    # Step 3: 載入既有 frames
    existing = _load_frames(owner_dir)
    existing_by_context: dict[str, ContextFrame] = {}
    for f in existing:
        # 用 trigger_patterns 的 keywords 嘗試匹配 context
        for tp in f.trigger_patterns:
            if tp.keywords:
                for kw in tp.keywords:
                    existing_by_context[kw] = f
    # 也用 frame_id 中的 context 匹配
    for f in existing:
        parts = f.frame_id.split("_")
        if len(parts) >= 2:
            existing_by_context[parts[1]] = f

    today = datetime.now().strftime("%Y-%m-%d")
    new_frames: list[ContextFrame] = []
    updated_ids: set[str] = set()

    for context, stats in candidates:
        # 檢查是否已有這個 context 的 frame
        matched = existing_by_context.get(context)

        if matched and matched.frame_id not in updated_ids:
            # 更新既有 frame
            matched.reasoning_patterns = _build_reasoning_patterns(stats)
            matched.conviction_profile.primary_convictions = _build_conviction_activations(
                stats, stats["trace_count"], conviction_map,
            )
            matched.effectiveness = _build_effectiveness(stats)
            if matched.lifecycle:
                matched.lifecycle.last_activated = today
            updated_ids.add(matched.frame_id)
            continue

        # 生成新 frame
        metadata = _generate_frame_metadata(context, stats, conviction_map, config)
        if not metadata:
            continue

        # 建構 trigger patterns
        trigger_patterns = []
        for tp_data in metadata.get("trigger_patterns", []):
            trigger_patterns.append(TriggerPattern(
                pattern=tp_data.get("pattern", context),
                keywords=tp_data.get("keywords"),
            ))
        if not trigger_patterns:
            trigger_patterns = [TriggerPattern(pattern=context)]

        # 建構 frame
        frame_seq = len(existing) + len(new_frames) + 1
        # 用 context 名稱做 frame_id（簡化）
        safe_ctx = context.replace(" ", "_")[:20]
        frame = ContextFrame(
            owner_id=owner_id,
            frame_id=f"frame_{safe_ctx}_{frame_seq:03d}",
            name=metadata.get("name", context)[:50],
            description=metadata.get("description", "")[:300],
            trigger_patterns=trigger_patterns,
            conviction_profile=ConvictionProfile(
                primary_convictions=_build_conviction_activations(
                    stats, stats["trace_count"], conviction_map,
                ),
            ),
            reasoning_patterns=_build_reasoning_patterns(stats),
            voice=FrameVoice(tone=metadata.get("tone")) if metadata.get("tone") else None,
            effectiveness=_build_effectiveness(stats),
            lifecycle=FrameLifecycle(
                status="active",
                first_observed=stats["date_range"][0] if stats["date_range"] else today,
                last_activated=today,
            ),
        )
        new_frames.append(frame)

    # 儲存
    all_frames = existing + new_frames
    _save_frames(owner_dir, all_frames)

    return new_frames
