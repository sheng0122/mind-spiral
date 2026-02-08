"""Mind Spiral CLI"""

import json

import click

from engine.config import load_config
from engine.signal_store import SignalStore


@click.group()
def cli():
    """Mind Spiral — 人類思維模型引擎"""
    pass


@cli.command()
@click.option("--owner", required=True, help="使用者 ID")
def stats(owner: str):
    """顯示各層統計資訊"""
    config = load_config()
    store = SignalStore(config, owner)
    result = store.stats()

    if result["total"] == 0:
        click.echo(f"[{owner}] 沒有任何 signals")
        return

    click.echo(f"\n=== {owner} 的 Signal 統計 ===")
    click.echo(f"Signals: {result['total']}")
    click.echo(f"\ndirection:")
    for k, v in result.get("direction", {}).items():
        click.echo(f"  {k}: {v}")
    click.echo(f"\nmodality:")
    for k, v in result.get("modality", {}).items():
        click.echo(f"  {k}: {v}")
    click.echo(f"\nauthority:")
    for k, v in result.get("authority", {}).items():
        click.echo(f"  {k}: {v}")
    click.echo(f"\ncontent_type:")
    for k, v in result.get("content_type", {}).items():
        click.echo(f"  {k}: {v}")
    if result.get("date_range"):
        dr = result["date_range"]
        click.echo(f"\ndate_range: {dr['earliest']} ~ {dr['latest']}")
    if result.get("top_topics"):
        click.echo(f"\ntop topics:")
        for topic, count in result["top_topics"][:10]:
            click.echo(f"  {topic}: {count}")
    click.echo(f"\nChromaDB vectors: {result.get('chroma_count', 0)}")


@cli.command()
@click.option("--owner", required=True)
@click.argument("text")
@click.option("-n", default=5, help="回傳數量")
@click.option("--direction", type=click.Choice(["input", "output"]), default=None)
def search(owner: str, text: str, n: int, direction: str | None):
    """語意搜尋 signals"""
    config = load_config()
    store = SignalStore(config, owner)
    results = store.query(text=text, direction=direction, n_results=n)

    if not results:
        click.echo("沒有找到相關 signals")
        return

    for i, s in enumerate(results, 1):
        click.echo(f"\n--- [{i}] {s.signal_id} ---")
        click.echo(f"  direction: {s.direction} | modality: {s.modality}")
        click.echo(f"  content: {s.content.text[:100]}")
        click.echo(f"  date: {s.source.date} | context: {s.source.context}")


@cli.command()
@click.option("--owner", required=True, help="使用者 ID")
def detect(owner: str):
    """偵測 convictions（embedding 聚類 + 共鳴收斂）"""
    from engine.conviction_detector import detect as run_detect

    config = load_config()
    new_convictions = run_detect(owner, config)

    if not new_convictions:
        click.echo(f"[{owner}] 沒有新的 conviction 候選")
        return

    click.echo(f"\n=== 新偵測到 {len(new_convictions)} 個 convictions ===")
    for c in new_convictions:
        click.echo(f"\n  [{c.conviction_id}]")
        click.echo(f"  statement: {c.statement}")
        click.echo(f"  strength: {c.strength.score} ({c.strength.level})")
        click.echo(f"  domains: {', '.join(c.domains)}")


@cli.command()
@click.option("--owner", required=True, help="使用者 ID")
def daily(owner: str):
    """執行每日批次（detect + contradictions + digest）"""
    from engine.daily_batch import run_daily

    config = load_config()
    click.echo(f"[{owner}] 開始每日批次...")

    result = run_daily(owner, config)

    click.echo(f"\n=== 每日批次完成 ===")
    click.echo(f"  新 convictions: {result['new_convictions']}")
    click.echo(f"  新 traces: {result['new_traces']}")
    click.echo(f"  矛盾偵測: {result['contradictions']}")
    click.echo(f"  決策追蹤: {result['followups']}")

    if result["digest"]:
        click.echo(f"\n--- 今日整理 ---")
        click.echo(result["digest"])
    else:
        click.echo("\n今日無需整理。")


@cli.command()
@click.option("--owner", required=True, help="使用者 ID")
@click.option("--limit", default=None, type=int, help="最多處理幾個 signals")
def extract(owner: str, limit: int | None):
    """從 output signals 提取推理軌跡（Layer 3）"""
    from engine.trace_extractor import extract as run_extract

    config = load_config()
    click.echo(f"[{owner}] 開始提取推理軌跡...")
    new_traces = run_extract(owner, config, limit=limit)

    if not new_traces:
        click.echo("沒有新的推理軌跡")
        return

    click.echo(f"\n=== 提取到 {len(new_traces)} 個推理軌跡 ===")
    for t in new_traces[:10]:
        click.echo(f"\n  [{t.trace_id}]")
        click.echo(f"  trigger: {t.trigger.situation[:80]}")
        click.echo(f"  style: {t.reasoning_path.style}")
        click.echo(f"  conclusion: {t.conclusion.decision[:80]}")
        click.echo(f"  confidence: {t.conclusion.confidence}")


@cli.command()
@click.option("--owner", required=True, help="使用者 ID")
def followups(owner: str):
    """列出待回訪的決策"""
    from engine.decision_tracker import get_pending_followups

    config = load_config()
    pending = get_pending_followups(owner, config)

    if not pending:
        click.echo(f"[{owner}] 沒有待回訪的決策")
        return

    click.echo(f"\n=== {len(pending)} 個待回訪決策 ===")
    for p in pending:
        click.echo(f"\n  [{p['trace_id']}] {p['days_ago']} 天前")
        click.echo(f"  決策: {p['decision'][:80]}")
        click.echo(f"  信心: {p['confidence']}")
        click.echo(f"  情境: {p['trigger'][:60]}")


@cli.command()
@click.option("--owner", required=True, help="使用者 ID")
@click.option("--trace-id", required=True, help="Trace ID")
@click.option("--result", required=True, type=click.Choice(["positive", "negative", "mixed", "unknown"]))
@click.option("--note", default=None, help="補充說明")
def outcome(owner: str, trace_id: str, result: str, note: str | None):
    """記錄決策結果（螺旋回饋）"""
    from engine.decision_tracker import record_outcome as do_record

    config = load_config()
    res = do_record(owner, trace_id, result, note, config)

    if "error" in res:
        click.echo(f"錯誤: {res['error']}")
        return

    click.echo(f"已記錄 {trace_id} 的結果: {result}")
    if res.get("convictions_updated"):
        click.echo(f"已更新 {len(res['convictions_updated'])} 個 conviction 的 strength")


@cli.command()
@click.option("--owner", required=True, help="使用者 ID")
def weekly(owner: str):
    """生成信念週報"""
    from engine.daily_batch import run_weekly

    config = load_config()
    click.echo(f"[{owner}] 生成信念週報...")

    result = run_weekly(owner, config)

    if result["report"]:
        click.echo(f"\n--- 信念週報 ({result.get('week_start', '')} ~ {result['date']}) ---")
        click.echo(result["report"])
        click.echo(f"\n新信念: {result['new_convictions']} | 強化: {result['reinforced']} | 新軌跡: {result['new_traces']} | 張力: {result['tensions']}")
    else:
        click.echo("本週無顯著變化。")


if __name__ == "__main__":
    cli()
