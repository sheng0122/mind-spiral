"""Identity Scanner — 從 frames 中篩選 Layer 5 身份核心

邏輯：
1. 載入所有 active frames
2. 統計每個 conviction 在多少個 frame 中被激活
3. 覆蓋率 > 80% 的 conviction 升級為 identity core
4. 用 LLM 生成每個 identity 在不同 frame 下的表現描述
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from engine.config import get_owner_dir
from engine.conviction_detector import _load_convictions
from engine.frame_clusterer import _load_frames, _save_frames
from engine.llm import batch_llm
from engine.models import (
    ContextFrame,
    Conviction,
    IdentityCore,
    IdentityExpression,
    IdentityStability,
    IdentityUniversality,
)


def _load_identity(owner_dir: Path) -> list[IdentityCore]:
    path = owner_dir / "identity.json"
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return [IdentityCore.model_validate(item) for item in data]
    return []


def _save_identity(owner_dir: Path, identities: list[IdentityCore]) -> None:
    path = owner_dir / "identity.json"
    with open(path, "w") as f:
        json.dump([i.model_dump() for i in identities], f, ensure_ascii=False, indent=2)


def _generate_expressions(
    conviction: Conviction,
    frames: list[ContextFrame],
    config: dict,
) -> list[IdentityExpression]:
    """用 LLM 生成一個 identity conviction 在各 frame 下的表現方式。"""
    frame_names = [f"- {f.frame_id}: {f.name}（{f.description[:60]}）" for f in frames[:8]]

    prompt = f"""以下是一個人的核心信念：
「{conviction.statement}」

以下是這個人的不同情境框架：
{chr(10).join(frame_names)}

請描述這個核心信念在每個情境中如何具體表現。
每個情境用一句話（最多 50 字），說明這個信念「在這個場景下會怎麼影響他的行為或說法」。

輸出 JSON（不要加 markdown 標記）：
{{"expressions": [{{"frame_id": "...", "how_it_manifests": "..."}}]}}"""

    result = call_llm_single(prompt, config)
    if not result:
        return []

    try:
        data = json.loads(result)
        return [
            IdentityExpression(
                frame_id=e["frame_id"],
                how_it_manifests=e["how_it_manifests"][:200],
            )
            for e in data.get("expressions", [])
        ]
    except (json.JSONDecodeError, KeyError):
        return []


def call_llm_single(prompt: str, config: dict) -> str | None:
    """單次 LLM 呼叫，處理 markdown 清理。"""
    from engine.llm import call_llm
    result = call_llm(prompt, config=config, tier="light").strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1] if "\n" in result else result[3:]
    if result.endswith("```"):
        result = result[:-3]
    return result.strip() or None


def scan(owner_id: str, config: dict) -> list[IdentityCore]:
    """主入口：掃描 frames，篩選 identity core convictions。

    1. 載入所有 active frames
    2. 統計每個 conviction 的跨 frame 覆蓋率
    3. 覆蓋率 > threshold 的升級為 identity
    4. LLM 生成 expressions
    """
    owner_dir = get_owner_dir(config, owner_id)
    frames = _load_frames(owner_dir)
    active_frames = [f for f in frames if f.lifecycle and f.lifecycle.status == "active"]

    if len(active_frames) < 2:
        return []

    convictions = _load_convictions(owner_dir)
    conviction_map = {c.conviction_id: c for c in convictions}

    # Step 1: 統計覆蓋率
    conviction_frame_map: dict[str, list[str]] = {}
    for frame in active_frames:
        for ca in frame.conviction_profile.primary_convictions:
            if ca.conviction_id not in conviction_frame_map:
                conviction_frame_map[ca.conviction_id] = []
            conviction_frame_map[ca.conviction_id].append(frame.frame_id)

    # Step 2: 篩選
    threshold = config.get("engine", {}).get("conviction", {}).get(
        "identity_coverage_threshold", 0.8
    )
    total_frames = len(active_frames)

    candidates: list[tuple[str, list[str], float]] = []
    for cid, frame_ids in conviction_frame_map.items():
        coverage = len(frame_ids) / total_frames
        if coverage >= threshold and cid in conviction_map:
            candidates.append((cid, frame_ids, coverage))

    # 如果沒有達標的，取覆蓋率最高的 top-3（至少出現在 2+ frames）
    if not candidates:
        fallback = []
        for cid, frame_ids in conviction_frame_map.items():
            if len(frame_ids) >= 2 and cid in conviction_map:
                coverage = len(frame_ids) / total_frames
                fallback.append((cid, frame_ids, coverage))
        fallback.sort(key=lambda x: (-x[2], -conviction_map[x[0]].strength.score))
        candidates = fallback[:3]

    if not candidates:
        return []

    # Step 3: 全量重建 identity（跟 frame_clusterer 一樣，每次重跑）
    today = datetime.now().strftime("%Y-%m-%d")
    new_identities: list[IdentityCore] = []

    for cid, frame_ids, coverage in candidates:
        conviction = conviction_map[cid]

        # LLM 生成 expressions
        expressions = _generate_expressions(conviction, active_frames, config)
        if not expressions:
            # fallback：簡單生成
            expressions = [
                IdentityExpression(
                    frame_id=fid,
                    how_it_manifests=f"在此情境下體現「{conviction.statement[:30]}」",
                )
                for fid in frame_ids[:5]
            ]

        seq = len(new_identities) + 1
        identity = IdentityCore(
            owner_id=owner_id,
            identity_id=f"id_{seq:03d}",
            core_belief=conviction.statement[:150],
            conviction_id=cid,
            universality=IdentityUniversality(
                active_in_frames=frame_ids,
                total_active_frames=total_frames,
                coverage=round(coverage, 2),
            ),
            expressions=expressions,
            non_negotiable=conviction.strength.score >= 0.9,
            stability=IdentityStability(
                held_since=conviction.lifecycle.first_detected,
                consistency_score=round(conviction.strength.score, 2),
            ),
        )
        new_identities.append(identity)

    # 儲存（全量覆寫）
    _save_identity(owner_dir, new_identities)

    return new_identities
