# Mind Spiral — 人類思維模型架構

## 設計哲學

這不是知識庫，是**思維模擬器**。

傳統做法（Knowledge Graph、Context Graph、RAG）都是由外而內：先定義結構，再把資料塞進去。Mind Spiral 是由內而外：先有信號，結構從交叉比對中**湧現**。

核心假設：**一個人真正相信什麼，不看他宣稱什麼，看他輸入和輸出的交叉收斂。**

- 讀過，也說過 → 內化了
- 讀過，沒說過 → 沒留下
- 沒刻意讀過，但反覆說 → 更深層的東西

## Multi-tenant 設計

Mind Spiral 是引擎，每個使用者是一個 instance。

```
data/
├── joey/          ← Joey 的思維模型
│   ├── signals.jsonl
│   ├── convictions.jsonl
│   ├── traces.jsonl
│   ├── frames.jsonl
│   └── identity.json
├── alice/         ← Alice 的思維模型
│   └── ...
```

所有五層資料都帶 `owner_id`。引擎 API 的每個操作都需要指定 `owner_id`。

## 五層架構

```
╔══════════════════════════════════════════════════╗
║  Layer 5: Identity Core（身份核心）5-15 條       ║
║  定義「我是誰」的不可動搖信念                      ║
║  ← 從 L4 的跨 frame 普遍性中湧現                  ║
╠══════════════════════════════════════════════════╣
║  Layer 4: Context Frames（情境框架）              ║
║  不同場景下，哪些信念被激活、怎麼組合               ║
║  ← 從 L3 的 trace 聚類中湧現                      ║
╠══════════════════════════════════════════════════╣
║  Layer 3: Reasoning Traces（推理軌跡）            ║
║  情境 → 信念激活 → 推理步驟 → 結論 → 回饋         ║
║  ← 從 L1 的論述/決策段落中提取                     ║
╠══════════════════════════════════════════════════╣
║  Layer 2: Convictions（信念層）                   ║
║  被反覆強化的觀點，有強度，會演化                   ║
║  ← 從 L1 的跨模態交叉比對中湧現                    ║
╠══════════════════════════════════════════════════╣
║  Layer 1: Signals（信號層）                       ║
║  所有接觸過的東西，標記 input/output               ║
║  ← 直接從原始素材提取                              ║
╚══════════════════════════════════════════════════╝
```

### 層間關係

- **L1 → L2**：信號的交叉比對產生信念（偵測收斂）
- **L1 → L3**：信號中的論述段落產生推理軌跡（提取推理）
- **L2 ↔ L3**：信念被推理軌跡引用；推理結果回饋信念強度（螺旋）
- **L3 → L4**：相似的推理軌跡聚類成情境框架（模式辨識）
- **L4 → L5**：跨所有 frame 都出現的信念升級為身份核心（普遍性篩選）
- **L5 → L4 → L3**：反向影響——identity 約束 frame 的信念組合，frame 約束推理路徑

## 各層詳細說明

### Layer 1: Signal（信號）

**Schema**: `schemas/signal.json`
**儲存**: `data/{owner_id}/signals.jsonl`

| direction | modality | 含義 |
|-----------|----------|------|
| input | searched | 主動搜尋——最強的興趣信號 |
| input | selected | 搜尋後點擊——判斷偏好 |
| input | highlighted | 讀到並畫線——引起注意 |
| input | consumed | 讀過但沒標記——純接觸 |
| input | received | 別人告訴你的 |
| output | spoken_spontaneous | 即興說出——最真實的信號 |
| output | spoken_scripted | 有準備地說——確信到願意公開 |
| output | spoken_interview | 訪談中的回應 |
| output | written_casual | 隨手寫——自然反應 |
| output | written_deliberate | 刻意寫——經過思考的表達 |
| output | written_structured | 高度結構化——課程/簡報 |
| output | decided | 做了一個決定——行動層面 |
| output | acted | 實際執行——最強的 output 信號 |

