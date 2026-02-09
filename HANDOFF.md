# Mind Spiral — HANDOFF（2026-02-09）

## 當前狀態

Phase 0-2 完成。五層架構全部有 Joey 實際數據，端到端 pipeline 已驗證。Generation mode 上線，數位分身可產出內容（文章/貼文/腳本/決策）。Conviction strength 已加入 cross-direction 門檻和 authority 加權，解決「他講的內容不代表他真的信」問題。

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
├── llm.py                    ← LLM 抽象層（local/cloud/claude_code + batch_llm 並行）
├── models.py                 ← 五層 Pydantic models
├── signal_store.py           ← Layer 1 CRUD + ChromaDB
├── conviction_detector.py    ← Layer 2：embedding 聚類 + 共鳴收斂 + cross-direction 門檻 + authority 加權
├── trace_extractor.py        ← Layer 3：按 (date, context) 分組提取 + 分組級去重
├── frame_clusterer.py        ← Layer 4：trace 語義 embedding 聚類（v2）+ LLM 生成 metadata
├── identity_scanner.py       ← Layer 5：跨 frame 覆蓋率篩選 + fallback top-3 + 全量重建
├── query_engine.py           ← 五層感知 RAG + Generation Mode + ask 統一入口
├── decision_tracker.py       ← 決策追蹤 + outcome 螺旋回饋 + 歷史跳過
├── contradiction_alert.py    ← 矛盾偵測 + LLM 信心分數過濾
└── daily_batch.py            ← 每日/每週 orchestrator

docs/architecture.html        ← 架構視覺化（五層 + 控制迴圈 + Phase 路線圖）
migrate_atoms.py              ← 遷移工具（支援新版 signal + 舊版 atom 格式）
config/default.yaml           ← claude_code backend + 防護設定
```

## Phase 2 新增模組說明

### conviction_detector.py（Cross-direction + Authority 加權）
- **Cross-direction 門檻**：`_has_cross_direction()` 檢查 signals 是否同時有 input 和 output，只有單方向 → cap 在 0.5
- **Authority 加權**：`_compute_authority_weight()` 根據 signal 的 authority 欄位計算乘數
- **全量重算**：detect 結束時從每個 conviction 的 `resonance_evidence` 回溯 signal_ids，重算所有 strength
- 背景：Joey 拍了投資理財短影音（output），但私下從沒聊過投資（沒有 input），系統誤判為核心信念

### frame_clusterer.py（Layer 4，v2→v3 調優）
- threshold 0.55→0.52，min_traces 5→3
- 產出 5 frames（原 4），覆蓋更多 traces
- 全量覆寫（每次重新聚類），不做增量更新

### identity_scanner.py（Layer 5，護欄模式）
- 全量重建取代增量更新（跟 frame_clusterer 一致）
- fallback 機制：沒有達到 coverage 門檻時，取 top-3 出現在 2+ frames 的 conviction
- Identity 在 prompt 中的角色降級為底線護欄

### query_engine.py（五層感知 RAG + Generation Mode）
- **反射匹配**：關鍵字命中 trigger_patterns → 跳過 embedding，< 1ms
- **embedding 匹配**：用 ChromaDB 索引找最相關的 frame
- **trace 檢索**：用 ChromaDB 索引找最相關的推理軌跡
- **identity 檢查**：底線護欄，只在矛盾時修正，不主動引導內容方向
- **build_index()**：一次性預建 trace/frame 的 embedding 索引

#### Generation Mode
- **generate()**：用五層思維模型產出完整內容，支援四種 output_type：
  - `article`：800-1500 字完整文章
  - `post`：200-400 字社群貼文
  - `script`：200-400 字短影音腳本（標註秒數）
  - `decision`：300-600 字決策分析
- 與 query 共用五層感知流程，但 generation 用更多 traces（8 vs 5）
- **ask()**：統一入口，關鍵字自動路由 query 或 generate

#### 測試結果（2026-02-09）
- query：不同問題走不同框架（帶團隊→系統設計、投資→長期主義、創作→行動優先），不再全部收束到同一結論
- generate：article/script/decision 品質驗證通過
- ask 自動路由：問句→query、「幫我寫腳本」→generate(script) 正確分流
- cross-direction 效果：純短影音投資 conviction 從 core 降到 developing/emerging

## LLM Backend

| Backend | 設定 | 用途 |
|---------|------|------|
| `local` | Ollama localhost:11434 | 本地免費，需啟動 Ollama |
| `cloud` | Cloudflare AI Gateway | 未設定 |
| `claude_code` | Agent SDK + 訂閱認證 | ✅ 目前主力，不需 API key |

## 下一步

### 立即可做
- [ ] 重跑 cluster → scan-identity → build-index（套用最新 conviction strength）
- [ ] 測試更新後的 ask/generate 品質

### Phase 2 剩餘
- [x] Generation Mode — 數位分身可產出文章/貼文/腳本/決策
- [x] `ask` 統一入口 — 自動判斷 query vs generate
- [x] Identity 護欄化 — 從綁架輸出改為底線護欄
- [x] Frame 調優 — 4→5 frames，覆蓋更多 traces
- [x] Cross-direction 門檻 — 解決「他講的不代表他信的」
- [ ] Signal 預過濾（ingest 時 embedding 快篩，增量 conviction 更新）
- [ ] 信念漂移偵測（定期重算 conviction embedding，方向變化 > 閾值 → 警報）
- [ ] 動態 strength 調整（PID 概念，取代固定 ±0.05）

### Phase 2.5 — 外部整合層（API Server + Demand Signal）⭐ 新增
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
