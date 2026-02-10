---
name: mind-spiral
description: 呼叫 Mind Spiral 人類思維模型引擎，用某個人的五層認知架構來回答問題或產出內容。當需要：(1) 用 Joey 的觀點回答問題 (2) 用 Joey 的風格寫文章、貼文、腳本 (3) 取得思維原料包讓自己的 LLM 產出內容 (4) 回溯記憶、追蹤觀點變化、偵測盲區 (5) 模擬情境預測反應時使用此 Skill。透過 HTTP API 呼叫 Mind Spiral Server。
---

# Mind Spiral — 人類思維模型引擎

```
BASE_URL = http://joey.shifu-ai.org:8000
```

回應格式：`{"status": "ok/error", "data": {...}, "meta": null}`

## 路由決策

根據需求選擇 endpoint：

| 你要做什麼 | Endpoint | 方法 | 速度 |
|-----------|----------|------|------|
| 讓 Mind Spiral 直接回答（最簡單） | `/ask` | POST | ~10s |
| 取思維原料自己組裝（推薦 Agent） | `/context` | POST | < 1s |
| 指定回答問題 | `/query` | POST | ~10s |
| 指定產出內容 | `/generate` | POST | ~13s |
| 搜尋原話記憶 | `/recall` | POST | ~1s |
| 展開某主題的完整思維 | `/explore` | POST | ~1s |
| 追蹤觀點演變 | `/evolution` | POST | ~1s |
| 偵測思維盲區 | `/blindspots` | GET | < 0.5s |
| 找兩個主題的關聯 | `/connections` | POST | ~1s |
| 模擬情境預測反應 | `/simulate` | POST | ~30s |
| 寫入新信號（需 owner token） | `/ingest` | POST | < 1s |
| 查看統計 | `/stats` | GET | < 0.5s |
| 健康檢查 | `/health` | GET | < 0.5s |

## 常用 Endpoints

### /ask — 統一入口（推薦）

```json
POST /ask
{"owner_id": "joey", "text": "用戶的問題或指令"}
```

自動判斷 query 或 generate，回傳 `data.mode` 告訴你走了哪條路。

### /context — 原料包（推薦外部 Agent）

```json
POST /context
{"owner_id": "joey", "question": "定價怎麼看？", "conviction_limit": 7, "trace_limit": 8}
```

不呼叫 LLM、不消耗 token。回傳五層結構化原料：`matched_frame`、`activated_convictions`、`reasoning_traces`、`identity_constraints`、`raw_signals`、`writing_style`。

拿到原料後，參考 [context-assembly.md](references/context-assembly.md) 組裝回應。

### /generate — 內容產出

```json
POST /generate
{"owner_id": "joey", "text": "寫一篇關於行動力的文章", "output_type": "article"}
```

`output_type`：`article`（800-1500字）| `post`（200-400字）| `script`（200-400字，含秒數）| `decision`（300-600字）

### /query — 五層查詢

```json
POST /query
{"owner_id": "joey", "question": "定價怎麼看？", "caller_id": "alice"}
```

### /ingest — 寫入信號（需 Owner Token）

```json
POST /ingest
Headers: Authorization: Bearer $MIND_SPIRAL_OWNER_TOKEN
{"owner_id": "joey", "signals": [{"signal_id": "sig-001", "direction": "output", "modality": "written_casual", "text": "內容", "date": "2026-02-10"}]}
```

## 探索 Endpoints

| Endpoint | 用途 | 範例 payload |
|----------|------|-------------|
| `/recall` | 搜尋原話 | `{"owner_id": "joey", "text": "定價", "limit": 10}` |
| `/explore` | 主題全展開 | `{"owner_id": "joey", "topic": "定價", "depth": "full"}` |
| `/evolution` | 觀點演變 | `{"owner_id": "joey", "topic": "AI"}` |
| `/blindspots` | 盲區偵測 | GET `?owner_id=joey` |
| `/connections` | 主題關聯 | `{"owner_id": "joey", "topic_a": "定價", "topic_b": "個人品牌"}` |
| `/simulate` | 情境模擬 | `{"owner_id": "joey", "scenario": "合作夥伴提議砍價", "context": "team_meeting"}` |

## 認證

**查詢類 endpoint 不需要 token**，直接呼叫即可（/ask、/context、/query、/generate、探索 endpoints、/stats、/health）。

唯一需要認證的是 `/ingest`（寫入信號），必須帶 owner token：`Authorization: Bearer $MIND_SPIRAL_OWNER_TOKEN`

## 深度參考

需要更多指引時，按需讀取：

- [references/context-assembly.md](references/context-assembly.md) — 用 /context 原料組裝回應的六步框架
- [references/joey-profile.md](references/joey-profile.md) — Joey 的思維模式、回應原則、寫作風格

## 注意事項

- 回答都是第一人稱「我」，模擬這個人的思維
- `low_confidence: true` 表示證據不足，回答可能不準確
- 目前可用 owner_id：`joey`
