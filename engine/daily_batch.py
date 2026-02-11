"""Daily Batch — 每日批次 orchestrator"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from engine.config import get_owner_dir, load_config
from engine.contradiction_alert import scan as scan_contradictions
from engine.conviction_detector import detect as detect_convictions
from engine.conviction_detector import _load_convictions
from engine.decision_tracker import get_pending_followups
from engine.llm import call_llm
from engine.trace_extractor import extract as extract_traces


def _load_frames(owner_dir: Path) -> list:
    """載入 frames。"""
    path = owner_dir / "frames.jsonl"
    if not path.exists():
        return []
    from engine.models import ContextFrame
    frames = []
    with open(path) as f:
        for line in f:
            if line.strip():
                frames.append(ContextFrame.model_validate_json(line))
    return frames


def _generate_digest(
    owner_id: str,
    new_convictions: list,
    strength_changes: list[dict],
    contradictions: list[dict],
    followups: list[dict],
    config: dict,
) -> str:
    """用 LLM 生成每日整理摘要。永遠有內容——沒有新事時回顧既有狀態。"""
    owner_dir = get_owner_dir(config, owner_id)
    all_convictions = _load_convictions(owner_dir)
    active = [c for c in all_convictions if c.lifecycle and c.lifecycle.status == "active"]
    active_count = len(active)

    sections = []

    # 新發現的信念
    if new_convictions:
        items = "\n".join(f"- {c.statement}" for c in new_convictions[:5])
        sections.append(f"【新發現的信念】\n{items}")

    # 信念強化/減弱
    if strength_changes:
        strengthened = [c for c in strength_changes if c["delta"] > 0]
        weakened = [c for c in strength_changes if c["delta"] < 0]
        if strengthened:
            items = "\n".join(
                f"- {c['statement']}（{c['old']:.2f} → {c['new']:.2f}，+{c['delta']:.2f}）"
                for c in sorted(strengthened, key=lambda x: -x["delta"])[:3]
            )
            sections.append(f"【信念強化】\n{items}")
        if weakened:
            items = "\n".join(
                f"- {c['statement']}（{c['old']:.2f} → {c['new']:.2f}，{c['delta']:.2f}）"
                for c in sorted(weakened, key=lambda x: x["delta"])[:3]
            )
            sections.append(f"【信念減弱】\n{items}")

    # 信念張力
    if contradictions:
        items = "\n".join(
            f"- {c['statement_a']} vs {c['statement_b']}（{c['relationship']}）"
            for c in contradictions[:3]
        )
        sections.append(f"【信念張力】\n{items}")

    # 決策追蹤
    if followups:
        items = "\n".join(
            f"- {f['decision']}（{f['days_ago']} 天前）"
            for f in followups[:3]
        )
        sections.append(f"【決策追蹤】\n{items}")

    # Fallback：沒有任何新事時，回顧既有狀態
    if not sections:
        # 最強的信念 top-3
        top_convictions = sorted(active, key=lambda c: -c.strength.score)[:3]
        if top_convictions:
            items = "\n".join(
                f"- {c.statement}（{c.strength.level}，{c.strength.score:.2f}）"
                for c in top_convictions
            )
            sections.append(f"【最活躍的信念】\n{items}")

        # 最活躍的框架
        frames = _load_frames(owner_dir)
        if frames:
            frame_names = [f.name for f in frames[:3]]
            sections.append(f"【思維框架】\n- " + "\n- ".join(frame_names))

    # 數據摘要
    from engine.trace_extractor import _load_traces
    traces = _load_traces(owner_dir)
    sections.append(
        f"【數據】活躍信念 {active_count} 個、推理軌跡 {len(traces)} 條"
    )

    raw = "\n\n".join(sections)
    prompt = (
        f"你是 {owner_id} 的思維助理。以下是今日的觀察摘要：\n\n"
        f"{raw}\n\n"
        "請用溫暖、簡潔的語氣把這些整理成一段早晨簡報（150 字以內），"
        "像是一位了解你的朋友在幫你整理思緒。不要用條列式。"
    )
    return call_llm(prompt, config=config, tier="light").strip()


def run_daily(owner_id: str, config: dict | None = None) -> dict:
    """執行每日批次流程。

    1. detect_convictions（含 strength_changes）
    2. extract_traces
    3. scan_contradictions
    4. check_decision_followups
    5. generate_digest
    6. 輸出到 data/{owner_id}/digests/
    """
    from engine.signal_store import SignalStore

    cfg = config or load_config()

    # 共用 store + signal_map，避免重複建 client 和 load_all
    store = SignalStore(cfg, owner_id)
    all_signals = store.load_all()
    signal_map = {s.signal_id: s for s in all_signals}

    # Step 1: Conviction detection（回傳 new_convictions + strength_changes）
    new_convictions, strength_changes = detect_convictions(
        owner_id, cfg, store=store, signal_map=signal_map
    )

    # Step 2: Trace extraction（需要在 conviction detection 之後，才能引用 convictions）
    new_traces = extract_traces(owner_id, cfg, store=store, signal_map=signal_map)

    # Step 3: Contradiction scan
    contradictions = scan_contradictions(owner_id, cfg)

    # Step 4: Decision followups
    followups = get_pending_followups(owner_id, cfg)

    # Step 5: Generate digest（永遠有內容）
    digest_text = _generate_digest(
        owner_id, new_convictions, strength_changes, contradictions, followups, cfg
    )

    # Step 6: 儲存 digest
    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "owner_id": owner_id,
        "new_convictions": len(new_convictions),
        "strength_changes": len(strength_changes),
        "new_traces": len(new_traces),
        "contradictions": len(contradictions),
        "followups": len(followups),
        "digest": digest_text,
    }

    owner_dir = get_owner_dir(cfg, owner_id)
    digest_dir = owner_dir / "digests"
    digest_dir.mkdir(exist_ok=True)
    digest_path = digest_dir / f"{result['date']}.json"
    with open(digest_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def _load_strength_snapshots(owner_dir: Path, since: str) -> list[dict]:
    """載入指定日期之後的 strength snapshots。"""
    path = owner_dir / "strength_snapshots.jsonl"
    if not path.exists():
        return []
    snapshots = []
    with open(path) as f:
        for line in f:
            if line.strip():
                snap = json.loads(line)
                if snap["date"] >= since:
                    snapshots.append(snap)
    return snapshots


def run_weekly(owner_id: str, config: dict | None = None) -> dict:
    """生成信念週報。

    1. 從 strength_snapshots 計算本週 vs 上週的 strength 變化
    2. 統計本週新 traces + 推理風格分佈
    3. 列出活躍 tensions
    4. 最活躍的 frame
    5. LLM 潤飾成週報
    """
    from engine.trace_extractor import _load_traces

    cfg = config or load_config()
    owner_dir = get_owner_dir(cfg, owner_id)
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    two_weeks_ago = (today - timedelta(days=14)).strftime("%Y-%m-%d")

    # 載入 convictions
    convictions = _load_convictions(owner_dir)
    active = [c for c in convictions if c.lifecycle and c.lifecycle.status == "active"]

    # 從 strength snapshots 計算 delta
    snapshots = _load_strength_snapshots(owner_dir, two_weeks_ago)
    this_week = [s for s in snapshots if s["date"] >= week_ago]
    last_week = [s for s in snapshots if s["date"] < week_ago]

    weekly_deltas: dict[str, float] = {}
    if this_week and last_week:
        latest = this_week[-1]["strengths"]
        earliest = last_week[0]["strengths"]
        for cid, new_score in latest.items():
            old_score = earliest.get(cid)
            if old_score is not None:
                delta = round(new_score - old_score, 3)
                if abs(delta) > 0.05:
                    weekly_deltas[cid] = delta

    # conviction lookup
    conv_map = {c.conviction_id: c for c in active}

    # 統計本週新 traces + 推理風格
    traces = _load_traces(owner_dir)
    new_traces = [t for t in traces if t.source.date >= week_ago]
    style_counts: dict[str, int] = {}
    for t in new_traces:
        style = t.reasoning_path.style if t.reasoning_path else "unknown"
        style_counts[style] = style_counts.get(style, 0) + 1

    # 載入 frames
    frames = _load_frames(owner_dir)

    # 建立週報內容
    sections = []

    # 信念強化 / 減弱（from snapshots）
    strengthened = {cid: d for cid, d in weekly_deltas.items() if d > 0 and cid in conv_map}
    weakened = {cid: d for cid, d in weekly_deltas.items() if d < 0 and cid in conv_map}

    if strengthened:
        items = "\n".join(
            f"- {conv_map[cid].statement}（+{d:.2f}）"
            for cid, d in sorted(strengthened.items(), key=lambda x: -x[1])[:5]
        )
        sections.append(f"【本週強化】\n{items}")

    if weakened:
        items = "\n".join(
            f"- {conv_map[cid].statement}（{d:.2f}）"
            for cid, d in sorted(weakened.items(), key=lambda x: x[1])[:3]
        )
        sections.append(f"【本週減弱】\n{items}")

    # 有張力的信念
    with_tensions = [c for c in active if c.tensions]
    if with_tensions:
        items = []
        for c in with_tensions[:3]:
            for t in (c.tensions or [])[:1]:
                items.append(f"- {c.statement} ⚡ {t.relationship}")
        if items:
            sections.append(f"【信念張力】\n" + "\n".join(items))

    # 推理風格分佈
    if style_counts:
        style_str = "、".join(f"{k}({v})" for k, v in sorted(style_counts.items(), key=lambda x: -x[1])[:4])
        sections.append(f"【本週推理風格】{style_str}")

    # 最活躍的框架
    if frames:
        sections.append(f"【思維框架】{', '.join(f.name for f in frames[:3])}")

    # 數據摘要
    sections.append(
        f"【數據】活躍信念 {len(active)} 個、本週新推理軌跡 {len(new_traces)} 條"
    )

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
        "strengthened": len(strengthened),
        "weakened": len(weakened),
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
