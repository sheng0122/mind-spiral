# Mind Spiral — HANDOFF（2026-02-09）

## 當前狀態

Phase 0 + Phase 1 核心完成。引擎可端到端跑：signal → conviction → trace → contradiction → daily digest。

Joey 的第一次全量跑已完成，結果可用。

## 數據現況（Joey）

| 層 | 數量 | 狀態 |
|----|------|------|
| Layer 1: Signals | 2,737 | ✅ 從 16_moltbot_joey atoms 遷移完成 |
| Layer 2: Convictions | 49 active | ✅ embedding 聚類 + 共鳴收斂 + LLM |
| Layer 3: Traces | 184 | ✅ v2 分組模式全量提取完成 |
| Layer 4: Frames | — | 尚未實作 |
| Layer 5: Identity | — | 尚未實作 |

Daily batch 首次結果：7 new convictions、208 new traces、61 contradictions、304 followups。

### Joey 的思維指紋（從 184 traces）

- **推理風格**：first_principles（70）> analytical（39）> storytelling（23）
- **觸發場景**：teaching_moment 佔 67%（106/158）
- **常用步驟**：apply_framework（114）> synthesize（87）> reframe（85）
- **信心程度**：97% high confidence

## 已完成的檔案

```
engine/
├── cli.py                    ← CLI（detect/extract/followups/outcome/daily/weekly/stats/search）
├── config.py                 ← 設定管理
├── llm.py                    ← LLM 抽象層（local/cloud/claude_code + batch_llm 並行）
├── models.py                 ← 五層 Pydantic models
├── signal_store.py           ← Layer 1 CRUD + ChromaDB
├── conviction_detector.py    ← Layer 2：embedding 聚類 + 五種共鳴收斂
├── trace_extractor.py        ← Layer 3：按 (date, context) 分組提取（v2）
├── decision_tracker.py       ← 決策追蹤 + outcome 螺旋回饋
├── contradiction_alert.py    ← 矛盾偵測
└── daily_batch.py            ← 每日/每週 orchestrator

config/default.yaml           ← 含 claude_code backend 設定
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

## 已知問題

### P0: LLM 幻覺混入假 conviction
- 「我需要先查看這些文件的內容才能總結核心信念」— LLM 自我描述，不是 Joey 的信念
- **解法**：prompt 加防護 + 後處理過濾 LLM 自指詞

### P1: 304 個待追蹤決策
- 歷史 traces 一次灌入，全部沒 outcome 所以全判 pending
- **解法**：`decision_tracker` 加 `backfill_skip`，首次跑跳過歷史

### P1: 61 個 contradictions 偏高
- 可能有 false positive
- **解法**：調高 similarity threshold 或加 LLM confidence 過濾

### P2: trace v2 去重邏輯
- 用 `trigger.from_signal`（組內第一個 signal）去重，不夠精確
- 實際影響不大

## 下一步

### 短期（修復 + 補完）
- [ ] 修復 P0：LLM 幻覺 conviction 過濾
- [ ] 修復 P1：decision_tracker 歷史跳過
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
# 設定 backend
# 在 config/default.yaml 中 engine.llm_backend: claude_code

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
7af9fdf refactor: trace_extractor v2 — 按 (date, context) 分組提取推理軌跡
8b2831b feat: Phase 1 完成 — conviction detection + trace extraction + claude_code backend
ef217e1 feat: Phase 0 完成 — 引擎基礎框架 + atoms 遷移工具
```
