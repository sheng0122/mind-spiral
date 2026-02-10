"""Explorer — 六種查詢模式的核心邏輯

1. Recall: 記憶回溯（原話搜尋 + 時間/情境過濾）
2. Explore: 思維展開（從主題串連五層資料）
3. Evolution: 演變追蹤（信念 strength 變化 + 轉折點）
4. Blind Spots: 盲區偵測（說做不一致、思維慣性等）
5. Connections: 關係圖譜（兩個主題之間的隱性連結）
6. Simulate: 模擬預測（假設情境下的反應路徑）
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from engine.config import get_owner_dir, load_config
from engine.conviction_detector import _load_convictions
from engine.frame_clusterer import _load_frames
from engine.identity_scanner import _load_identity
from engine.llm import call_llm
from engine.models import Conviction, ContextFrame, ReasoningTrace
from engine.signal_store import SignalStore
from engine.trace_extractor import _load_traces


# ─── 1. Recall（記憶回溯）───


def recall(
    owner_id: str,
    text: str,
    context: str | None = None,
    direction: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
    config: dict | None = None,
) -> list[dict]:
    """搜尋原話，回傳日期、情境、原文。"""
    cfg = config or load_config()
    store = SignalStore(cfg, owner_id)

    date_range = None
    if date_from or date_to:
        date_range = (date_from or "2000-01-01", date_to or "2099-12-31")

    signals = store.query(
        text=text,
        direction=direction,
        date_range=date_range,
        n_results=limit,
    )

    # 如果有 context 過濾，在 Python 層做（ChromaDB where 不支援多條件組合太好）
    if context:
        signals = [s for s in signals if s.source.context == context]

    results = []
    for s in signals:
        results.append({
            "signal_id": s.signal_id,
            "text": s.content.text,
            "type": s.content.type,
            "direction": s.direction,
            "modality": s.modality,
            "date": s.source.date,
            "context": s.source.context,
            "source_file": s.source.source_file,
            "participants": s.source.participants,
            "confidence": s.content.confidence,
            "emotion": s.content.emotion,
            "topics": s.topics,
        })

    return results


# ─── 2. Explore（思維展開）───


def explore(
    owner_id: str,
    topic: str,
    depth: str = "full",
    config: dict | None = None,
) -> dict:
    """從主題出發，串連五層資料成樹狀結構。"""
    cfg = config or load_config()
    owner_dir = get_owner_dir(cfg, owner_id)
    store = SignalStore(cfg, owner_id)

    convictions = _load_convictions(owner_dir)
    traces = _load_traces(owner_dir)
    frames = _load_frames(owner_dir)

    # 用 embedding 找相關 convictions
    q_emb = store.compute_embedding(topic)

    import chromadb
    chroma_dir = owner_dir / "chroma"
    client = chromadb.PersistentClient(path=str(chroma_dir))

    # 找相關 convictions
    conviction_map = {c.conviction_id: c for c in convictions}
    related_convictions = []
    try:
        col = client.get_collection(name=f"{owner_id}_convictions")
        results = col.query(query_embeddings=[q_emb], n_results=10)
        if results["ids"] and results["ids"][0]:
            for i, cid in enumerate(results["ids"][0]):
                if cid in conviction_map:
                    c = conviction_map[cid]
                    distance = results["distances"][0][i] if results.get("distances") else 1.0
                    related_convictions.append((c, distance))
    except Exception:
        pass

    # 過濾距離太遠的
    related_convictions = [(c, d) for c, d in related_convictions if d < 0.8]

    if depth == "lite":
        return {
            "topic": topic,
            "convictions": [
                {
                    "statement": c.statement,
                    "strength": c.strength.score,
                    "level": c.strength.level,
                    "domains": c.domains,
                    "relevance": round(1 - d, 2),
                }
                for c, d in related_convictions
            ],
        }

    # Full depth: 加 traces, frames, tensions, signals
    conviction_ids = {c.conviction_id for c, _ in related_convictions}
    trace_map = {t.trace_id: t for t in traces}

    # 找相關 traces
    related_traces = []
    try:
        col = client.get_collection(name=f"{owner_id}_traces")
        results = col.query(query_embeddings=[q_emb], n_results=10)
        if results["ids"] and results["ids"][0]:
            for tid in results["ids"][0]:
                if tid in trace_map:
                    related_traces.append(trace_map[tid])
    except Exception:
        pass

    # 找所屬 frames
    related_frames = []
    for f in frames:
        primary_ids = {ca.conviction_id for ca in f.conviction_profile.primary_convictions}
        if primary_ids & conviction_ids:
            related_frames.append(f)

    # 找 tensions
    tensions = []
    for c, _ in related_convictions:
        if c.tensions:
            for t in c.tensions:
                opposing = conviction_map.get(t.opposing_conviction)
                tensions.append({
                    "conviction_a": c.statement,
                    "conviction_b": opposing.statement if opposing else t.opposing_conviction,
                    "relationship": t.relationship,
                    "note": t.note,
                })

    # 回溯原話
    signal_results = recall(owner_id, topic, limit=6, config=cfg)

    return {
        "topic": topic,
        "convictions": [
            {
                "conviction_id": c.conviction_id,
                "statement": c.statement,
                "strength": c.strength.score,
                "level": c.strength.level,
                "trend": c.strength.trend,
                "domains": c.domains,
                "relevance": round(1 - d, 2),
            }
            for c, d in related_convictions
        ],
        "traces": [
            {
                "trace_id": t.trace_id,
                "situation": t.trigger.situation,
                "style": t.reasoning_path.style,
                "steps": [s.action for s in t.reasoning_path.steps],
                "conclusion": t.conclusion.decision,
                "confidence": t.conclusion.confidence,
                "date": t.source.date,
                "context": t.source.context,
            }
            for t in related_traces
        ],
        "frames": [
            {
                "frame_id": f.frame_id,
                "name": f.name,
                "description": f.description,
                "preferred_style": f.reasoning_patterns.preferred_style,
                "tone": f.voice.tone if f.voice else None,
            }
            for f in related_frames
        ],
        "tensions": tensions,
        "raw_signals": signal_results[:6],
    }


# ─── 3. Evolution（演變追蹤）───


def evolution(
    owner_id: str,
    topic: str,
    config: dict | None = None,
) -> dict:
    """追蹤某主題的信念演變軌跡。"""
    cfg = config or load_config()
    owner_dir = get_owner_dir(cfg, owner_id)
    store = SignalStore(cfg, owner_id)

    convictions = _load_convictions(owner_dir)
    traces = _load_traces(owner_dir)

    # 找相關 convictions
    q_emb = store.compute_embedding(topic)

    import chromadb
    chroma_dir = owner_dir / "chroma"
    client = chromadb.PersistentClient(path=str(chroma_dir))

    conviction_map = {c.conviction_id: c for c in convictions}
    related_ids = []
    try:
        col = client.get_collection(name=f"{owner_id}_convictions")
        results = col.query(query_embeddings=[q_emb], n_results=8)
        if results["ids"] and results["ids"][0]:
            for i, cid in enumerate(results["ids"][0]):
                d = results["distances"][0][i] if results.get("distances") else 1.0
                if d < 0.8 and cid in conviction_map:
                    related_ids.append(cid)
    except Exception:
        pass

    # 讀 strength snapshots
    snapshots_path = owner_dir / "strength_snapshots.jsonl"
    snapshots = []
    if snapshots_path.exists():
        with open(snapshots_path) as f:
            for line in f:
                if line.strip():
                    snapshots.append(json.loads(line))

    # 組裝每個 conviction 的 strength 歷史
    conviction_timelines = []
    for cid in related_ids:
        c = conviction_map[cid]
        timeline = []
        for snap in snapshots:
            if cid in snap.get("strengths", {}):
                timeline.append({
                    "date": snap["date"],
                    "strength": snap["strengths"][cid],
                })

        conviction_timelines.append({
            "conviction_id": cid,
            "statement": c.statement,
            "current_strength": c.strength.score,
            "current_level": c.strength.level,
            "trend": c.strength.trend,
            "first_detected": c.lifecycle.first_detected,
            "strength_history": timeline,
        })

    # 相關 traces 按時間排列
    trace_map = {t.trace_id: t for t in traces}
    related_traces = []
    try:
        col = client.get_collection(name=f"{owner_id}_traces")
        results = col.query(query_embeddings=[q_emb], n_results=15)
        if results["ids"] and results["ids"][0]:
            for tid in results["ids"][0]:
                if tid in trace_map:
                    related_traces.append(trace_map[tid])
    except Exception:
        pass

    related_traces.sort(key=lambda t: t.source.date)

    # 推理風格隨時間的變化
    style_by_period: dict[str, list[str]] = {}
    for t in related_traces:
        period = t.source.date[:7]  # YYYY-MM
        style_by_period.setdefault(period, []).append(t.reasoning_path.style)

    style_evolution = []
    for period in sorted(style_by_period.keys()):
        counts = Counter(style_by_period[period])
        dominant = counts.most_common(1)[0][0]
        style_evolution.append({"period": period, "dominant_style": dominant, "count": dict(counts)})

    return {
        "topic": topic,
        "convictions": conviction_timelines,
        "traces_timeline": [
            {
                "trace_id": t.trace_id,
                "date": t.source.date,
                "situation": t.trigger.situation,
                "style": t.reasoning_path.style,
                "conclusion": t.conclusion.decision,
            }
            for t in related_traces
        ],
        "style_evolution": style_evolution,
    }


# ─── 4. Blind Spots（盲區偵測）───


def blindspots(
    owner_id: str,
    config: dict | None = None,
) -> dict:
    """偵測思維盲區：說做不一致、單方向信念、思維慣性等。"""
    cfg = config or load_config()
    owner_dir = get_owner_dir(cfg, owner_id)
    store = SignalStore(cfg, owner_id)

    convictions = _load_convictions(owner_dir)
    traces = _load_traces(owner_dir)
    frames = _load_frames(owner_dir)
    signals = store.load_all()

    # --- 1. 說做不一致（有 action_alignment 為 false 的信念）---
    say_do_gaps = []
    for c in convictions:
        ev = c.resonance_evidence
        if ev.action_alignment:
            misaligned = [a for a in ev.action_alignment if a.aligned is False]
            if misaligned:
                say_do_gaps.append({
                    "conviction": c.statement,
                    "strength": c.strength.score,
                    "misaligned_count": len(misaligned),
                })

    # --- 2. 只輸出沒輸入（常講但從不吸收）---
    output_only = []
    for c in convictions:
        if c.strength.score < 0.3:
            continue
        signal_ids: set[str] = set()
        ev = c.resonance_evidence
        for source_list in [
            ev.temporal_persistence or [],
            ev.cross_context_consistency or [],
            ev.spontaneous_mentions or [],
        ]:
            for item in source_list:
                if hasattr(item, "signal_ids"):
                    signal_ids.update(item.signal_ids)
                elif hasattr(item, "signal_id"):
                    signal_ids.add(item.signal_id)

        signal_map = {s.signal_id: s for s in signals if s.signal_id in signal_ids}
        directions = {s.direction for s in signal_map.values()}
        if directions == {"output"}:
            output_only.append({
                "conviction": c.statement,
                "strength": c.strength.score,
                "note": "常講但從未吸收相關輸入",
            })

    # --- 3. 只輸入沒輸出（大量閱讀但從未表態）---
    # 統計各 topic 的 input/output 比例
    topic_directions: dict[str, dict[str, int]] = {}
    for s in signals:
        if s.topics:
            for t in s.topics:
                topic_directions.setdefault(t, {"input": 0, "output": 0})
                topic_directions[t][s.direction] += 1

    input_heavy = []
    for topic, counts in topic_directions.items():
        total = counts["input"] + counts["output"]
        if total >= 5 and counts["input"] > 0 and counts["output"] == 0:
            input_heavy.append({
                "topic": topic,
                "input_count": counts["input"],
                "output_count": counts["output"],
                "note": "大量吸收但從未表態",
            })

    # --- 4. 矛盾張力 ---
    tensions = []
    conviction_map = {c.conviction_id: c for c in convictions}
    for c in convictions:
        if c.tensions:
            for t in c.tensions:
                if t.relationship == "contradiction":
                    opposing = conviction_map.get(t.opposing_conviction)
                    tensions.append({
                        "conviction_a": c.statement,
                        "conviction_b": opposing.statement if opposing else t.opposing_conviction,
                        "note": t.note,
                    })

    # --- 5. 思維慣性（推理風格分佈）---
    style_counts = Counter(t.reasoning_path.style for t in traces)
    total_traces = len(traces)
    style_distribution = {
        style: {"count": count, "ratio": round(count / total_traces, 2) if total_traces else 0}
        for style, count in style_counts.most_common()
    }

    dominant_style = style_counts.most_common(1)[0] if style_counts else None
    thinking_inertia = None
    if dominant_style and total_traces > 10:
        ratio = dominant_style[1] / total_traces
        if ratio > 0.4:
            thinking_inertia = {
                "dominant_style": dominant_style[0],
                "ratio": round(ratio, 2),
                "note": f"推理風格過度集中在 {dominant_style[0]}（{round(ratio*100)}%），可能有思維慣性",
            }

    # --- 6. 框架缺口 ---
    frame_contexts = set()
    for f in frames:
        for tp in f.trigger_patterns:
            if tp.audience_type:
                frame_contexts.update(tp.audience_type)

    signal_contexts = set(s.source.context for s in signals)
    # 簡單判斷：有 signal 的情境但沒有 frame 覆蓋
    # （這是粗略判斷，精確版需要 trace → frame 映射）

    return {
        "say_do_gaps": say_do_gaps,
        "output_only_convictions": output_only,
        "input_heavy_topics": sorted(input_heavy, key=lambda x: -x["input_count"])[:10],
        "contradictions": tensions,
        "style_distribution": style_distribution,
        "thinking_inertia": thinking_inertia,
        "total_traces_analyzed": total_traces,
        "total_convictions_analyzed": len(convictions),
    }


# ─── 5. Connections（關係圖譜）───


def connections(
    owner_id: str,
    topic_a: str,
    topic_b: str,
    config: dict | None = None,
) -> dict:
    """找兩個主題之間的隱性連結。"""
    cfg = config or load_config()
    owner_dir = get_owner_dir(cfg, owner_id)
    store = SignalStore(cfg, owner_id)

    convictions = _load_convictions(owner_dir)
    traces = _load_traces(owner_dir)
    frames = _load_frames(owner_dir)

    import chromadb
    chroma_dir = owner_dir / "chroma"
    client = chromadb.PersistentClient(path=str(chroma_dir))
    conviction_map = {c.conviction_id: c for c in convictions}

    emb_a = store.compute_embedding(topic_a)
    emb_b = store.compute_embedding(topic_b)

    def _find_conviction_ids(emb: list[float], limit: int = 8) -> set[str]:
        try:
            col = client.get_collection(name=f"{owner_id}_convictions")
            results = col.query(query_embeddings=[emb], n_results=limit)
            if results["ids"] and results["ids"][0]:
                ids = set()
                for i, cid in enumerate(results["ids"][0]):
                    d = results["distances"][0][i] if results.get("distances") else 1.0
                    if d < 0.8:
                        ids.add(cid)
                return ids
        except Exception:
            pass
        return set()

    def _find_trace_ids(emb: list[float], limit: int = 8) -> set[str]:
        try:
            col = client.get_collection(name=f"{owner_id}_traces")
            results = col.query(query_embeddings=[emb], n_results=limit)
            if results["ids"] and results["ids"][0]:
                return set(results["ids"][0])
        except Exception:
            pass
        return set()

    ids_a = _find_conviction_ids(emb_a)
    ids_b = _find_conviction_ids(emb_b)
    shared_conviction_ids = ids_a & ids_b

    trace_ids_a = _find_trace_ids(emb_a)
    trace_ids_b = _find_trace_ids(emb_b)
    shared_trace_ids = trace_ids_a & trace_ids_b

    # 找共用的 frames
    frame_ids_a = set()
    frame_ids_b = set()
    for f in frames:
        primary_ids = {ca.conviction_id for ca in f.conviction_profile.primary_convictions}
        if primary_ids & ids_a:
            frame_ids_a.add(f.frame_id)
        if primary_ids & ids_b:
            frame_ids_b.add(f.frame_id)
    shared_frame_ids = frame_ids_a & frame_ids_b

    # 找 tension 連結（A 的信念跟 B 的信念有 tension）
    tension_links = []
    for cid_a in ids_a:
        c = conviction_map.get(cid_a)
        if c and c.tensions:
            for t in c.tensions:
                if t.opposing_conviction in ids_b:
                    opposing = conviction_map.get(t.opposing_conviction)
                    tension_links.append({
                        "from_topic": topic_a,
                        "conviction_a": c.statement,
                        "to_topic": topic_b,
                        "conviction_b": opposing.statement if opposing else t.opposing_conviction,
                        "relationship": t.relationship,
                    })

    trace_map = {t.trace_id: t for t in traces}

    return {
        "topic_a": topic_a,
        "topic_b": topic_b,
        "shared_convictions": [
            {"conviction_id": cid, "statement": conviction_map[cid].statement, "strength": conviction_map[cid].strength.score}
            for cid in shared_conviction_ids if cid in conviction_map
        ],
        "shared_traces": [
            {
                "trace_id": tid,
                "situation": trace_map[tid].trigger.situation,
                "conclusion": trace_map[tid].conclusion.decision,
                "date": trace_map[tid].source.date,
            }
            for tid in shared_trace_ids if tid in trace_map
        ],
        "shared_frames": [
            {"frame_id": fid, "name": next(f.name for f in frames if f.frame_id == fid)}
            for fid in shared_frame_ids
        ],
        "tension_links": tension_links,
        "connection_strength": {
            "shared_convictions": len(shared_conviction_ids),
            "shared_traces": len(shared_trace_ids),
            "shared_frames": len(shared_frame_ids),
            "tension_links": len(tension_links),
        },
    }


# ─── 6. Simulate（模擬預測）───


def simulate(
    owner_id: str,
    scenario: str,
    context: str | None = None,
    config: dict | None = None,
) -> dict:
    """模擬這個人在假設情境下的反應路徑。"""
    cfg = config or load_config()

    # 用 explore 取得相關的五層資料
    explored = explore(owner_id, scenario, depth="full", config=cfg)

    # 用 blindspots 取得可能的盲區提醒
    spots = blindspots(owner_id, config=cfg)

    # 組裝 context 給 LLM
    conviction_lines = []
    for c in explored["convictions"]:
        conviction_lines.append(f"- {c['statement']}（strength: {c['strength']}）")
    convictions_text = "\n".join(conviction_lines) if conviction_lines else "（無特定信念）"

    trace_lines = []
    for t in explored["traces"][:5]:
        steps = " → ".join(t["steps"])
        trace_lines.append(f"- [{t['date']}] {t['situation']} → {steps} → {t['conclusion']}")
    traces_text = "\n".join(trace_lines) if trace_lines else "（無相關推理軌跡）"

    frame_info = ""
    if explored["frames"]:
        f = explored["frames"][0]
        frame_info = f"最可能觸發的情境框架：{f['name']}（{f['description']}），推理風格：{f['preferred_style']}，語氣：{f['tone']}"

    tension_lines = []
    for t in explored["tensions"]:
        tension_lines.append(f"- {t['conviction_a']} ↔ {t['conviction_b']}（{t['relationship']}）")
    tensions_text = "\n".join(tension_lines) if tension_lines else "（無內部衝突）"

    inertia_note = ""
    if spots.get("thinking_inertia"):
        inertia_note = f"\n⚠️ 思維慣性提醒：{spots['thinking_inertia']['note']}"

    context_line = f"情境脈絡：{context}" if context else ""

    prompt = f"""你要模擬一個人面對以下假設情境時的反應路徑。不是回答問題，而是預測這個人會怎麼想、怎麼推理、最後做什麼決定。

假設情境：{scenario}
{context_line}

{frame_info}

這個人的相關信念：
{convictions_text}

過去類似情境的推理範例：
{traces_text}

內部信念張力：
{tensions_text}
{inertia_note}

請用以下格式回答：

## 第一反應
（這個人聽到這個情境時的直覺反應，1-2 句）

## 推理路徑
（這個人會怎麼思考這件事，列出 3-5 個推理步驟）

## 最可能的決策
（最終會做什麼決定，以及信心程度：高/中/低）

## 可能忽略的面向
（基於這個人的思維慣性和盲區，他可能會忽略什麼）

## 內部衝突
（這個情境是否會觸發信念之間的張力，如果是，他會怎麼處理）

用第一人稱「我」回答，語氣符合這個人的風格。"""

    response = call_llm(prompt, config=cfg, tier="medium")

    return {
        "scenario": scenario,
        "context": context,
        "simulation": response,
        "triggered_frame": explored["frames"][0]["name"] if explored["frames"] else None,
        "activated_convictions": [c["statement"] for c in explored["convictions"]],
        "relevant_traces": len(explored["traces"]),
        "tensions_involved": len(explored["tensions"]),
        "blindspot_warning": spots.get("thinking_inertia"),
    }
