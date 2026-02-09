# Mind Spiral — HANDOFF（2026-02-10）

## 當前狀態

Phase 0-2 完成 + 效能大幅優化。五層架構全部有 Joey 實際數據，端到端 pipeline 已驗證。Generation mode 上線，數位分身可產出內容（文章/貼文/腳本/決策）。查詢效能經過三輪優化：向量索引全覆蓋、LLM 分級省成本、batch embedding 加速、資料快取去重複載入。

## 數據現況（Joey）

| 層 | 數量 | 狀態 |
|----|------|------|
| Layer 1: Signals | 2,737 | ✅ 從 16 新版 signal 格式全量匯入（2,856 atoms → 119 去重） |
| Layer 2: Convictions | 369 | ✅ 15 core + 20 established + 269 developing + 65 emerging |
| Layer 3: Traces | 254 | ✅ 分組提取 + 去重（93% high confidence） |
| Layer 4: Frames | 5 | ✅ threshold 0.52，見下方情境框架詳情 |
| Layer 5: Identity | 2 | ✅ fallback top-3 機制，見下方身份核心詳情 |

Contradictions: 11（全為 creative_tension / context_dependent，無真正矛盾）
Pending followups: 0（backfill_cutoff 生效）

### Conviction Strength 新規則（2026-02-09）

解決「他講的內容不代表他真的信」問題：

- **Cross-direction 門檻**：只有 output（創作內容）沒有 input（吸收/私下提到）的 conviction → cap 在 developing（≤0.5）
- **Authority 加權**：first_person ×1.0 > second_person ×0.8 > third_party ×0.6
- **全量重算**：每次 detect 結束時對所有 conviction 重算 strength
- **效果**：core 30→15，純靠短影音撐起的投資 conviction 全部降級

### Joey 的思維指紋（從 254 traces）

- **推理風格**：first_principles（77）> analytical（74）> empathy_driven（35）> pattern_matching（32）
- **觸發場景**：teaching_moment（78）> problem_encountered（70）> decision_required（52）
- **信心程度**：93% high confidence、6% medium
- **信念領域**：short_video（21）> content_creation（18）> personal_branding（17）> entrepreneurship（14）

### Layer 4: 思維框架（v3 調優後）

threshold 0.55→0.52，min_traces 5→3，產出 5 frames（原 4）。

| Frame | 名稱 | 推理風格 | 主要信念 | 語氣 |
|-------|------|----------|----------|------|
| 1 | 行動優先實戰驗證框架 | first_principles | 1 | direct |
| 2 | 價值驅動的務實行動框架 | first_principles | 7 | direct |
| 3 | 系統設計優先思維 | analytical | 6 | authoritative |
| 4 | 長期主義資產增值框架 | analytical | 7 | authoritative |
| 5 | 角色定位與系統優先思維 | first_principles | 4 | authoritative |

### Layer 5: 身份核心（護欄模式）

Identity 角色從「核心主題」降級為「底線護欄」——只在回答明顯矛盾時修正，不主動當主旨發揮。

1. **「向優秀前輩學習勝過盲目創新，培養人才要無保留傳授而非藏私，適度激勵能讓雙方共贏並建立長期能力。」**
   - 覆蓋率：40%（2/5 frames：系統設計優先 + 角色定位系統優先）

2. **「先用最小成本快速驗證，再根據實際反饋逐步優化，避免一開始追求完美而導致失敗」**
   - 覆蓋率：40%（2/5 frames：行動優先實戰 + 長期主義資產增值）

identity_scanner 改為全量重建 + fallback 機制：沒有達到 50% 門檻時，取覆蓋率最高且出現在 2+ frames 的 top-3 conviction。

## 已完成的檔案

