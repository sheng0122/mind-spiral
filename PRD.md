# Mind Spiral — Product Requirements Document

## 產品願景

**一句話**：被動觀察一個人的日常行為，自動建構他的思維模型，讓 AI 數位分身能用這個人的方式思考、推理、回應。

**目標用戶**：創業者、講師、創作者 — 每天產生大量想法但沒時間整理的人。

**核心假設**：一個人真正相信什麼，不看他宣稱什麼，看他**輸入和輸出的交叉收斂**。

**設計原則**：
- **零摩擦** — 使用者不需要改變任何日常行為
- **被動擷取** — 從已有行為中自動收集信號
- **主動觸碰** — 只在有價值的事要說時，用最輕的方式觸碰使用者
- **湧現而非宣告** — 信念、推理模式、身份都是從資料中偵測出來的
- **Multi-tenant** — 引擎共用，每個人的思維模型完全獨立

---

## 思維模型架構

> 完整架構文件見 `MIND_SPIRAL.md`，完整 schema 見 `schemas/`。

### 五層架構

```
Layer 5: Identity Core     身份核心（5-15 條）
Layer 4: Context Frames    情境框架
Layer 3: Reasoning Traces  推理軌跡
Layer 2: Convictions       信念層
Layer 1: Signals           信號層
```

由下而上湧現，由上而下約束。詳見 `MIND_SPIRAL.md`。

---

## 產品形態：隱形收集 + 主動觸碰

### 架構總覽

```
使用者的日常生活（不改變任何行為）
│
│  被動擷取（零摩擦）
│
├── 瀏覽器 ──→ 瀏覽器插件（靜默）──→ 搜尋詞、點擊、停留、畫線
├── 開會 ────→ 會議錄音 ──────────→ 逐字稿
├── 聊天 ────→ LINE 整合 ─────────→ 對話內容
├── 發文 ────→ 社群追蹤 ─────────→ 貼文 + 互動數據
├── 讀書 ────→ 閱讀匯入 ─────────→ 畫線 + 筆記
│
└──────────── 全部匯入 ──→ Mind Spiral Engine（背景）
                                    │
                             主動觸碰（低頻、高價值）
                                    │
                                    ▼
                            LINE Channel（唯一出口）
                            ├── 每日早晨整理
                            ├── 矛盾偵測通知
                            ├── 決策追蹤回訪
                            └── 信念週報
```

---

## 被動擷取層

### 1. 瀏覽器插件（核心新元件）

主動搜尋是最強的興趣信號。

| 行為 | 信號類型 | 強度 |
|------|----------|------|
| 搜尋關鍵字 | `input/searched` | ★★★★ 主動興趣 |
| 搜尋後點擊特定結果 | `input/selected` | ★★★★★ 判斷偏好 |
| 頁面停留 >30 秒 | `input/consumed` | ★★ 注意力 |
| 畫線/複製 | `input/highlighted` | ★★★★★ 認同或想記住 |
| 連續搜尋（搜尋鏈） | 探索路徑 | ★★★★★ 思考軌跡 |

搜尋鏈的特殊價值：連續搜尋串起來 = 一條探索路徑，是 reasoning trace 的原始素材。

插件設計原則：
- **完全靜默** — 不彈通知、不問問題、不在頁面上加 UI
- **只記錄，不干擾** — 背景同步到 Engine
- **隱私優先** — 資料存本地，不上傳第三方，可設定排除網站

### 2. 會議錄音

自動錄音 → 轉錄 → signal pipeline。由各 instance 的輸入管線處理。

### 3. LINE 整合

聊天記錄自動進入 signal pipeline。

### 4. 社群追蹤

貼文：`output/written_deliberate` signal。互動數據：outcome feedback。

### 5. 閱讀匯入

書籍/文章：`input/consumed` 或 `input/highlighted`。

---

## 主動觸碰層

系統只透過 LINE 觸碰使用者。

### 觸碰 1：每日早晨整理（每天）

整理昨天的 input 和 output，標示交叉收斂。

