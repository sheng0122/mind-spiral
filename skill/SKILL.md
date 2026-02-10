---
name: mind-spiral
description: 呼叫 Mind Spiral 人類思維模型引擎，用某個人的五層認知架構來回答問題或產出內容。當需要：(1) 用 Joey 的觀點回答問題 (2) 用 Joey 的風格寫文章、貼文、腳本 (3) 取得思維原料包讓自己的 LLM 產出內容 (4) 回溯記憶、追蹤觀點變化、偵測盲區 (5) 模擬情境預測反應時使用此 Skill。透過 HTTP API 呼叫 Mind Spiral Server。
---

# Mind Spiral — 人類思維模型引擎

## 概述

Mind Spiral 從一個人的日常行為中建構五層思維模型，讓 AI 能用這個人的方式思考和表達。

五層架構：
```
Layer 5: Identity Core     身份核心（底線護欄）
Layer 4: Context Frames    情境框架（思維模式切換）
Layer 3: Reasoning Traces  推理軌跡（怎麼想的）
Layer 2: Convictions       信念層（相信什麼）
Layer 1: Signals           信號層（原始行為資料）
```

## API Server

```
BASE_URL = http://172.104.53.227:8000
```

所有回應格式：`{"status": "ok/error", "data": {...}, "meta": null}`

## Endpoints

### 1. 統一入口（推薦）

自動判斷要 query（回答問題）還是 generate（產出內容）。

```bash
curl -X POST $BASE_URL/ask \
  -H "Content-Type: application/json" \
  -d '{"owner_id": "joey", "text": "用戶的問題或指令"}'
```

回傳的 `data.mode` 會告訴你走了哪條路。

### 2. 五層查詢

用這個人的思維方式回答問題。

```bash
curl -X POST $BASE_URL/query \
  -H "Content-Type: application/json" \
  -d '{"owner_id": "joey", "question": "定價怎麼看？", "caller_id": "alice"}'
```

回傳：
- `response` — 用第一人稱「我」的回答
- `matched_frame` — 命中的情境框架
- `activated_convictions` — 被激活的信念列表
- `relevant_traces` — 相關推理軌跡數量

### 3. 內容產出

用這個人的風格產出完整內容。

```bash
curl -X POST $BASE_URL/generate \
  -H "Content-Type: application/json" \
  -d '{"owner_id": "joey", "text": "寫一篇關於行動力的文章", "output_type": "article"}'
```

`output_type` 選項：
| 類型 | 說明 | 長度 |
|------|------|------|
| `article` | 完整文章 | 800-1500 字 |
| `post` | 社群貼文 | 200-400 字 |
| `script` | 短影音腳本（含秒數標註） | 200-400 字 |
| `decision` | 決策分析 | 300-600 字 |

### 4. 統計資訊

```bash
curl "$BASE_URL/stats?owner_id=joey"
```

### 5. 健康檢查

```bash
curl $BASE_URL/health
```

### 6. 原料包模式（Context）— 推薦外部 Agent 使用

只做五層檢索，不呼叫 LLM，不消耗 token。回傳結構化的思維原料包，供你用自己的 LLM 產出內容。

```bash
curl -X POST $BASE_URL/context \
  -H "Content-Type: application/json" \
  -d '{"owner_id": "joey", "question": "定價怎麼看？", "conviction_limit": 7, "trace_limit": 8}'
```

回傳：
- `matched_frame` — 命中的情境框架（含推理模式）
- `activated_convictions` — 被激活的信念（含 strength、level、domains）
- `reasoning_traces` — 推理軌跡（含步驟、風格、結論）
- `identity_constraints` — 身份核心（底線護欄）
- `raw_signals` — 原話佐證
- `writing_style` — 寫作風格原則

**何時用 /context vs /query vs /generate：**
| 場景 | Endpoint | 說明 |
|------|----------|------|
| 你有自己的 LLM，只需要思維原料 | `/context` | < 1s，0 token |
| 需要 Mind Spiral 直接回答問題 | `/query` | ~10s，含 LLM |
| 需要 Mind Spiral 直接產出內容 | `/generate` | ~13s，含 LLM |

### 7. 寫入 Signals（需 Owner Token）

```bash
curl -X POST $BASE_URL/ingest \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MIND_SPIRAL_OWNER_TOKEN" \
  -d '{
    "owner_id": "joey",
    "signals": [
      {
        "signal_id": "sig-001",
        "direction": "output",
        "modality": "written_casual",
        "text": "信號內容",
        "date": "2026-02-10",
        "content_type": "belief",
        "context": "casual_chat"
      }
    ]
  }'
```

Signal 必要欄位：`signal_id`, `direction`, `modality`, `text`, `date`

## 認證

| 角色 | 環境變數 | 權限 |
|------|----------|------|
| owner | `MIND_SPIRAL_OWNER_TOKEN` | 全部（含 ingest） |
| agent | `MIND_SPIRAL_AGENT_TOKENS` | ask/query/generate/stats + 探索 |
| viewer | `MIND_SPIRAL_VIEWER_TOKENS` | ask/query/generate/stats + 探索 |
| public | 無 token | health/stats |