```
engine/
├── cli.py                    ← CLI（ask/query/generate/detect/extract/cluster/scan-identity/build-index/...）
├── config.py                 ← 設定管理
├── llm.py                    ← LLM 抽象層（local/cloud/claude_code + batch + tier 分級）
├── models.py                 ← 五層 Pydantic models
├── signal_store.py           ← Layer 1 CRUD + ChromaDB
├── conviction_detector.py    ← Layer 2：embedding 聚類 + 共鳴收斂 + cross-direction + batch embedding
├── trace_extractor.py        ← Layer 3：按 (date, context) 分組提取 + 分組級去重
├── frame_clusterer.py        ← Layer 4：trace 語義 embedding 聚類（v2）+ batch embedding
├── identity_scanner.py       ← Layer 5：跨 frame 覆蓋率篩選 + fallback top-3 + 全量重建
├── query_engine.py           ← 五層感知 RAG + 資料快取 + conviction 向量索引 + signal 回溯 + 時序查詢 + 信心校準
├── decision_tracker.py       ← 決策追蹤 + outcome 螺旋回饋 + 歷史跳過
├── contradiction_alert.py    ← 矛盾偵測 + LLM 信心過濾 + pair cache（跳過已檢查）
└── daily_batch.py            ← 每日/每週 orchestrator + signal cache（共用 store）

config/default.yaml           ← claude_code backend + Haiku/Sonnet 分級 + 防護設定
```

## 效能優化記錄（2026-02-10）

### 第一輪：查詢效能（query_engine.py）

| 改動 | 效果 |
|------|------|
| Conviction 向量索引 | build_index 新增 conviction embedding，查詢用語義搜尋取代 top-strength fallback |
| 資料快取 | 同一 owner 的五層資料只載入一次（`_cache` + `invalidate_cache()`） |
| ChromaDB client 單例化 | 同一 owner 共用一個 PersistentClient |
| 共用 pipeline | `_run_five_layer_pipeline()` 抽出，query/generate 共用，embedding 最多算一次 |

### 第二輪：CloneMemBench 啟發增強

| 改動 | 解決的問題 |
|------|-----------|
| Signal 回溯層 | 從 conviction 的 resonance_evidence 取回原話佐證（ChromaDB get by ID），解決「過度抽象丟失真實性」 |
| 時序感知查詢 | 偵測時序意圖（「變化」「以前」「最近」），取不同時期 traces 讓 LLM 看到變化軌跡 |
| 信心校準 | 證據不足時提示「不確定」而非猜測（distance > 0.8 → low_confidence） |

### 第三輪：全引擎效能 review

| 改動 | 原本 | 修正後 | 影響範圍 |
|------|------|--------|----------|
| LLM 分級（tier） | 全部用 Sonnet | 瑣事用 Haiku，只有最終生成用 Sonnet | 省 ~80% LLM 成本 |
| Embedding batch 化 | conviction 369 次逐一 encode | 1 次 batch encode | detect/contradiction/cluster 加速 5-10x |
| Daily batch signal cache | load_all() 呼叫 2+ 次 | 1 次，傳入共用 store + signal_map | daily batch 整體加速 |
| Contradiction pair cache | 每次重掃全部 1,035 對 | checked_pairs.json 跳過已檢查的 | 大幅減少 LLM 呼叫 |
| 移除 dead code | `_check_decision_followups` 從未被呼叫 | 刪除 | 減少混淆 |

### LLM 三檔制對照表

| 模組 | 任務 | Tier | 模型 |
|------|------|------|------|
| contradiction_alert | 分類兩個 conviction 關係 | light | Haiku |
| frame_clusterer | 生成 frame metadata | light | Haiku |
| identity_scanner | 生成 identity 表述 | light | Haiku |
| daily_batch | digest / weekly report | light | Haiku |
| conviction_detector | 歸納 conviction statement | medium | Sonnet |
| trace_extractor | 提取推理軌跡（batch） | medium | Sonnet |
| **query_engine** | **query / generate 最終生成** | **heavy** | **Opus** |

## Phase 2 新增模組說明

### conviction_detector.py（Cross-direction + Authority 加權 + Batch Embedding）
- **Cross-direction 門檻**：`_has_cross_direction()` 檢查 signals 是否同時有 input 和 output，只有單方向 → cap 在 0.5
- **Authority 加權**：`_compute_authority_weight()` 根據 signal 的 authority 欄位計算乘數
- **全量重算**：detect 結束時從每個 conviction 的 `resonance_evidence` 回溯 signal_ids，重算所有 strength
- **Batch embedding**：既有 conviction 的 embedding 改用 `_get_embedder().encode()` 一次算完
- **可選 store/signal_map**：daily_batch 傳入共用的，避免重複載入

