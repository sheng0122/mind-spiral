# Mind Spiral — HANDOFF（2026-02-09）

## 當前狀態

Phase 0-2 完成。五層架構全部有 Joey 實際數據，端到端 pipeline 已驗證。Generation mode 上線，數位分身可產出內容（文章/貼文/腳本/決策）。

## 數據現況（Joey）

| 層 | 數量 | 狀態 |
|----|------|------|
| Layer 1: Signals | 2,737 | ✅ 從 16 新版 signal 格式全量匯入（2,856 atoms → 119 去重） |
| Layer 2: Convictions | 132 | ✅ threshold 0.55，30 core + 48 established + 54 developing |
| Layer 3: Traces | 254 | ✅ 分組提取 + 去重（93% high confidence） |
| Layer 4: Frames | 4 | ✅ 見下方情境框架詳情 |
| Layer 5: Identity | 1 | ✅ 見下方身份核心詳情 |

Contradictions: 11（全為 creative_tension / context_dependent，無真正矛盾）
Pending followups: 0（backfill_cutoff 生效）

### Joey 的思維指紋（從 254 traces）

- **推理風格**：first_principles（77）> analytical（74）> empathy_driven（35）> pattern_matching（32）
- **觸發場景**：teaching_moment（78）> problem_encountered（70）> decision_required（52）
- **信心程度**：93% high confidence、6% medium
- **信念領域**：short_video（21）> content_creation（18）> personal_branding（17）> entrepreneurship（14）

### Layer 4: 思維框架（v2 語義聚類）

v2 改用 trace 語義特徵 embedding 聚類，不再按字面 context 分組。框架代表「怎麼想」而非「在哪裡想」。

| Frame | 名稱 | 推理風格 | Traces | 關聯信念 |
|-------|------|----------|--------|----------|
| 1 | 行動優先實戰框架 | first_principles | 20 | 5 |
| 2 | 系統化管理與第一原則決策 | first_principles | 20 | 7 |
| 3 | 同理傾聽驅動決策 | empathy_driven | 18 | 7 |
| 4 | 反直覺理性投資框架 | analytical | 5 | 7 |

### Layer 5: 身份核心

> **「先用最小成本快速驗證，再根據實際反饋逐步優化，避免一開始追求完美而導致失敗」**

- 覆蓋率：75%（3/4 frames）
- consistency: 0.8
- 跨框架表現：
  - **行動優先實戰**：先推出最簡陋的 MVP 測試市場反應，透過真實用戶反饋決定下一步
  - **系統化管理**：建立最小可行的追蹤系統先跑數據，根據初期結果調整指標與流程
  - **同理傾聽**：先用簡單提問快速確認對方核心需求，依回應動態調整建議
  - **理性投資**：先用小額資金測試投資策略的實際效果，透過市場波動修正心態

## 已完成的檔案

```
engine/
├── cli.py                    ← CLI（ask/query/generate/detect/extract/cluster/scan-identity/build-index/...）
├── config.py                 ← 設定管理
├── llm.py                    ← LLM 抽象層（local/cloud/claude_code + batch_llm 並行）
├── models.py                 ← 五層 Pydantic models
├── signal_store.py           ← Layer 1 CRUD + ChromaDB
├── conviction_detector.py    ← Layer 2：embedding 聚類 + 共鳴收斂 + 幻覺過濾
├── trace_extractor.py        ← Layer 3：按 (date, context) 分組提取 + 分組級去重
├── frame_clusterer.py        ← Layer 4：trace 語義 embedding 聚類（v2）+ LLM 生成 metadata
├── identity_scanner.py       ← Layer 5：跨 frame 覆蓋率篩選 + LLM 生成 expressions
├── query_engine.py           ← 五層感知 RAG + Generation Mode + ask 統一入口
├── decision_tracker.py       ← 決策追蹤 + outcome 螺旋回饋 + 歷史跳過
├── contradiction_alert.py    ← 矛盾偵測 + LLM 信心分數過濾
└── daily_batch.py            ← 每日/每週 orchestrator

docs/architecture.html        ← 架構視覺化（五層 + 控制迴圈 + Phase 路線圖）
migrate_atoms.py              ← 遷移工具（支援新版 signal + 舊版 atom 格式）
config/default.yaml           ← claude_code backend + 防護設定
```

