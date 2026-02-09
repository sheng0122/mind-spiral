"""Daily Batch — 每日批次 orchestrator"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from engine.config import get_owner_dir, load_config
from engine.contradiction_alert import scan as scan_contradictions
from engine.conviction_detector import detect as detect_convictions
from engine.conviction_detector import _load_convictions
from engine.decision_tracker import get_pending_followups
from engine.llm import call_llm
from engine.trace_extractor import extract as extract_traces


def _check_decision_followups(owner_id: str, config: dict) -> list[dict]:
    """檢查需要回訪的決策。掃描 signals 中 modality=decided 且到期的。"""
    from engine.signal_store import SignalStore

    store = SignalStore(config, owner_id)
    signals = store.load_all()
    today = datetime.now()
    followup_cfg = config.get("engine", {}).get("touch", {}).get("decision_followup", {})
    default_days = followup_cfg.get("tactical_days", 14)

    pending = []
    for s in signals:
        if s.modality != "decided":
            continue
        decided_date = datetime.strptime(s.source.date, "%Y-%m-%d")
        days_ago = (today - decided_date).days
        if days_ago >= default_days:
            pending.append({
                "signal_id": s.signal_id,
                "decision": s.content.text[:100],
                "decided_date": s.source.date,
                "days_ago": days_ago,
            })
    return pending


def _generate_digest(
    owner_id: str,
    new_convictions: list,
    contradictions: list[dict],
    followups: list[dict],
    config: dict,
) -> str:
    """用 LLM 生成每日整理摘要。"""
    sections = []

    if new_convictions:
        items = "\n".join(f"- {c.statement}" for c in new_convictions[:5])
        sections.append(f"【新發現的信念】\n{items}")

    if contradictions:
        items = "\n".join(
            f"- {c['statement_a']} vs {c['statement_b']}（{c['relationship']}）"
            for c in contradictions[:3]
        )
        sections.append(f"【信念張力】\n{items}")

    if followups:
        items = "\n".join(
            f"- {f['decision']}（{f['days_ago']} 天前）"
            for f in followups[:3]
        )
        sections.append(f"【決策追蹤】\n{items}")

    if not sections:
        return ""

    # 載入既有 convictions 數量
    owner_dir = get_owner_dir(config, owner_id)
    all_convictions = _load_convictions(owner_dir)
    active_count = sum(1 for c in all_convictions if c.lifecycle and c.lifecycle.status == "active")

    raw = "\n\n".join(sections)
    prompt = (
        f"你是 {owner_id} 的思維助理。以下是今日的觀察摘要：\n\n"
        f"{raw}\n\n"
        f"目前共有 {active_count} 個活躍信念。\n\n"
        "請用溫暖、簡潔的語氣把這些整理成一段早晨簡報（150 字以內），"
        "像是一位了解你的朋友在幫你整理思緒。不要用條列式。"
    )
    return call_llm(prompt, config=config, tier="light").strip()


def run_daily(owner_id: str, config: dict | None = None) -> dict:
    """執行每日批次流程。

    1. detect_convictions
    2. scan_contradictions
    3. check_decision_followups
    4. generate_digest
    5. 輸出到 data/{owner_id}/digests/
    """
    cfg = config or load_config()

    # Step 1: Conviction detection
    new_convictions = detect_convictions(owner_id, cfg)

    # Step 2: Trace extraction（需要在 conviction detection 之後，才能引用 convictions）
    new_traces = extract_traces(owner_id, cfg)

    # Step 3: Contradiction scan
    contradictions = scan_contradictions(owner_id, cfg)

    # Step 4: Decision followups（改用 decision_tracker）
    followups = get_pending_followups(owner_id, cfg)

    # Step 5: Generate digest
    digest_text = _generate_digest(owner_id, new_convictions, contradictions, followups, cfg)

    # Step 6: 儲存 digest
    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "owner_id": owner_id,
        "new_convictions": len(new_convictions),
        "new_traces": len(new_traces),
        "contradictions": len(contradictions),
        "followups": len(followups),
        "digest": digest_text,
    }

    if digest_text:
        owner_dir = get_owner_dir(cfg, owner_id)
        digest_dir = owner_dir / "digests"
        digest_dir.mkdir(exist_ok=True)
        digest_path = digest_dir / f"{result['date']}.json"
        with open(digest_path, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def run_weekly(owner_id: str, config: dict | None = None) -> dict:
    """生成信念週報。

    1. 比對 convictions 的 strength 變化
    2. 統計本週新 traces
    3. 列出活躍 tensions
    4. LLM 潤飾成週報
    5. 存到 digests/weekly_{date}.json
    """
    from engine.trace_extractor import _load_traces

    cfg = config or load_config()
    owner_dir = get_owner_dir(cfg, owner_id)
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    week_ago = (today - __import__("datetime").timedelta(days=7)).strftime("%Y-%m-%d")

    # 載入 convictions
    convictions = _load_convictions(owner_dir)
    active = [c for c in convictions if c.lifecycle and c.lifecycle.status == "active"]

    # 分類：本週新偵測 / 最近強化 / 有張力的
    new_this_week = [
        c for c in active
        if c.lifecycle and c.lifecycle.first_detected and c.lifecycle.first_detected >= week_ago
    ]
    recently_reinforced = [
        c for c in active
        if c.lifecycle and c.lifecycle.last_reinforced and c.lifecycle.last_reinforced >= week_ago
        and c not in new_this_week
    ]
    with_tensions = [c for c in active if c.tensions]

    # 統計本週新 traces
    traces = _load_traces(owner_dir)
    new_traces = [t for t in traces if t.source.date >= week_ago]

    # 建立週報內容
    sections = []

    if new_this_week:
        items = "\n".join(f"- {c.statement}（{c.strength.level}）" for c in new_this_week[:5])
        sections.append(f"【本週新發現】\n{items}")

    if recently_reinforced:
        items = "\n".join(
            f"- {c.statement}（strength: {c.strength.score}）"
            for c in sorted(recently_reinforced, key=lambda x: -x.strength.score)[:5]
        )
        sections.append(f"【持續強化中】\n{items}")

    weakening = [c for c in active if c.strength.trend == "weakening"]
    if weakening:
        items = "\n".join(f"- {c.statement}（{c.strength.score}）" for c in weakening[:3])
        sections.append(f"【逐漸減弱】\n{items}")

    if with_tensions:
        items = []
        for c in with_tensions[:3]:
            for t in (c.tensions or [])[:1]:
                items.append(f"- {c.statement} ⚡ {t.relationship}")
        if items:
            sections.append(f"【信念張力】\n" + "\n".join(items))

    sections.append(f"【數據】\n- 活躍信念: {len(active)}\n- 本週新推理軌跡: {len(new_traces)}")

    if not sections:
        return {"date": today_str, "owner_id": owner_id, "report": ""}

    raw = "\n\n".join(sections)
    prompt = (
        f"你是 {owner_id} 的思維助理。以下是本週的信念變化摘要：\n\n"
        f"{raw}\n\n"
        "請用溫暖但有洞察的語氣寫一份週報（200 字以內），"
        "重點放在趨勢和值得注意的變化。不要用條列式。"
    )
    report = call_llm(prompt, config=cfg, tier="light").strip()

    result = {
        "date": today_str,
        "week_start": week_ago,
        "owner_id": owner_id,
        "new_convictions": len(new_this_week),
        "reinforced": len(recently_reinforced),
        "new_traces": len(new_traces),
        "tensions": len(with_tensions),
        "report": report,
    }

    # 儲存
    digest_dir = owner_dir / "digests"
    digest_dir.mkdir(exist_ok=True)
    with open(digest_dir / f"weekly_{today_str}.json", "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
