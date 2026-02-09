"""Query Engine — 五層感知 RAG

流程：
1. Frame Matching — 反射匹配（關鍵字命中）或 embedding 匹配
2. Conviction Activation — 向量搜尋找最相關信念（有 frame 時從 frame 激活）
3. Trace Retrieval — 用 ChromaDB 向量搜尋找相關推理軌跡
4. Identity Check — 確認不違反身份核心
5. Response Generation — 用該 frame 的語氣和推理風格生成回應

效能設計：
- Frame/Trace/Conviction 的 embedding 預先建好索引（build_index）
- 查詢時只算一次問題的 embedding，其餘用 ChromaDB 向量搜尋
- 反射匹配命中時完全跳過 embedding 計算
- 資料快取：同一 owner 的資料只載入一次，後續查詢直接用記憶體
- ChromaDB client 單例化：同一 owner 共用一個 client
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import chromadb

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
    raw_signals: list[str] = field(default_factory=list)  # 原話佐證
    low_confidence: bool = False  # 信心校準：證據不足時為 True
    is_temporal: bool = False  # 時序查詢標記
    response: str = ""


# ─── 時序偵測 ───

_TEMPORAL_KEYWORDS = [
    "變化", "改變", "以前", "之前", "最近", "一直", "演變", "轉變",
    "過去", "現在", "從前", "後來", "趨勢", "還是一樣", "不一樣了",
]


def _is_temporal_query(question: str) -> bool:
    return any(kw in question for kw in _TEMPORAL_KEYWORDS)


# ─── 快取 + 單例 ───

_cache: dict[str, dict] = {}


def _get_cached(owner_id: str, owner_dir: Path) -> dict:
    """取得或建立該 owner 的快取（資料 + ChromaDB client）。"""
    if owner_id not in _cache:
        chroma_dir = owner_dir / "chroma"
        _cache[owner_id] = {
            "frames": _load_frames(owner_dir),
            "convictions": _load_convictions(owner_dir),
            "traces": _load_traces(owner_dir),
            "identities": _load_identity(owner_dir),
            "conviction_map": {},
            "chroma": chromadb.PersistentClient(path=str(chroma_dir)),
        }
        _cache[owner_id]["conviction_map"] = {
            c.conviction_id: c for c in _cache[owner_id]["convictions"]
        }
    return _cache[owner_id]


def invalidate_cache(owner_id: str | None = None):
    """清除快取。build_index / detect / cluster 後應呼叫。"""
    if owner_id:
        _cache.pop(owner_id, None)
    else:
        _cache.clear()


# ─── 索引管理 ───


def build_index(owner_id: str, config: dict) -> dict:
    """預先建立 trace、frame、conviction 的 ChromaDB 索引。

    應在 cluster / scan-identity / detect 之後執行一次。
    回傳統計資訊。
    """
    owner_dir = get_owner_dir(config, owner_id)
    store = SignalStore(config, owner_id)
    chroma_dir = owner_dir / "chroma"
    client = chromadb.PersistentClient(path=str(chroma_dir))

    stats = {"traces_indexed": 0, "frames_indexed": 0, "convictions_indexed": 0}

    # --- Trace 索引 ---
    traces = _load_traces(owner_dir)
    if traces:
        col = client.get_or_create_collection(
            name=f"{owner_id}_traces",
            metadata={"hnsw:space": "cosine"},
        )
        existing = col.get()
        if existing["ids"]:
            col.delete(ids=existing["ids"])

        ids = []
        documents = []
        metadatas = []
        for t in traces:
            text = f"{t.trigger.situation} {t.conclusion.decision}"
            ids.append(t.trace_id)
            documents.append(text)
            metadatas.append({
                "style": t.reasoning_path.style,
                "stimulus_type": t.trigger.stimulus_type,
                "context": t.source.context or "",
                "date": t.source.date,
            })

        embeddings = store._get_embedder().encode(
            documents, normalize_embeddings=True, show_progress_bar=len(documents) > 50,
        ).tolist()

        col.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
        stats["traces_indexed"] = len(ids)

    # --- Frame 索引 ---
    frames = _load_frames(owner_dir)
    if frames:
        col = client.get_or_create_collection(
            name=f"{owner_id}_frames",
            metadata={"hnsw:space": "cosine"},
        )
        existing = col.get()
        if existing["ids"]:
            col.delete(ids=existing["ids"])

        ids = []
        documents = []
        for f in frames:
            text = f"{f.name} {f.description}"
            for tp in f.trigger_patterns:
                text += f" {tp.pattern}"
            ids.append(f.frame_id)
            documents.append(text)

        embeddings = store._get_embedder().encode(
            documents, normalize_embeddings=True,
        ).tolist()

        col.add(ids=ids, documents=documents, embeddings=embeddings)
        stats["frames_indexed"] = len(ids)

    # --- Conviction 索引 ---
    convictions = _load_convictions(owner_dir)
    if convictions:
        col = client.get_or_create_collection(
            name=f"{owner_id}_convictions",
            metadata={"hnsw:space": "cosine"},
        )
        existing = col.get()
        if existing["ids"]:
            col.delete(ids=existing["ids"])

        ids = []
        documents = []
        metadatas = []
        for c in convictions:
            ids.append(c.conviction_id)
            documents.append(c.statement)
            metadatas.append({
                "domain": ", ".join(c.domains) if c.domains else "",
                "strength": c.strength.score,
                "level": c.strength.level,
            })

        embeddings = store._get_embedder().encode(
            documents, normalize_embeddings=True,
            show_progress_bar=len(documents) > 50,
        ).tolist()

        col.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
        stats["convictions_indexed"] = len(ids)

    # 清除快取，下次查詢會重新載入
    invalidate_cache(owner_id)

    return stats


# ─── Frame Matching ───


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


def _embedding_match_frame(
    question: str,
    frames: list[ContextFrame],
    q_emb: list[float],
    client: chromadb.ClientAPI,
    owner_id: str,
) -> ContextFrame | None:
    """用 ChromaDB 索引匹配 frame。共用 q_emb 和 client。"""
    if not frames:
        return None

    frame_map = {f.frame_id: f for f in frames}

    try:
        col = client.get_collection(name=f"{owner_id}_frames")
        results = col.query(query_embeddings=[q_emb], n_results=1)
        if results["ids"] and results["ids"][0]:
            best_id = results["ids"][0][0]
            distance = results["distances"][0][0] if results.get("distances") else 1.0
            if distance < 0.7 and best_id in frame_map:
                return frame_map[best_id]
    except Exception:
        pass

    return None


# ─── Conviction Activation（向量搜尋） ───


def _find_relevant_convictions(
    q_emb: list[float],
    client: chromadb.ClientAPI,
    owner_id: str,
    conviction_map: dict[str, Conviction],
    limit: int = 5,
) -> list[Conviction]:
    """用 ChromaDB 索引找跟問題最相關的 convictions。"""
    try:
        col = client.get_collection(name=f"{owner_id}_convictions")
        results = col.query(query_embeddings=[q_emb], n_results=limit)
        if results["ids"] and results["ids"][0]:
            found = []
            for cid in results["ids"][0]:
                if cid in conviction_map:
                    found.append(conviction_map[cid])
            if found:
                return found
    except Exception:
        pass

    # Fallback: strength 最高的（索引不存在時）
    sorted_convictions = sorted(conviction_map.values(), key=lambda c: -c.strength.score)
    return sorted_convictions[:limit]


# ─── Trace Retrieval ───


def _find_relevant_traces(
    q_emb: list[float],
    frame: ContextFrame | None,
    client: chromadb.ClientAPI,
    owner_id: str,
    trace_map: dict[str, ReasoningTrace],
    limit: int = 5,
) -> list[ReasoningTrace]:
    """用 ChromaDB 索引找相關 traces。共用 q_emb 和 client。"""
    # 如果有 frame 且 historical_traces 夠多，直接用
    if frame and frame.reasoning_patterns.historical_traces:
        frame_trace_ids = set(frame.reasoning_patterns.historical_traces)
        frame_traces = [t for tid, t in trace_map.items() if tid in frame_trace_ids]
        if len(frame_traces) >= limit:
            return frame_traces[:limit]

    try:
        col = client.get_collection(name=f"{owner_id}_traces")
        results = col.query(query_embeddings=[q_emb], n_results=limit)
        if results["ids"] and results["ids"][0]:
            found = []
            for tid in results["ids"][0]:
                if tid in trace_map:
                    found.append(trace_map[tid])
            if found:
                return found
    except Exception:
        pass

    # Fallback: frame 的 historical_traces
    if frame and frame.reasoning_patterns.historical_traces:
        frame_trace_ids = set(frame.reasoning_patterns.historical_traces)
        return [t for tid, t in trace_map.items() if tid in frame_trace_ids][:limit]

    # 最後 fallback: 按日期取最近的
    sorted_traces = sorted(trace_map.values(), key=lambda t: t.source.date, reverse=True)
    return sorted_traces[:limit]


def _find_temporal_traces(
    q_emb: list[float],
    client: chromadb.ClientAPI,
    owner_id: str,
    trace_map: dict[str, ReasoningTrace],
    limit: int = 6,
) -> list[ReasoningTrace]:
    """時序查詢：取相關 traces 後按時間分散，讓 LLM 看到變化軌跡。"""
    # 先用向量搜尋拿較多候選
    candidates = []
    try:
        col = client.get_collection(name=f"{owner_id}_traces")
        results = col.query(query_embeddings=[q_emb], n_results=min(limit * 3, len(trace_map)))
        if results["ids"] and results["ids"][0]:
            for tid in results["ids"][0]:
                if tid in trace_map:
                    candidates.append(trace_map[tid])
    except Exception:
        candidates = list(trace_map.values())

    if not candidates:
        return []

    # 按日期排序，取最早、中間、最近各 1/3
    candidates.sort(key=lambda t: t.source.date)
    n = len(candidates)
    if n <= limit:
        return candidates

    third = max(1, limit // 3)
    early = candidates[:third]
    recent = candidates[-third:]
    mid_start = n // 3
    mid_end = 2 * n // 3
    middle = candidates[mid_start:mid_end][:limit - 2 * third]
    return early + middle + recent


# ─── Signal 回溯 ───


def _collect_raw_signals(
    convictions: list[Conviction],
    store: SignalStore,
    max_signals: int = 6,
) -> list[str]:
    """從被激活的 convictions 回溯原始 signal 文本。用 ChromaDB get by ID，不做 vector search。"""
    signal_ids: list[str] = []
    for c in convictions:
        ev = c.resonance_evidence
        for source_list in [
            ev.temporal_persistence or [],
            ev.cross_context_consistency or [],
            ev.input_output_convergence or [],
            ev.spontaneous_mentions or [],
            ev.action_alignment or [],
        ]:
            for item in source_list:
                if hasattr(item, "signal_ids"):
                    signal_ids.extend(item.signal_ids[:2])
        if len(signal_ids) >= max_signals * 2:
            break

    if not signal_ids:
        return []

    # 去重，保持順序
    seen = set()
    unique_ids = []
    for sid in signal_ids:
        if sid not in seen:
            seen.add(sid)
            unique_ids.append(sid)
    unique_ids = unique_ids[:max_signals]

    # ChromaDB get by ID — O(1)，不是 vector search
    try:
        col = store._collection
        results = col.get(ids=unique_ids)
        return results.get("documents", []) or []
    except Exception:
        return []


# ─── 信心校準 ───


def _check_low_confidence(
    q_emb: list[float],
    client: chromadb.ClientAPI,
    owner_id: str,
    distance_threshold: float = 0.8,
) -> bool:
    """檢查最相關的 conviction 和 trace 是否都離問題太遠。"""
    try:
        for col_name in [f"{owner_id}_convictions", f"{owner_id}_traces"]:
            col = client.get_collection(name=col_name)
            results = col.query(query_embeddings=[q_emb], n_results=1)
            if results["distances"] and results["distances"][0]:
                if results["distances"][0][0] < distance_threshold:
                    return False  # 至少有一個夠近
        return True  # 全部都太遠
    except Exception:
        return False  # 索引不存在時不標記


# ─── Response Generation ───


def _build_common_context(ctx: QueryContext) -> dict[str, str]:
    """組裝共用的 prompt 素材，query 和 generate 共用。"""
    # 信念
    conviction_lines = []
    for c in ctx.activated_convictions:
        conviction_lines.append(f"- {c.statement}（strength: {c.strength.score}）")
    convictions_text = "\n".join(conviction_lines) if conviction_lines else "（無特定信念激活）"

    # 推理軌跡範例
    trace_lines = []
    trace_limit = 5 if not ctx.is_temporal else len(ctx.relevant_traces)
    for t in ctx.relevant_traces[:trace_limit]:
        steps = " → ".join(s.action for s in t.reasoning_path.steps)
        date_prefix = f"[{t.source.date}] " if ctx.is_temporal else ""
        trace_lines.append(
            f"- {date_prefix}情境：{t.trigger.situation}\n"
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

    # 原話佐證（signal 回溯）
    raw_signals_text = ""
    if ctx.raw_signals:
        signal_lines = [f"- 「{s[:150]}」" for s in ctx.raw_signals if s]
        if signal_lines:
            raw_signals_text = "這個人說過的原話（佐證，可適度引用）：\n" + "\n".join(signal_lines)

    # 信心校準
    confidence_note = ""
    if ctx.low_confidence:
        confidence_note = (
            "\n⚠️ 注意：此問題的相關記錄很少。如果你不確定這個人的立場，"
            "請坦承「這方面我沒有明確想法」或「我不太確定」，而非猜測。\n"
        )

    # 時序提示
    temporal_note = ""
    if ctx.is_temporal:
        temporal_note = (
            "\n📅 這是一個關於時間變化的問題。上方推理軌跡已按時間排列，"
            "請關注不同時期的差異和演變趨勢，不要只取最近的觀點。\n"
        )

    return {
        "convictions_text": convictions_text,
        "traces_text": traces_text,
        "identity_text": identity_text,
        "frame_info": frame_info,
        "raw_signals_text": raw_signals_text,
        "confidence_note": confidence_note,
        "temporal_note": temporal_note,
        "caller_info": f"提問者：{ctx.caller}" if ctx.caller else "",
    }


def _build_response_prompt(ctx: QueryContext) -> str:
    """組裝最終的回應生成 prompt。"""
    p = _build_common_context(ctx)

    return f"""你現在要模擬一個人的思維方式來回答問題。

