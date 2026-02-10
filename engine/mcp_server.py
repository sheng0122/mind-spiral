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

mcp = FastMCP("mind-spiral", instructions="Mind Spiral 人類思維模型引擎 — 五層認知架構查詢與內容產出")

_config = load_config()


@mcp.tool()
def mind_spiral_ask(owner_id: str, text: str, caller_id: str | None = None) -> dict:
    """統一入口 — 自動判斷 query（回答問題）或 generate（產出內容）。

    用法範例：
    - "定價怎麼看？" → 自動 query
    - "幫我寫一篇關於創業的短影音腳本" → 自動 generate
    """
    return ask(owner_id=owner_id, text=text, caller=caller_id, config=_config)


@mcp.tool()
def mind_spiral_query(owner_id: str, question: str, caller_id: str | None = None) -> dict:
    """五層感知查詢 — 用這個人的思維方式回答問題。

    回傳包含：response（回答）、matched_frame（命中框架）、activated_convictions（激活信念）等。
    """
    return query(owner_id=owner_id, question=question, caller=caller_id, config=_config)


@mcp.tool()
def mind_spiral_generate(
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
def mind_spiral_stats(owner_id: str) -> dict:
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


@mcp.tool()
def mind_spiral_ingest(
    owner_id: str,
    signals: list[dict],
) -> dict:
    """寫入 signals 到引擎。

    每個 signal dict 需要：signal_id, direction, modality, text, date。
    可選：authority, content_type, confidence, emotion, context, topics, source_file, participants。
    """
    from engine.models import Signal, SignalContent, SignalSource, SignalLifecycle

    store = SignalStore(_config, owner_id)
    parsed = []
    for s in signals:
        signal = Signal(
            owner_id=owner_id,
            signal_id=s["signal_id"],
            direction=s["direction"],
            modality=s["modality"],
            authority=s.get("authority"),
            content=SignalContent(
                text=s["text"],
                type=s.get("content_type", "idea"),
                reasoning=s.get("reasoning"),
                confidence=s.get("confidence"),
                emotion=s.get("emotion"),
            ),
            source=SignalSource(
                date=s["date"],
                context=s.get("context", "other"),
                participants=s.get("participants"),
                source_file=s.get("source_file"),
            ),
            topics=s.get("topics"),
            lifecycle=SignalLifecycle(active=True, created_at=s["date"]),
        )
        parsed.append(signal)

    count = store.ingest(parsed)
    return {"ingested": count, "total_submitted": len(signals)}


if __name__ == "__main__":
    mcp.run()
