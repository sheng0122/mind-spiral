---
project: mind-spiral
status: doing
owner: Leo
context: shifu-context/projects/mind-spiral.md
---

# Mind Spiral — 人類思維模型引擎

## 專案目標

被動觀察一個人的日常行為，自動建構五層思維模型（Signal → Conviction → Reasoning Trace → Context Frame → Identity Core），讓 AI 數位分身能用這個人的方式思考、推理、回應。

**這是引擎專案，不是某個人的資料庫。** 每個使用者（如 Joey、Alice）是一個 instance，資料獨立，引擎共用。

## 系統本質：閉環控制系統

Mind Spiral 不只是「被動觀察」——它是一個**閉環控制系統**，有明確的目標和航向：

### 三個控制迴圈

```
迴圈 1：螺旋回饋（conviction calibration）
  決策 → 追蹤 → outcome 回來 → conviction strength 調整
  目標：讓 conviction 的 strength 越來越準確反映現實

迴圈 2：一致性維護（contradiction detection）
  新 conviction 出現 → 比對既有 convictions → 偵測矛盾/演化
  目標：維護認知模型的內部一致性

迴圈 3：查詢導航（query engine）
  問題進來 → frame matching → conviction activation → 推理 → 回應
  目標：在五層資料中找到正確的信念+推理組合，生成「像這個人」的回答
```

### 參考架構：CyberLoop (AICL)

