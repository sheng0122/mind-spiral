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
