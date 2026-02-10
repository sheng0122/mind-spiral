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
    new_convictions, strength_changes = run_detect(owner, config)

    if strength_changes:
        click.echo(f"\n=== {len(strength_changes)} 個信念 strength 變動 ===")
        for sc in strength_changes[:10]:
            sign = "+" if sc["delta"] > 0 else ""
            click.echo(f"  {sc['statement'][:40]}… {sc['old']:.2f} → {sc['new']:.2f}（{sign}{sc['delta']:.2f}）")

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


@cli.command(name="cluster")
@click.option("--owner", required=True, help="使用者 ID")
@click.option("--min-traces", default=3, help="每組最少 traces 數")
def cluster_cmd(owner: str, min_traces: int):
    """從 traces 聚類情境框架（Layer 4）"""
    from engine.frame_clusterer import cluster as run_cluster

    config = load_config()
    click.echo(f"[{owner}] 開始聚類情境框架...")
    new_frames = run_cluster(owner, config, min_traces=min_traces)

    if not new_frames:
        click.echo("沒有新的情境框架")
        return

    click.echo(f"\n=== 聚類出 {len(new_frames)} 個情境框架 ===")
    for f in new_frames:
        click.echo(f"\n  [{f.frame_id}] {f.name}")
        click.echo(f"  描述: {f.description[:80]}")
        click.echo(f"  推理風格: {f.reasoning_patterns.preferred_style}")
        click.echo(f"  主要信念: {len(f.conviction_profile.primary_convictions)} 個")
        if f.voice and f.voice.tone:
            click.echo(f"  語氣: {f.voice.tone}")


@cli.command(name="scan-identity")
@click.option("--owner", required=True, help="使用者 ID")
def scan_identity_cmd(owner: str):
    """掃描身份核心（Layer 5）"""
    from engine.identity_scanner import scan as run_scan

    config = load_config()
    click.echo(f"[{owner}] 開始掃描身份核心...")
    new_identities = run_scan(owner, config)

    if not new_identities:
        click.echo("沒有新的身份核心（可能 frames 不足，或沒有 conviction 達到 80% 覆蓋率）")
        return

    click.echo(f"\n=== 發現 {len(new_identities)} 個身份核心 ===")
    for i in new_identities:
        click.echo(f"\n  [{i.identity_id}] {i.core_belief}")
        click.echo(f"  conviction: {i.conviction_id}")
        click.echo(f"  覆蓋率: {i.universality.coverage:.0%}（{len(i.universality.active_in_frames)}/{i.universality.total_active_frames} frames）")
        click.echo(f"  不可妥協: {'是' if i.non_negotiable else '否'}")


@cli.command(name="build-index")
@click.option("--owner", required=True, help="使用者 ID")
def build_index_cmd(owner: str):
    """建立 trace/frame/conviction 的向量索引（加速查詢）"""
    from engine.query_engine import build_index

    config = load_config()
    click.echo(f"[{owner}] 建立向量索引...")
    stats = build_index(owner, config)
    click.echo(f"  Traces 索引: {stats['traces_indexed']} 筆")
    click.echo(f"  Frames 索引: {stats['frames_indexed']} 筆")
    click.echo(f"  Convictions 索引: {stats['convictions_indexed']} 筆")
    click.echo("索引建立完成，查詢速度已優化。")


@cli.command(name="query")
@click.option("--owner", required=True, help="使用者 ID")
@click.option("--caller", default=None, help="提問者身份")
@click.argument("question")
def query_cmd(owner: str, caller: str | None, question: str):
    """用五層感知回答問題（數位分身）"""
    from engine.query_engine import query as run_query

    config = load_config()
    click.echo(f"[{owner}] 五層感知查詢中...")
    result = run_query(owner, question, caller=caller, config=config)

    click.echo(f"\n--- 回應 ---")
    click.echo(result["response"])
    click.echo(f"\n--- 查詢資訊 ---")
    click.echo(f"  匹配 frame: {result['matched_frame'] or '無'}（{result['match_method'] or 'N/A'}）")
    click.echo(f"  激活信念: {len(result['activated_convictions'])} 個")
    for c in result["activated_convictions"][:3]:
        click.echo(f"    - {c[:60]}")
    click.echo(f"  參考軌跡: {result['relevant_traces']} 個")
    click.echo(f"  身份約束: {len(result['identity_constraints'])} 個")