[CyberLoop](https://github.com/roackb2/cyberloop) 是一個 AI Agent 控制框架，用控制理論（PID 控制器 + 卡爾曼濾波器）讓 Agent 在向量空間中導航時不偏航。其核心概念可直接應用於 Mind Spiral 的三個場景：

| CyberLoop 概念 | Mind Spiral 應用場景 | Phase |
|---|---|---|
| **航向保持**（角偏差偵測） | Query Engine 在五層資料導航時，防止回答偏離 identity | Phase 3 |
| **PID 修正力**（比例/積分/微分） | 螺旋回饋中 conviction strength 的調整力道應動態計算，而非固定 ±0.05 | Phase 3 |
| **反射系統**（Line-of-Sight） | Frame matching 時，關鍵字直接命中 trigger_patterns → 跳過 LLM 推理 | Phase 3 |
| **雙速架構**（便宜內迴圈 + 貴外迴圈） | Signal 預過濾用 embedding 數學，深度分析才呼叫 LLM | Phase 2 |
| **漂移偵測**（向量方向變化） | 追蹤 conviction embedding 隨時間的方向變化，偵測信念漂移 | Phase 2 |
| **守衛系統**（防重複繞圈） | 偵測 reasoning trace 的重複 pattern，識別思維慣性 vs 舒適圈 | Phase 3 |

## 與 16_moltbot_joey 的關係

```
18-mind-spiral/     引擎 + 插件 + LINE Bot（共用）
16_moltbot_joey/    Joey 的資料 + 輸入管線（instance）
```

Joey 是 Mind Spiral 的第一個使用者。16 的 `process_*.py` 負責把 Joey 的原始素材轉成 signal 格式，餵進 18 的引擎。

## 目錄結構

```
18-mind-spiral/
├── CLAUDE.md                    ← 你在這裡
├── README.md                    ← 專案說明
├── PRD.md                       ← 產品需求文件
├── MIND_SPIRAL.md               ← 五層架構設計文件
├── HANDOFF.md                   ← 交接文件（含數據現況）
├── schemas/                     ← 五層 JSON Schema（multi-tenant）
│   ├── signal.json              ← Layer 1: 信號
│   ├── conviction.json          ← Layer 2: 信念
│   ├── reasoning_trace.json     ← Layer 3: 推理軌跡
│   ├── context_frame.json       ← Layer 4: 情境框架
│   └── identity_core.json       ← Layer 5: 身份核心
├── engine/                      ← 核心運算邏輯
│   ├── __init__.py
│   ├── config.py                ← 設定管理（LLM、儲存路徑）
│   ├── models.py                ← 資料模型（Pydantic）
│   ├── llm.py                   ← LLM 抽象層（local/cloud/claude_code + batch）
│   ├── cli.py                   ← CLI 入口
│   ├── signal_store.py          ← Layer 1 CRUD + ChromaDB
│   ├── conviction_detector.py   ← Layer 2 共鳴偵測 + 幻覺過濾
│   ├── trace_extractor.py       ← Layer 3 推理軌跡提取（v2 分組模式）
│   ├── contradiction_alert.py   ← 矛盾偵測 + LLM 信心過濾
│   ├── decision_tracker.py      ← 決策追蹤 + outcome 螺旋回饋
│   ├── daily_batch.py           ← 每日/每週 orchestrator
│   ├── frame_clusterer.py       ← Layer 4 情境框架聚類
│   ├── identity_scanner.py      ← Layer 5 身份核心掃描
│   └── query_engine.py          ← 五層感知 RAG（反射匹配 + embedding）
├── browser-ext/                 ← Chrome 擴充套件（Phase 2）
├── line-bot/                    ← LINE Bot（主動觸碰出口）
├── config/
│   └── default.yaml             ← 預設引擎參數
└── tests/
```

## 開發路線圖

### Phase 0 — 基礎建設 ✅

五層 schema、Pydantic models、config、LLM 抽象層、signal_store CRUD、Joey atoms 遷移。

### Phase 1 — 核心螺旋 ✅

conviction detection（embedding 聚類 + 五種共鳴 + 幻覺過濾）、trace extraction（v2 分組模式）、decision tracker（outcome 螺旋回饋）、contradiction alert（cosine + LLM 信心過濾）、daily batch orchestrator。

**Joey 數據現況**：2,737 signals → 46 convictions → 392 traces

### Phase 2 — 上層模型 + 數位分身 ← 進行中

瀏覽器插件延後，優先用既有資料建構上層模型。

| 項目 | 說明 | 狀態 |
|------|------|---|
| frame_clusterer.py | 從 traces 聚類情境框架（Layer 4） | ✅ |
| identity_scanner.py | 跨 frame 覆蓋率篩選（Layer 5） | ✅ |
| query_engine.py | 五層感知 RAG + 反射匹配 + ChromaDB 索引加速 | ✅ |
| Signal 預過濾 | ingest 時用 embedding 快篩，增量 conviction 更新 | 待做 |
| 信念漂移偵測 | 定期重算 conviction embedding，方向變化 > 閾值 → 警報 | 待做 |
| 動態 strength 調整 | outcome 回饋時根據累積趨勢動態計算，取代固定 ±0.05（PID） | 待做 |

### Phase 3 — 被動擷取（延後）

| 項目 | 說明 |
|------|------|
| 瀏覽器插件（搜尋/點擊/停留/畫線） | 最強的 input signal 來源 |
| 搜尋鏈偵測 | 連續搜尋 = 探索路徑 = reasoning trace 原始素材 |

### Phase 4 — 多人 + 產品化

Onboarding 流程、第二個使用者上線、信念演變視覺化、Web dashboard。

## Multi-tenant 設計

每個使用者一個 `owner_id`，所有五層資料都帶 `owner_id`。

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

## 指令

```bash
# 安裝
cd 18-mind-spiral
pip install -e .

# 日常操作
mind-spiral stats --owner joey
mind-spiral detect --owner joey          # conviction detection
mind-spiral extract --owner joey --limit 10  # trace extraction
mind-spiral followups --owner joey       # 待追蹤決策
mind-spiral outcome --owner joey --trace-id xxx --result positive --note "成效不錯"
mind-spiral daily --owner joey           # 每日整理
mind-spiral weekly --owner joey          # 每週報告
mind-spiral cluster --owner joey         # 聚類情境框架（Layer 4）
mind-spiral scan-identity --owner joey   # 掃描身份核心（Layer 5）
mind-spiral build-index --owner joey     # 建立向量索引（加速查詢，一次性）
mind-spiral query --owner joey "定價怎麼看？"  # 五層感知查詢
mind-spiral query --owner joey --caller alice "定價怎麼看？"  # 帶提問者身份

# 全量跑
uv run python run_full_extract.py

# LINE Bot
cd line-bot && uvicorn app:app --reload

# 瀏覽器插件：在 Chrome 載入 browser-ext/ 未封裝的擴充功能
```

## LLM Backend

| Backend | 設定 | 用途 |
|---------|------|------|
| `local` | Ollama localhost:11434 | 本地免費，需啟動 Ollama |
| `cloud` | Cloudflare AI Gateway | 未設定 |
| `claude_code` | Agent SDK + 訂閱認證 | **目前主力**，不需 API key |

`batch_llm()` 在 `claude_code` 模式下透過 `asyncio.Semaphore(5)` 並行處理。

## 環境變數

- `MIND_SPIRAL_DATA_DIR` — 資料根目錄（預設 `./data`）
- `LLM_BACKEND` — `local` | `cloud`
- `ANTHROPIC_API_KEY` — cloud 模式用
- `LINE_CHANNEL_ACCESS_TOKEN` — LINE Bot
- `LINE_CHANNEL_SECRET` — LINE Bot

## 開發注意事項

- `data/` 在 `.gitignore` 中，使用者資料不進版控
- 所有 LLM 呼叫通過 `engine/llm.py`
- Schema 設計見 `schemas/` 目錄，Pydantic 模型見 `engine/models.py`
- 引擎是純 Python library，不依賴任何 web framework
- LINE Bot 和瀏覽器插件是獨立的介面層，透過引擎 API 操作
- Phase 3 實作 query_engine 時，需引入向量空間導航控制（參考 CyberLoop AICL 架構）
