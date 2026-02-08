"""Trace Extractor — 從 output signals 中提取 Layer 3 推理軌跡"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from engine.config import get_owner_dir
from engine.conviction_detector import _load_convictions
from engine.llm import batch_llm, call_llm
from engine.models import (
    ActivatedConviction,
    ReasoningPath,
    ReasoningStep,
    ReasoningTrace,
    Signal,
    TraceConclusion,
    TraceSource,
    TraceTrigger,
)
from engine.signal_store import SignalStore


# 適合提取推理軌跡的 modality
_EXTRACTABLE_MODALITIES = {
    "spoken_spontaneous",
    "spoken_scripted",
    "spoken_interview",
    "written_deliberate",
    "written_structured",
    "decided",
}


def _load_traces(owner_dir: Path) -> list[ReasoningTrace]:
    path = owner_dir / "traces.jsonl"
    if not path.exists():
        return []
    traces = []
    with open(path) as f:
        for line in f:
            if line.strip():
                traces.append(ReasoningTrace.model_validate_json(line))
    return traces


def _save_traces(owner_dir: Path, traces: list[ReasoningTrace]) -> None:
    path = owner_dir / "traces.jsonl"
    with open(path, "w") as f:
        for t in traces:
            f.write(t.model_dump_json() + "\n")


def _build_conviction_context(convictions: list) -> str:
    """建立 conviction 列表供 LLM 參考。"""
    if not convictions:
        return "（目前沒有已偵測到的信念）"
    lines = []
    for c in convictions:
        lines.append(f"- [{c.conviction_id}] {c.statement}（strength: {c.strength.score}）")
    return "\n".join(lines)


def _build_prompt(signal: Signal, conviction_context: str) -> str:
    """建立單一 signal 的提取 prompt。"""
    return f"""以下是一段表達內容：

---
{signal.content.text}
---

情境：{signal.source.context}
日期：{signal.source.date}
類型：{signal.content.type}
信心程度：{signal.content.confidence or "未標記"}

以下是這個人目前已知的信念清單：
{conviction_context}

請分析這段內容中的推理過程，輸出 JSON 格式（不要加 markdown 標記）：

{{
  "has_reasoning": true/false,
  "trigger": {{
    "situation": "觸發推理的情境描述（50字內）",
    "stimulus_type": "question_received|problem_encountered|decision_required|opinion_challenged|opportunity_spotted|conflict_to_resolve|teaching_moment|self_reflection"
  }},
  "activated_convictions": [
    {{
      "conviction_id": "從上方列表中選擇",
      "role": "premise|framework|evidence|constraint|value_anchor|counterpoint",
      "activation_note": "為什麼激活這個信念（30字內）"
    }}
  ],
  "reasoning_path": {{
    "steps": [
      {{
        "action": "empathize|reframe|analyze|compare|recall_experience|apply_framework|challenge_assumption|weigh_tradeoff|synthesize|decide",
        "description": "這一步做了什麼（50字內）",
        "uses_conviction": "conviction_id 或 null"
      }}
    ],
    "style": "analytical|intuitive|storytelling|socratic|first_principles|pattern_matching|empathy_driven"
  }},
  "conclusion": {{
    "decision": "最終結論（80字內）",
    "confidence": "high|medium|low|uncertain",
    "alternative_considered": "考慮過但沒選的替代方案（50字內，可為 null）"
  }}
}}

如果這段內容沒有明確的推理過程（只是陳述事實或隨口一提），請回傳：
{{"has_reasoning": false}}"""


def _parse_response(raw: str, signal: Signal) -> ReasoningTrace | None:
    """解析 LLM 回應，轉成 ReasoningTrace。"""
    # 清理可能的 markdown code block
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    if not data.get("has_reasoning"):
        return None

    try:
        activated = []
        for ac in data.get("activated_convictions", []):
            activated.append(ActivatedConviction(
                conviction_id=ac["conviction_id"],
                role=ac["role"],
                activation_note=ac.get("activation_note"),
            ))

        steps = []
        for step in data["reasoning_path"]["steps"]:
            steps.append(ReasoningStep(
                action=step["action"],
                description=step["description"],
                uses_conviction=step.get("uses_conviction"),
            ))
        path = ReasoningPath(
            steps=steps,
            style=data["reasoning_path"]["style"],
        )

        conclusion = TraceConclusion(
            decision=data["conclusion"]["decision"],
            confidence=data["conclusion"]["confidence"],
            alternative_considered=data["conclusion"].get("alternative_considered"),
            output_signal=signal.signal_id,
        )

        return ReasoningTrace(
            owner_id=signal.owner_id,
            trace_id=f"trace_{uuid.uuid4().hex[:8]}",
            trigger=TraceTrigger(
                situation=data["trigger"]["situation"],
                stimulus_type=data["trigger"]["stimulus_type"],
                from_signal=signal.signal_id,
            ),
            activated_convictions=activated,
            reasoning_path=path,
            conclusion=conclusion,
            source=TraceSource(
                date=signal.source.date,
                source_file=signal.source.source_file,
                participants=signal.source.participants,
            ),
        )

    except (KeyError, ValueError):
        return None


def extract(owner_id: str, config: dict, limit: int | None = None) -> list[ReasoningTrace]:
    """主入口：從 output signals 提取推理軌跡。

    1. 篩選適合的 output signals
    2. 排除已提取過的
    3. 載入 convictions 作為 LLM context
    4. 用 batch_llm 並行提取（claude_code backend）或循序提取
    5. 儲存到 traces.jsonl
    """
    store = SignalStore(config, owner_id)
    owner_dir = get_owner_dir(config, owner_id)

    all_signals = store.load_all()
    candidates = [
        s for s in all_signals
        if s.direction == "output" and s.modality in _EXTRACTABLE_MODALITIES
    ]

    if not candidates:
        return []

    existing_traces = _load_traces(owner_dir)
    extracted_signal_ids = {
        t.trigger.from_signal
        for t in existing_traces
        if t.trigger.from_signal
    }
    candidates = [s for s in candidates if s.signal_id not in extracted_signal_ids]

    if not candidates:
        return []

    # 限制處理數量
    if limit:
        candidates = candidates[:limit]

    # 載入 convictions 作為 context
    convictions = _load_convictions(owner_dir)
    active_convictions = [c for c in convictions if c.lifecycle and c.lifecycle.status == "active"]
    conviction_context = _build_conviction_context(active_convictions)

    # 建立所有 prompts
    prompts = [_build_prompt(s, conviction_context) for s in candidates]

    # 批次呼叫 LLM（claude_code 會並行，其他循序）
    responses = batch_llm(prompts, config=config)

    # 解析結果
    new_traces: list[ReasoningTrace] = []
    for signal, raw in zip(candidates, responses):
        trace = _parse_response(raw, signal)
        if trace:
            new_traces.append(trace)

    if new_traces:
        all_traces = existing_traces + new_traces
        _save_traces(owner_dir, all_traces)

    return new_traces
