"""Atoms/Signals → Mind Spiral Signals 遷移工具

支援兩種格式：
1. 舊版 atom 格式（有 atom_id、content 為 string）
2. 新版 signal 格式（有 signal_id、content 為 string、已含 direction/modality）
"""

import json
import sys
from pathlib import Path

from engine.config import load_config
from engine.models import Signal, SignalContent, SignalSource, SignalAudience, SignalLifecycle
from engine.signal_store import SignalStore


ATOMS_PATH = Path(__file__).parent.parent / "16_moltbot_joey" / "knowledge-base" / "atoms.jsonl"


def _convert_new_format(raw: dict, owner_id: str) -> Signal:
    """將 16 的新版 signal 格式轉為 Mind Spiral Signal。"""
    src = raw.get("source", {})

    # context 驗證
    valid_contexts = {
        "solo_thinking", "team_meeting", "one_on_one", "phone_call",
        "brainstorm", "client_meeting", "presentation", "casual_chat",
        "commute", "short_video", "social_post", "interview_guest",
        "host_interview", "line_private", "line_group", "email",
        "book_reading", "article_reading", "podcast_listening",
        "course_learning", "other",
    }
    context_val = src.get("context", "other")
    if context_val not in valid_contexts:
        context_val = "other"

    # content type 映射
    type_map = {"open_question": "question", "action_item": "action", "cta_pattern": "instruction"}
    raw_type = raw.get("type", "observation")
    content_type = type_map.get(raw_type, raw_type)

    # 驗證 content type
    valid_types = {
        "idea", "belief", "decision", "action", "framework", "story",
        "quote", "question", "observation", "reaction", "instruction",
        "hook_pattern", "narrative_pattern", "key_message",
    }
    if content_type not in valid_types:
        content_type = "observation"

    content = SignalContent(
        text=str(raw.get("content", ""))[:300],
        type=content_type,
        confidence=raw.get("confidence") if raw.get("confidence") in (
            "strong_opinion", "exploring", "tentative", "quoting_others"
        ) else None,
    )

    source = SignalSource(
        date=src.get("date", "2026-01-01"),
        context=context_val,
        participants=src.get("participants") or None,
        source_file=src.get("source_file"),
        book_title=src.get("book_title"),
        book_author=src.get("book_author"),
        chapter=src.get("chapter"),
    )

    # audience
    aud = raw.get("audience")
    audience = None
    if aud:
        vis = aud.get("visibility")
        valid_vis = {"public", "team_internal", "management_only", "one_on_one_private", "self_only"}
        rel = aud.get("relationship_context")
        valid_rel = {
            "boss_to_team", "peer_to_peer", "to_client", "to_investor",
            "to_partner", "self_reflection", "public_facing", "content_creator",
            "teacher_to_student",
        }
        raw_directed = aud.get("directed_to")
        if isinstance(raw_directed, str):
            raw_directed = [raw_directed]
        audience = SignalAudience(
            directed_to=raw_directed or None,
            visibility=vis if vis in valid_vis else None,
            relationship_context=rel if rel in valid_rel else None,
        )

    # direction / modality 驗證
    valid_modalities = {
        "spoken_spontaneous", "spoken_scripted", "spoken_interview",
        "written_casual", "written_deliberate", "written_structured",
        "highlighted", "consumed", "received", "decided", "acted",
    }
    direction = raw.get("direction", "input")
    modality = raw.get("modality", "consumed")
    if direction not in ("input", "output"):
        direction = "input"
    if modality not in valid_modalities:
        modality = "consumed" if direction == "input" else "spoken_spontaneous"

    # authority
    authority_val = raw.get("authority")
    valid_auth = {"own_voice", "endorsed", "referenced", "received"}
    authority = authority_val if authority_val in valid_auth else None

    # lifecycle
    lc = raw.get("lifecycle", {})
    lifecycle = SignalLifecycle(
        active=lc.get("active", True),
        created_at=lc.get("created_at"),
    )

    return Signal(
        owner_id=owner_id,
        signal_id=raw.get("signal_id", f"sig_{id(raw)}"),
        direction=direction,
        modality=modality,
        authority=authority,
        content=content,
        source=source,
        audience=audience,
        topics=raw.get("topics") or None,
        lifecycle=lifecycle,
    )


def migrate(
    atoms_path: Path = ATOMS_PATH,
    owner_id: str = "joey",
    compute_embeddings: bool = True,
) -> dict:
    """執行遷移，回傳統計。"""
    if not atoms_path.exists():
        print(f"找不到檔案: {atoms_path}")
        sys.exit(1)

    # 讀取
    raw_items = []
    with open(atoms_path) as f:
        for line in f:
            if line.strip():
                raw_items.append(json.loads(line))

    print(f"讀取 {len(raw_items)} 筆資料")

    # 偵測格式：新版有 signal_id，舊版有 atom_id
    has_signal_id = any(r.get("signal_id") for r in raw_items[:5])
    print(f"格式：{'新版 signal' if has_signal_id else '舊版 atom'}")

    # 轉換
    signals = []
    errors = []
    for i, raw in enumerate(raw_items):
        try:
            sig = _convert_new_format(raw, owner_id)
            signals.append(sig)
        except Exception as e:
            errors.append({"index": i, "id": raw.get("signal_id") or raw.get("atom_id", "?"), "error": str(e)})

    print(f"轉換成功: {len(signals)}，失敗: {len(errors)}")
    if errors:
        for err in errors[:10]:
            print(f"  錯誤: {err}")

    # 寫入
    config = load_config()
    store = SignalStore(config, owner_id)
    count = store.ingest(signals, compute_embeddings=compute_embeddings)
    print(f"寫入 {count} 個新 signals")

    # 統計
    stats = store.stats()
    return stats


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Atoms/Signals → Mind Spiral 遷移")
    parser.add_argument("--atoms", type=Path, default=ATOMS_PATH)
    parser.add_argument("--owner", default="joey")
    parser.add_argument("--no-embeddings", action="store_true", help="跳過 embedding 計算（快速測試用）")
    args = parser.parse_args()

    stats = migrate(args.atoms, args.owner, compute_embeddings=not args.no_embeddings)
    print("\n=== 統計 ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
