# Mind Spiral — HANDOFF（2026-02-09）

## 當前狀態

Phase 0 + Phase 1 核心完成，P0-P2 全部修復並驗證。資料已從 16 重新全量匯入 + 重跑全部 pipeline。

## 數據現況（Joey）

| 層 | 數量 | 狀態 |
|----|------|------|
| Layer 1: Signals | 2,737 | ✅ 從 16 新版 signal 格式全量重新匯入 |
| Layer 2: Convictions | 14 | ✅ 全部乾淨，零幻覺 |
| Layer 3: Traces | 221 | ✅ 分組提取 + 去重（94% high confidence） |
| Layer 4: Frames | — | 尚未實作 |
| Layer 5: Identity | — | 尚未實作 |

Contradictions: 0（min_confidence=7 過濾後無通過）
Pending followups: 0（backfill_cutoff 生效）

### Joey 的思維指紋（從 221 traces）

- **推理風格**：first_principles（70）> analytical（68）> pattern_matching（32）> storytelling（20）
- **觸發場景**：teaching_moment（70）> problem_encountered（62）> decision_required（41）
- **信心程度**：94% high confidence、6% medium

## 已完成的檔案

```
engine/
├── cli.py                    ← CLI（detect/extract/followups/outcome/daily/weekly/stats/search）
├── config.py                 ← 設定管理
├── llm.py                    ← LLM 抽象層（local/cloud/claude_code + batch_llm 並行）
├── models.py                 ← 五層 Pydantic models（TraceSource 含 context 欄位）
├── signal_store.py           ← Layer 1 CRUD + ChromaDB
├── conviction_detector.py    ← Layer 2：embedding 聚類 + 共鳴收斂 + 幻覺過濾
├── trace_extractor.py        ← Layer 3：按 (date, context) 分組提取 + 分組級去重
├── decision_tracker.py       ← 決策追蹤 + outcome 螺旋回饋 + 歷史跳過
├── contradiction_alert.py    ← 矛盾偵測 + LLM 信心分數過濾
└── daily_batch.py            ← 每日/每週 orchestrator

migrate_atoms.py              ← 遷移工具（支援新版 signal + 舊版 atom 格式）
config/default.yaml           ← claude_code backend + 防護設定
run_full_extract.py           ← 全量 extract 腳本
run_daily_after_extract.sh    ← extract 完接 daily batch
```

## LLM Backend

三種模式：

| Backend | 設定 | 用途 |
|---------|------|------|
| `local` | Ollama localhost:11434 | 本地免費，需啟動 Ollama |
| `cloud` | Cloudflare AI Gateway | 未設定，待 Task #5 |
| `claude_code` | Agent SDK + 訂閱認證 | ✅ 目前主力，不需 API key |

`batch_llm()` 在 `claude_code` 模式下透過 `asyncio.Semaphore(5)` 並行處理。

## 已修復問題（2026-02-09）

### P0: LLM 幻覺混入假 conviction ✅ 已驗證
- **修復**：prompt 防護 + 20+ blocklist 後處理 + SKIP 機制
- **驗證**：重跑 detect，14 筆全部乾淨零幻覺

### P1: 歷史決策全判 pending ✅ 已驗證
- **修復**：`backfill_cutoff_date: "2026-02-09"`，早於此日期自動跳過
- **驗證**：pending followups = 0

### P1: contradictions false positive ✅ 已驗證
- **修復**：LLM 信心分數 + `min_confidence: 7` 過濾
- **驗證**：從 61 降到 0（全部低於信心門檻）

### P2: trace 去重不精確 ✅ 已驗證
- **修復**：TraceSource 加 context 欄位，用 (date, context) 分組級去重
- **驗證**：重跑 extract 產出 221 traces，無重複

## 資料重建記錄（2026-02-09）

16 那邊更新了 signal 格式（atom → signal），觸發全量重建：

1. 清除 `data/joey/` 全部資料（signals + chroma + convictions + traces + logs）
2. 更新 `migrate_atoms.py` 支援新版 signal 格式（有 signal_id、扁平 content）
3. 重新匯入 2,856 atoms → 2,737 signals（119 重複去重）
4. 重跑 conviction detection → 14 筆
5. 重跑 trace extraction → 221 筆
6. 重跑 contradiction scan → 0 筆

## 下一步

### 短期（補完）
- [ ] LLM 雲端模型支援（Cloudflare AI Gateway）

### Phase 2（PRD 定義）— 被動擷取
- [ ] 瀏覽器插件（搜尋/點擊/停留/畫線）
- [ ] 搜尋鏈偵測
- [ ] process_browsing.py

### Phase 3 — 數位分身
- [ ] frame_clusterer.py（Layer 4：從 traces 聚類情境框架）
- [ ] identity_scanner.py（Layer 5：跨 frame 覆蓋率篩選）
- [ ] query_engine.py（五層感知 RAG）

## 常用指令

```bash
# 設定 backend（目前用 claude_code）
# 在 config/default.yaml 中 engine.llm_backend: claude_code

# 資料匯入
uv run python migrate_atoms.py --atoms /path/to/atoms.jsonl --owner joey

# 日常操作
mind-spiral stats --owner joey
mind-spiral detect --owner joey
mind-spiral extract --owner joey --limit 10
mind-spiral followups --owner joey
mind-spiral outcome --owner joey --trace-id xxx --result positive --note "成效不錯"
mind-spiral daily --owner joey
mind-spiral weekly --owner joey

# 全量跑
uv run python run_full_extract.py
```

## Git log

```
28b7812 docs: 更新 HANDOFF — P0-P2 全部修復，資料已清理
6c5d468 fix: 修復 P0-P2 已知問題 — 幻覺過濾、歷史跳過、矛盾信心、trace 去重
87da127 docs: 更新 HANDOFF — Phase 1 完成，含數據現況與已知問題
7af9fdf refactor: trace_extractor v2 — 按 (date, context) 分組提取推理軌跡
8b2831b feat: Phase 1 完成 — conviction detection + trace extraction + claude_code backend
ef217e1 feat: Phase 0 完成 — 引擎基礎框架 + atoms 遷移工具
```