有 token 時加 header：`Authorization: Bearer <token>`

## 探索 Endpoints（六種查詢模式）

### 8. 記憶回溯（Recall）

「我什麼時候講過定價？」搜尋原話 + 時間/情境過濾。

```bash
curl -X POST $BASE_URL/recall \
  -H "Content-Type: application/json" \
  -d '{"owner_id": "joey", "text": "定價", "context": "team_meeting", "limit": 10}'
```

可選過濾：`context`、`direction`（input/output）、`date_from`、`date_to`

### 9. 思維展開（Explore）

「把我對定價的想法全部攤開來看」— 從主題串連信念、推理、框架、張力、原話。

```bash
curl -X POST $BASE_URL/explore \
  -H "Content-Type: application/json" \
  -d '{"owner_id": "joey", "topic": "定價", "depth": "full"}'
```

`depth`: `lite`（只看信念）| `full`（五層全展開）

### 10. 演變追蹤（Evolution）

「我對 AI 的看法這半年怎麼變的？」— 信念 strength 曲線 + 推理風格變化。

```bash
curl -X POST $BASE_URL/evolution \
  -H "Content-Type: application/json" \
  -d '{"owner_id": "joey", "topic": "AI"}'
```

### 11. 盲區偵測（Blind Spots）

說做不一致、只輸出沒輸入、思維慣性、矛盾張力。

```bash
curl "$BASE_URL/blindspots?owner_id=joey"
```

### 12. 關係圖譜（Connections）

「定價跟個人品牌在我腦中怎麼連？」— 找共用信念、推理、框架、張力連結。

```bash
curl -X POST $BASE_URL/connections \
  -H "Content-Type: application/json" \
  -d '{"owner_id": "joey", "topic_a": "定價", "topic_b": "個人品牌"}'
```

### 13. 模擬預測（Simulate）

「如果有人提議砍價，我會怎麼反應？」— 預測反應路徑 + 盲區提醒。

```bash
curl -X POST $BASE_URL/simulate \
  -H "Content-Type: application/json" \
  -d '{"owner_id": "joey", "scenario": "合作夥伴提議把課程定價砍半來衝量", "context": "team_meeting"}'
```

## 回應時間參考

| Endpoint 類型 | 時間 | 說明 |
|---------------|------|------|
| /health, /stats, /blindspots | < 0.5s | 純本地計算 |
| /context | < 1s | 五層檢索，不呼叫 LLM |
| /recall, /explore, /evolution, /connections | 0.3-1.6s | embedding 搜尋 |
| /query, /ask | ~10s | embedding + LLM 生成 |
| /generate | ~13s | embedding + LLM 長文生成 |
| /simulate | ~30s | embedding + LLM 深度推理 |

## 使用情境

### 情境 A：外部 Agent 用自己的 LLM 產出內容（推薦）

你是一個有 LLM 能力的 Agent，需要用 Joey 的思維寫東西 → 呼叫 `/context` 取得原料包，用自己的 LLM 搭配原料包產出。不消耗 Mind Spiral 的 LLM token。

### 情境 B：用 Joey 的觀點回答問題

用戶問「Joey 怎麼看 AI 課程定價？」→ 呼叫 `/ask`，把回傳的 `response` 給用戶。

### 情境 C：用 Joey 的風格寫內容

用戶要「幫 Joey 寫一篇社群貼文談創業」→ 呼叫 `/generate`，`output_type: "post"`。

### 情境 D：決策分析

用戶問「Joey 會怎麼決定要不要開新課？」→ 呼叫 `/generate`，`output_type: "decision"`。

### 情境 E：查看思維模型狀態

用戶想了解 Joey 的信念分佈 → 呼叫 `/stats`。

### 情境 F：回溯記憶

用戶問「Joey 什麼時候講過定價？」→ 呼叫 `/recall`，回傳原話 + 日期 + 情境。

### 情境 G：理解思維全貌

用戶想知道「Joey 對短影音的完整想法」→ 呼叫 `/explore`，depth=full。

### 情境 H：觀點變化追蹤

用戶問「Joey 對 AI 的看法有沒有改變？」→ 呼叫 `/evolution`。

### 情境 I：自我覺察

用戶想幫 Joey 做自我檢視 → 呼叫 `/blindspots`。

### 情境 J：主題關聯

用戶問「Joey 腦中定價跟品牌怎麼連在一起？」→ 呼叫 `/connections`。

### 情境 K：情境模擬

用戶問「如果有人提議砍價，Joey 會怎麼反應？」→ 呼叫 `/simulate`。

## 注意事項

- 回答都是第一人稱「我」，因為是模擬這個人的思維
- 如果回傳包含 `low_confidence: true`，表示證據不足，回答可能不夠準確
- `matched_frame` 告訴你引擎用了哪個情境框架，可用來判斷回答品質
- 目前可用的 owner_id：`joey`
- VPS 部署地址：`http://172.104.53.227:8000`
