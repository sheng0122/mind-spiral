"""Signal Store — Layer 1 CRUD + embedding 計算"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import chromadb

from engine.config import get_owner_dir
from engine.models import Signal


class SignalStore:
    def __init__(self, config: dict, owner_id: str):
        self.config = config
        self.owner_id = owner_id
        self.owner_dir = get_owner_dir(config, owner_id)
        self.signals_path = self.owner_dir / "signals.jsonl"

        # ChromaDB — 本地持久化
        chroma_dir = self.owner_dir / "chroma"
        self._chroma = chromadb.PersistentClient(path=str(chroma_dir))
        self._collection = self._chroma.get_or_create_collection(
            name=f"{owner_id}_signals",
            metadata={"hnsw:space": "cosine"},
        )

        # Embedding model（lazy load）
        self._embedder = None

    def _get_embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            model_name = self.config.get("llm", {}).get("local", {}).get("embedding_model", "BAAI/bge-m3")
            # 如果只寫 bge-m3，補完整名稱
            if "/" not in model_name:
                model_name = f"BAAI/{model_name}"
            self._embedder = SentenceTransformer(model_name)
        return self._embedder

    def compute_embedding(self, text: str) -> list[float]:
        embedder = self._get_embedder()
        return embedder.encode(text, normalize_embeddings=True).tolist()

    def ingest(self, signals: list[Signal], compute_embeddings: bool = True) -> int:
        """寫入 signals 到 JSONL + ChromaDB。回傳寫入數量。"""
        if not signals:
            return 0

        # 取得已存在的 IDs 避免重複
        existing_ids = set()
        if self.signals_path.exists():
            with open(self.signals_path) as f:
                for line in f:
                    if line.strip():
                        obj = json.loads(line)
                        existing_ids.add(obj.get("signal_id", ""))

        # 去重：跳過已存在 + batch 內去重
        seen = set(existing_ids)
        new_signals = []
        for s in signals:
            if s.signal_id not in seen:
                seen.add(s.signal_id)
                new_signals.append(s)
        if not new_signals:
            return 0

        # 寫入 JSONL
        with open(self.signals_path, "a") as f:
            for s in new_signals:
                f.write(s.model_dump_json() + "\n")

        # 寫入 ChromaDB
        ids = [s.signal_id for s in new_signals]
        documents = [s.content.text for s in new_signals]
        metadatas = [
            {
                "direction": s.direction,
                "modality": s.modality,
                "authority": s.authority or "",
                "content_type": s.content.type,
                "date": s.source.date,
                "context": s.source.context,
            }
            for s in new_signals
        ]

        if compute_embeddings:
            embedder = self._get_embedder()
            embeddings = embedder.encode(
                documents, normalize_embeddings=True, show_progress_bar=len(documents) > 100
            ).tolist()
            self._collection.add(
                ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings,
            )
        else:
            self._collection.add(ids=ids, documents=documents, metadatas=metadatas)

        return len(new_signals)

    def query(
        self,
        text: str | None = None,
        topics: list[str] | None = None,
        date_range: tuple[str, str] | None = None,
        direction: str | None = None,
        n_results: int = 20,
    ) -> list[Signal]:
        """查詢 signals。支援語意搜尋 + metadata 過濾。"""
        where = {}
        if direction:
            where["direction"] = direction
        if date_range:
            where["$and"] = [
                {"date": {"$gte": date_range[0]}},
                {"date": {"$lte": date_range[1]}},
            ]

        kwargs: dict = {"n_results": n_results}
        if where:
            kwargs["where"] = where

        if text:
            embedding = self.compute_embedding(text)
            kwargs["query_embeddings"] = [embedding]
        else:
            # 無文字查詢時，用 get 代替 query
            get_kwargs: dict = {}
            if where:
                get_kwargs["where"] = where
            get_kwargs["limit"] = n_results
            results = self._collection.get(**get_kwargs)
            return self._load_signals_by_ids(results["ids"]) if results["ids"] else []

        results = self._collection.query(**kwargs)
        ids = results["ids"][0] if results["ids"] else []
        return self._load_signals_by_ids(ids)

    def _load_signals_by_ids(self, ids: list[str]) -> list[Signal]:
        """從 JSONL 載入指定 ID 的 signals。"""
        id_set = set(ids)
        signals = []
        if not self.signals_path.exists():
            return signals
        with open(self.signals_path) as f:
            for line in f:
                if line.strip():
                    obj = json.loads(line)
                    if obj.get("signal_id") in id_set:
                        signals.append(Signal.model_validate(obj))
        return signals

    def load_all(self) -> list[Signal]:
        """載入所有 signals。"""
        signals = []
        if not self.signals_path.exists():
            return signals
        with open(self.signals_path) as f:
            for line in f:
                if line.strip():
                    signals.append(Signal.model_validate_json(line))
        return signals

    def stats(self) -> dict:
        """各維度統計。"""
        signals = self.load_all()
        if not signals:
            return {"total": 0}

        direction_counts = Counter(s.direction for s in signals)
        modality_counts = Counter(s.modality for s in signals)
        authority_counts = Counter(s.authority or "unknown" for s in signals)
        content_type_counts = Counter(s.content.type for s in signals)
        context_counts = Counter(s.source.context for s in signals)

        dates = [s.source.date for s in signals]
        topics_all: list[str] = []
        for s in signals:
            if s.topics:
                topics_all.extend(s.topics)
        topic_counts = Counter(topics_all).most_common(20)

        return {
            "total": len(signals),
            "direction": dict(direction_counts),
            "modality": dict(modality_counts),
            "authority": dict(authority_counts),
            "content_type": dict(content_type_counts),
            "context": dict(context_counts),
            "date_range": {"earliest": min(dates), "latest": max(dates)} if dates else None,
            "top_topics": topic_counts,
            "chroma_count": self._collection.count(),
        }
