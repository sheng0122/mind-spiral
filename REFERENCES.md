# Mind Spiral — 參考專案與研究

## Mind Spiral 的六個關鍵面向 vs 現有專案

| 面向 | 現有專案有沒有 | Mind Spiral 的差異化 |
|------|--------------|---------------------|
| Input-Output Convergence | ❌ 沒有 | 用跨模態交叉比對偵測真實信念 |
| 五層湧現式模型 | 最多三層 | Layer 3（推理軌跡）和 Layer 4（情境激活）是新的 |
| 被動擷取 | ✅ 有成熟方案 | 可站在巨人肩膀上（ActivityWatch、Memex） |
| 主動觸碰產品體驗 | ❌ 技術有，產品沒有 | 矛盾偵測 → LINE 推送 → 三種回應處理的完整閉環 |
| Outcome 螺旋回饋 | ❌ 沒有 | 決策追蹤 → 結果 → 信念強度調整 |
| Context Frame 激活/壓制 | ❌ 沒有 | GraphRAG 社群偵測可借鑑做聚類 |

---

## 優先整合候選（直接可用）

### ActivityWatch — 被動追蹤底層
- **GitHub**: https://github.com/ActivityWatch/activitywatch
- **Stars**: 16,655
- **用途**: 開源自動化時間追蹤，記錄所有電腦活動含瀏覽器。跨平台，隱私優先，資料存本地。
- **整合方式**: 用它當瀏覽器追蹤底層，透過 REST API 查詢資料，上面接 Mind Spiral 的 signal pipeline。不需要自己從零做瀏覽器追蹤。
- **對應面向**: 被動擷取

### Mem0 — 記憶儲存/檢索效能參考
- **GitHub**: https://github.com/mem0ai/mem0
- **Stars**: 46,870
- **用途**: AI 記憶層，自我改進。重複出現的記憶自動增強。CrewAI、Flowise、Langflow 原生整合。
- **可借鑑**: 儲存和檢索的效能設計、記憶增強機制。
- **限制**: 扁平結構（沒有五層分級）、沒有 conviction 強度、沒有 outcome 回饋螺旋。
- **對應面向**: 五層模型的底層儲存參考

### Microsoft GraphRAG — Frame Clustering 演算法
- **GitHub**: https://github.com/microsoft/graphrag
- **Stars**: 30,805
- **用途**: 從文本自動提取知識圖譜，建立社群階層，生成摘要。
- **可借鑑**: 社群偵測（community detection）演算法——哪些 conviction 經常一起出現 = 一個 Context Frame。用在 `frame_clusterer.py`。
- **對應面向**: Context Frame 激活機制

---

## 按面向分類的參考專案

### 面向 1：Input-Output Convergence（信念偵測）

#### CloneMem — 個人認知模型 Benchmark
- **GitHub**: https://github.com/AvatarMemory/CloneMemBench
- **論文**: https://arxiv.org/abs/2601.07023
- **Stars**: 21
- **用途**: 評估 AI 系統從非對話式數位痕跡（日記、社群、email）模擬個人的能力。1,183 個測試問題，涵蓋事實回憶、時間推理、因果鏈、反事實推演。
- **關鍵發現**: 扁平保留原始信號比摘要更好（validity-fidelity trade-off）。摘要會丟失追蹤信念演變所需的細節。
- **對 Mind Spiral 的啟示**: 驗證了保留 Layer 1 完整 signal 的設計。不要過早摘要。

#### pydbm — Dynamic Belief Model
- **GitHub**: https://github.com/Gilles86/pydbm
- **用途**: Dynamic Belief Model (Yu & Cohen, 2008) 的 Python 實作。根據觀察歷史計算信念強度。
- **對 Mind Spiral 的啟示**: conviction score 計算的理論基礎。可參考其數學模型設計 conviction strength 的更新公式。

---

### 面向 2：五層湧現式認知模型

#### memU — 三層記憶框架
- **GitHub**: https://github.com/NevaMind-AI/memU
- **Stars**: 8,400
- **用途**: 24/7 主動式 AI agent 的記憶框架。三層結構：Resources（原始資料）→ Items（提取的事實/偏好）→ Categories（自動組織的主題）。
- **關鍵特性**: 雙模式記憶——reactive（針對性檢索）+ proactive（背景模式偵測、情境預測）。
- **對 Mind Spiral 的啟示**: 三層結構是你五層的子集（Resources = signals, Items = convictions, Categories ≈ frames）。proactive mode 的背景偵測值得深入研究。

#### MemOS — 記憶作業系統
- **GitHub**: https://github.com/MemTensor/MemOS
- **Stars**: 4,987
- **用途**: LLM 的記憶作業系統。儲存完整的工具使用歷史、決策、輸入和結果作為「經驗記憶」。模組化架構（MemCube）。
- **對 Mind Spiral 的啟示**: 「經驗記憶」的概念接近 Reasoning Trace。模組化架構可借鑑來設計五層的模組化。