### frame_clusterer.py（Layer 4，v2→v3 調優 + Batch Embedding）
- threshold 0.55→0.52，min_traces 5→3
- trace embedding 改用 batch encode（原本是 list comprehension 逐一算）
- 全量覆寫（每次重新聚類），不做增量更新

### identity_scanner.py（Layer 5，護欄模式）
- 全量重建取代增量更新（跟 frame_clusterer 一致）
- fallback 機制：沒有達到 coverage 門檻時，取 top-3 出現在 2+ frames 的 conviction
- Identity 在 prompt 中的角色降級為底線護欄

### query_engine.py（五層感知 RAG + 效能優化 + CloneMemBench 增強）
- **資料快取**：`_cache` dict + `_get_cached()` + `invalidate_cache()`
- **反射匹配**：關鍵字命中 trigger_patterns → 跳過 embedding，< 1ms
- **embedding 匹配**：用 ChromaDB 索引找最相關的 frame
- **conviction 向量搜尋**：`_find_relevant_convictions()` 用 ChromaDB 索引找跟問題最相關的信念
- **trace 檢索**：用 ChromaDB 索引，時序查詢走 `_find_temporal_traces()`
- **signal 回溯**：`_collect_raw_signals()` 從 conviction 回溯原話佐證
- **信心校準**：`_check_low_confidence()` 檢查匹配品質
- **build_index()**：預建 trace/frame/conviction 三種索引
- **共用 prompt 組裝**：`_build_common_context()` 抽出共用邏輯

#### Generation Mode
- **generate()**：用五層思維模型產出完整內容，支援四種 output_type：
  - `article`：800-1500 字完整文章
  - `post`：200-400 字社群貼文
  - `script`：200-400 字短影音腳本（標註秒數）
  - `decision`：300-600 字決策分析
- 與 query 共用 `_run_five_layer_pipeline()`，但 generation 用更多 traces（8 vs 5）、convictions（7 vs 5）
- **ask()**：統一入口，關鍵字自動路由 query 或 generate

### contradiction_alert.py（Pair Cache）
- `checked_pairs.json` 記錄已 LLM 確認過的 pair
- 下次 scan 只對新 conviction 相關的 pair 呼叫 LLM
- pair key 排序確保 (a,b)/(b,a) 一致性
- batch embedding 取代逐一計算

### daily_batch.py（Signal Cache + Dead Code 清理）
- `run_daily()` 只建一次 `SignalStore` + `load_all()`，傳給 detect/extract 共用
- 移除從未呼叫的 `_check_decision_followups()`

## LLM Backend

| Backend | 設定 | 用途 |
|---------|------|------|
| `local` | Ollama localhost:11434 | 本地免費，需啟動 Ollama |
| `cloud` | Cloudflare AI Gateway | 未設定 |
| `claude_code` | Agent SDK + 訂閱認證 | ✅ 目前主力，三檔制：Opus + Sonnet + Haiku |

## 下一步

### 立即可做
- [x] 重跑 cluster → scan-identity → build-index（套用最新 conviction strength + conviction 索引）
- [x] 測試更新後的 ask/generate 品質（驗證 signal 回溯 + 時序查詢 + 信心校準）

### 已識別的品質問題
- [ ] Frame matching 偏差：問「短影音怎麼做」match 到「指數投資複利思維」frame，conviction 搜尋正確但 frame 誤導 LLM 回應方向
- [ ] Convictions 膨脹：369→587，部分為重複語義，需去重或合併機制

### Phase 2 剩餘
- [x] Generation Mode — 數位分身可產出文章/貼文/腳本/決策
- [x] `ask` 統一入口 — 自動判斷 query vs generate
- [x] Identity 護欄化 — 從綁架輸出改為底線護欄
- [x] Frame 調優 — 4→5 frames，覆蓋更多 traces
- [x] Cross-direction 門檻 — 解決「他講的不代表他信的」
- [x] 查詢效能優化 — 向量索引 + 快取 + batch embedding + LLM 分級
- [x] CloneMemBench 增強 — signal 回溯 + 時序查詢 + 信心校準
- [ ] Signal 預過濾（ingest 時 embedding 快篩，增量 conviction 更新）
- [ ] 信念漂移偵測（定期重算 conviction embedding，方向變化 > 閾值 → 警報）
- [ ] 動態 strength 調整（PID 概念，取代固定 ±0.05）