```
☀️ 昨日整理

📖 你搜尋了「value-based pricing」相關內容，
   看了 3 篇文章，在其中一篇畫了線：
   「定價的錨點應該是客戶感知的價值，不是你的成本」

🎙️ 下午跟 Alice 的會議中你提到：
   「我們的課程定價要重新想，
    不能只看同業在收多少」

💡 這兩件事指向同一個方向——
   你對「價值定價」的信念正在增強 (0.72 → 0.78)

有什麼想補充的嗎？或者直接忽略也行 👌
```

三種回應都有價值：回覆補充 → 強化 conviction；回覆修正 → 校準 conviction；已讀不回 → 也是信號（降低該主題權重）。

### 觸碰 2：矛盾偵測（事件驅動，每週 1-3 次）

```
⚡ 發現一個有趣的變化

三週前你說：「先把免費內容做好，付費的之後再說」
但昨天你搜尋了「課程預售策略」，還看了兩篇 MVP 定價的文章。

想法有轉變嗎？還是這是不同情境？
```

回應處理：「改主意了」→ evolution_chain；「不同情境」→ context_dependent；不回 → 不改動。

### 觸碰 3：決策追蹤（定時回訪，每週 1-2 次）

```
📋 三週前的決定追蹤

2/6 你決定新課程定價 $2,999
當時的理由是「反映價值，不跟同業比價」

結果怎麼樣？
1️⃣ 比預期好
2️⃣ 差不多
3️⃣ 不如預期
4️⃣ 還沒有結果
```

三秒回一個數字，螺旋的回饋環就完成了。

排程邏輯：戰術決策 1-2 週、策略決策 1-3 個月、人事決策 1 個月。

### 觸碰 4：信念週報（每週一次）

```
📊 本週你的思維變化

增強中：↑ 價值定價（出現 5 次，跨 3 種情境）
減弱中：↓ 先免費再付費（三週沒提到）
新張力：⚡「品牌不打折」vs「新產品先求驗證」
探索路徑：定價策略 → SaaS 模式 → 訂閱制 → LTV 計算
```

### 使用者時間預算

| 觸碰 | 頻率 | 使用者時間 |
|------|------|-----------|
| 早晨整理 | 每天 | 0-60 秒 |
| 矛盾偵測 | 每週 1-3 次 | 0-30 秒 |
| 決策追蹤 | 每週 1-2 次 | 3 秒 |
| 信念週報 | 每週 1 次 | 0-2 分鐘 |
| **合計** | | **每天 < 2 分鐘** |

---

## Multi-tenant 架構

### 使用者模型

每個使用者一個 `owner_id`，資料完全隔離。

```
data/
├── joey/
│   ├── signals.jsonl
│   ├── convictions.jsonl
│   ├── traces.jsonl
│   ├── frames.jsonl
│   └── identity.json
├── alice/
│   └── ...
```

### Onboarding 流程

新使用者加入時需要：

1. **安裝瀏覽器插件** — 最低門檻的被動擷取
2. **連結 LINE** — 接收觸碰的出口
3. **（可選）匯入歷史資料** — 既有的逐字稿、文章、書籍，加速冷啟動

冷啟動預估：
- 純靠瀏覽器插件：2-3 週開始有 conviction 浮現
- 有歷史資料匯入：第一天就能偵測 conviction

### Instance 與引擎的關係

```
┌─────────────────────┐     ┌─────────────────────┐
│  Joey Instance       │     │  Alice Instance      │
│  (16_moltbot_joey)   │     │  (獨立或同 repo)      │
│                      │     │                      │
│  process_daily.py    │     │  process_daily.py    │
│  process_content.py  │     │  process_chat.py     │
│  process_chat.py     │     │  ...                 │
│  process_reading.py  │     │                      │
│  ...                 │     │                      │
└──────────┬───────────┘     └──────────┬───────────┘
           │ signals                     │ signals
           ▼                             ▼
┌───────────────────────────────────────────────────┐
│              Mind Spiral Engine                     │
│              (18-mind-spiral)                       │
│                                                     │
│  conviction_detector → trace_extractor              │
│  → frame_clusterer → identity_scanner               │
│  → daily_digest → contradiction_alert               │
│  → decision_tracker → query_engine                  │
└───────────────────────────────────────────────────┘
           │                             │
           ▼                             ▼
   LINE (Joey)                    LINE (Alice)
```