@cli.command(name="ask")
@click.option("--owner", required=True, help="使用者 ID")
@click.option("--caller", default=None, help="提問者身份")
@click.argument("text")
def ask_cmd(owner: str, caller: str | None, text: str):
    """統一入口 — 自動判斷要回答問題還是產出內容"""
    from engine.query_engine import ask as run_ask

    config = load_config()
    click.echo(f"[{owner}] 思考中...")
    result = run_ask(owner, text, caller=caller, config=config)

    mode = result.get("mode", "query")
    if mode == "generate":
        click.echo(f"\n--- 產出內容（{result['output_type']}）---")
        click.echo(result["content"])
    else:
        click.echo(f"\n--- 回應 ---")
        click.echo(result["response"])

    click.echo(f"\n--- 資訊 ---")
    click.echo(f"  模式: {mode}")
    click.echo(f"  匹配 frame: {result['matched_frame'] or '無'}（{result['match_method'] or 'N/A'}）")
    click.echo(f"  激活信念: {len(result['activated_convictions'])} 個")
    for c in result["activated_convictions"][:3]:
        click.echo(f"    - {c[:60]}")
    click.echo(f"  參考軌跡: {result['relevant_traces']} 個")


@cli.command(name="generate")
@click.option("--owner", required=True, help="使用者 ID")
@click.option("--type", "output_type", default="article",
              type=click.Choice(["article", "post", "decision", "script"]),
              help="產出類型")
@click.option("--caller", default=None, help="提問者身份")
@click.option("--extra", default="", help="額外指示")
@click.argument("task")
def generate_cmd(owner: str, output_type: str, caller: str | None, extra: str, task: str):
    """用五層思維模型產出內容（文章/貼文/決策/腳本）"""
    from engine.query_engine import generate as run_generate

    config = load_config()
    click.echo(f"[{owner}] 五層感知 generation（{output_type}）...")
    result = run_generate(owner, task, output_type=output_type,
                          extra_instructions=extra, caller=caller, config=config)

    click.echo(f"\n--- 產出內容（{result['output_type']}）---")
    click.echo(result["content"])
    click.echo(f"\n--- 生成資訊 ---")
    click.echo(f"  匹配 frame: {result['matched_frame'] or '無'}（{result['match_method'] or 'N/A'}）")
    click.echo(f"  激活信念: {len(result['activated_convictions'])} 個")
    for c in result["activated_convictions"][:3]:
        click.echo(f"    - {c[:60]}")
    click.echo(f"  參考軌跡: {result['relevant_traces']} 個")
    click.echo(f"  身份約束: {len(result['identity_constraints'])} 個")


@cli.command(name="dedupe")
@click.option("--owner", required=True, help="使用者 ID")
@click.option("--dry-run", is_flag=True, help="預覽模式，不實際執行")
@click.option("--threshold", default=0.90, type=float, help="相似度門檻（預設 0.90）")
def dedupe_cmd(owner: str, dry_run: bool, threshold: float):
    """Conviction 語義去重（合併重複信念）"""
    from engine.conviction_deduper import dedupe

    config = load_config()
    click.echo(f"[{owner}] {'預覽' if dry_run else '執行'} conviction 去重（threshold={threshold}）...")
    result = dedupe(owner, config, dry_run=dry_run, threshold=threshold)

    click.echo(f"\n=== 去重結果 ===")
    click.echo(f"  候選 pairs: {result['pairs_found']}")
    click.echo(f"  LLM 確認: {result['pairs_confirmed']}")

    if dry_run:
        click.echo(f"\n--- 預覽（不執行）---")
        for d in result.get("details", []):
            confirmed = "✓" if d.get("confirmed") else "?"
            click.echo(f"\n  [{confirmed}] similarity={d['similarity']}")
            click.echo(f"    保留: {d['primary']} — {d['primary_statement'][:60]}")
            click.echo(f"    移除: {d['secondary']} — {d['secondary_statement'][:60]}")
    else:
        click.echo(f"  已合併: {result['merged']}")
        if result.get("downstream_stats"):
            click.echo(f"\n--- 下游更新 ---")
            for k, v in result["downstream_stats"].items():
                click.echo(f"    {k}: {v}")
        if result["merged"] > 0:
            click.echo(f"\n提示：請執行 `mind-spiral build-index --owner {owner}` 重建索引。")


if __name__ == "__main__":
    cli()
