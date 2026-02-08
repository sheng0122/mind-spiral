"""Query Engine — 五層感知 RAG

流程：
1. Frame Matching — 反射匹配（關鍵字命中）或 embedding 匹配
2. Conviction Activation — 根據 frame 激活信念組合
3. Trace Retrieval — 用 ChromaDB 向量搜尋找相關推理軌跡
4. Identity Check — 確認不違反身份核心
5. Response Generation — 用該 frame 的語氣和推理風格生成回應

效能設計：
- Frame/Trace 的 embedding 預先建好索引（build_index）
- 查詢時只算一次問題的 embedding，其餘用 ChromaDB 向量搜尋
- 反射匹配命中時完全跳過 embedding 計算
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import chromadb
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


# ─── 索引管理 ───


def build_index(owner_id: str, config: dict) -> dict:
    """預先建立 trace 和 frame 的 ChromaDB 索引。

    應在 cluster / scan-identity 之後執行一次，之後查詢就不用逐一算 embedding。
    回傳統計資訊。
    """
    owner_dir = get_owner_dir(config, owner_id)
    store = SignalStore(config, owner_id)
    chroma_dir = owner_dir / "chroma"
    client = chromadb.PersistentClient(path=str(chroma_dir))

    stats = {"traces_indexed": 0, "frames_indexed": 0}

    # --- Trace 索引 ---
    traces = _load_traces(owner_dir)
    if traces:
        col = client.get_or_create_collection(
            name=f"{owner_id}_traces",
            metadata={"hnsw:space": "cosine"},
        )
        # 清除舊索引重建
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
    store: SignalStore,
    owner_id: str,
    owner_dir: Path,
) -> ContextFrame | None:
    """用 ChromaDB 索引匹配 frame。如果索引不存在則 fallback 到即時計算。"""
    if not frames:
        return None

    frame_map = {f.frame_id: f for f in frames}

    # 嘗試用 ChromaDB 索引
    chroma_dir = owner_dir / "chroma"
    try:
        client = chromadb.PersistentClient(path=str(chroma_dir))
        col = client.get_collection(name=f"{owner_id}_frames")
        q_emb = store.compute_embedding(question)
        results = col.query(query_embeddings=[q_emb], n_results=1)
        if results["ids"] and results["ids"][0]:
            best_id = results["ids"][0][0]
            distance = results["distances"][0][0] if results.get("distances") else 1.0
            # cosine distance: 0 = identical, 2 = opposite. threshold ~0.7 similarity = ~0.3 distance
            if distance < 0.7 and best_id in frame_map:
                return frame_map[best_id]
    except Exception:
        pass

    # Fallback: 即時計算（frame 數量少，不會太慢）
    q_emb = np.array(store.compute_embedding(question))
    best_frame = None
    best_sim = -1.0

    for frame in frames:
        frame_text = f"{frame.name} {frame.description}"
        for tp in frame.trigger_patterns:
            frame_text += f" {tp.pattern}"
        f_emb = np.array(store.compute_embedding(frame_text))
        sim = float(np.dot(q_emb, f_emb) / (np.linalg.norm(q_emb) * np.linalg.norm(f_emb) + 1e-8))
        if sim > best_sim:
            best_sim = sim
            best_frame = frame

    return best_frame if best_sim > 0.3 else None


# ─── Trace Retrieval ───


def _find_relevant_traces(
    question: str,
    frame: ContextFrame | None,
    traces: list[ReasoningTrace],
    store: SignalStore,
    owner_id: str,
    owner_dir: Path,
    limit: int = 5,
) -> list[ReasoningTrace]:
    """用 ChromaDB 索引找相關 traces。如果索引不存在則 fallback。"""
    if not traces:
        return []

    trace_map = {t.trace_id: t for t in traces}

    # 如果有 frame 且 historical_traces 夠多，直接用
    if frame and frame.reasoning_patterns.historical_traces:
        frame_trace_ids = set(frame.reasoning_patterns.historical_traces)
        frame_traces = [t for t in traces if t.trace_id in frame_trace_ids]
        if len(frame_traces) >= limit:
            return frame_traces[:limit]

    # 嘗試用 ChromaDB 索引
    chroma_dir = owner_dir / "chroma"
    try:
        client = chromadb.PersistentClient(path=str(chroma_dir))
        col = client.get_collection(name=f"{owner_id}_traces")
        q_emb = store.compute_embedding(question)
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

    # Fallback: 只用 frame 的 historical_traces（避免逐一算 embedding）
    if frame and frame.reasoning_patterns.historical_traces:
        frame_trace_ids = set(frame.reasoning_patterns.historical_traces)
        return [t for t in traces if t.trace_id in frame_trace_ids][:limit]

    # 最後 fallback: 按日期取最近的
    sorted_traces = sorted(traces, key=lambda t: t.source.date, reverse=True)
    return sorted_traces[:limit]


# ─── Response Generation ───


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

身份核心（底線護欄，只在回答明顯矛盾時修正，不要主動當主旨發揮）：
{identity_text}

這個人在類似情境下的推理範例：
{traces_text}

問題：{ctx.question}

請用這個人的思維方式、推理風格和語氣來回答。
要求：
- 用第一人稱「我」回答
- 內容方向由上述信念和推理軌跡主導，不要總是收束到同一個結論
- 身份核心是底線護欄：只在回答明顯矛盾時修正，不要主動把它當主旨發揮
- 語氣要符合情境框架的設定
- 長度適中（100-300 字）
- 可以引用自己過去的推理邏輯作為佐證"""