每個 instance 負責自己的**輸入管線**（把原始素材轉成 signal）。引擎負責**所有 Layer 2-5 的運算 + 主動觸碰**。

---

## 處理管線

### Signal Ingestion（Layer 1）

由各 instance 的輸入管線負責，輸出統一的 signal 格式到 `data/{owner_id}/signals.jsonl`。

引擎提供 `signal_store.py`：
- `ingest(owner_id, signals: list[Signal])` — 寫入
- `query(owner_id, topics, date_range, direction)` — 查詢
- `stats(owner_id)` — 統計

### Conviction Detection（Layer 2）

`conviction_detector.py` — 離線批次，掃描新 signal vs 既有 signal：

```
新 signal 進來
  → 語意比對：跟哪些既有 signal 相似？
  → 共鳴偵測：五種共鳴類型
  → 匹配到既有 conviction？→ 更新 strength
  → 沒匹配？信號夠強？→ 建立新 conviction
```

### Reasoning Trace Extraction（Layer 3）

`trace_extractor.py` — 從 output signal 的論述/決策段落中提取推理軌跡。

### Context Frame Clustering（Layer 4）

`frame_clusterer.py` — 每週執行，從 traces 聚類出情境框架。

### Identity Detection（Layer 5）

`identity_scanner.py` — 每月執行，掃描 conviction 的跨 frame 覆蓋率。

### Proactive Touch

| 模組 | 頻率 | 觸發 |
|------|------|------|
| `daily_digest.py` | 每天 | cron |
| `contradiction_alert.py` | 事件驅動 | conviction detection 時偵測到矛盾 |
| `decision_tracker.py` | 排程 | trace 中有 conclusion.confidence != uncertain |
| 週報 | 每週 | cron |

### Query Engine

`query_engine.py` — 數位分身回答問題：

```
query(owner_id, caller, question)
  → Frame Matching → Conviction Activation
  → Trace Retrieval → Identity Check
  → Response Generation
```

---

## 基礎設施

### 本地部署

```
Mac Mini (Apple Silicon)
├── Mind Spiral Engine      Python package
├── Ollama                  LLM 推理
├── ChromaDB                向量索引
├── FastAPI                 API（查詢 + LINE webhook + 插件接收）
└── cron                    定期運算排程
```

### 雲端（未來）

```
Cloudflare
├── AI Gateway      LLM 路由
├── Vectorize       向量 DB
├── Workers         API
├── R2              備份
└── D1 / KV         使用者設定
```

### 費用

| 項目 | 本地 | 雲端 |
|------|------|------|
| LLM | $0（Ollama） | ~$1/月/人 |
| Vector DB | $0（ChromaDB） | $0（free tier） |
| 備份 | — | $0（R2 free） |
| **每人月費** | **$0** | **~$1** |

---

## 開發路線圖

### Phase 0 — 基礎建設（現在）

| 項目 | 狀態 |
|------|------|
| 五層 schema 設計（multi-tenant） | ✅ |
| 架構文件（MIND_SPIRAL.md） | ✅ |
| PRD | ✅ |
| 專案結構 | ✅ |
| engine/ 基本框架（models, config, llm） | 🔲 |
| signal_store.py（CRUD） | 🔲 |
| Joey atoms → signals 遷移工具 | 🔲 |

### Phase 1 — 核心螺旋

| 項目 | 優先級 |
|------|--------|
| conviction_detector.py | P0 |
| trace_extractor.py | P0 |
| LINE Bot 基礎（早晨整理 + 矛盾通知） | P0 |
| decision_tracker.py | P1 |
| 信念週報生成 | P1 |

