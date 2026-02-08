"""Decision Tracker — 決策追蹤佇列 + outcome 回饋螺旋"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from engine.config import get_owner_dir
from engine.conviction_detector import _load_convictions, _save_convictions
from engine.models import ConvictionImpact, ReasoningTrace, TraceOutcome
from engine.trace_extractor import _load_traces, _save_traces


def get_pending_followups(owner_id: str, config: dict) -> list[dict]:
    """取得需要回訪的決策列表。

    掃描 traces 中 outcome 為 None 或 pending 的，
    根據 config 的天數設定判斷是否到期。

    backfill_cutoff_date: 早於此日期的 trace 視為歷史資料，跳過追蹤。
    """
    owner_dir = get_owner_dir(config, owner_id)
    traces = _load_traces(owner_dir)
    today = datetime.now()

    followup_cfg = config.get("engine", {}).get("touch", {}).get("decision_followup", {})
    default_days = followup_cfg.get("tactical_days", 14)
    # 歷史截止日：早於此日期的 trace 不進入追蹤佇列
    backfill_cutoff = followup_cfg.get("backfill_cutoff_date")

    pending = []
    for t in traces:
        # 只追蹤有明確結論的（非 uncertain）
        if t.conclusion.confidence == "uncertain":
            continue

        # 跳過已有 outcome 且不是 pending 的
        if t.outcome and t.outcome.result and t.outcome.result != "pending":
            continue

        trace_date = datetime.strptime(t.source.date, "%Y-%m-%d")

        # 歷史資料跳過：首次全量匯入的 trace 不應進入追蹤佇列
        if backfill_cutoff:
            cutoff = datetime.strptime(backfill_cutoff, "%Y-%m-%d")
            if trace_date < cutoff:
                continue

        days_ago = (today - trace_date).days

        if days_ago >= default_days:
            pending.append({
                "trace_id": t.trace_id,
                "decision": t.conclusion.decision,
                "confidence": t.conclusion.confidence,
                "date": t.source.date,
                "days_ago": days_ago,
                "trigger": t.trigger.situation,
                "activated_convictions": [
                    ac.conviction_id for ac in t.activated_convictions
                ],
            })

    # 按天數排序（最久未回訪的在前）
    pending.sort(key=lambda x: -x["days_ago"])
    return pending


def record_outcome(
    owner_id: str,
    trace_id: str,
    result: str,
    note: str | None = None,
    config: dict | None = None,
) -> dict:
    """記錄決策結果，並回饋到 conviction strength（螺旋機制）。

    result: positive / negative / mixed / unknown
    """
    from engine.config import load_config
    cfg = config or load_config()
    owner_dir = get_owner_dir(cfg, owner_id)

    # 載入 traces
    traces = _load_traces(owner_dir)
    target = None
    for t in traces:
        if t.trace_id == trace_id:
            target = t
            break

    if not target:
        return {"error": f"trace {trace_id} not found"}

    today = datetime.now().strftime("%Y-%m-%d")

    # 決定 conviction impact
    impact_effect = {
        "positive": "reinforced",
        "negative": "weakened",
        "mixed": "unchanged",
        "unknown": "unchanged",
    }.get(result, "unchanged")

    conviction_impacts = [
        ConvictionImpact(conviction_id=ac.conviction_id, effect=impact_effect)
        for ac in target.activated_convictions
    ]

    # 更新 trace outcome
    target.outcome = TraceOutcome(
        result=result,
        feedback_note=note,
        conviction_impact=conviction_impacts,
        recorded_at=today,
    )

    # 儲存 traces
    _save_traces(owner_dir, traces)

    # 螺旋回饋：更新 conviction strength
    if result in ("positive", "negative"):
        convictions = _load_convictions(owner_dir)
        affected_ids = {ac.conviction_id for ac in target.activated_convictions}
        changed = []

        for c in convictions:
            if c.conviction_id not in affected_ids:
                continue
            delta = 0.05 if result == "positive" else -0.05
            new_score = max(0, min(1, c.strength.score + delta))
            c.strength.score = round(new_score, 2)

            # 更新 level
            if new_score >= 0.8:
                c.strength.level = "core"
            elif new_score >= 0.6:
                c.strength.level = "established"
            elif new_score >= 0.4:
                c.strength.level = "developing"
            else:
                c.strength.level = "emerging"

            c.strength.last_computed = today
            if c.lifecycle:
                c.lifecycle.last_reinforced = today
            changed.append(c.conviction_id)

        _save_convictions(owner_dir, convictions)

        return {
            "trace_id": trace_id,
            "result": result,
            "convictions_updated": changed,
        }

    return {"trace_id": trace_id, "result": result, "convictions_updated": []}
