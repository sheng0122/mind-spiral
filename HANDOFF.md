# Mind Spiral — HANDOFF（2026-02-09）

## 當前狀態

Phase 0 + Phase 1 完成。Phase 2 核心模組（frame_clusterer / identity_scanner / query_engine）已實作，待用 Joey 資料實際跑一次驗證。

## 數據現況（Joey）

| 層 | 數量 | 狀態 |
|----|------|------|
| Layer 1: Signals | 2,737 | ✅ 從 16 新版 signal 格式全量重新匯入 |
| Layer 2: Convictions | 14 | ✅ 全部乾淨，零幻覺 |
| Layer 3: Traces | 221 | ✅ 分組提取 + 去重（94% high confidence） |
| Layer 4: Frames | — | ✅ 程式碼已完成，待首次 `cluster` 執行 |
| Layer 5: Identity | — | ✅ 程式碼已完成，待首次 `scan-identity` 執行 |

Contradictions: 0（min_confidence=7 過濾後無通過）
Pending followups: 0（backfill_cutoff 生效）

### Joey 的思維指紋（從 221 traces）

- **推理風格**：first_principles（70）> analytical（68）> pattern_matching（32）> storytelling（20）
- **觸發場景**：teaching_moment（70）> problem_encountered（62）> decision_required（41）
- **信心程度**：94% high confidence、6% medium

## 已完成的檔案

```
engine/
├── cli.py                    ← CLI（detect/extract/cluster/scan-identity/build-index/query/...）
├── config.py                 ← 設定管理
├── llm.py                    ← LLM 抽象層（local/cloud/claude_code + batch_llm 並行）
├── models.py                 ← 五層 Pydantic models
├── signal_store.py           ← Layer 1 CRUD + ChromaDB
├── conviction_detector.py    ← Layer 2：embedding 聚類 + 共鳴收斂 + 幻覺過濾
├── trace_extractor.py        ← Layer 3：按 (date, context) 分組提取 + 分組級去重
├── frame_clusterer.py        ← Layer 4：按 context 分組 + 統計 + LLM 生成 metadata
├── identity_scanner.py       ← Layer 5：跨 frame 覆蓋率篩選 + LLM 生成 expressions
├── query_engine.py           ← 五層感知 RAG（反射匹配 + ChromaDB 索引 + identity 檢查）
├── decision_tracker.py       ← 決策追蹤 + outcome 螺旋回饋 + 歷史跳過
├── contradiction_alert.py    ← 矛盾偵測 + LLM 信心分數過濾
└── daily_batch.py            ← 每日/每週 orchestrator

docs/architecture.html        ← 架構視覺化（五層 + 控制迴圈 + Phase 路線圖）
migrate_atoms.py              ← 遷移工具（支援新版 signal + 舊版 atom 格式）
config/default.yaml           ← claude_code backend + 防護設定
```

## Phase 2 新增模組說明

### frame_clusterer.py（Layer 4）
- 從 traces 按 `source.context` 分組（如 team_meeting / one_on_one / presentation）
- 每組統計：conviction 激活頻率、推理風格分佈、觸發類型
- 用 LLM 生成 frame 名稱、描述、trigger_patterns、語氣
- 比對既有 frames，避免重複（更新 or 新增）

### identity_scanner.py（Layer 5）
- 載入所有 active frames，統計每個 conviction 的跨 frame 覆蓋率
- 覆蓋率 > 80%（可在 config 調整）的 conviction 升級為 identity core
- 用 LLM 生成每個 identity 在不同 frame 下的表現描述
- 自動設定 non_negotiable（strength >= 0.9）

### query_engine.py（五層感知 RAG）
- **反射匹配**：關鍵字命中 trigger_patterns → 跳過 embedding，< 1ms
- **embedding 匹配**：用 ChromaDB 索引找最相關的 frame
- **trace 檢索**：用 ChromaDB 索引找最相關的推理軌跡（不再逐一算 embedding）
- **identity 檢查**：把 identity core 作為回應生成的護欄
- **build_index()**：一次性預建 trace/frame 的 embedding 索引，查詢時只算一次問題 embedding
- Fallback 設計：索引不存在時用 historical_traces 或最近 traces，不會卡住

## LLM Backend

| Backend | 設定 | 用途 |
|---------|------|------|
| `local` | Ollama localhost:11434 | 本地免費，需啟動 Ollama |
| `cloud` | Cloudflare AI Gateway | 未設定 |
| `claude_code` | Agent SDK + 訂閱認證 | ✅ 目前主力，不需 API key |

## 下一步

### 立即可做
- [ ] 用 Joey 資料跑一次完整流程：`cluster` → `scan-identity` → `build-index` → `query`
- [ ] 驗證 query 回應品質

### Phase 2 剩餘
- [ ] Signal 預過濾（ingest 時 embedding 快篩，增量 conviction 更新）
- [ ] 信念漂移偵測（定期重算 conviction embedding，方向變化 > 閾值 → 警報）
- [ ] 動態 strength 調整（PID 概念，取代固定 ±0.05）

### Phase 3 — 被動擷取（延後）
- [ ] 瀏覽器插件（搜尋/點擊/停留/畫線）
- [ ] 搜尋鏈偵測

### Phase 4 — 多人 + 產品化
- [ ] Onboarding 流程
- [ ] 第二個使用者上線

## 常用指令

```bash
# 完整流程（首次）
mind-spiral cluster --owner joey         # 聚類情境框架（Layer 4）
mind-spiral scan-identity --owner joey   # 掃描身份核心（Layer 5）
mind-spiral build-index --owner joey     # 建立向量索引（加速查詢）
mind-spiral query --owner joey "定價怎麼看？"  # 五層感知查詢

# 日常操作
mind-spiral stats --owner joey
mind-spiral detect --owner joey
mind-spiral extract --owner joey --limit 10
mind-spiral daily --owner joey
mind-spiral weekly --owner joey

# 決策追蹤
mind-spiral followups --owner joey
mind-spiral outcome --owner joey --trace-id xxx --result positive --note "成效不錯"

# 資料匯入
uv run python migrate_atoms.py --atoms /path/to/atoms.jsonl --owner joey
```

## Git log

```
1598fd3 feat: Phase 2 核心完成 — frame_clusterer + identity_scanner + query_engine
3906fa3 docs: 重寫 CLAUDE.md — 定義閉環控制系統架構 + CyberLoop 概念對照 + Phase 路線圖
28b7812 docs: 更新 HANDOFF — P0-P2 全部修復，資料已清理
6c5d468 fix: 修復 P0-P2 已知問題 — 幻覺過濾、歷史跳過、矛盾信心、trace 去重
87da127 docs: 更新 HANDOFF — Phase 1 完成，含數據現況與已知問題
7af9fdf refactor: trace_extractor v2 — 按 (date, context) 分組提取推理軌跡
8b2831b feat: Phase 1 完成 — conviction detection + trace extraction + claude_code backend
ef217e1 feat: Phase 0 完成 — 引擎基礎框架 + atoms 遷移工具
```