### Phase 2 — 被動擷取

| 項目 | 優先級 |
|------|--------|
| 瀏覽器插件（搜尋/點擊/停留/畫線） | P0 |
| 搜尋鏈偵測 | P1 |
| process_browsing.py | P0 |
| 社群追蹤 | P2 |

### Phase 3 — 數位分身

| 項目 | 優先級 |
|------|--------|
| frame_clusterer.py | P0 |
| identity_scanner.py | P1 |
| query_engine.py（五層感知 RAG） | P0 |
| 使用者修正學習 | P1 |
| Voice Profile | P2 |

### Phase 4 — 多人 + 產品化

| 項目 | 優先級 |
|------|--------|
| Onboarding 流程 | P0 |
| 第二個使用者上線 | P0 |
| 信念演變視覺化 | P1 |
| 內容生成（從 conviction + voice） | P2 |
| Web dashboard | P2 |

---

## 外部整合層：Mind Spiral 作為獨立服務

> 2026-02-09 設計。Mind Spiral 引擎從「本地 CLI 工具」演進為「獨立 API Server」，可被多個前端 Agent（OpenClaw、LINE Bot、MCP Client 等）呼叫。

### 設計動機

Mind Spiral 的核心價值不在介面層（OpenClaw / LINE），而在五層思維模型。將引擎獨立部署為 API Server，可以：

1. **一個模型，多個出口** — OpenClaw、LINE Bot、瀏覽器插件、MCP Client 都能存取同一份思維模型
2. **前端解耦** — 換 Agent 平台不需要改引擎
3. **存取控制統一** — 所有呼叫者透過同一個 API 認證，不需要每個前端各自實作

### 呼叫者分類與權限

四種角色，權限遞減：

| 角色 | 範例 | 可呼叫 API | Signal 寫入 | Demand Log |
|------|------|-----------|-------------|------------|
| **① Owner（本人）** | Joey 自己的 OpenClaw / LINE | 全部 | ✅ output signals | — |
| **② Agent（代理人）** | 自動發文 Agent、Email Agent | query / generate | ⚠️ 需確認機制（見下方） | — |
| **③ Viewer（外部查詢者）** | 客戶、團隊、朋友的 OpenClaw | query / generate（存取控制過濾） | ❌ | ✅ 自動側錄 |
| **④ System（系統呼叫）** | MCP Server、CI/CD、Webhook | 特定 endpoint | ❌ | ✅ usage log |

認證方式：

```
① Owner    → owner_token（完整讀寫權限）
② Agent    → agent_token（讀取 + 受限寫入）
③ Viewer   → caller_token + caller_id（讀取 + demand 側錄）
④ System   → api_key（讀取 + usage 側錄）
```

### API 設計

```
Mind Spiral Server
│
├─ POST /query          五層感知 RAG（回答問題）
├─ POST /generate       內容生成（文章/貼文/腳本/決策）
├─ POST /ask            統一入口（自動路由 query or generate）
├─ POST /ingest         寫入 signals（僅 ① Owner）
├─ GET  /stats          知識庫統計
├─ GET  /demand/stats   Demand 分析報告
│
│  以下為 ② Agent 專用
├─ POST /agent/confirm  代理人行為確認（見「代理人問題」）
│
│  以下為內部
├─ POST /detect         觸發 conviction detection
├─ POST /extract        觸發 trace extraction
└─ GET  /health         健康檢查
```

### 迴路設計：誰的資料可以回寫？

Mind Spiral 的核心假設是「從真實行為中偵測信念」。不同來源的資料有不同的可信度：

