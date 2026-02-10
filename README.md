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

## 安裝

```bash
cd 18-mind-spiral
uv sync
```

## CLI 指令

```bash
# 基本狀態
mind-spiral stats --owner joey

# 核心螺旋
mind-spiral detect --owner joey              # 信念偵測（Layer 2）
mind-spiral extract --owner joey --limit 10  # 推理軌跡提取（Layer 3）
mind-spiral cluster --owner joey             # 情境框架聚類（Layer 4）
mind-spiral scan-identity --owner joey       # 身份核心掃描（Layer 5）

# 日常 / 週報
mind-spiral daily --owner joey               # 每日整理（detect + extract + digest）
mind-spiral weekly --owner joey              # 每週報告（信念變化 + 矛盾 + 回顧）

# 決策追蹤
mind-spiral followups --owner joey           # 待追蹤決策清單
mind-spiral outcome --owner joey --trace-id xxx --result positive --note "成效不錯"

# 數位分身互動（推薦用 ask 統一入口）
mind-spiral ask --owner joey "定價怎麼看？"                    # 自動判斷 → query
mind-spiral ask --owner joey "幫我寫一篇關於創業的短影音腳本"    # 自動判斷 → generate
mind-spiral query --owner joey "定價怎麼看？"                  # 直接 query
mind-spiral generate --owner joey --type article "寫一篇關於行動力的文章"

# 維護
mind-spiral build-index --owner joey         # 建立向量索引（一次性）
mind-spiral dedupe --owner joey              # 信念語義去重
mind-spiral dedupe --owner joey --dry-run    # 預覽去重結果
```

## API Server

### 啟動

```bash
# 本地開發
uv run uvicorn engine.api:app --reload --port 8000

# Docker 部署
docker compose up -d --build
```

### 基礎 Endpoints

| Endpoint | Method | 認證 | 說明 |
|----------|--------|------|------|
| `/health` | GET | 不需 | 版本 + uptime + ChromaDB 狀態 |
| `/stats` | GET | 不需 | 五層數據統計 |
| `/ask` | POST | 任何角色 | 統一入口（自動判斷 query/generate） |
| `/query` | POST | 任何角色 | 五層感知查詢 |
| `/generate` | POST | 任何角色 | 內容產出（article/post/script/decision） |
| `/context` | POST | 任何角色 | 原料包模式 — 只做五層檢索不呼叫 LLM，供外部 Agent 用 |
| `/ingest` | POST | owner | 寫入 signals |

### 探索 Endpoints

| Endpoint | Method | 說明 |
|----------|--------|------|
| `/recall` | POST | 記憶回溯 — 搜尋原話 + 時間/情境過濾 |
| `/explore` | POST | 思維展開 — 從主題串連五層資料成樹狀結構 |
| `/evolution` | POST | 演變追蹤 — 信念 strength 變化 + 推理風格演變 |
| `/blindspots` | GET | 盲區偵測 — 說做不一致、思維慣性、輸入輸出失衡 |
| `/connections` | POST | 關係圖譜 — 找兩主題間的隱性連結 |
| `/simulate` | POST | 模擬預測 — 假設情境下的反應路徑 + 盲區提醒 |

### 使用範例

```bash
# 查詢
curl http://localhost:8000/health
curl "http://localhost:8000/stats?owner_id=joey"

# 數位分身
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","text":"定價怎麼看？"}'

curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","text":"寫一篇關於行動力的短影音腳本","output_type":"script"}'

# 原料包（不呼叫 LLM，供外部 Agent 用自己的 LLM 搭配產出）
curl -X POST http://localhost:8000/context \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","question":"定價怎麼看？"}'

# 探索
curl -X POST http://localhost:8000/recall \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","text":"定價","limit":5}'

curl -X POST http://localhost:8000/explore \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","topic":"短影音","depth":"full"}'

curl -X POST http://localhost:8000/evolution \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","topic":"AI"}'

curl "http://localhost:8000/blindspots?owner_id=joey"

curl -X POST http://localhost:8000/connections \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","topic_a":"定價","topic_b":"個人品牌"}'

curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","scenario":"合作夥伴提議把課程定價砍半來衝量"}'

# 寫入 signals（需 owner token）
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer $MIND_SPIRAL_OWNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"owner_id":"joey","signals":[{"signal_id":"s1","direction":"input","modality":"written_casual","text":"測試","date":"2026-02-10","content_type":"idea"}]}'
```