{p["frame_info"]}
{p["caller_info"]}

這個人的核心信念：
{p["convictions_text"]}

身份核心（底線護欄，只在回答明顯矛盾時修正，不要主動當主旨發揮）：
{p["identity_text"]}

這個人在類似情境下的推理範例：
{p["traces_text"]}

{p["raw_signals_text"]}
{p["confidence_note"]}{p["temporal_note"]}
問題：{ctx.question}

請用這個人的思維方式、推理風格和語氣來回答。
要求：
- 用第一人稱「我」回答
- 內容方向由上述信念和推理軌跡主導，不要總是收束到同一個結論
- 身份核心是底線護欄：只在回答明顯矛盾時修正，不要主動把它當主旨發揮
- 語氣要符合情境框架的設定
- 長度適中（100-300 字）
- 可以引用自己過去的推理邏輯或原話作為佐證"""


def _build_generation_prompt(ctx: QueryContext, output_type: str, extra_instructions: str) -> str:
    """組裝 generation mode 的 prompt。"""
    p = _build_common_context(ctx)

    type_guides = {
        "article": (
            "寫一篇完整文章。結構要有吸引人的開頭（用故事、問題或反直覺觀點切入）、"
            "有邏輯的中段（用信念和推理軌跡展開論述，穿插個人經驗和具體案例）、"
            "有力的結尾（回扣核心信念，給讀者明確行動方向）。"
            "長度：800-1500 字。"
        ),
        "post": (
            "寫一則社群貼文。開頭要有鉤子（一句話抓住注意力），"
            "中間用短句、分段，保持節奏感，結尾帶 call to action 或引發討論。"
            "長度：200-400 字。"
        ),
        "decision": (
            "針對這個決策情境，用這個人的推理方式做分析。"
            "列出核心考量、用信念和推理風格權衡選項，給出明確建議和下一步行動。"
            "長度：300-600 字。"
        ),
        "script": (
            "寫一段短影音腳本。開頭 3 秒要有吸引力的 hook，"
            "中間用口語化表達，節奏快，每段一個重點，"
            "結尾帶 CTA（按讚、留言、追蹤）。"
            "長度：200-400 字，標註分段和預估秒數。"
        ),
    }
    format_guide = type_guides.get(output_type, type_guides["article"])

    extra_block = f"\n額外要求：{extra_instructions}" if extra_instructions else ""

    return f"""你現在要用一個人的思維方式和風格來產出內容。