```
┌──────────────────────────────────────────────────────────┐
│                    Mind Spiral Server                      │
│                                                            │
│  signals.jsonl ← 只接受可信來源的寫入                        │
│  demand.jsonl  ← 所有非 Owner 的查詢自動側錄                 │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 可信來源（可寫入 signals）                              │ │
│  │                                                        │ │
│  │  ① Joey 本人的對話 → direction: output                 │ │
│  │    modality: written_casual / spoken_spontaneous        │ │
│  │                                                        │ │
│  │  ② 代理人行為（經 Joey 確認後）→ direction: output      │ │
│  │    modality: agent_generated_confirmed                  │ │
│  │                                                        │ │
│  │  既有管線（process_daily / content / chat / reading）    │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 不可信來源（不寫入 signals，寫入 demand）               │ │
│  │                                                        │ │
│  │  ③ 外部查詢者的問題 → demand log                       │ │
│  │  ④ 系統呼叫的 metadata → usage log                     │ │
│  │  ② 代理人未經確認的產出 → 不記錄                        │ │
│  └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### 代理人問題：AI 代替你說的話算不算你說的？

當 ② Agent 用 mind-spiral 的 generate() 產出內容（自動發社群貼文、自動回信），外界看到的是「Joey 說的」，但 Joey 本人並沒有真的說過。

三種策略：

| 策略 | 做法 | 適用場景 |
|------|------|----------|
| **不回寫** | 代理人產出不進 signals | 低風險自動化（回覆罐頭訊息） |
| **標記回寫** | 進 signals，modality = `agent_generated`，conviction 權重 ×0.3 | 風格一致但非 Joey 本人的產出 |
| **確認後回寫** | Joey 審核後轉為 `agent_generated_confirmed`，權重 ×0.8 | 重要的公開發言、決策 |

建議：預設「不回寫」，只有 Joey 主動確認的才進模型。避免 AI 自我強化的迴路（AI 生成 → 寫入模型 → 影響下次生成 → 越來越偏）。

### Demand Signal：外界認知的鏡子

當 ③ Viewer 或 ④ System 查詢 Mind Spiral 時，問題本身就是有價值的信號 — 不是關於 Joey 怎麼想，而是關於**外界認為 Joey 能回答什麼**。

#### Demand Log 格式

```jsonl
{
  "date": "2026-02-09",
  "caller_id": "alice",
  "caller_role": "viewer",
  "source_agent": "openclaw-team",
  "question": "定價怎麼看？",
  "matched_frame": "價值驅動的務實行動框架",
  "topics": ["pricing", "strategy"],
  "interaction": {
    "followup_count": 2,
    "session_duration_sec": 180
  }
}
```

#### Demand 分析維度

| 維度 | 分析內容 | 價值 |
|------|----------|------|
| **Topic Demand** | 哪些主題被問最多 | Joey 的外界專業形象 |
| **Framing Demand** | 怎麼問的（「你覺得...」vs「幫我分析...」） | 外界對 Joey 的角色認知（顧問 vs 工具） |
| **Satisfaction Signal** | 追問、離開、反問 | 回答品質 + 話題深度 |
| **Audience Pattern** | 誰在問（創業者、投資人、學生） | Joey 的受眾畫像 |

#### Demand × Conviction 落差分析

交叉比對 demand 頻率和 conviction strength，揭示自我認知與外界認知的差距：

| conviction 高 + demand 高 | 核心領域，內外一致 |
|---|---|
| **conviction 高 + demand 低** | Joey 很懂但沒人知道（隱藏優勢 → 可主動推廣） |
| **conviction 低 + demand 高** | 別人以為他懂但其實不深（風險 → 需加強或澄清） |
| conviction 低 + demand 低 | 不相關，忽略 |

此分析可定期產出報告，透過主動觸碰（LINE Bot）回饋給 Joey：

```
📊 外界認知報告（本月）

🔥 高需求主題：
  AI 應用（被問 23 次）— 但你的 conviction 只有 0.35
  → 要不要多聊聊這個領域？

💎 隱藏優勢：
  系統化思維（conviction 0.82）— 但只被問 2 次
  → 外界還不知道你很擅長這個

👥 受眾變化：
  本月新增 3 位投資人提問（上月 0 位）
  → 你的內容可能開始觸及新族群
