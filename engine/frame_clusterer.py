"""Frame Clusterer — 從 traces 語義聚類出 Layer 4 情境框架

v2: 不再按字面 source.context 分組，改用 trace 語義特徵 embedding 聚類。
每個 trace 的特徵 = trigger.situation + conclusion.decision + activated convictions。
這樣同一個 team_meeting 裡「討論定價」和「處理人事」會被分到不同 frame。
"""

from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.cluster import AgglomerativeClustering

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
from engine.signal_store import SignalStore
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


def _trace_to_text(trace: ReasoningTrace, conviction_map: dict[str, str]) -> str:
    """將 trace 轉成語義特徵文字，用於 embedding。"""
    parts = []
    # 觸發情境
    parts.append(f"情境：{trace.trigger.situation}")
    # 結論
    parts.append(f"結論：{trace.conclusion.decision}")
    # 激活的信念（用 statement 而非 ID）
    for ac in trace.activated_convictions[:3]:
        stmt = conviction_map.get(ac.conviction_id, "")
        if stmt:
            parts.append(f"信念：{stmt}")
    # 推理風格 + 觸發類型（結構化特徵）
    parts.append(f"風格：{trace.reasoning_path.style}｜觸發：{trace.trigger.stimulus_type}")
    return " ".join(parts)


