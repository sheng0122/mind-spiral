# Mind Spiral — HANDOFF（2026-02-09）

## 當前狀態

Phase 0 + Phase 1 核心完成，P0-P2 已知問題全部修復。引擎可端到端跑：signal → conviction → trace → contradiction → daily digest。

Joey 的第一次全量跑已完成，資料已清理。

## 數據現況（Joey）

| 層 | 數量 | 狀態 |
|----|------|------|
| Layer 1: Signals | 2,737 | ✅ 從 16_moltbot_joey atoms 遷移完成 |
| Layer 2: Convictions | 46 active | ✅ 已清除 3 筆 LLM 幻覺（原 49） |
| Layer 3: Traces | 392 | ✅ v2 分組模式全量提取完成 |
| Layer 4: Frames | — | 尚未實作 |
| Layer 5: Identity | — | 尚未實作 |

### Joey 的思維指紋（從 392 traces）

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
├── models.py                 ← 五層 Pydantic models（TraceSource 含 context 欄位）
├── signal_store.py           ← Layer 1 CRUD + ChromaDB
├── conviction_detector.py    ← Layer 2：embedding 聚類 + 共鳴收斂 + 幻覺過濾
├── trace_extractor.py        ← Layer 3：按 (date, context) 分組提取 + 分組級去重
├── decision_tracker.py       ← 決策追蹤 + outcome 螺旋回饋 + 歷史跳過
├── contradiction_alert.py    ← 矛盾偵測 + LLM 信心分數過濾
└── daily_batch.py            ← 每日/每週 orchestrator

config/default.yaml           ← 含 claude_code backend + 新增防護設定
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

### P0: LLM 幻覺混入假 conviction ✅
- **問題**：LLM 輸出自我指涉語句（如「我需要先查看這些文件」）被當成 conviction
- **修復**：
  - `conviction_detector.py` prompt 加防護指令 + 無法歸納時回 SKIP
  - 20+ 個中英文 blocklist 後處理過濾（`_is_llm_hallucination()`）
  - 回傳 None 時跳過該 cluster
- **資料清理**：刪除 3 筆幻覺 conviction（49 → 46）

### P1: 304 個待追蹤決策 ✅
- **問題**：歷史 traces 一次灌入，全部沒 outcome 全判 pending
- **修復**：
  - `decision_tracker.py` 新增 `backfill_cutoff_date` 邏輯
  - `default.yaml` 設定 `backfill_cutoff_date: "2026-02-09"`
  - 392 筆歷史 trace 全部早於 cutoff，自動跳過
- **資料**：不需動，code 層面已解決

### P1: 61 個 contradictions 偏高 ✅
- **問題**：LLM 矛盾判定無信心門檻，false positive 多
- **修復**：
  - `contradiction_alert.py` prompt 改為回傳「關係詞 + 信心分數(1-10)」
  - `default.yaml` 新增 `contradiction.min_confidence: 7`，低於 7 分過濾
- **資料**：現有 tensions 欄位為空，下次 daily batch 自動用新邏輯

### P2: trace 去重不精確 ✅
- **問題**：用 `trigger.from_signal`（單一 signal ID）去重，不夠可靠
- **修復**：
  - `models.py` TraceSource 新增 `context` 欄位
  - `trace_extractor.py` 去重改用 `(date, context)` 分組級別
  - 同一個 (date, context) 只會被處理一次
- **資料**：既有 trace 的 `source.context` 為 null（向後相容），下次 extract 生效

## 下一步

### 短期（補完）
- [ ] LLM 雲端模型支援（Cloudflare AI Gateway）
- [ ] 重跑一次 conviction detection 驗證幻覺過濾效果
- [ ] 重跑一次 contradiction scan 驗證信心過濾效果

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
6c5d468 fix: 修復 P0-P2 已知問題 — 幻覺過濾、歷史跳過、矛盾信心、trace 去重
87da127 docs: 更新 HANDOFF — Phase 1 完成，含數據現況與已知問題
7af9fdf refactor: trace_extractor v2 — 按 (date, context) 分組提取推理軌跡
8b2831b feat: Phase 1 完成 — conviction detection + trace extraction + claude_code backend
ef217e1 feat: Phase 0 完成 — 引擎基礎框架 + atoms 遷移工具
```
