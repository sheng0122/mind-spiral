"""Atoms → Signals 遷移工具

將 16_moltbot_joey 的 atoms.jsonl 轉換為 Mind Spiral Signal 格式。
"""

import json
import sys
from pathlib import Path

from engine.config import load_config
from engine.models import Signal, SignalContent, SignalSource, SignalAudience, SignalLifecycle
from engine.signal_store import SignalStore


ATOMS_PATH = Path(__file__).parent.parent / "16_moltbot_joey" / "knowledge-base" / "atoms.jsonl"

# modality → direction 映射（input_modality 欄位）
MODALITY_MAP = {
    "spoken_spontaneous": ("output", "spoken_spontaneous"),
    "spoken_scripted": ("output", "spoken_scripted"),
    "spoken_interview": ("output", "spoken_interview"),
    "written_casual": ("output", "written_casual"),
    "written_deliberate": ("output", "written_deliberate"),
    "written_structured": ("output", "written_structured"),
    "highlighted": ("input", "highlighted"),
    "consumed": ("input", "consumed"),
    "received": ("input", "received"),
    "decided": ("output", "decided"),
    "acted": ("output", "acted"),
}

# authority → direction fallback
AUTHORITY_DIRECTION = {
    "own_voice": "output",
    "endorsed": "input",
    "referenced": "input",
    "received": "input",
}


def determine_direction_and_modality(atom: dict) -> tuple[str, str]:
    """從 atom 欄位決定 direction 和 modality。"""
    input_modality = atom.get("source", {}).get("input_modality", "")

    # 優先用 input_modality
    if input_modality in MODALITY_MAP:
        return MODALITY_MAP[input_modality]

    # Fallback: 用 authority
    authority = atom.get("authority", "")
    direction = AUTHORITY_DIRECTION.get(authority, "input")

    # 猜 modality
    context = atom.get("source", {}).get("context", "")
    if direction == "output":
        if context in ("solo_thinking", "commute"):
            modality = "spoken_spontaneous"
        elif context in ("short_video", "social_post"):
            modality = "written_deliberate"
        elif context in ("line_private", "line_group"):
            modality = "written_casual"
        else:
            modality = "spoken_spontaneous"
    else:
        if context == "book_reading":
            modality = "highlighted" if authority == "endorsed" else "consumed"
        elif context in ("article_reading", "podcast_listening", "course_learning"):
            modality = "consumed"
        else:
            modality = "received"

    return direction, modality


def atom_to_signal(atom: dict, owner_id: str) -> Signal:
    """將一個 atom 轉換為 Signal。"""
    direction, modality = determine_direction_and_modality(atom)

    # signal_id: 保留 atom_id 前綴，加 sig_ 標記
    atom_id = atom.get("atom_id", "unknown")
    signal_id = f"sig_{atom_id}"

    # content type 映射
    type_map = {"open_question": "question", "action_item": "action", "cta_pattern": "instruction"}
    raw_type = atom.get("type", "observation")
    content_type = type_map.get(raw_type, raw_type)

    # content
    content = SignalContent(
        text=atom.get("content", "")[:300],
        type=content_type,
        confidence=atom.get("confidence") if atom.get("confidence") in (
            "strong_opinion", "exploring", "tentative", "quoting_others"
        ) else None,
    )

    # source
    src = atom.get("source", {})
    context_val = src.get("context", "other")
    # 確保 context 值合法
    valid_contexts = {
        "solo_thinking", "team_meeting", "one_on_one", "phone_call",
        "brainstorm", "client_meeting", "presentation", "casual_chat",
        "commute", "short_video", "social_post", "interview_guest",
        "host_interview", "line_private", "line_group", "email",
        "book_reading", "article_reading", "podcast_listening",
        "course_learning", "other",
    }
    if context_val not in valid_contexts:
        context_val = "other"

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
    aud = atom.get("audience")
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
        # directed_to 可能是 string 或 list
        raw_directed = aud.get("directed_to")
        if isinstance(raw_directed, str):
            raw_directed = [raw_directed]
        audience = SignalAudience(
            directed_to=raw_directed or None,
            visibility=vis if vis in valid_vis else None,
            relationship_context=rel if rel in valid_rel else None,
        )

    # authority
    authority_val = atom.get("authority")
    valid_auth = {"own_voice", "endorsed", "referenced", "received"}
    authority = authority_val if authority_val in valid_auth else None

    # lifecycle
    lc = atom.get("lifecycle", {})
    lifecycle = SignalLifecycle(
        active=lc.get("active", True),
        created_at=lc.get("created_at"),
    )

    # topics
    topics = atom.get("topics") or None

    return Signal(
        owner_id=owner_id,
        signal_id=signal_id,
        direction=direction,
        modality=modality,
        authority=authority,
        content=content,
        source=source,
        audience=audience,
        topics=topics,
        lifecycle=lifecycle,
    )


def migrate(
    atoms_path: Path = ATOMS_PATH,
    owner_id: str = "joey",
    compute_embeddings: bool = True,
) -> dict:
    """執行遷移，回傳統計。"""
    if not atoms_path.exists():
        print(f"找不到 atoms 檔案: {atoms_path}")
        sys.exit(1)

    # 讀取 atoms
    atoms = []
    with open(atoms_path) as f:
        for line in f:
            if line.strip():
                atoms.append(json.loads(line))

    print(f"讀取 {len(atoms)} 個 atoms")

    # 轉換
    signals = []
    errors = []
    for i, atom in enumerate(atoms):
        try:
            sig = atom_to_signal(atom, owner_id)
            signals.append(sig)
        except Exception as e:
            errors.append({"index": i, "atom_id": atom.get("atom_id", "?"), "error": str(e)})

    print(f"轉換成功: {len(signals)}，失敗: {len(errors)}")
    if errors:
        for err in errors[:5]:
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
    parser = argparse.ArgumentParser(description="Atoms → Signals 遷移")
    parser.add_argument("--atoms", type=Path, default=ATOMS_PATH)
    parser.add_argument("--owner", default="joey")
    parser.add_argument("--no-embeddings", action="store_true", help="跳過 embedding 計算（快速測試用）")
    args = parser.parse_args()

    stats = migrate(args.atoms, args.owner, compute_embeddings=not args.no_embeddings)
    print("\n=== 統計 ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
