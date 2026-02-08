# Mind Spiral — HANDOFF

## 當前狀態（2026-02-08）

專案剛從 16_moltbot_joey 拆出來。**概念設計完成，程式碼尚未開始。**

Joey 的知識庫（16）已有 2,856 個 atoms，五條輸入管線都能跑。Mind Spiral（18）要做的是把這些 atoms 升級為五層思維模型的引擎，並支援多人使用。

### 已完成

| 項目 | 檔案 | 狀態 |
|------|------|------|
| 五層架構設計 | `MIND_SPIRAL.md` | ✅ |
| Layer 1 Signal schema（含 owner_id） | `schemas/signal.json` | ✅ |
| Layer 2 Conviction schema | `schemas/conviction.json` | ✅ |
| Layer 3 Reasoning Trace schema | `schemas/reasoning_trace.json` | ✅ |
| Layer 4 Context Frame schema | `schemas/context_frame.json` | ✅ |
| Layer 5 Identity Core schema | `schemas/identity_core.json` | ✅ |
| PRD v1（概念完整版） | `PRD.md` | ✅ |
| PRD v2（效能優先版） | `PRD-v2-performance.md` | ✅ |
| 參考專案研究 | `REFERENCES.md` | ✅ |
| 專案結構 + CLAUDE.md | `CLAUDE.md` | ✅ |
| 預設設定 | `config/default.yaml` | ✅ |
| 16 的 CLAUDE.md 更新為 instance 角色 | `16_moltbot_joey/CLAUDE.md` | ✅ |
| shifu 總目錄加入 18 | `shifu/CLAUDE.md` | ✅ |

### 未開始

| 項目 | 優先級 | 說明 |
|------|--------|------|
| engine/ 基本框架 | **Phase 0** | models.py, config.py, llm.py |
| signal_store.py | **Phase 0** | CRUD + embedding 計算 |
| atoms → signals 遷移工具 | **Phase 0** | 2,856 atoms 加 direction + owner_id |
| conviction_detector.py | **Phase 1** | 核心中的核心 |
| contradiction_alert.py | **Phase 1** | 偵測矛盾 → 推 LINE |
| LINE Bot 最小版 | **Phase 1** | 推送 + 收回覆 |
| daily_batch.py（v2 限定） | **Phase 1** | 整合每日運算 |
| trace_extractor.py | **Phase 2** | 從逐字稿提取推理軌跡 |
| daily_digest.py | **Phase 2** | 每日早晨整理 |
| decision_tracker.py | **Phase 2** | 決策追蹤回訪 |
| frame_clusterer.py | **Phase 3** | 情境框架聚類 |
| identity_scanner.py | **Phase 3** | 身份核心偵測 |
| query_engine.py | **Phase 3** | 數位分身回答 |
| 瀏覽器插件 | **Phase 4** | 被動擷取 |

---

## 兩版 PRD 的關係

| | PRD.md（v1） | PRD-v2-performance.md（v2） |
|---|---|---|
| 定位 | 概念完整，準確率優先 | 效能優先，成本最低 |
| Conviction 偵測 | LLM 逐一比對 | embedding 聚類 + 欄位檢查 |
| 每日 LLM calls | 100-500 | 1-9 |
| 查詢延遲 | 5-15 秒（5 次 LLM） | 1-3 秒（1 次 LLM） |
| 月度 tokens | 3M-7.5M | ~900K |
| 預期準確率 | ~90% | ~80%（待驗證） |

**兩版共用同一套 schema。** 差異只在 `conviction_detector.py` 和 `query_engine.py` 的實作方式。可用 feature flag 切換。

**建議**：先實作 v2（快、便宜），用 benchmark 驗證準確率。如果夠好就用 v2；如果某些場景不夠，再針對那些場景用 v1 的 LLM 比對補強。

---

## 下一步：Phase 0 的具體任務

Phase 0 的目標：**讓 2,856 個既有 atoms 變成可被引擎處理的 signals。**

### 任務 0-1：engine/ 基本框架

建立 Python package 結構：

```
engine/
├── __init__.py
├── config.py        ← 讀 config/default.yaml
├── models.py        ← Pydantic models（從 schemas/ 生成）
└── llm.py           ← call_llm() 抽象層
```

