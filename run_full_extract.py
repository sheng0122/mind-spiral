"""全量 trace extraction v2 — 背景執行用"""

import json
import sys
import time
from datetime import datetime

from engine.config import load_config, get_owner_dir
from engine.conviction_detector import detect as detect_convictions
from engine.trace_extractor import extract, _load_traces, _group_signals, _EXTRACTABLE_MODALITIES
from engine.signal_store import SignalStore

config = load_config()
config["engine"]["llm_backend"] = "claude_code"

owner_id = "joey"
owner_dir = get_owner_dir(config, owner_id)
log_path = owner_dir / "extract_log_v2.jsonl"

print(f"[{datetime.now().isoformat()}] 開始全量處理 v2（分組模式）", flush=True)

# Step 1: Conviction detection
print("[1/2] Conviction detection...", flush=True)
new_convictions, strength_changes = detect_convictions(owner_id, config)
print(f"  新 convictions: {len(new_convictions)}，strength 變動: {len(strength_changes)}", flush=True)

# Step 2: 全量 trace extraction（分批，每批 10 組）
print("[2/2] Trace extraction v2（分組模式）...", flush=True)

# 算一下總共有幾組
store = SignalStore(config, owner_id)
signals = store.load_all()
candidates = [s for s in signals if s.direction == "output" and s.modality in _EXTRACTABLE_MODALITIES]
total_groups = len(_group_signals(candidates))
print(f"  總共 {total_groups} 組（每組最多 30 signals）", flush=True)

batch_size = 10  # 每批處理 10 組
total_extracted = 0
batch_num = 0

while True:
    batch_num += 1
    start = time.time()
    print(f"  batch {batch_num}（{batch_size} 組）...", flush=True)

    new_traces = extract(owner_id, config, limit=batch_size)

    elapsed = time.time() - start
    total_extracted += len(new_traces)

    log_entry = {
        "batch": batch_num,
        "new_traces": len(new_traces),
        "total_extracted": total_extracted,
        "elapsed_sec": round(elapsed, 1),
        "timestamp": datetime.now().isoformat(),
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    print(f"  → {len(new_traces)} traces（累計 {total_extracted}，耗時 {elapsed:.0f}s）", flush=True)

    if len(new_traces) == 0:
        print("  沒有更多分組了，結束。", flush=True)
        break

# 最終統計
all_traces = _load_traces(owner_dir)
print(f"\n[{datetime.now().isoformat()}] 完成！", flush=True)
print(f"  總 traces: {len(all_traces)}", flush=True)
print(f"  本次新增: {total_extracted}", flush=True)
print(f"  log: {log_path}", flush=True)