#### DiffMem — Git-based 記憶版本控制
- **GitHub**: https://github.com/Growth-Kinetics/DiffMem
- **Stars**: 775
- **用途**: 用 Git 追蹤記憶演變。當前知識存在 Markdown，歷史變更透過 Git 追蹤。agent 可以查詢「這個事實什麼時候改變的？」。
- **對 Mind Spiral 的啟示**: conviction 的 evolution_chain 可以用類似機制。把 convictions.jsonl 用 git 追蹤，自動獲得信念變遷歷史。`git diff` = 偵測信念什麼時候改變。

#### Retain — 多平台 AI 對話聚合
- **GitHub**: https://github.com/BayramAnnakov/retain
- **Stars**: 141
- **用途**: 聚合多個 AI 平台（Claude Code、ChatGPT、Cursor）的對話，自動提取偏好和修正模式（如「用 X 代替 Y」）。
- **對 Mind Spiral 的啟示**: 修正模式偵測（「不是 A 是 B」）= 高品質的 conviction 校準信號。類似 Joey 修正分身回答時產生的信號。

---

### 面向 3：零摩擦被動擷取

#### Promnesia — 瀏覽 Context 引擎
- **GitHub**: https://github.com/karlicoss/promnesia
- **Stars**: 1,858
- **用途**: 瀏覽器擴充，顯示你之前在哪裡看過這個頁面（聊天、Twitter、Reddit、本地檔案）。跨來源索引。
- **關鍵特性**: Context attribution——區分「自己搜到的」vs「別人傳的」。
- **對 Mind Spiral 的啟示**: 來源歸因影響 signal 的 direction 和強度。自己搜到的 = input/searched（強信號），別人傳的 = input/received（較弱）。

#### HPI — 統一個人資料 API
- **GitHub**: https://github.com/karlicoss/HPI
- **Stars**: 1,573
- **用途**: Python 介面統一存取所有個人資料來源（瀏覽器歷史、書籤、標註、Reddit、Twitter、聊天記錄、位置歷史）。
- **對 Mind Spiral 的啟示**: `process_*.py` 可以改為 HPI 模組，統一資料存取方式。減少每個來源寫一套 parser 的重複工作。

#### WorldBrain Memex — 瀏覽器全文搜尋 + 標註
- **GitHub**: https://github.com/WorldBrain/Memex
- **Stars**: 4,618
- **用途**: 瀏覽器擴充。全文搜尋瀏覽歷史、在網頁上畫線和加筆記、按標籤和集合組織。
- **關鍵特性**: 畫線 = `input/highlighted` signal。筆記 = 更高品質的 signal。隱私優先。
- **對 Mind Spiral 的啟示**: 不需要自己做畫線功能。Memex 的標註資料可以直接作為高品質 input signal 來源。

#### QS Ledger — 量化自我儀表板
- **GitHub**: https://github.com/markwk/qs_ledger
- **Stars**: 1,050
- **用途**: 聚合 20+ 自我追蹤服務（Strava、Todoist、RescueTime、Fitbit、Instapaper、Goodreads），用 Pandas 視覺化。
- **對 Mind Spiral 的啟示**: 跨域關聯分析的範例。信念週報的視覺化可以參考它的 Jupyter notebook 模板。

---

### 面向 4：主動觸碰 + 矛盾偵測

#### KnowledgeBase Guardian — 矛盾偵測
- **GitHub**: https://github.com/datarootsio/knowledgebase_guardian
- **用途**: 用 LLM 偵測新資訊與既有知識庫的矛盾。最小但可用的實作。
- **對 Mind Spiral 的啟示**: `contradiction_alert.py` 的 prompt 設計可以參考。

#### Empirica — 認知作業系統
- **GitHub**: https://github.com/Nubaeon/empirica
- **用途**: Git-native 認知中間層。引入 epistemic vectors（認知向量），量化 AI agent 的知識狀態變化。CASCADE 工作流。
- **關鍵概念**: 把「不確定性」當成一等公民追蹤，而不是忽略它。
- **對 Mind Spiral 的啟示**: conviction 的 `strength.trend`（strengthening / weakening / fluctuating）可以用類似 epistemic vector 的方式追蹤和視覺化。

---

### 面向 5：Conviction 動態強度 + 螺旋回饋

#### Headkey (CIBFE) — 信念形成引擎
- **GitHub**: https://github.com/savantly-net/headkey-legacy-poc
- **用途**: Cognitive Ingestion & Belief Formation Engine。讓 AI 能選擇性遺忘同時保持信念一致性。
- **對 Mind Spiral 的啟示**: conviction lifecycle（active → weakening → superseded → dormant）的遺忘機制參考。如何在「忘記」的同時保持整體一致性。

