"""Contradiction Alert — 矛盾偵測：conviction pairs cosine similarity + LLM 確認"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np

from engine.config import get_owner_dir
from engine.conviction_detector import _load_convictions, _save_convictions
from engine.llm import call_llm
from engine.models import Conviction, ConvictionTension
from engine.signal_store import SignalStore


def _classify_tension(c1: Conviction, c2: Conviction, config: dict) -> str | None:
    """用 LLM 判斷兩個 conviction 的關係。回傳 relationship 或 None（不矛盾）。"""
    prompt = (
        "以下是同一個人持有的兩個信念：\n\n"
        f"A: {c1.statement}\n"
        f"B: {c2.statement}\n\n"
        "請判斷這兩個信念的關係，只回答以下其中一個詞：\n"
        "- contradiction（直接矛盾）\n"
        "- evolution（觀點演進，B 取代 A）\n"
        "- context_dependent（在不同情境下都合理）\n"
        "- creative_tension（有張力但共存）\n"
        "- unrelated（無關）\n\n"
        "只回答一個詞。"
    )
    result = call_llm(prompt, config=config).strip().lower()
    valid = {"contradiction", "evolution", "context_dependent", "creative_tension"}
    return result if result in valid else None


def scan(owner_id: str, config: dict) -> list[dict]:
    """掃描所有 active convictions，找出潛在矛盾 pairs。

    1. 取所有 active convictions 的 embeddings
    2. 找 cosine similarity > 0.7 的 pairs
    3. LLM 確認關係
    4. 如果是 contradiction → 寫入 conviction.tensions
    """
    owner_dir = get_owner_dir(config, owner_id)
    convictions = _load_convictions(owner_dir)
    active = [c for c in convictions if c.lifecycle and c.lifecycle.status == "active"]

    if len(active) < 2:
        return []

    store = SignalStore(config, owner_id)

    # 計算所有 conviction 的 embeddings
    conv_embeddings: list[tuple[Conviction, np.ndarray]] = []
    for c in active:
        emb = np.array(store.compute_embedding(c.statement))
        conv_embeddings.append((c, emb))

    # 找相似 pairs（similarity > 0.7 但不完全相同）
    results: list[dict] = []
    checked: set[tuple[str, str]] = set()

    for i, (c1, e1) in enumerate(conv_embeddings):
        for j, (c2, e2) in enumerate(conv_embeddings):
            if i >= j:
                continue
            pair_key = (c1.conviction_id, c2.conviction_id)
            if pair_key in checked:
                continue
            checked.add(pair_key)

            sim = float(np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2) + 1e-8))
            if sim < 0.7 or sim > 0.95:  # 太相似的可能是同一概念
                continue

            # LLM 確認
            relationship = _classify_tension(c1, c2, config)
            if not relationship:
                continue

            results.append({
                "conviction_a": c1.conviction_id,
                "conviction_b": c2.conviction_id,
                "statement_a": c1.statement,
                "statement_b": c2.statement,
                "similarity": round(sim, 3),
                "relationship": relationship,
            })

            # 寫入 tensions
            if relationship == "contradiction":
                tension_a = ConvictionTension(
                    opposing_conviction=c2.conviction_id,
                    relationship="contradiction",
                )
                tension_b = ConvictionTension(
                    opposing_conviction=c1.conviction_id,
                    relationship="contradiction",
                )
                if c1.tensions is None:
                    c1.tensions = []
                if c2.tensions is None:
                    c2.tensions = []
                # 避免重複
                existing_a = {t.opposing_conviction for t in c1.tensions}
                existing_b = {t.opposing_conviction for t in c2.tensions}
                if c2.conviction_id not in existing_a:
                    c1.tensions.append(tension_a)
                if c1.conviction_id not in existing_b:
                    c2.tensions.append(tension_b)

    # 儲存更新後的 convictions
    _save_convictions(owner_dir, convictions)

    return results
