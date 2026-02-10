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

### 基礎 Endpoints

| Endpoint | Method | 認證 | 說明 |
|----------|--------|------|------|
| `/health` | GET | 不需 | 版本 + uptime + ChromaDB 狀態 |
| `/stats` | GET | 不需 | 五層數據統計 |
| `/ask` | POST | 任何角色 | 統一入口（自動判斷 query/generate） |
| `/query` | POST | 任何角色 | 五層感知查詢 |
| `/generate` | POST | 任何角色 | 內容產出（article/post/script/decision） |
| `/ingest` | POST | owner | 寫入 signals |

### 探索 Endpoints（六種查詢模式）

| Endpoint | Method | 說明 | 用途 |
|----------|--------|------|------|
| `/recall` | POST | 記憶回溯 | 「我什麼時候講過定價？」搜尋原話 + 時間/情境過濾 |
| `/explore` | POST | 思維展開 | 「把我對定價的想法全部攤開」從主題串連五層資料成樹狀結構 |
| `/evolution` | POST | 演變追蹤 | 「我對 AI 的看法這半年怎麼變的？」信念 strength 曲線 + 推理風格演變 |
| `/blindspots` | GET | 盲區偵測 | 說做不一致、只輸出沒輸入、思維慣性、矛盾張力 |
| `/connections` | POST | 關係圖譜 | 「定價跟個人品牌在我腦中怎麼連？」找兩主題間的隱性連結 |
| `/simulate` | POST | 模擬預測 | 「如果有人提議砍價，我會怎麼反應？」預測反應路徑 + 盲區提醒 |

#### 使用範例

```bash
# 記憶回溯：我什麼時候講過定價？
curl -X POST http://localhost:8000/recall \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","text":"定價","limit":5}'

# 思維展開：攤開我對短影音的完整想法
curl -X POST http://localhost:8000/explore \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","topic":"短影音","depth":"full"}'

# 演變追蹤：我對 AI 的看法怎麼變的？
curl -X POST http://localhost:8000/evolution \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","topic":"AI"}'

# 盲區偵測
curl "http://localhost:8000/blindspots?owner_id=joey"

# 關係圖譜：定價跟個人品牌怎麼連？
curl -X POST http://localhost:8000/connections \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","topic_a":"定價","topic_b":"個人品牌"}'

# 模擬預測：合作夥伴提議砍價，我會怎麼反應？
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","scenario":"合作夥伴提議把課程定價砍半來衝量","context":"team_meeting"}'
```

### 認證

`Authorization: Bearer <token>`，環境變數 `MIND_SPIRAL_OWNER_TOKEN` / `MIND_SPIRAL_AGENT_TOKENS` / `MIND_SPIRAL_VIEWER_TOKENS`。

### MCP Server（Claude Desktop 整合）

```json
{
  "mcpServers": {
    "mind-spiral": {
      "command": "uv",
      "args": ["--directory", "/path/to/18-mind-spiral", "run", "python", "-m", "engine.mcp_server"]
    }
  }
}
```

提供 11 個 tools：ask, query, generate, stats, ingest, recall, explore, evolution, blindspots, connections, simulate。

## 文件

- [PRD.md](PRD.md) — 產品需求文件
- [MIND_SPIRAL.md](MIND_SPIRAL.md) — 五層架構設計
- [schemas/](schemas/) — 五層 JSON Schema
- [CLAUDE.md](CLAUDE.md) — 開發指引