### 任務 0-2：signal_store.py

```python
# 核心介面
def ingest(owner_id, signals: list[Signal]) -> None
def query(owner_id, topics=None, date_range=None, direction=None) -> list[Signal]
def compute_embedding(text: str) -> list[float]
def stats(owner_id) -> dict
```

寫入時同時計算 embedding，存入 ChromaDB。

### 任務 0-3：atoms → signals 遷移工具

```python
# migrate_atoms.py
# 讀 16_moltbot_joey/knowledge-base/atoms.jsonl
# 映射規則：
#   atom.type in [idea, belief, decision, framework, quote, open_question]
#     + atom.source.input_modality starts with "spoken" or "written"
#     → direction = "output"
#   atom.authority == "referenced" or "endorsed"
#     → direction = "input"
#   atom.authority == "own_voice"
#     → direction = "output"
#   atom_id → signal_id（格式轉換）
#   加 owner_id = "joey"
```

遷移完成後跑 `stats("joey")` 確認數量和分佈。

### 任務 0-4：驗證

```bash
# 遷移後應該看到
mind-spiral stats --owner joey

Signals: 2,856
  direction:
    input: ~1,200（書籍、referenced atoms）
    output: ~1,656（spoken/written atoms）
  modality distribution: ...
  date range: ...
  topics: ...
```

---

## Phase 1 的前置決策

進入 Phase 1 前需要決定：

### 決策 1：先跑 v1 還是 v2？

**建議 v2 先**。理由：
- 2,856 個 signals 的 embedding 聚類只要幾秒
- 馬上就能看到 conviction 候選
- 如果準確率夠好，省下大量開發和成本
- 如果不夠好，v1 的 LLM 比對可以後加

### 決策 2：Embedding 模型選哪個？

| 模型 | 大小 | 中文品質 | 速度 |
|------|------|---------|------|
| bge-m3 | 2.3GB | 好 | 中 |
| bge-large-zh | 1.3GB | 好 | 快 |
| text-embedding-3-small（OpenAI） | 雲端 | 中 | 快 |

**建議 bge-m3**（本地跑，中文品質最好）。

### 決策 3：聚類 threshold 設多少？

需要實驗。初始建議：
- cosine similarity > 0.80 = 同一個 cluster
- 跑完後人工抽查 20 個 cluster，調整 threshold

---

## 與 16_moltbot_joey 的協作方式

```
16（Joey instance）                    18（Mind Spiral engine）

process_daily.py ─── 輸出 signal ────→ signal_store.ingest("joey", signals)
process_content.py ─ 輸出 signal ────→ signal_store.ingest("joey", signals)
process_chat.py ──── 輸出 signal ────→ signal_store.ingest("joey", signals)
process_reading.py ─ 輸出 signal ────→ signal_store.ingest("joey", signals)

                                       conviction_detector.detect("joey")
                                       daily_batch.run("joey")
                                       query_engine.query("joey", caller, question)
```

16 的 pipeline 需要適配輸出格式（atom → signal），但邏輯不用大改。可以在 16 加一個 `signal_adapter.py` 做格式轉換。

---

## 檔案清單

```
18-mind-spiral/
├── CLAUDE.md                       ← 開發指引
├── README.md                       ← 專案說明
├── HANDOFF.md                      ← 你在這裡
├── PRD.md                          ← v1 概念完整版
├── PRD-v2-performance.md           ← v2 效能優先版
├── MIND_SPIRAL.md                  ← 五層架構設計
├── REFERENCES.md                   ← 參考專案研究
├── .gitignore                      ← 排除 data/
├── config/
│   └── default.yaml                ← 預設引擎參數
├── schemas/
│   ├── signal.json                 ← Layer 1
│   ├── conviction.json             ← Layer 2
│   ├── reasoning_trace.json        ← Layer 3
│   ├── context_frame.json          ← Layer 4
│   └── identity_core.json          ← Layer 5
├── engine/                         ← 待開發
├── browser-ext/                    ← 待開發
├── line-bot/                       ← 待開發
└── tests/                          ← 待開發
```
