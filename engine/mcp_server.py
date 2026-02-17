"""Mind Spiral MCP Server — 讓 Claude Desktop 直接呼叫引擎"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from engine.config import load_config
from engine.query_engine import ask, query, generate, build_index
from engine.signal_store import SignalStore
from engine.conviction_detector import _load_convictions
from engine.trace_extractor import _load_traces
from engine.frame_clusterer import _load_frames
from engine.identity_scanner import _load_identity

mcp = FastMCP(
    "joey",
    instructions="Joey 的五層認知架構思維引擎 — 用 Joey 的方式思考、推理、回應、產出內容",
    host="0.0.0.0",
    port=8001,
)

_config = load_config()


@mcp.tool()
def joey_ask(owner_id: str, text: str, caller_id: str | None = None) -> dict:
    """統一入口 — 自動判斷 query（回答問題）或 generate（產出內容）。

    用法範例：
    - "定價怎麼看？" → 自動 query
    - "幫我寫一篇關於創業的短影音腳本" → 自動 generate
    """
    return ask(owner_id=owner_id, text=text, caller=caller_id, config=_config)


@mcp.tool()
def joey_query(owner_id: str, question: str, caller_id: str | None = None) -> dict:
    """五層感知查詢 — 用這個人的思維方式回答問題。

    回傳包含：response（回答）、matched_frame（命中框架）、activated_convictions（激活信念）等。
    """
    return query(owner_id=owner_id, question=question, caller=caller_id, config=_config)


@mcp.tool()
def joey_generate(
    owner_id: str,
    text: str,
    output_type: str = "article",
    caller_id: str | None = None,
) -> dict:
    """Generation Mode — 用五層思維模型產出內容。

    output_type: article（文章）| post（社群貼文）| script（短影音腳本）| decision（決策分析）
    """
    return generate(
        owner_id=owner_id, task=text, output_type=output_type,
        caller=caller_id, config=_config,
    )


@mcp.tool()
def joey_stats(owner_id: str) -> dict:
    """查看五層數據統計。"""
    from engine.config import get_owner_dir

    owner_dir = get_owner_dir(_config, owner_id)
    store = SignalStore(_config, owner_id)

    return {
        "signals": store.stats(),
        "convictions_count": len(_load_convictions(owner_dir)),
        "traces_count": len(_load_traces(owner_dir)),
        "frames_count": len(_load_frames(owner_dir)),
        "identities_count": len(_load_identity(owner_dir)),
    }


# joey_ingest 已封閉 — 寫入功能僅限 owner 透過 HTTP API + Bearer token 操作


@mcp.tool()
def joey_context(
    owner_id: str,
    question: str,
    caller_id: str | None = None,
    conviction_limit: int = 7,
    trace_limit: int = 8,
) -> dict:
    """原料包模式 — 只做五層檢索，不呼叫 LLM，回傳結構化的思維 context。

    回傳信念、推理軌跡、框架、身份約束、原話佐證、寫作風格。
    供外部 Agent 用自己的 LLM 搭配這些原料產出內容。

    用法：當你有自己的 LLM 能力，只需要「這個人的思維原料」時用此 tool。
    """
    from engine.query_engine import context
    return context(owner_id=owner_id, question=question, caller=caller_id,
                   config=_config, conviction_limit=conviction_limit,
                   trace_limit=trace_limit)


@mcp.tool()
def joey_recall(
    owner_id: str,
    text: str,
    context: str | None = None,
    direction: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """記憶回溯 — 搜尋原話，回傳日期、情境、原文。

    用法：「我什麼時候講過定價？」「我在開會時說過什麼關於 AI 的話？」
    """
    from engine.explorer import recall
    return recall(owner_id=owner_id, text=text, context=context, direction=direction,
                  date_from=date_from, date_to=date_to, limit=limit, config=_config)


@mcp.tool()
def joey_explore(owner_id: str, topic: str, depth: str = "full") -> dict:
    """思維展開 — 從主題串連五層資料（信念、推理、框架、張力、原話）。

    depth: lite（只看信念）| full（五層全展開）
    """
    from engine.explorer import explore
    return explore(owner_id=owner_id, topic=topic, depth=depth, config=_config)


@mcp.tool()
def joey_evolution(owner_id: str, topic: str) -> dict:
    """演變追蹤 — 某主題的信念 strength 變化 + 推理風格演變。"""
    from engine.explorer import evolution
    return evolution(owner_id=owner_id, topic=topic, config=_config)


@mcp.tool()
def joey_blindspots(owner_id: str) -> dict:
    """盲區偵測 — 說做不一致、思維慣性、只輸入沒輸出等。"""
    from engine.explorer import blindspots
    return blindspots(owner_id=owner_id, config=_config)


@mcp.tool()
def joey_connections(owner_id: str, topic_a: str, topic_b: str) -> dict:
    """關係圖譜 — 找兩個主題之間的隱性連結（共用信念、推理、框架、張力）。"""
    from engine.explorer import connections
    return connections(owner_id=owner_id, topic_a=topic_a, topic_b=topic_b, config=_config)


@mcp.tool()
def joey_simulate(owner_id: str, scenario: str, context: str | None = None) -> dict:
    """模擬預測 — 假設情境下這個人會怎麼反應、推理、決策。"""
    from engine.explorer import simulate
    return simulate(owner_id=owner_id, scenario=scenario, context=context, config=_config)


if __name__ == "__main__":
    import sys

    transport = "stdio"
    if "--http" in sys.argv:
        transport = "streamable-http"
    elif "--sse" in sys.argv:
        transport = "sse"

    mcp.run(transport=transport)
