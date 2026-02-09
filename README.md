# Mind Spiral

被動觀察一個人的日常行為，自動建構五層思維模型，讓 AI 數位分身能用這個人的方式思考。

## 核心概念

**一個人真正相信什麼，不看他宣稱什麼，看他輸入和輸出的交叉收斂。**

系統從使用者已有的行為（瀏覽、開會、聊天、發文、讀書）中被動擷取信號，在背景建構五層思維模型：

```
Layer 5: Identity Core     身份核心（5-15 條）
Layer 4: Context Frames    情境框架
Layer 3: Reasoning Traces  推理軌跡
Layer 2: Convictions       信念層
Layer 1: Signals           信號層
```

使用者每天花不到 2 分鐘。大部分時候是 0。

## API Server

Mind Spiral 提供 FastAPI HTTP API，可被外部 Agent 呼叫：

```bash
# 啟動
uv run uvicorn engine.api:app --reload --port 8000

# 查詢
curl http://localhost:8000/health
curl "http://localhost:8000/stats?owner_id=joey"
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","text":"定價怎麼看？"}'
```

| Endpoint | Method | 認證 | 說明 |
|----------|--------|------|------|
| `/health` | GET | 不需 | 版本 + uptime + ChromaDB 狀態 |
| `/stats` | GET | 不需 | 五層數據統計 |
| `/ask` | POST | 任何角色 | 統一入口（自動判斷 query/generate） |
| `/query` | POST | 任何角色 | 五層感知查詢 |
| `/generate` | POST | 任何角色 | 內容產出（article/post/script/decision） |
| `/ingest` | POST | owner | 寫入 signals |

認證：`Authorization: Bearer <token>`，環境變數 `MIND_SPIRAL_OWNER_TOKEN` / `MIND_SPIRAL_AGENT_TOKENS` / `MIND_SPIRAL_VIEWER_TOKENS`。

## 文件

- [PRD.md](PRD.md) — 產品需求文件
- [MIND_SPIRAL.md](MIND_SPIRAL.md) — 五層架構設計
- [schemas/](schemas/) — 五層 JSON Schema
- [CLAUDE.md](CLAUDE.md) — 開發指引