### 認證

`Authorization: Bearer <token>`

| 角色 | 環境變數 | 權限 |
|------|----------|------|
| owner | `MIND_SPIRAL_OWNER_TOKEN` | 所有操作（含 /ingest） |
| agent | `MIND_SPIRAL_AGENT_TOKENS`（逗號分隔） | 查詢 + 生成 |
| viewer | `MIND_SPIRAL_VIEWER_TOKENS`（逗號分隔） | 查詢 |
| public | 不帶 token | /health, /stats |

## Docker 部署

```bash
# 建立 .env
cat > .env << EOF
ANTHROPIC_API_KEY=sk-ant-...
MIND_SPIRAL_OWNER_TOKEN=your-owner-token
HF_TOKEN=hf_...               # HuggingFace token（embeddinggemma-300m 需要）
EOF

# 啟動
docker compose up -d --build

# 查看 logs
docker compose logs -f

# 停止
docker compose down
```

`data/` 目錄透過 volume 掛載，容器重建不會遺失資料。

## MCP Server（Claude Desktop 整合）

在 Claude Desktop 設定中加入：

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

### 12 個 MCP Tools

| Tool | 說明 |
|------|------|
| `mind_spiral_ask` | 統一入口 — 自動判斷 query 或 generate |
| `mind_spiral_query` | 五層感知查詢 — 用這個人的思維方式回答問題 |
| `mind_spiral_generate` | 內容產出 — article/post/script/decision |
| `mind_spiral_context` | 原料包 — 只做五層檢索不呼叫 LLM，供外部 Agent 用 |
| `mind_spiral_stats` | 五層數據統計 |
| `mind_spiral_ingest` | 寫入 signals |
| `mind_spiral_recall` | 記憶回溯 — 搜尋原話 + 時間/情境過濾 |
| `mind_spiral_explore` | 思維展開 — 從主題串連五層資料 |
| `mind_spiral_evolution` | 演變追蹤 — 信念 strength 變化曲線 |
| `mind_spiral_blindspots` | 盲區偵測 — 說做不一致、思維慣性 |
| `mind_spiral_connections` | 關係圖譜 — 兩主題間的隱性連結 |
| `mind_spiral_simulate` | 模擬預測 — 假設情境下的反應路徑 |

## 環境變數

| 變數 | 必要 | 說明 |
|------|------|------|
| `ANTHROPIC_API_KEY` | cloud 模式 | Anthropic API key |
| `HF_TOKEN` | 是 | HuggingFace token（embeddinggemma-300m 需要認證） |
| `MIND_SPIRAL_OWNER_TOKEN` | API Server | Owner 認證 token |
| `MIND_SPIRAL_AGENT_TOKENS` | 選填 | Agent tokens（逗號分隔） |
| `MIND_SPIRAL_VIEWER_TOKENS` | 選填 | Viewer tokens（逗號分隔） |
| `MIND_SPIRAL_DATA_DIR` | 選填 | 資料根目錄（預設 `./data`） |
| `MIND_SPIRAL_CORS_ORIGINS` | 選填 | CORS 允許來源（逗號分隔，預設 `*`） |
| `LLM_BACKEND` | 選填 | `claude_code`（預設）/ `cloud` / `local` |

## LLM Backend

| Backend | 用途 | 說明 |
|---------|------|------|
| `claude_code` | 本地開發 | 透過 Claude Agent SDK，不需 API key |
| `cloud` | VPS 部署 | 直接呼叫 Anthropic API，三檔 model mapping |
| `local` | 離線使用 | Ollama localhost:11434 |

`cloud` backend 三檔制：heavy=Sonnet（最終生成）、medium=Sonnet（歸納推理）、light=Haiku（分類填表）。

## 文件

- [PRD.md](PRD.md) — 產品需求文件
- [MIND_SPIRAL.md](MIND_SPIRAL.md) — 五層架構設計
- [HANDOFF.md](HANDOFF.md) — 交接文件（含數據現況）
- [schemas/](schemas/) — 五層 JSON Schema
- [CLAUDE.md](CLAUDE.md) — 開發指引