### 已識別但未修的效能問題
- [ ] frame/identity 全量重建（P3，目前 weekly 頻率可接受，需增量更新邏輯）

### ~~待修：Digest / Weekly Report 邏輯重構~~ ✅ 已完成（2026-02-10）

目前 `daily_batch.py` 的 `_generate_digest()` 和 `run_weekly()` 有以下設計問題：

**問題 1：Digest 只看「今天新增的」，看不到全貌**
- `_generate_digest()` 只拿 `new_convictions` 和 `contradictions`
- contradiction pair cache 生效後，第二天起 contradictions 幾乎永遠是空
- 沒有新 signal 進來 → `new_convictions` 也空 → digest 回傳空字串 → 沒有早晨簡報
- 一個「了解你的朋友」不該因為「今天沒新事」就沉默

**問題 2：Digest 不知道「什麼被強化了」**
- `detect()` 全量重算所有 conviction strength，但只回傳 `new_convictions`
- 既有 conviction 的 strength 變動（變強/變弱）完全沒傳給 digest
- 使用者不知道「今天我的哪些信念變強/變弱了」

**問題 3：Weekly 用日期篩選，但日期欄位不可靠**
- `first_detected >= week_ago` 是字串比較
- 很多 conviction 同一天 batch 建立，「本週新發現」可能一直是 0 或全部

**問題 4：Weekly 沒有 strength 歷史紀錄**
- 註解寫「比對 convictions 的 strength 變化」，但沒有歷史 snapshot
- 只看當前 strength，無法算「這週漲了跌了」
- `strength.trend` 是 detect 時計算的靜態欄位，不是 weekly 自己比對

**問題 5：兩者都沒用到五層架構的深度**
- 只看 conviction 層，不看 trace/frame/identity
- 不知道「今天提取了什麼推理軌跡」「哪個框架最活躍」「身份核心有沒有動搖」

#### 修正方案

**1. Digest 永遠有內容（改 `_generate_digest`）**
- 沒有新事時也回顧：最活躍的信念 top-3、最近的推理模式、下一個待追蹤決策
- 從 `cached["frames"]` 取最活躍框架名稱，讓 digest 有五層深度
- 確保 digest 永遠不回傳空字串

**2. 追蹤 strength 變動（改 `detect` + `_generate_digest`）**
- `detect()` 回傳不只 `new_convictions`，也回傳 `strength_changes: list[dict]`
  - 格式：`{"conviction_id": ..., "statement": ..., "old": 0.6, "new": 0.72, "delta": +0.12}`
- detect 前先快照既有 strength，detect 後比對差異，只回傳 |delta| > 0.05 的
- `_generate_digest` 新增【信念強化/減弱】區塊

**3. Strength 歷史快照（新增 `strength_snapshots.jsonl`）**
- 每次 `detect()` 完成後，存一行：`{"date": "2026-02-10", "strengths": {"conv_id": score, ...}}`
- `run_weekly()` 讀取本週和上週的 snapshot，計算每個 conviction 的 delta
- 取代目前不可靠的 `first_detected` 日期篩選

**4. Weekly 加入五層摘要**
- 本週新 traces 數量 + 推理風格分佈
- 最活躍的 frame（被匹配最多次的）
- identity 覆蓋率變化（如果有重跑 scan-identity）

#### 涉及檔案
- `engine/daily_batch.py` — 主要改動
- `engine/conviction_detector.py` — detect 回傳 strength_changes
- `data/{owner}/strength_snapshots.jsonl` — 新檔案