{p["frame_info"]}

這個人的核心信念：
{p["convictions_text"]}

身份核心（底線護欄，只在回答明顯矛盾時修正，不要主動當主旨發揮）：
{p["identity_text"]}

這個人在類似情境下的推理範例：
{p["traces_text"]}

{p["raw_signals_text"]}
{p["confidence_note"]}{p["temporal_note"]}
任務：{ctx.question}

輸出格式：{format_guide}
{extra_block}

要求：
- 用第一人稱「我」撰寫
- 內容方向由上述信念和推理軌跡主導，不要總是收束到同一個結論
- 身份核心是底線護欄，不是每篇都要提到的主旨
- 語氣要符合情境框架的設定
- 要有這個人的個人特色：用詞習慣、常用句式、思考方式
- 論點要具體，用推理軌跡中的邏輯、案例或原話佐證，不要空泛"""


# ─── 主入口 ───


def _run_five_layer_pipeline(
    owner_id: str,
    question: str,
    caller: str | None,
    cfg: dict,
    conviction_limit: int = 5,
    trace_limit: int = 5,
) -> QueryContext:
    """共用的五層感知 pipeline，query 和 generate 都走這裡。"""
    owner_dir = get_owner_dir(cfg, owner_id)
    store = SignalStore(cfg, owner_id)
    cached = _get_cached(owner_id, owner_dir)

    ctx = QueryContext(question=question, caller=caller)

    frames = cached["frames"]
    active_frames = [f for f in frames if f.lifecycle and f.lifecycle.status == "active"]
    conviction_map = cached["conviction_map"]
    trace_map = {t.trace_id: t for t in cached["traces"]}
    client = cached["chroma"]

    # Step 1: Frame Matching（反射優先，命中則跳過 embedding）
    matched = _reflex_match(question, active_frames)
    if matched:
        ctx.matched_frame = matched
        ctx.match_method = "reflex"

    # 只算一次 embedding，反射命中時不算
    q_emb = None
    if not ctx.matched_frame:
        q_emb = store.compute_embedding(question)
        matched = _embedding_match_frame(question, active_frames, q_emb, client, owner_id)
        if matched:
            ctx.matched_frame = matched
            ctx.match_method = "embedding"

    # Step 2: Conviction Activation（向量搜尋取代 top-strength）
    if ctx.matched_frame:
        for ca in ctx.matched_frame.conviction_profile.primary_convictions:
            conv = conviction_map.get(ca.conviction_id)
            if conv:
                ctx.activated_convictions.append(conv)
    if not ctx.activated_convictions:
        # frame 沒激活到 conviction 或沒命中 frame → 用向量搜尋
        if q_emb is None:
            q_emb = store.compute_embedding(question)
        ctx.activated_convictions = _find_relevant_convictions(
            q_emb, client, owner_id, conviction_map, limit=conviction_limit,
        )

    # Step 3: Trace Retrieval（時序查詢走不同路徑）
    if q_emb is None:
        q_emb = store.compute_embedding(question)
    ctx.is_temporal = _is_temporal_query(question)
    if ctx.is_temporal:
        ctx.relevant_traces = _find_temporal_traces(
            q_emb, client, owner_id, trace_map, limit=trace_limit,
        )
    else:
        ctx.relevant_traces = _find_relevant_traces(
            q_emb, ctx.matched_frame, client, owner_id, trace_map, limit=trace_limit,
        )

    # Step 4: Identity Check
    ctx.identity_constraints = cached["identities"]

    # Step 5: Signal 回溯（從 conviction 拿原話佐證）
    ctx.raw_signals = _collect_raw_signals(ctx.activated_convictions, store)

    # Step 6: 信心校準（檢查匹配品質）
    ctx.low_confidence = _check_low_confidence(q_emb, client, owner_id)

    return ctx


def query(
    owner_id: str,
    question: str,
    caller: str | None = None,
    config: dict | None = None,
) -> dict:
    """主入口：五層感知查詢。"""
    from engine.config import load_config
    cfg = config or load_config()

    ctx = _run_five_layer_pipeline(owner_id, question, caller, cfg,
                                    conviction_limit=5, trace_limit=5)

    # Step 5: Response Generation（五層 context 已精準，Sonnet 足夠）
    prompt = _build_response_prompt(ctx)
    ctx.response = call_llm(prompt, config=cfg, tier="medium")

    return {
        "response": ctx.response,
        "matched_frame": ctx.matched_frame.name if ctx.matched_frame else None,
        "match_method": ctx.match_method,
        "activated_convictions": [c.statement for c in ctx.activated_convictions],
        "relevant_traces": len(ctx.relevant_traces),
        "identity_constraints": [i.core_belief for i in ctx.identity_constraints],
    }


def _classify_intent(text: str) -> dict:
    """用關鍵字快速判斷意圖：query vs generate + output_type。"""
    t = text.lower()

    # 明確產出指令
    gen_signals = {
        "script": ["腳本", "script", "短影音腳本", "影片腳本"],
        "article": ["寫一篇", "幫我寫", "寫文章", "寫文", "撰寫", "產出文章", "寫稿"],
        "post": ["貼文", "發文", "社群貼文", "po文", "fb貼文", "ig貼文", "threads"],
        "decision": ["幫我決定", "該選哪個", "怎麼選", "決策分析", "幫我分析要不要"],
    }

    for output_type, keywords in gen_signals.items():
        for kw in keywords:
            if kw in t:
                return {"mode": "generate", "output_type": output_type}

    # 預設 query
    return {"mode": "query", "output_type": None}


def ask(
    owner_id: str,
    text: str,
    caller: str | None = None,
    config: dict | None = None,
) -> dict:
    """統一入口 — 自動判斷 query 或 generate，路由到對應模式。"""
    intent = _classify_intent(text)

    if intent["mode"] == "generate":
        result = generate(owner_id, text, output_type=intent["output_type"],
                          caller=caller, config=config)
        result["mode"] = "generate"
        return result
    else:
        result = query(owner_id, text, caller=caller, config=config)
        result["mode"] = "query"
        return result


def generate(
    owner_id: str,
    task: str,
    output_type: str = "article",
    extra_instructions: str = "",
    caller: str | None = None,
    config: dict | None = None,
) -> dict:
    """Generation Mode — 用五層思維模型產出內容或做決策。

    output_type: article | post | decision | script
    """
    from engine.config import load_config
    cfg = config or load_config()

    ctx = _run_five_layer_pipeline(owner_id, task, caller, cfg,
                                    conviction_limit=7, trace_limit=8)

    # Step 5: Generation（五層 context 已精準，Sonnet 足夠）
    prompt = _build_generation_prompt(ctx, output_type, extra_instructions)
    ctx.response = call_llm(prompt, config=cfg, tier="medium")

    return {
        "content": ctx.response,
        "output_type": output_type,
        "matched_frame": ctx.matched_frame.name if ctx.matched_frame else None,
        "match_method": ctx.match_method,
        "activated_convictions": [c.statement for c in ctx.activated_convictions],
        "relevant_traces": len(ctx.relevant_traces),
        "identity_constraints": [i.core_belief for i in ctx.identity_constraints],
    }