def _analyze_group(traces: list[ReasoningTrace]) -> dict:
    """分析一組 traces 的統計特徵。"""
    conviction_counts: Counter[str] = Counter()
    conviction_roles: dict[str, Counter[str]] = defaultdict(Counter)
    for t in traces:
        for ac in t.activated_convictions:
            conviction_counts[ac.conviction_id] += 1
            conviction_roles[ac.conviction_id][ac.role] += 1

    style_counts = Counter(t.reasoning_path.style for t in traces)
    step_counts: Counter[str] = Counter()
    for t in traces:
        for step in t.reasoning_path.steps:
            step_counts[step.action] += 1

    trigger_counts = Counter(t.trigger.stimulus_type for t in traces)
    context_counts = Counter(t.source.context or "other" for t in traces)

    positive = sum(1 for t in traces if t.outcome and t.outcome.result == "positive")
    negative = sum(1 for t in traces if t.outcome and t.outcome.result == "negative")
    total_with_outcome = sum(1 for t in traces if t.outcome and t.outcome.result not in (None, "pending"))

    dates = sorted(t.source.date for t in traces)

    return {
        "trace_count": len(traces),
        "conviction_counts": conviction_counts,
        "conviction_roles": conviction_roles,
        "style_counts": style_counts,
        "step_counts": step_counts,
        "trigger_counts": trigger_counts,
        "context_counts": context_counts,
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
    activations = []
    for cid, count in stats["conviction_counts"].most_common(7):
        weight = round(count / total_traces, 2)
        if weight < 0.1:
            continue
        role_counter = stats["conviction_roles"].get(cid, Counter())
        typical_role = role_counter.most_common(1)[0][0] if role_counter else "framework"
        activations.append(ConvictionActivation(
            conviction_id=cid,
            activation_weight=weight,
            typical_role=typical_role,
        ))
    return activations


def _build_reasoning_patterns(stats: dict) -> FrameReasoningPatterns:
    preferred = stats["style_counts"].most_common(1)
    preferred_style = preferred[0][0] if preferred else None
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
    stats: dict,
    sample_traces: list[ReasoningTrace],
    conviction_map: dict[str, str],
    config: dict,
) -> dict | None:
    """用 LLM 從 cluster 統計 + 樣本 traces 生成 frame metadata。"""
    top_convictions = []
    for cid, count in stats["conviction_counts"].most_common(5):
        statement = conviction_map.get(cid, cid)
        top_convictions.append(f"- {statement}（出現 {count}/{stats['trace_count']} 次）")

    triggers = [f"- {t}: {c} 次" for t, c in stats["trigger_counts"].most_common(5)]
    styles = [f"- {s}: {c} 次" for s, c in stats["style_counts"].most_common(3)]
    contexts = [f"- {c}: {n} 次" for c, n in stats["context_counts"].most_common(3)]

    # 取 3 個樣本 trace 的 situation + decision
    samples = []
    for t in sample_traces[:3]:
        samples.append(f"- 觸發：{t.trigger.situation} → 結論：{t.conclusion.decision}")

    prompt = f"""以下是一個人某種「思維模式」的統計（從推理軌跡聚類得出）：

推理次數：{stats['trace_count']}

主要信念：
{chr(10).join(top_convictions)}

出現場景：
{chr(10).join(contexts)}

觸發類型：
{chr(10).join(triggers)}

推理風格：
{chr(10).join(styles)}

代表性推理樣本：
{chr(10).join(samples)}

請根據以上統計，為這個思維框架生成：
1. name：框架名稱（中文，最多 15 字，描述思維模式而非場景，例如「第一原則拆解問題」「同理心引導說服」）
2. description：描述這個人啟用此框架時的思維特徵（中文，最多 100 字）
3. trigger_patterns：2-4 個觸發模式，每個包含 pattern（描述）和 keywords（2-3 個關鍵詞）
4. tone：語氣（professional/warm/direct/patient/passionate/casual/authoritative 擇一）

輸出 JSON（不要加 markdown 標記）：
{{"name": "...", "description": "...", "trigger_patterns": [{{"pattern": "...", "keywords": ["...", "..."]}}], "tone": "..."}}"""

    result = call_llm(prompt, config=config, tier="light").strip()
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
    """主入口：從 traces 語義聚類出 context frames。

    v2: 用 trace 語義特徵 embedding 聚類，不再按字面 context 分組。

    1. 載入 traces + convictions
    2. 每個 trace 轉成語義文字 → embedding
    3. AgglomerativeClustering 聚類
    4. 過濾：至少 min_traces 個 traces 的 cluster
    5. LLM 生成 frame metadata
    """
    owner_dir = get_owner_dir(config, owner_id)
    traces = _load_traces(owner_dir)
    if not traces:
        return []

    convictions = _load_convictions(owner_dir)
    conviction_map = {c.conviction_id: c.statement for c in convictions}

    # Step 1: 每個 trace → 語義文字 → embedding
    store = SignalStore(config, owner_id)
    trace_texts = [_trace_to_text(t, conviction_map) for t in traces]
    embeddings = store._get_embedder().encode(
        trace_texts, normalize_embeddings=True,
        show_progress_bar=len(trace_texts) > 50,
    )

    if len(traces) < 2:
        return []

    # Step 2: AgglomerativeClustering
    frame_cfg = config.get("engine", {}).get("frame", {})
    threshold = frame_cfg.get("similarity_threshold", 0.55)

    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=1 - threshold,
        metric="cosine",
        linkage="average",
    )
    labels = clustering.fit_predict(embeddings)

    # 按 label 分組
    groups: dict[int, list[int]] = defaultdict(list)
    for idx, label in enumerate(labels):
        groups[label].append(idx)

    # Step 3: 過濾 + 分析 + 生成
    today = datetime.now().strftime("%Y-%m-%d")
    new_frames: list[ContextFrame] = []

    for label, indices in sorted(groups.items(), key=lambda x: -len(x[1])):
        if len(indices) < min_traces:
            continue

        cluster_traces = [traces[i] for i in indices]
        stats = _analyze_group(cluster_traces)

        # LLM 生成 metadata
        metadata = _generate_frame_metadata(stats, cluster_traces, conviction_map, config)
        if not metadata:
            continue

        # 建構 trigger patterns
        trigger_patterns = []
        for tp_data in metadata.get("trigger_patterns", []):
            trigger_patterns.append(TriggerPattern(
                pattern=tp_data.get("pattern", ""),
                keywords=tp_data.get("keywords"),
            ))
        if not trigger_patterns:
            trigger_patterns = [TriggerPattern(pattern="general")]

        frame_seq = len(new_frames) + 1
        frame = ContextFrame(
            owner_id=owner_id,
            frame_id=f"frame_{uuid.uuid4().hex[:6]}_{frame_seq:03d}",
            name=metadata.get("name", f"frame_{frame_seq}")[:50],
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

    # 儲存（全量覆寫，因為是重新聚類）
    _save_frames(owner_dir, new_frames)

    return new_frames
