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
│   ├── signal_store.py          ← Layer 1 CRUD
│   ├── conviction_detector.py   ← Layer 2 共鳴偵測
│   ├── trace_extractor.py       ← Layer 3 推理軌跡提取
│   ├── frame_clusterer.py       ← Layer 4 情境框架聚類
│   ├── identity_scanner.py      ← Layer 5 身份偵測
│   ├── query_engine.py          ← OpenClaw 查詢（五層感知）
│   ├── daily_digest.py          ← 每日早晨整理生成
│   ├── contradiction_alert.py   ← 矛盾偵測通知
│   ├── decision_tracker.py      ← 決策追蹤佇列
│   └── llm.py                   ← LLM 抽象層
├── browser-ext/                 ← Chrome 擴充套件
│   ├── manifest.json
│   ├── background.js            ← 背景服務（搜尋/點擊/停留追蹤）
│   ├── content.js               ← 內容腳本（畫線偵測）
│   └── popup.html               ← 極簡設定頁面
├── line-bot/                    ← LINE Bot（主動觸碰出口）
│   ├── app.py                   ← FastAPI webhook
│   ├── messages.py              ← 訊息模板（早晨整理/矛盾/追蹤/週報）
│   └── scheduler.py             ← 推送排程
├── config/                      ← 預設設定
│   └── default.yaml             ← 預設引擎參數
└── tests/
```

## Multi-tenant 設計

每個使用者一個 `owner_id`，所有五層資料都帶 `owner_id`。

資料隔離方式：
- **本地模式**：每個使用者一個子目錄 `data/{owner_id}/`
- **雲端模式**：資料庫查詢帶 `owner_id` 過濾

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

# 引擎操作
mind-spiral ingest --owner joey --source transcript.txt --type daily
mind-spiral detect --owner joey          # 執行 conviction detection
mind-spiral cluster --owner joey         # 執行 frame clustering
mind-spiral scan --owner joey            # 執行 identity detection
mind-spiral query --owner joey --caller alice --question "定價怎麼看？"
mind-spiral digest --owner joey          # 生成每日早晨整理
mind-spiral stats --owner joey           # 各層統計

# LINE Bot
cd line-bot
uvicorn app:app --reload

# 瀏覽器插件
cd browser-ext
# 在 Chrome 載入未封裝的擴充功能
```

## 依賴

```
anthropic          # 目前 LLM（之後改 OpenAI-compatible）
pydantic           # 資料模型驗證
chromadb           # 本地向量搜尋
fastapi            # LINE Bot + API
uvicorn            # ASGI server
line-bot-sdk       # LINE Messaging API
pyyaml             # 設定檔
```

環境變數：
- `MIND_SPIRAL_DATA_DIR` — 資料根目錄（預設 `./data`）
- `LLM_BACKEND` — `local` | `cloud`
- `ANTHROPIC_API_KEY` — 目前用
- `LINE_CHANNEL_ACCESS_TOKEN` — LINE Bot
- `LINE_CHANNEL_SECRET` — LINE Bot

## 開發注意事項

- `data/` 在 `.gitignore` 中，使用者資料不進版控
- 所有 LLM 呼叫通過 `engine/llm.py`
- Schema 設計見 `schemas/` 目錄，Pydantic 模型見 `engine/models.py`
- 引擎是純 Python library，不依賴任何 web framework
- LINE Bot 和瀏覽器插件是獨立的介面層，透過引擎 API 操作