### Layer 2: Conviction（信念）

**Schema**: `schemas/conviction.json`
**儲存**: `data/{owner_id}/convictions.jsonl`

五種共鳴偵測：

| 共鳴類型 | 偵測方式 | 強化權重 |
|----------|----------|----------|
| **Input-Output Convergence** | 讀到 X，後來說了 X' | ★★★★★ |
| **Action Alignment** | 說了 X，然後真的做了 | ★★★★★ |
| **Temporal Persistence** | 一月說 X，三月又說 X | ★★★★ |
| **Cross-Context Consistency** | 對客戶說、對團隊也說 | ★★★★ |
| **Spontaneous Emergence** | 沒人問，主動提起 | ★★★ |

強度等級：

| level | score | 含義 |
|-------|-------|------|
| emerging | 0-0.3 | 剛出現幾次，可能只是試探 |
| developing | 0.3-0.6 | 多次出現但尚未穩定 |
| established | 0.6-0.85 | 跨情境一致的穩定信念 |
| core | 0.85-1.0 | 接近 identity level |

張力類型：contradiction、creative_tension、context_dependent、evolving

### Layer 3: Reasoning Trace（推理軌跡）

**Schema**: `schemas/reasoning_trace.json`
**儲存**: `data/{owner_id}/traces.jsonl`

```
觸發（什麼情境）
  → 激活（哪些 conviction，各扮演什麼角色）
  → 推理（什麼步驟、什麼風格）
  → 結論（決定了什麼、多確信）
  → 回饋（後來怎樣 → 強化或削弱 conviction）
```

**螺旋機制**：trace 的 outcome 回頭修改 conviction 的 strength。

### Layer 4: Context Frame（情境框架）

**Schema**: `schemas/context_frame.json`
**儲存**: `data/{owner_id}/frames.jsonl`

核心概念：
- **primary_convictions** — 激活的信念 + 各自的激活權重
- **suppressed_convictions** — 被壓制的信念
- **reasoning_patterns** — 偏好的推理風格和步驟序列
- **voice** — 語氣、常用句式、避免的說法
- **effectiveness** — 從歷史 trace 的 outcome 統計

### Layer 5: Identity Core（身份核心）

**Schema**: `schemas/identity_core.json`
**儲存**: `data/{owner_id}/identity.json`

篩選標準：conviction 在 >80% 的 active frame 中都被激活。數量 5-15 條。

## 資料流

### 寫入（Ingestion）

```
原始素材（來自各 instance 的輸入管線）
  │
  ├─→ [提取] Layer 1: Signals
  ├─→ [提取] Layer 3: Reasoning Traces
  ├─→ [偵測] Layer 2: Convictions（共鳴偵測）
  ├─→ [聚類] Layer 4: Context Frames（定期）
  └─→ [掃描] Layer 5: Identity Core（定期）
```

### 讀取（Query）

```
問題進來（帶 owner_id + caller 身份）
  │
  ├─ 1. Frame Matching → 匹配情境框架
  ├─ 2. Conviction Activation → 激活信念組合
  ├─ 3. Trace Retrieval → 找推理路徑模板
  ├─ 4. Identity Check → 不違反身份核心
  └─ 5. Response Generation → 用該 frame 的語氣和推理風格
```

## 設計原則

1. **湧現而非宣告** — 信念、框架、身份都是偵測出來的
2. **螺旋而非管線** — outcome 回饋 conviction，conviction 影響下一次推理
3. **激活而非搜尋** — 根據情境激活特定區域，不是搜全庫
4. **情境感知** — 同一個人在不同情境下是不同的
5. **強度連續** — 信念是 0-1 的連續分數
6. **可追溯** — 每一層都可以追溯到下一層的證據來源
7. **Multi-tenant** — 引擎共用，資料隔離，每人一個思維模型
