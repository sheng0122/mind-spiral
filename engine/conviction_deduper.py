"""Conviction Deduper — 語義去重 + 下游引用更新"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from engine.config import get_owner_dir, load_config
from engine.conviction_detector import _load_convictions, _save_convictions
from engine.models import (
    Conviction,
    ResonanceEvidence,
)
from engine.signal_store import SignalStore


def _merge_evidence(primary: ResonanceEvidence, secondary: ResonanceEvidence) -> ResonanceEvidence:
    """合併兩個 conviction 的 resonance evidence。"""
    def _merge_list(a, b):
        if not a and not b:
            return None
        return (a or []) + (b or [])

    return ResonanceEvidence(
        input_output_convergence=_merge_list(
            primary.input_output_convergence, secondary.input_output_convergence
        ),
        temporal_persistence=_merge_list(
            primary.temporal_persistence, secondary.temporal_persistence
        ),
        cross_context_consistency=_merge_list(
            primary.cross_context_consistency, secondary.cross_context_consistency
        ),
        spontaneous_mentions=_merge_list(
            primary.spontaneous_mentions, secondary.spontaneous_mentions
        ),
        action_alignment=_merge_list(
            primary.action_alignment, secondary.action_alignment
        ),
    )


def _find_duplicate_pairs(
    convictions: list[Conviction],
    store: SignalStore,
    threshold: float = 0.90,
) -> list[tuple[Conviction, Conviction, float]]:
    """用 embedding cosine similarity 找出候選重複 pair。"""
    if len(convictions) < 2:
        return []

    statements = [c.statement for c in convictions]
    embeddings = store._get_embedder().encode(
        statements, normalize_embeddings=True,
        show_progress_bar=len(statements) > 50,
    )
    emb_matrix = np.array(embeddings)

    # cosine similarity matrix（已 normalize，直接 dot）
    sim_matrix = emb_matrix @ emb_matrix.T

    pairs = []
    seen = set()
    for i in range(len(convictions)):
        for j in range(i + 1, len(convictions)):
            if sim_matrix[i][j] > threshold:
                pair_key = tuple(sorted([convictions[i].conviction_id, convictions[j].conviction_id]))
                if pair_key not in seen:
                    seen.add(pair_key)
                    pairs.append((convictions[i], convictions[j], float(sim_matrix[i][j])))

    # 高相似度排前面
    pairs.sort(key=lambda x: -x[2])
    return pairs


def _llm_confirm_duplicates(
    pairs: list[tuple[Conviction, Conviction, float]],
) -> list[tuple[Conviction, Conviction, float]]:
    """用 LLM 確認候選 pair 是否語義等價。"""
    if not pairs:
        return []

    from engine.llm import batch_llm

    prompts = []
    for a, b, sim in pairs:
        prompts.append(
            f"以下兩個信念陳述是否表達相同的意思？\n\n"
            f"A: {a.statement}\n"
            f"B: {b.statement}\n\n"
            f"只回答 YES 或 NO。如果意思幾乎一樣只是用詞/標點不同，回答 YES。"
        )

    results = batch_llm(prompts, tier="light")

    confirmed = []
    for (a, b, sim), result in zip(pairs, results):
        if result.strip().upper().startswith("YES"):
            confirmed.append((a, b, sim))

    return confirmed


def _choose_primary(a: Conviction, b: Conviction) -> tuple[Conviction, Conviction]:
    """選擇要保留的 primary（strength 較高者）。回傳 (primary, secondary)。"""
    if a.strength.score >= b.strength.score:
        return a, b
    return b, a


def _update_downstream_references(owner_dir: Path, id_map: dict[str, str]) -> dict[str, int]:
    """更新所有下游檔案中的 conviction_id 引用。回傳各檔更新數。"""
    stats = {}

    # 1. traces.jsonl
    traces_path = owner_dir / "traces.jsonl"
    if traces_path.exists():
        updated = 0
        lines = []
        with open(traces_path) as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                changed = False

                # activated_convictions
                for ac in data.get("activated_convictions", []):
                    if ac.get("conviction_id") in id_map:
                        ac["conviction_id"] = id_map[ac["conviction_id"]]
                        changed = True

                # reasoning_path.steps[].uses_conviction
                for step in data.get("reasoning_path", {}).get("steps", []):
                    if step.get("uses_conviction") in id_map:
                        step["uses_conviction"] = id_map[step["uses_conviction"]]
                        changed = True

                # outcome.conviction_impact
                for ci in (data.get("outcome") or {}).get("conviction_impact", []) or []:
                    if ci.get("conviction_id") in id_map:
                        ci["conviction_id"] = id_map[ci["conviction_id"]]
                        changed = True

                if changed:
                    updated += 1
                lines.append(json.dumps(data, ensure_ascii=False))

        with open(traces_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        stats["traces"] = updated

    # 2. frames.jsonl
    frames_path = owner_dir / "frames.jsonl"
    if frames_path.exists():
        updated = 0
        lines = []
        with open(frames_path) as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                changed = False

                for ca in data.get("conviction_profile", {}).get("primary_convictions", []):
                    if ca.get("conviction_id") in id_map:
                        ca["conviction_id"] = id_map[ca["conviction_id"]]
                        changed = True

                for sc in data.get("conviction_profile", {}).get("suppressed_convictions", []) or []:
                    if sc.get("conviction_id") in id_map:
                        sc["conviction_id"] = id_map[sc["conviction_id"]]
                        changed = True

                if changed:
                    updated += 1
                lines.append(json.dumps(data, ensure_ascii=False))

        with open(frames_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        stats["frames"] = updated

    # 3. identity.json
    identity_path = owner_dir / "identity.json"
    if identity_path.exists():
        updated = 0
        with open(identity_path) as f:
            identities = json.load(f)

        if isinstance(identities, list):
            for ident in identities:
                if ident.get("conviction_id") in id_map:
                    ident["conviction_id"] = id_map[ident["conviction_id"]]
                    updated += 1

            with open(identity_path, "w") as f:
                json.dump(identities, f, ensure_ascii=False, indent=2)
        stats["identity"] = updated

    # 4. contradiction_checked.jsonl — 刪除包含 secondary id 的 pair
    checked_path = owner_dir / "contradiction_checked.jsonl"
    if checked_path.exists():
        removed = 0
        secondary_ids = set(id_map.keys())
        kept_lines = []
        with open(checked_path) as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                pair = data.get("pair", [])
                if any(pid in secondary_ids for pid in pair):
                    removed += 1
                else:
                    kept_lines.append(line.strip())

        with open(checked_path, "w") as f:
            for ln in kept_lines:
                f.write(ln + "\n")
        stats["contradiction_checked_removed"] = removed

    # 5. convictions 自身的 tensions[].opposing_conviction
    # 這個在 merge 時處理（呼叫端負責）

    return stats


def dedupe(
    owner: str,
    config: dict | None = None,
    dry_run: bool = False,
    threshold: float = 0.90,
) -> dict:
    """執行 conviction 去重。

    Returns:
        dict with keys: pairs_found, pairs_confirmed, merged, id_map, downstream_stats
    """
    if config is None:
        config = load_config()

    owner_dir = get_owner_dir(config, owner)
    store = SignalStore(config, owner)
    convictions = _load_convictions(owner_dir)

    if len(convictions) < 2:
        return {"pairs_found": 0, "pairs_confirmed": 0, "merged": 0, "id_map": {}, "downstream_stats": {}}

    # Step 1: embedding 找候選
    pairs = _find_duplicate_pairs(convictions, store, threshold=threshold)

    if not pairs:
        return {"pairs_found": 0, "pairs_confirmed": 0, "merged": 0, "id_map": {}, "downstream_stats": {}}

    # Step 2: LLM 確認
    confirmed = _llm_confirm_duplicates(pairs)

    result = {
        "pairs_found": len(pairs),
        "pairs_confirmed": len(confirmed),
        "merged": 0,
        "id_map": {},
        "downstream_stats": {},
        "details": [],
    }

    if dry_run or not confirmed:
        # dry-run: 只報告，不執行
        for a, b, sim in (confirmed if confirmed else pairs):
            primary, secondary = _choose_primary(a, b)
            result["details"].append({
                "primary": primary.conviction_id,
                "secondary": secondary.conviction_id,
                "primary_statement": primary.statement,
                "secondary_statement": secondary.statement,
                "similarity": round(sim, 4),
                "confirmed": (a, b, sim) in confirmed if not confirmed else True,
            })
        return result

    # Step 3: 執行合併
    id_map: dict[str, str] = {}  # secondary_id → primary_id
    remove_ids: set[str] = set()

    for a, b, sim in confirmed:
        primary, secondary = _choose_primary(a, b)

        # 跳過已被合併的
        if primary.conviction_id in remove_ids or secondary.conviction_id in remove_ids:
            continue

        # 合併 evidence
        primary.resonance_evidence = _merge_evidence(
            primary.resonance_evidence, secondary.resonance_evidence
        )

        # 合併 domains
        merged_domains = list(set(primary.domains + secondary.domains))
        primary.domains = merged_domains

        # 合併 statement_variants
        variants = list(primary.statement_variants or [])
        if secondary.statement_variants:
            variants.extend(secondary.statement_variants)
        # 加入 secondary 的 statement 作為 variant
        from engine.models import StatementVariant
        variants.append(StatementVariant(text=secondary.statement, context="merged_duplicate"))
        primary.statement_variants = variants

        # 合併 tensions（更新 opposing_conviction 引用）
        primary_tensions = list(primary.tensions or [])
        for t in (secondary.tensions or []):
            if t.opposing_conviction != primary.conviction_id:
                # 避免自我引用
                primary_tensions.append(t)
        primary.tensions = primary_tensions if primary_tensions else None

        id_map[secondary.conviction_id] = primary.conviction_id
        remove_ids.add(secondary.conviction_id)

        result["details"].append({
            "primary": primary.conviction_id,
            "secondary": secondary.conviction_id,
            "primary_statement": primary.statement,
            "secondary_statement": secondary.statement,
            "similarity": round(sim, 4),
        })

    # 過濾掉被合併的 convictions，並更新剩餘的 tensions 引用
    merged_convictions = []
    for c in convictions:
        if c.conviction_id in remove_ids:
            continue
        # 更新 tensions 中的 opposing_conviction
        if c.tensions:
            for t in c.tensions:
                if t.opposing_conviction in id_map:
                    t.opposing_conviction = id_map[t.opposing_conviction]
        merged_convictions.append(c)

    # 儲存
    _save_convictions(owner_dir, merged_convictions)

    # Step 4: 更新下游引用
    downstream_stats = _update_downstream_references(owner_dir, id_map)

    result["merged"] = len(remove_ids)
    result["id_map"] = id_map
    result["downstream_stats"] = downstream_stats

    return result
