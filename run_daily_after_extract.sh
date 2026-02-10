#!/bin/bash
# 等 extract 跑完後自動跑 daily batch
cd /Users/leochen/Documents/shifu/_dev/18-mind-spiral

echo "[$(date)] 等待 PID 56120 (extract) 完成..."
while kill -0 56120 2>/dev/null; do
    sleep 30
done

echo "[$(date)] Extract 完成，開始 daily batch..."
uv run python -c "
from engine.config import load_config
from engine.daily_batch import run_daily
import json

config = load_config()
config['engine']['llm_backend'] = 'claude_code'

result = run_daily('joey', config)
print(json.dumps(result, ensure_ascii=False, indent=2))
" 2>&1 | grep -v "Loading weights\|it/s\|Materializing"

echo "[$(date)] Daily batch 完成"
