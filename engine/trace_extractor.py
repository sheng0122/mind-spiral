"""Trace Extractor — 從 output signals 中提取 Layer 3 推理軌跡

v2: 按 (date, context) 分組，把同一場景的 signals 合併送 LLM，
讓 LLM 從整段對話/內容中提取推理軌跡。
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from engine.config import get_owner_dir
from engine.conviction_detector import _load_convictions
from engine.llm import batch_llm
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

# 每個 chunk 的最大 signals 數（避免 prompt 太長）
_MAX_SIGNALS_PER_CHUNK = 30


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
    if not convictions:
        return "（目前沒有已偵測到的信念）"
    lines = []
    for c in convictions:
        lines.append(f"- [{c.conviction_id}] {c.statement}（strength: {c.strength.score}）")
    return "\n".join(lines)


def _group_signals(signals: list[Signal]) -> list[tuple[str, str, list[Signal]]]:
    """按 (date, context) 分組，大組再拆 chunk。回傳 [(date, context, signals), ...]"""
    groups: dict[tuple[str, str], list[Signal]] = defaultdict(list)
    for s in signals:
        groups[(s.source.date, s.source.context)].append(s)

    result = []
    for (date, context), sigs in sorted(groups.items()):
        # 大組拆 chunk
        for i in range(0, len(sigs), _MAX_SIGNALS_PER_CHUNK):
            chunk = sigs[i:i + _MAX_SIGNALS_PER_CHUNK]
            result.append((date, context, chunk))
    return result


def _build_group_prompt(date: str, context: str, signals: list[Signal], conviction_context: str) -> str:
    """建立一組 signals 的提取 prompt。"""
    signal_lines = []
    for i, s in enumerate(signals, 1):
        meta = f"[{s.content.type}|{s.modality}|{s.content.confidence or '未標記'}]"
        signal_lines.append(f"{i}. {meta} {s.content.text}")
    signals_text = "\n".join(signal_lines)

    return f"""以下是同一個人在同一場景中的多段表達：

日期：{date}
情境：{context}
共 {len(signals)} 段：

{signals_text}

---

以下是這個人目前已知的信念清單：
{conviction_context}

請從上面的內容中找出「有推理過程」的段落組合（某人面對一個問題→思考→得出結論），提取推理軌跡。

注意：
- 不是每段都有推理，只提取真正有推理過程的
- 多段內容可能組成一個推理（例如：先描述問題，再分析，最後做決定）
- 單獨的金句、引用、指令不算推理
- 請標注每個 trace 用到了哪些段落編號（from_signals）

輸出 JSON 格式（不要加 markdown 標記）：

{{
  "traces": [
    {{
      "from_signals": [1, 3, 5],
      "trigger": {{
        "situation": "觸發推理的情境描述（50字內）",
        "stimulus_type": "question_received|problem_encountered|decision_required|opinion_challenged|opportunity_spotted|conflict_to_resolve|teaching_moment|self_reflection"
      }},
      "activated_convictions": [
        {{
          "conviction_id": "從上方信念列表中選擇",
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
  ]
}}

如果整組內容都沒有明確的推理過程，請回傳：
{{"traces": []}}"""


def _parse_group_response(raw: str, signals: list[Signal], date: str, context: str) -> list[ReasoningTrace]:
    """解析 LLM 對一組 signals 的回應。"""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return []

    raw_traces = data.get("traces", [])
    if not raw_traces:
        return []

    results = []
    for rt in raw_traces:
        try:
            # 找出對應的 signal IDs
            from_indices = rt.get("from_signals", [])
            from_signal_ids = []
            for idx in from_indices:
                if 1 <= idx <= len(signals):
                    from_signal_ids.append(signals[idx - 1].signal_id)

            activated = []
            for ac in rt.get("activated_convictions", []):
                activated.append(ActivatedConviction(
                    conviction_id=ac["conviction_id"],
                    role=ac["role"],
                    activation_note=ac.get("activation_note"),
                ))

            steps = []
            for step in rt["reasoning_path"]["steps"]:
                steps.append(ReasoningStep(
                    action=step["action"],
                    description=step["description"],
                    uses_conviction=step.get("uses_conviction"),
                ))
            path = ReasoningPath(
                steps=steps,
                style=rt["reasoning_path"]["style"],
            )

            conclusion = TraceConclusion(
                decision=rt["conclusion"]["decision"],
                confidence=rt["conclusion"]["confidence"],
                alternative_considered=rt["conclusion"].get("alternative_considered"),
                output_signal=from_signal_ids[0] if from_signal_ids else None,
            )

            owner_id = signals[0].owner_id
            source_file = signals[0].source.source_file if signals else None
            participants = signals[0].source.participants if signals else None

            trace = ReasoningTrace(
                owner_id=owner_id,
                trace_id=f"trace_{uuid.uuid4().hex[:8]}",
                trigger=TraceTrigger(
                    situation=rt["trigger"]["situation"],
                    stimulus_type=rt["trigger"]["stimulus_type"],
                    from_signal=from_signal_ids[0] if from_signal_ids else None,
                ),
                activated_convictions=activated,
                reasoning_path=path,
                conclusion=conclusion,
                source=TraceSource(
                    date=date,
                    source_file=source_file,
                    participants=participants,
                ),
            )
            results.append(trace)

        except (KeyError, ValueError, IndexError):
            continue

    return results


def extract(owner_id: str, config: dict, limit: int | None = None) -> list[ReasoningTrace]:
    """主入口：從 output signals 提取推理軌跡。

    v2: 按 (date, context) 分組送 LLM，從整段對話中提取推理軌跡。

    1. 篩選適合的 output signals
    2. 排除已處理過的分組
    3. 按 (date, context) 分組
    4. 用 batch_llm 並行處理各組
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

    # 排除已提取過的 signals
    existing_traces = _load_traces(owner_dir)
    extracted_signal_ids = {
        t.trigger.from_signal
        for t in existing_traces
        if t.trigger.from_signal
    }
    candidates = [s for s in candidates if s.signal_id not in extracted_signal_ids]

    if not candidates:
        return []

    # 按 (date, context) 分組
    groups = _group_signals(candidates)

    # 限制處理組數
    if limit:
        groups = groups[:limit]

    # 載入 convictions 作為 context
    convictions = _load_convictions(owner_dir)
    active_convictions = [c for c in convictions if c.lifecycle and c.lifecycle.status == "active"]
    conviction_context = _build_conviction_context(active_convictions)

    # 建立所有 prompts
    prompts = [
        _build_group_prompt(date, context, sigs, conviction_context)
        for date, context, sigs in groups
    ]

    # 批次呼叫 LLM
    responses = batch_llm(prompts, config=config)

    # 解析結果
    new_traces: list[ReasoningTrace] = []
    for (date, context, sigs), raw in zip(groups, responses):
        traces = _parse_group_response(raw, sigs, date, context)
        new_traces.extend(traces)

    if new_traces:
        all_traces = existing_traces + new_traces
        _save_traces(owner_dir, all_traces)

    return new_traces
