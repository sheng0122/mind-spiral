"""Conviction Detector — embedding 聚類 + 五種共鳴收斂檢查 + conviction 生成/更新"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from engine.config import get_owner_dir
from engine.llm import call_llm
from engine.models import (
    ActionAlignment,
    Conviction,
    ConvictionLifecycle,
    ConvictionStrength,
    CrossContextConsistency,
    InputOutputConvergence,
    ResonanceEvidence,
    Signal,
    SpontaneousMention,
    TemporalPersistence,
)
from engine.signal_store import SignalStore


def _has_both_directions(signals: list[Signal]) -> list[InputOutputConvergence]:
    """檢查 cluster 內是否同時有 input 和 output signals。"""
    inputs = [s for s in signals if s.direction == "input"]
    outputs = [s for s in signals if s.direction == "output"]
    if not inputs or not outputs:
        return []
    return [
        InputOutputConvergence(
            input_signal=inputs[0].signal_id,
            output_signal=outputs[0].signal_id,
            detected_at=datetime.now().strftime("%Y-%m-%d"),
        )
    ]


def _spans_days(signals: list[Signal], min_days: int = 7) -> list[TemporalPersistence]:
    """檢查 signals 是否跨越至少 min_days 天。"""
    dates = sorted(set(s.source.date for s in signals))
    if len(dates) < 2:
        return []
    first, last = dates[0], dates[-1]
    span = (datetime.strptime(last, "%Y-%m-%d") - datetime.strptime(first, "%Y-%m-%d")).days
    if span < min_days:
        return []
    return [
        TemporalPersistence(
            signal_ids=[s.signal_id for s in signals],
            time_span_days=span,
            first_date=first,
            last_date=last,
        )
    ]


def _spans_contexts(signals: list[Signal], min_contexts: int = 2) -> list[CrossContextConsistency]:
    """檢查 signals 是否涵蓋至少 min_contexts 種情境。"""
    contexts = list(set(s.source.context for s in signals))
    if len(contexts) < min_contexts:
        return []
    return [
        CrossContextConsistency(
            signal_ids=[s.signal_id for s in signals],
            contexts=contexts,
        )
    ]


def _has_unprompted_outputs(signals: list[Signal]) -> list[SpontaneousMention]:
    """檢查是否有未經提示的 output（spontaneous）。"""
    spontaneous = [
        s for s in signals
        if s.direction == "output" and s.modality in ("spoken_spontaneous", "written_casual")
    ]
    if not spontaneous:
        return []
    return [SpontaneousMention(signal_id=s.signal_id, was_prompted=False) for s in spontaneous[:3]]


def _has_decided_or_acted(signals: list[Signal]) -> list[ActionAlignment]:
    """檢查是否有 decided/acted modality 的 signals。"""
    actions = [s for s in signals if s.modality in ("decided", "acted")]
    statements = [s for s in signals if s.modality not in ("decided", "acted")]
    if not actions or not statements:
        return []
    return [
        ActionAlignment(
            statement_signal=statements[0].signal_id,
            action_signal=actions[0].signal_id,
            aligned=True,
        )
    ]


def _build_resonance(signals: list[Signal]) -> tuple[ResonanceEvidence, int]:
    """建立共鳴證據並回傳共鳴類型數量。"""
    ioc = _has_both_directions(signals)
    tp = _spans_days(signals)
    ccc = _spans_contexts(signals)
    sm = _has_unprompted_outputs(signals)
    aa = _has_decided_or_acted(signals)

    count = sum(1 for x in [ioc, tp, ccc, sm, aa] if x)
    evidence = ResonanceEvidence(
        input_output_convergence=ioc or None,
        temporal_persistence=tp or None,
        cross_context_consistency=ccc or None,
        spontaneous_mentions=sm or None,
        action_alignment=aa or None,
    )
    return evidence, count


_LLM_SELF_REF_BLOCKLIST = [
    "我需要先查看", "我需要先了解", "我無法確定", "我無法判斷",
    "讓我先", "讓我查看", "根據以上", "根據這些",
    "需要更多資訊", "需要更多信息", "需要先查看", "需要先了解",
    "I need to", "I cannot", "Let me", "Based on the above",
    "作為AI", "作為一個AI", "作為語言模型",
    "我需要查看", "無法從這些", "這些文件",
]


def _is_llm_hallucination(statement: str) -> bool:
    """檢查 conviction statement 是否為 LLM 自我指涉的幻覺。"""
    lower = statement.lower()
    for phrase in _LLM_SELF_REF_BLOCKLIST:
        if phrase.lower() in lower:
            return True
    return False


def _generate_conviction_statement(signals: list[Signal], config: dict) -> str | None:
    """用 LLM 從一組 signals 生成 conviction statement。回傳 None 代表無效。"""
    texts = [f"- [{s.direction}/{s.source.context}] {s.content.text}" for s in signals[:10]]
    prompt = (
        "以下是一個人在不同場景下反覆表達的類似想法：\n\n"
        + "\n".join(texts)
        + "\n\n請用一句簡潔的中文（最多 50 字）總結這個人的核心信念。"
        "只輸出信念本身，不要加前綴或解釋。\n\n"
        "重要規則：\n"
        "- 你是在描述「這個人」的信念，不是你自己的想法\n"
        "- 絕對不要輸出「我需要」「我無法」「讓我」「根據以上」等 AI 自我指涉語句\n"
        "- 如果這些想法太零散無法歸納出明確信念，只回答 SKIP"
    )
    result = call_llm(prompt, config=config, tier="light").strip().strip("「」""\"'")

    if not result or result.upper() == "SKIP":
        return None
    if _is_llm_hallucination(result):
        return None
    return result


def _load_convictions(owner_dir: Path) -> list[Conviction]:
    """載入既有 convictions。"""
    path = owner_dir / "convictions.jsonl"
    if not path.exists():
        return []
    convictions = []
    with open(path) as f:
        for line in f:
            if line.strip():
                convictions.append(Conviction.model_validate_json(line))
    return convictions


def _save_convictions(owner_dir: Path, convictions: list[Conviction]) -> None:
    """儲存 convictions（完整覆寫）。"""
    path = owner_dir / "convictions.jsonl"
    with open(path, "w") as f:
        for c in convictions:
            f.write(c.model_dump_json() + "\n")


def _compute_authority_weight(signals: list[Signal]) -> float:
    """根據 signals 的 authority 計算加權乘數。"""
    weights = {"first_person": 1.0, "second_person": 0.8, "third_party": 0.6}
    if not signals:
        return 1.0
    total = sum(weights.get(s.authority, 0.8) for s in signals)
    return total / len(signals)


def _has_cross_direction(signals: list[Signal]) -> bool:
    """檢查 signals 是否同時有 input 和 output。"""
    has_input = any(s.direction == "input" for s in signals)
    has_output = any(s.direction == "output" for s in signals)
    return has_input and has_output


def _compute_strength(
    resonance_count: int,
    signal_count: int,
    signals: list[Signal] | None = None,
) -> ConvictionStrength:
    """根據共鳴數、signal 數、authority 加權和 cross-direction 驗證計算 strength。

    規則：
    - 基礎分 = resonance_count * 0.15 + signal_count * 0.05
    - authority 加權：first_person ×1.0, second_person ×0.8, third_party ×0.6
    - cross-direction 門檻：只有 output 沒有 input 的 conviction，cap 在 developing（≤0.5）
    """
    score = min(1.0, (resonance_count * 0.15 + signal_count * 0.05))

    if signals:
        # Authority 加權
        auth_weight = _compute_authority_weight(signals)
        score = score * auth_weight

        # Cross-direction 門檻：只有單方向 → cap 在 0.5
        if not _has_cross_direction(signals):
            score = min(score, 0.5)

    score = round(min(1.0, score), 2)

    if score >= 0.8:
        level = "core"
    elif score >= 0.6:
        level = "established"
    elif score >= 0.4:
        level = "developing"
    else:
        level = "emerging"
    return ConvictionStrength(
        score=score,
        level=level,
        trend="strengthening",
        last_computed=datetime.now().strftime("%Y-%m-%d"),
    )


def _extract_domains(signals: list[Signal]) -> list[str]:
    """從 signals 的 topics 中提取最常見的 domains。"""
    all_topics: list[str] = []
    for s in signals:
        if s.topics:
            all_topics.extend(s.topics)
    if not all_topics:
        return ["general"]
    from collections import Counter
    return [t for t, _ in Counter(all_topics).most_common(3)]


def detect(owner_id: str, config: dict) -> list[Conviction]:
    """主入口：偵測 convictions。

    1. 從 ChromaDB 取所有 signal embeddings
    2. AgglomerativeClustering 聚類
    3. 每個 cluster 做五種共鳴收斂檢查
    4. 通過門檻的 cluster 生成/更新 conviction
    """
    store = SignalStore(config, owner_id)
    owner_dir = get_owner_dir(config, owner_id)

    # 取所有 signals + embeddings
    collection = store._collection
    all_data = collection.get(include=["embeddings", "documents"])
    if not all_data["ids"] or all_data["embeddings"] is None:
        return []

    ids = all_data["ids"]
    embeddings = np.array(all_data["embeddings"])
    if embeddings.size == 0:
        return []

    if len(ids) < 2:
        return []

    # Step 1: AgglomerativeClustering
    threshold = config.get("engine", {}).get("conviction", {}).get("similarity_threshold", 0.75)
    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=1 - threshold,  # cosine distance = 1 - similarity
        metric="cosine",
        linkage="average",
    )
    labels = clustering.fit_predict(embeddings)

    # 按 label 分組
    clusters: dict[int, list[str]] = defaultdict(list)
    for signal_id, label in zip(ids, labels):
        clusters[label].append(signal_id)

    # 載入 signals（一次性）
    all_signals = store.load_all()
    signal_map = {s.signal_id: s for s in all_signals}

    # 載入既有 convictions — batch encode 取代逐一計算
    existing = _load_convictions(owner_dir)
    existing_embeddings: list[tuple[Conviction, np.ndarray]] = []
    if existing:
        statements = [c.statement for c in existing]
        embs = store._get_embedder().encode(
            statements, normalize_embeddings=True,
            show_progress_bar=len(statements) > 50,
        )
        for c, emb in zip(existing, embs):
            existing_embeddings.append((c, np.array(emb)))

    min_resonance = config.get("engine", {}).get("conviction", {}).get("min_resonance_count", 2)
    new_convictions: list[Conviction] = []
    updated_ids: set[str] = set()
    today = datetime.now().strftime("%Y-%m-%d")

    for label, signal_ids in clusters.items():
        if len(signal_ids) < 3:  # 至少 3 個 signals 才考慮
            continue

        cluster_signals = [signal_map[sid] for sid in signal_ids if sid in signal_map]
        if not cluster_signals:
            continue

        # Step 2: 共鳴收斂檢查
        evidence, resonance_count = _build_resonance(cluster_signals)
        if resonance_count < min_resonance:
            continue

        # Step 3: 比對既有 convictions
        cluster_emb = embeddings[[i for i, sid in enumerate(ids) if sid in set(signal_ids)]].mean(axis=0)
        matched_existing = None
        if existing_embeddings:
            for conv, conv_emb in existing_embeddings:
                sim = float(np.dot(cluster_emb, conv_emb) / (np.linalg.norm(cluster_emb) * np.linalg.norm(conv_emb) + 1e-8))
                if sim > 0.85 and conv.conviction_id not in updated_ids:
                    matched_existing = conv
                    break

        if matched_existing:
            # 更新既有 conviction 的 strength
            matched_existing.strength = _compute_strength(resonance_count, len(cluster_signals), cluster_signals)
            matched_existing.resonance_evidence = evidence
            if matched_existing.lifecycle:
                matched_existing.lifecycle.last_reinforced = today
            updated_ids.add(matched_existing.conviction_id)
        else:
            # 生成新 conviction
            statement = _generate_conviction_statement(cluster_signals, config)
            if statement is None:
                continue  # LLM 幻覺或無法歸納，跳過
            conviction = Conviction(
                owner_id=owner_id,
                conviction_id=f"conv_{uuid.uuid4().hex[:8]}",
                statement=statement,
                strength=_compute_strength(resonance_count, len(cluster_signals), cluster_signals),
                domains=_extract_domains(cluster_signals),
                resonance_evidence=evidence,
                lifecycle=ConvictionLifecycle(
                    status="active",
                    first_detected=today,
                    last_reinforced=today,
                ),
            )
            new_convictions.append(conviction)

    # 全量重算所有 conviction 的 strength（套用 cross-direction + authority 新規則）
    all_convictions = existing + new_convictions
    for conv in all_convictions:
        # 收集這個 conviction 關聯的 signal IDs
        sig_ids: set[str] = set()
        if conv.resonance_evidence:
            re = conv.resonance_evidence
            if re.input_output_convergence:
                for ioc in re.input_output_convergence:
                    sig_ids.add(ioc.input_signal)
                    sig_ids.add(ioc.output_signal)
            if re.temporal_persistence:
                for tp in re.temporal_persistence:
                    sig_ids.update(tp.signal_ids)
            if re.cross_context_consistency:
                for ccc in re.cross_context_consistency:
                    sig_ids.update(ccc.signal_ids)
            if re.spontaneous_mentions:
                for sm in re.spontaneous_mentions:
                    sig_ids.add(sm.signal_id)
            if re.action_alignment:
                for aa in re.action_alignment:
                    sig_ids.add(aa.statement_signal)
                    sig_ids.add(aa.action_signal)

        conv_signals = [signal_map[sid] for sid in sig_ids if sid in signal_map]
        if conv_signals:
            resonance_count = sum(1 for x in [
                conv.resonance_evidence.input_output_convergence if conv.resonance_evidence else None,
                conv.resonance_evidence.temporal_persistence if conv.resonance_evidence else None,
                conv.resonance_evidence.cross_context_consistency if conv.resonance_evidence else None,
                conv.resonance_evidence.spontaneous_mentions if conv.resonance_evidence else None,
                conv.resonance_evidence.action_alignment if conv.resonance_evidence else None,
            ] if x)
            conv.strength = _compute_strength(resonance_count, len(conv_signals), conv_signals)

    _save_convictions(owner_dir, all_convictions)

    return new_convictions