def _build_generation_prompt(ctx: QueryContext, output_type: str, extra_instructions: str) -> str:
    """組裝 generation mode 的 prompt。"""
    # 信念
    conviction_lines = []
    for c in ctx.activated_convictions:
        conviction_lines.append(f"- {c.statement}（strength: {c.strength.score}）")
    convictions_text = "\n".join(conviction_lines) if conviction_lines else "（無特定信念激活）"

    # 推理軌跡範例（generation 用更多）
    trace_lines = []
    for t in ctx.relevant_traces[:5]:
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

    # 根據 output_type 設定格式指引
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

{frame_info}

這個人的核心信念：
{convictions_text}

身份核心（底線護欄，只在回答明顯矛盾時修正，不要主動當主旨發揮）：
{identity_text}

這個人在類似情境下的推理範例：
{traces_text}

任務：{ctx.question}

輸出格式：{format_guide}
{extra_block}

要求：
- 用第一人稱「我」撰寫
- 內容方向由上述信念和推理軌跡主導，不要總是收束到同一個結論
- 身份核心是底線護欄，不是每篇都要提到的主旨
- 語氣要符合情境框架的設定
- 要有這個人的個人特色：用詞習慣、常用句式、思考方式
- 論點要具體，用推理軌跡中的邏輯和案例佐證，不要空泛"""


# ─── 主入口 ───


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
        matched = _embedding_match_frame(question, active_frames, store, owner_id, owner_dir)
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

    # Step 3: Trace Retrieval（用 ChromaDB 索引）
    ctx.relevant_traces = _find_relevant_traces(
        question, ctx.matched_frame, traces, store, owner_id, owner_dir,
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
    owner_dir = get_owner_dir(cfg, owner_id)
    store = SignalStore(cfg, owner_id)

    ctx = QueryContext(question=task, caller=caller)

    # 載入各層資料（同 query）
    frames = _load_frames(owner_dir)
    active_frames = [f for f in frames if f.lifecycle and f.lifecycle.status == "active"]
    convictions = _load_convictions(owner_dir)
    conviction_map = {c.conviction_id: c for c in convictions}
    traces = _load_traces(owner_dir)
    identities = _load_identity(owner_dir)

    # Step 1: Frame Matching
    matched = _reflex_match(task, active_frames)
    if matched:
        ctx.matched_frame = matched
        ctx.match_method = "reflex"
    else:
        matched = _embedding_match_frame(task, active_frames, store, owner_id, owner_dir)
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
        sorted_convictions = sorted(convictions, key=lambda c: -c.strength.score)
        ctx.activated_convictions = sorted_convictions[:7]

    # Step 3: Trace Retrieval（generation 用更多 traces）
    ctx.relevant_traces = _find_relevant_traces(
        task, ctx.matched_frame, traces, store, owner_id, owner_dir, limit=8,
    )

    # Step 4: Identity Check
    ctx.identity_constraints = identities

    # Step 5: Generation
    prompt = _build_generation_prompt(ctx, output_type, extra_instructions)
    ctx.response = call_llm(prompt, config=cfg)

    return {
        "content": ctx.response,
        "output_type": output_type,
        "matched_frame": ctx.matched_frame.name if ctx.matched_frame else None,
        "match_method": ctx.match_method,
        "activated_convictions": [c.statement for c in ctx.activated_convictions],
        "relevant_traces": len(ctx.relevant_traces),
        "identity_constraints": [i.core_belief for i in ctx.identity_constraints],
    }
