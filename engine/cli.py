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


if __name__ == "__main__":
    cli()