#### Decision Record — 結構化決策追蹤
- **GitHub**: https://github.com/joelparkerhenderson/decision-record
- **用途**: 非 AI 專案，但提供結構化決策記錄的模板和方法論。
- **對 Mind Spiral 的啟示**: `decision_tracker.py` 的資料結構和追蹤方式可參考。

---

### 面向 6：Context Frame 激活機制

#### LightRAG — 知識圖譜 + 向量混合檢索
- **GitHub**: https://github.com/HKUDS/LightRAG
- **Stars**: 28,093
- **論文**: EMNLP 2025
- **用途**: 高效能 RAG，結合知識圖譜提取和向量檢索。支援 Qwen 等開源模型。內建 RAGAS 評估。
- **對 Mind Spiral 的啟示**: `query_engine.py` 的混合檢索參考——graph-based 找 frame 結構，vector-based 找細節 signal。可搭配 PageIndex 的推理導航一起使用。

#### TrustGraph — Context Graph 工廠
- **GitHub**: https://github.com/trustgraph-ai/trustgraph
- **Stars**: 1,165
- **用途**: 把碎片資料轉成 AI 優化的知識結構。支援自訂 ontology、本地/雲端雙軌部署。
- **關鍵概念**: 可載入/卸載的 Context Core，類似 Context Frame 的激活/停用。
- **對 Mind Spiral 的啟示**: 雙軌部署架構（Mac Mini + Cloudflare）的參考。Context Core 的模組化設計。

---

## 學術資源

| 資源 | 連結 | 關聯 |
|------|------|------|
| CloneMem 論文 | https://arxiv.org/abs/2601.07023 | 個人認知模型評估方法 |
| Context Graph (CGR³) | https://arxiv.org/abs/2406.11160 | Context Graph 的學術定義和框架 |
| GraphRAG Survey | https://arxiv.org/abs/2501.00309 | 圖增強 RAG 的完整綜述 |
| Multimodal KG Survey | https://github.com/zjukg/KG-MM-Survey | 多模態知識圖譜研究 |
| Awesome AI Memory | https://github.com/IAAR-Shanghai/Awesome-AI-Memory | AI 記憶系統研究彙整 |
| Awesome Personalized RAG | https://github.com/Applied-Machine-Learning-Lab/Awesome-Personalized-RAG-Agent | 個人化 RAG agent 研究彙整 |
| Dynamic Belief Model | Yu & Cohen, 2008（via pydbm） | 信念強度計算的數學基礎 |

---

### 跨面向：查詢引擎架構

#### PageIndex — 無向量、推理式 RAG
- **GitHub**: https://github.com/VectifyAI/PageIndex
- **Stars**: 14,200
- **用途**: 不用向量資料庫和人工切塊，建構階層樹狀索引，讓 LLM 用推理導航文件結構。在 FinanceBench 金融分析 benchmark 達到 98.7% 準確率，大幅超越傳統向量 RAG。
- **核心理念**: **similarity ≠ relevance**——語意相似不等於真正相關。用推理沿著結構導航，比向量相似度匹配更好。
- **對 Mind Spiral 的啟示**: Mind Spiral 的五層架構本身就是一棵語意樹。`query_engine.py` 不該做扁平向量搜尋，而是用 PageIndex 的思路，讓 LLM 推理導航五層結構：Frame Matching（第一層）→ Conviction Activation（第二層）→ Trace Retrieval（第三層）→ Signal 佐證（第四層）。這比「embedding 全部 signal 然後 top-K」更精準，因為相關性來自結構位置，不是語意距離。
- **整合方式**: 借鑑其 agentic tree indexing 的推理導航方法，設計 `query_engine.py` 的五層推理式檢索。

---

## 建議的整合優先級

| 優先級 | 專案 | 整合方式 | 對應 Mind Spiral 元件 |
|--------|------|---------|---------------------|
| P3 | ActivityWatch | 用它當瀏覽器追蹤底層（引擎完成後再做） | `process_browsing.py` |
| P0 | GraphRAG 的社群偵測 | 借鑑演算法做 conviction 聚類 | `frame_clusterer.py` |
| P1 | DiffMem 的 git 追蹤 | convictions.jsonl 用 git 追蹤演變 | conviction evolution_chain |
| P1 | KnowledgeBase Guardian | 參考矛盾偵測 prompt | `contradiction_alert.py` |
| P2 | Memex | 標註資料作為 highlighted signal | `process_browsing.py` |
| P1 | PageIndex | 推理式樹導航取代向量搜尋 | `query_engine.py` |
| P2 | memU | proactive mode 的背景偵測邏輯 | `daily_digest.py` |
| P3 | Mem0 | 大規模記憶儲存/檢索效能 | `signal_store.py` |
| P3 | pydbm | conviction score 更新公式 | `conviction_detector.py` |