### Phase 2.5 — 外部整合層（API Server + Demand Signal）
- [ ] FastAPI 薄包裝（把現有 CLI 的 ask/query/generate 包成 HTTP API）
- [ ] 認證機制（四種角色：Owner / Agent / Viewer / System）
- [ ] Demand log 側錄（非 Owner 查詢自動記錄）
- [ ] Demand × Conviction 落差分析（外界認知 vs 自我認知）
- [ ] OpenClaw Skill（接上 OpenClaw 的 query/generate）
- [ ] 代理人確認機制（AI 代替說的話，確認後才寫入）
- [ ] Owner 對話回寫管線（Joey 在 OpenClaw 的對話 → signals）
- 詳見 PRD.md「外部整合層」章節

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
mind-spiral build-index --owner joey     # 建立向量索引（trace/frame/conviction）
mind-spiral ask --owner joey "定價怎麼看？"        # 統一入口（自動判斷 query）
mind-spiral ask --owner joey "幫我寫一篇短影音腳本"  # 統一入口（自動判斷 generate）
mind-spiral query --owner joey "定價怎麼看？"        # 直接 query
mind-spiral generate --owner joey --type script "短影音腳本主題"  # 直接 generate

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

## 本次修改紀錄（2026-02-10）

### Digest / Weekly Report 重構
- `conviction_detector.py`：`detect()` 回傳 `(new_convictions, strength_changes)` + 每次存 strength snapshot
- `daily_batch.py`：digest 永遠有內容（fallback 回顧 top-3 信念 + 框架）、新增【信念強化/減弱】區塊、五層深度
- `daily_batch.py`：weekly 改用 `strength_snapshots.jsonl` 計算真實 delta，新增推理風格分佈 + 框架資訊
- `query_engine.py`：修 bug `c.domain` → `c.domains`
- `cli.py`：detect 命令顯示 strength 變動
- `run_full_extract.py`：適配新 detect 回傳格式
- `CLAUDE.md`：`pip install -e .` → `uv sync`

### 效能優化（第四輪）
- `conviction_detector.py`：新 conviction 生成改 `batch_llm` 並行、跳過已覆蓋 clusters、比對門檻 0.85→0.80、向量化 similarity
- `contradiction_alert.py`：循序 LLM 改 `batch_llm` 並行、每次最多 50 pairs
- `query_engine.py`：query/generate 最終生成從 Opus 降為 Sonnet（五層 context 已精準，不需 Opus 推理）
- daily 從**跑不完** → **1 分鐘**，ask 從 ~40s → ~23s

### 新檔案
- `data/{owner}/strength_snapshots.jsonl` — 每次 detect 後自動產生

## Git log

```
fbf31ff docs: 更新 HANDOFF — 效能優化三輪記錄 + LLM 分級對照表 + P2 修正清單
95cad4d perf: daily batch signal cache + contradiction pair cache + 移除 dead code
a5a4a24 perf: 查詢效能大幅優化 + LLM 分級省成本 + CloneMemBench 啟發增強
cd68c4c docs: 新增外部整合層設計 — Mind Spiral 作為獨立 API Server
950f88f docs: 更新 HANDOFF — cross-direction 門檻 + identity 護欄 + frame v3
e5d2dde feat: conviction strength 加入 cross-direction 門檻 + authority 加權
62bb366 fix: identity 從綁架輸出改為底線護欄 + frame 聚類調優
0b2abc9 docs: 更新 CLAUDE.md — 加入 ask/generate 指令說明
2e43197 docs: 更新 HANDOFF — generation mode + ask 統一入口
5f54763 feat: generation mode + ask 統一入口 — 數位分身可產出內容和做決策
056828d docs: 更新 HANDOFF — frame_clusterer v2 語義聚類 + 五層完整數據
7abd6ee refactor: frame_clusterer v2 — 語義聚類取代字面 context 分組
a1f9f20 feat: Layer 4/5 首次執行 — 4 frames + 1 identity core
668622d tune: similarity_threshold 0.75→0.55，conviction 14→132 筆
014360d perf: query_engine 改用 ChromaDB 索引加速 + 更新全部文件
4cfb62c refactor: 更新遷移工具支援新版 signal 格式 + 全量重建資料
1598fd3 feat: Phase 2 核心完成 — frame_clusterer + identity_scanner + query_engine
6c5d468 fix: 修復 P0-P2 已知問題 — 幻覺過濾、歷史跳過、矛盾信心、trace 去重
8b2831b feat: Phase 1 完成 — conviction detection + trace extraction + claude_code backend
ef217e1 feat: Phase 0 完成 — 引擎基礎框架 + atoms 遷移工具
```