## Phase 2 新增模組說明

### frame_clusterer.py（Layer 4，v2 語義聚類）
- 每個 trace 轉成語義文字（trigger.situation + conclusion + activated convictions + style）
- 用 embedding + AgglomerativeClustering 聚類（threshold 可調，預設 0.55）
- 每個 cluster 統計：conviction 激活頻率、推理風格、觸發類型、出現場景
- 用 LLM 生成 frame 名稱、描述、trigger_patterns、語氣
- 全量覆寫（每次重新聚類），不做增量更新

### identity_scanner.py（Layer 5）
- 載入所有 active frames，統計每個 conviction 的跨 frame 覆蓋率
- 覆蓋率 > 50%（config 可調，原 80% 因 frame 數少調降）的 conviction 升級為 identity core
- 用 LLM 生成每個 identity 在不同 frame 下的表現描述
- 自動設定 non_negotiable（strength >= 0.9）

### query_engine.py（五層感知 RAG + Generation Mode）
- **反射匹配**：關鍵字命中 trigger_patterns → 跳過 embedding，< 1ms
- **embedding 匹配**：用 ChromaDB 索引找最相關的 frame
- **trace 檢索**：用 ChromaDB 索引找最相關的推理軌跡（不再逐一算 embedding）
- **identity 檢查**：把 identity core 作為回應生成的護欄
- **build_index()**：一次性預建 trace/frame 的 embedding 索引，查詢時只算一次問題 embedding
- Fallback 設計：索引不存在時用 historical_traces 或最近 traces，不會卡住

#### Generation Mode（新增）
- **generate()**：用五層思維模型產出完整內容，支援四種 output_type：
  - `article`：800-1500 字完整文章（故事開頭 + 信念論述 + 行動結尾）
  - `post`：200-400 字社群貼文（鉤子 + 短句節奏 + CTA）
  - `script`：200-400 字短影音腳本（Hook + 痛點 + 方法 + CTA，標註秒數）
  - `decision`：300-600 字決策分析（核心考量 + 信念權衡 + 明確建議）
- 與 query 共用五層感知流程，但 generation 用更多 traces（8 vs 5）和更豐富的 prompt
- **ask()**：統一入口，用 `_classify_intent()` 關鍵字自動路由 query 或 generate
  - 「寫一篇」「幫我寫」「撰寫」→ article
  - 「腳本」→ script
  - 「貼文」「發文」→ post
  - 「幫我決定」「該選哪個」→ decision
  - 其餘 → query

#### 測試結果（2026-02-09）
- query 測試：定價/帶團隊/短影音 三題全通過，frame 分流正確
- generate 測試：article（~1200 字）、script（~280 字 x 3 支）品質驗證通過
- ask 自動路由：問句 → query、「幫我寫腳本」→ generate(script) 正確分流

## LLM Backend

| Backend | 設定 | 用途 |
|---------|------|------|
| `local` | Ollama localhost:11434 | 本地免費，需啟動 Ollama |
| `cloud` | Cloudflare AI Gateway | 未設定 |
| `claude_code` | Agent SDK + 訂閱認證 | ✅ 目前主力，不需 API key |

## 下一步

### 立即可做
- [x] 用 Joey 資料跑一次完整流程：`cluster` → `scan-identity`（已完成）
- [x] `build-index` → `query` 驗證五層感知查詢品質（已完成）
- [x] Generation Mode — 數位分身可產出文章/貼文/腳本/決策（已完成）
- [x] `ask` 統一入口 — 自動判斷 query vs generate（已完成）

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

## Git log

```
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