```

### 部署架構

```
┌─────────────────────────────────────┐
│     Mind Spiral Server               │
│     (Akamai VPS / 獨立部署)           │
│                                       │
│  Python + FastAPI + ChromaDB          │
│  LLM: claude_code backend            │
│  Data: /data/{owner_id}/             │
│                                       │
│  Port: 8000（內部）                    │
│  透過 Zeabur Ingress 或 Nginx 對外     │
└────────┬──────────────────────────────┘
         │
    ┌────┴────┬──────────┬──────────┬──────────┐
    │         │          │          │          │
 OpenClaw A  OpenClaw B  LINE Bot   MCP Client  其他 Agent
 (Joey 本人) (團隊用)   (主動觸碰)  (系統整合)   (自動化)
 ① Owner    ③ Viewer   ① Owner    ④ System    ② Agent
```

### 與 OpenClaw 的整合方式

OpenClaw 透過 **Skill** 或 **Tool** 呼叫 Mind Spiral API：

| OpenClaw 端 | Mind Spiral 端 | 說明 |
|---|---|---|
| `SOUL.md` | identity.json (Layer 5) | Joey 的身份核心，同步或手動維護 |
| `AGENTS.md` | frames.jsonl (Layer 4) | 情境框架描述，引導 Agent 行為 |
| Skill: `mind-spiral-query` | `POST /ask` | 查詢或生成內容 |
| Hook: `tool_result_persist` | `POST /demand` | 自動側錄非 Owner 的查詢 |
| Cron job | `GET /demand/stats` | 定期拉取 demand 分析報告 |

### 與既有管線的關係

既有的輸入管線（16_moltbot_joey 的 process_*.py）不受影響：

```
既有管線（不變）：
  錄音 → process_daily.py  → POST /ingest
  貼文 → process_content.py → POST /ingest
  聊天 → process_chat.py   → POST /ingest
  書籍 → process_reading.py → POST /ingest

新增管線：
  OpenClaw 對話（Joey 本人）→ session JSONL → 回饋管線 → POST /ingest
  OpenClaw 對話（其他人）  → 自動側錄 → demand.jsonl（不進 signals）
```

### 開發優先級

| 項目 | 優先級 | 說明 |
|------|--------|------|
| FastAPI 薄包裝（/ask /query /generate） | P0 | 把現有 CLI 包成 HTTP API |
| 認證機制（owner_token / caller_token） | P0 | 區分四種角色 |
| Demand log 側錄 | P1 | 每次非 Owner 查詢自動記錄 |
| Demand × Conviction 落差分析 | P1 | 定期報告 |
| OpenClaw Skill 開發 | P1 | 接上 OpenClaw |
| 代理人確認機制 | P2 | Agent 產出的回寫流程 |
| Owner 對話回寫管線 | P2 | Joey 本人在 OpenClaw 的對話轉 signals |

---

## 技術約束

| 項目 | 決策 |
|------|------|
| 主要語言 | Python |
| 引擎形態 | Python package（可 pip install） |
| LLM | OpenAI-compatible API（Ollama / CF Gateway） |
| 資料格式 | JSONL + JSON，JSON Schema draft-07 驗證 |
| Vector DB | ChromaDB（本地）/ Vectorize（雲端） |
| 訊息出口 | LINE Messaging API |
| 瀏覽器插件 | Chrome Extension Manifest V3 |
| 資料隔離 | 檔案系統目錄（本地）/ owner_id 欄位（雲端） |

---

## 成功指標

| 指標 | 目標 |
|------|------|
| 每日被動信號量 | >20 signals/天/人 |
| 早晨整理回覆率 | >30% |
| Conviction 偵測準確率 | 使用者確認 >80% |
| 數位分身回答認可率 | >80% |
| 使用者每日時間投入 | < 2 分鐘 |
| 螺旋完整度 | >50% 的決策有 outcome 回饋 |
| 冷啟動時間（有歷史資料） | < 1 天出現第一個 conviction |
| 冷啟動時間（純插件） | < 3 週 |
