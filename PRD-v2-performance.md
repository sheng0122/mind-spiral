# Mind Spiral — PRD v2（效能優先版）

> 對照 `PRD.md`（概念完整版）。兩版共用同一套 schema 和五層概念模型，差異在**運算方式**。
> 目標：跑完後比較兩版的準確率、延遲、token 消耗，決定最終採用哪一版或混合。

## 核心設計差異

| | v1（概念完整版） | v2（效能優先版） |
|---|---|---|
| Conviction 偵測 | LLM 逐一比對 signal 對 | embedding 聚類 + 欄位檢查 + 少量 LLM |
| Trace 提取 | 獨立 LLM pass | 跟 signal 提取合併成同一次 LLM call |
| Frame 聚類 | LLM 分析 trace 群 | conviction co-occurrence 矩陣 + 閾值切割 |
| 查詢 | 5 次串行 LLM call | 預計算 context + 1 次 LLM call |
| 每日整理 | LLM 從 signal 生成 | 模板填充 + 1 次 LLM 潤飾 |
| 矛盾偵測 | LLM 兩兩比對 | embedding 距離 + direction 衝突 + 1 次 LLM 確認 |

---

## 設計原則

1. **LLM 只做人類語言的活**——總結、潤飾、生成回答。不做比對、分類、聚類。
2. **能用數學解決的不用 LLM**——embedding 相似度、聚類、欄位比對、覆蓋率計算。
3. **預計算 > 即時計算**——Layer 2-5 是快照，不是即時運算。
4. **寫入快、批次算、查詢只一跳**——三條路徑各自優化。

---

## 三條路徑

### 路徑 1：寫入（即時，< 1 秒）

```
新 signal 進來
  → 計算 embedding（本地 bge-m3，~50ms）
  → append to signals.jsonl
  → upsert to 向量索引（ChromaDB，~10ms）
  → done
```

不做任何 LLM call。不做 conviction 偵測。不做矛盾檢查。
純粹記錄 + 索引。

### 路徑 2：批次運算（每日背景，3-10 分鐘）

每天凌晨或固定時間跑一次，處理當天所有新 signal。

#### Step 1：Embedding 聚類（純數學，~5 秒 / 3000 signals）

```python
# 所有 signal 的 embedding 已經在寫入時算好
embeddings = load_all_embeddings(owner_id)

# 用 HDBSCAN 或 agglomerative clustering
# similarity threshold = 0.80
clusters = cluster_embeddings(embeddings, threshold=0.80)
```

每個 cluster = 一群語意相近的 signal。

**不需要 LLM。**

#### Step 2：收斂檢查（純欄位比對，~1 秒）

```python
for cluster in clusters:
    signals_in_cluster = get_signals(cluster)

    # 五種共鳴，全部是欄位檢查，不需要 LLM
    resonance = {
        "input_output_convergence": has_both_directions(signals_in_cluster),
        "temporal_persistence": spans_multiple_dates(signals_in_cluster, min_days=7),
        "cross_context_consistency": spans_multiple_contexts(signals_in_cluster, min=2),
        "spontaneous_emergence": has_unprompted_outputs(signals_in_cluster),
        "action_alignment": has_decided_or_acted(signals_in_cluster),
    }

    resonance_count = sum(resonance.values())

    if resonance_count >= 2:
        conviction_candidates.append({
            "cluster": cluster,
            "signals": signals_in_cluster,
            "resonance": resonance,
            "score": compute_score(resonance, signals_in_cluster)
        })
```

**不需要 LLM。**

#### Step 3：Conviction 生成 / 更新（少量 LLM call）

只對 Step 2 篩出的候選做 LLM call：

```python
for candidate in conviction_candidates:  # 通常 20-50 個
    # 檢查是否匹配既有 conviction（embedding 距離）
    existing = find_nearest_conviction(candidate.cluster_centroid)

    if existing and similarity > 0.85:
        # 更新既有 conviction 的 strength
        update_conviction_strength(existing, candidate)  # 純數學
    else:
        # 新 conviction：需要 1 次 LLM call 生成 statement
        statement = llm_call(
            "用使用者的語氣，把這組信號的共同觀點總結成一句話",
            context=candidate.signals[:5]  # 最多給 5 個代表 signal
        )
        create_conviction(statement, candidate)
```

**LLM call 數量 = 新 conviction 的數量，通常每天 0-5 個。**

#### Step 4：矛盾偵測（embedding + 1 次 LLM 確認）

```python
# 找 conviction 之間 embedding 相似但 statement 語意相反的
for pair in high_similarity_conviction_pairs:
    # 快速排除：同方向（都是正面或都是負面）= 不是矛盾
    if same_sentiment(pair):
        continue

    # 只對疑似矛盾的做 LLM 確認（每天 0-3 個）
    relationship = llm_call(
        "這兩個觀點的關係是 contradiction / evolution / context_dependent / creative_tension？",
        context=pair
    )

    if relationship == "contradiction":
        queue_line_notification(pair)
```

**LLM call 數量 = 疑似矛盾的 conviction 對數，通常每天 0-3 個。**

#### Step 5：生成觸碰訊息（1 次 LLM call）

```python
# 組合今天的素材
digest_context = {
    "new_signals_summary": summarize_today_signals(),      # 純模板
    "conviction_changes": get_conviction_changes_today(),   # 純查表
    "contradictions": get_new_contradictions(),              # 從 Step 4
    "pending_decision_followups": get_due_followups(),      # 從佇列
}

# 1 次 LLM call：把結構化素材變成自然語言的 LINE 訊息
message = llm_call(
    "把以下素材寫成簡短的每日整理訊息",
    context=digest_context
)
```

#### 每日批次 LLM call 總計

| 步驟 | LLM calls | 說明 |
|------|-----------|------|
| 聚類 | 0 | 純數學 |
| 收斂檢查 | 0 | 純欄位比對 |
| 新 conviction 生成 | 0-5 | 只對新發現的 |
| 矛盾確認 | 0-3 | 只對疑似矛盾的 |
| 觸碰訊息 | 1 | 每日整理 |
| **合計** | **1-9** | |

### 路徑 3：查詢（即時，1-3 秒）

```python
def query(owner_id, caller, question):
    # Step 1: Frame Matching — keyword + embedding，不用 LLM
    frame = match_frame(
        question=question,
        caller_type=get_caller_type(caller),
        frames=load_frames(owner_id)
    )  # ~50ms

    # Step 2: Conviction Activation — 從 frame 直接查表
    convictions = frame.primary_convictions  # ~1ms

    # Step 3: Trace Retrieval — embedding 搜尋
    traces = search_traces(
        query_embedding=embed(question),
        frame_id=frame.frame_id,
        top_k=3
    )  # ~50ms

    # Step 4: 組 context，一次 LLM call
    response = llm_call(
        prompt="用以下材料，以使用者的語氣和推理方式回答問題",
        context={
            "identity_core": load_identity(owner_id),        # 5-15 條
            "frame": frame,                                    # 1 個
            "active_convictions": convictions,                  # 3-7 條
            "relevant_traces": traces,                         # 3 條
            "access_control": get_visibility(caller),
            "question": question
        }
    )  # 1-3 秒

    return response
```

**1 次 LLM call。** 前面的匹配和檢索全部是毫秒級。

---

## Token 消耗預估

### 每日批次（3000 signals 規模）

| 步驟 | calls | input tokens/call | output tokens/call | 小計 |
|------|-------|-------------------|-------------------|------|
| 新 conviction 生成 | 5 | ~500（5 個 signal 摘要） | ~50 | 2,750 |
| 矛盾確認 | 3 | ~200（2 個 conviction） | ~50 | 750 |
| 每日整理 | 1 | ~800（結構化素材） | ~300 | 1,100 |
| **合計** | **9** | | | **~4,600 tokens** |

### 每次查詢

| 步驟 | calls | input tokens | output tokens | 小計 |
|------|-------|-------------|--------------|------|
| 回答生成 | 1 | ~2,000（五層 context） | ~500 | 2,500 |

### 月度成本對比

假設：每天 1 次批次 + 10 次查詢，使用 Qwen 本地或 Gemini Flash 雲端。

| | v1（概念完整版） | v2（效能優先版） |
|---|---|---|
| 每日批次 LLM calls | ~100-500 | ~1-9 |
| 每日批次 tokens | ~50K-200K | ~4.6K |
| 每次查詢 LLM calls | 5 | 1 |
| 每次查詢 tokens | ~5K-10K | ~2.5K |
| 每日總 tokens | ~100K-250K | ~30K |
| 月度 tokens | ~3M-7.5M | ~900K |
| Gemini Flash 月費 | ~$0.45-$1.13 | ~$0.14 |
| 本地 Ollama | 免費但慢（分鐘級→小時級） | 免費且快（分鐘級） |

**v2 的 token 消耗約為 v1 的 10-15%。**

---

## 準確率的潛在犧牲

v2 用 embedding 聚類取代 LLM 逐一比對，可能在以下場景犧牲準確率：

| 場景 | 風險 | 緩解方式 |
|------|------|---------|
| 語意相近但立場相反的 signal | embedding 距離近但不是同一觀點 | Step 4 矛盾偵測會捕捉 |
| 同一觀點但用詞差異大 | embedding 距離遠，漏掉收斂 | 降低聚類 threshold（0.75），容忍更多候選 |
| 隱含的推理路徑 | embedding 不捕捉推理結構 | trace 提取仍用 LLM（但合併在 signal 提取時做） |
| 細微的情境差異 | 聚類忽略 context 維度 | 收斂檢查時用欄位比對補強 |

**預期：conviction 偵測準確率從 ~90% 降到 ~80%，但速度快 100 倍、成本降 90%。**

這個 trade-off 是否值得，需要跑 benchmark 驗證。

---

## Benchmark 計劃

用 Joey 的 2,856 個既有 atoms 作為測試資料：

### 測試 1：Conviction 偵測準確率

```
1. 人工標注 30 個「Joey 真正的信念」作為 ground truth
2. v1: 用 LLM 逐一比對所有 signal 對，看能偵測到幾個
3. v2: 用 embedding 聚類 + 收斂檢查，看能偵測到幾個
4. 比較 precision / recall / F1
```

### 測試 2：矛盾偵測準確率

```
1. 人工標注 10 個已知的矛盾 / 演變 / 情境依賴
2. v1: LLM 兩兩比對
3. v2: embedding 距離 + LLM 確認
4. 比較 precision / recall
```

### 測試 3：查詢品質

```
1. 準備 20 個測試問題（跨不同 frame 和 caller）
2. v1: 5 次串行 LLM call 生成回答
3. v2: 預計算 context + 1 次 LLM call 生成回答
4. Joey 人工評分：回答品質 1-5 分
5. 比較平均分 + 回答延遲
```

### 測試 4：Token / 成本

```
1. 跑完測試 1-3，記錄每個步驟的 token 消耗
2. 計算月度成本（本地 Ollama vs 雲端 Gemini Flash）
3. 繪製 準確率 vs 成本 的 trade-off 圖
```

---

## 處理管線（效能優先版）

### Signal Ingestion（即時）

```python
# signal_store.py
def ingest(owner_id: str, signals: list[Signal]):
    for signal in signals:
        signal.embedding = compute_embedding(signal.content.text)  # ~50ms
        append_to_jsonl(f"data/{owner_id}/signals.jsonl", signal)
        upsert_to_vector_index(owner_id, signal)                   # ~10ms
```

### Daily Batch（每日背景）

```python
# daily_batch.py — 整合所有每日運算
def run_daily(owner_id: str):
    # 1. Conviction Detection（聚類 + 收斂檢查 + 少量 LLM）
    new_convictions = detect_convictions(owner_id)

    # 2. Contradiction Scan（embedding 距離 + LLM 確認）
    contradictions = scan_contradictions(owner_id)

    # 3. Decision Follow-up Check（純查表）
    due_followups = check_decision_followups(owner_id)

    # 4. Generate Daily Digest（1 次 LLM call）
    digest = generate_digest(owner_id, new_convictions, contradictions, due_followups)

    # 5. Push to LINE
    push_line_message(owner_id, digest)
```

### Weekly Batch（每週背景）

```python
# weekly_batch.py
def run_weekly(owner_id: str):
    # Frame Clustering（conviction co-occurrence，純數學）
    update_frames(owner_id)

    # Weekly Report（1 次 LLM call）
    report = generate_weekly_report(owner_id)
    push_line_message(owner_id, report)
```

### Monthly Batch

```python
# monthly_batch.py
def run_monthly(owner_id: str):
    # Identity Detection（覆蓋率查表，純數學）
    update_identity(owner_id)
```

### Query（即時）

```python
# query_engine.py
def query(owner_id: str, caller: str, question: str) -> str:
    frame = match_frame_by_keywords(owner_id, question, caller)  # ~50ms
    convictions = lookup_active_convictions(frame)                 # ~1ms
    traces = search_traces_by_embedding(owner_id, question, k=3)  # ~50ms
    identity = load_identity(owner_id)                             # ~1ms

    context = build_context(identity, frame, convictions, traces, caller)
    response = llm_call("回答問題", context=context, question=question)  # 1-3s

    return response
```

---

## 與 v1 共用的部分

| 元件 | 共用 | 說明 |
|------|------|------|
| Schema（五層） | ✅ | 完全相同的 JSON Schema |
| 資料格式 | ✅ | 同樣的 JSONL / JSON 檔案 |
| signal_store.py | ✅ | CRUD 介面相同 |
| LINE Bot | ✅ | 推送和接收介面相同 |
| 存取控制 | ✅ | 相同的角色過濾邏輯 |
| conviction_detector.py | ❌ | v1 用 LLM，v2 用 embedding 聚類 |
| query_engine.py | ❌ | v1 用 5 次 LLM，v2 用 1 次 LLM |
| daily_batch.py | ❌ | v2 獨有，整合所有每日運算 |

**可以用 feature flag 切換 v1 / v2 的實作**，跑 A/B 測試。

---

## 開發路線圖（效能優先版）

### Phase 0 — 基礎（同 v1）

| 項目 | 狀態 |
|------|------|
| Schema + 架構文件 | ✅ |
| engine/ 基本框架 | 🔲 |
| signal_store.py + embedding 計算 | 🔲 |
| atoms → signals 遷移 | 🔲 |

### Phase 1 — 核心螺旋（效能版）

| 項目 | 說明 |
|------|------|
| embedding 聚類模組 | HDBSCAN / agglomerative，可調 threshold |
| 收斂檢查模組 | 五種共鳴的欄位比對 |
| conviction 生成（少量 LLM） | 只對候選做 statement 總結 |
| 矛盾偵測（embedding + LLM 確認） | 快速篩 + 精準確認 |
| daily_batch.py | 整合以上 + 生成觸碰 |
| LINE Bot 最小版 | 推送 + 收回覆 |

### Phase 1.5 — Benchmark

| 項目 | 說明 |
|------|------|
| 人工標注 ground truth | 30 conviction + 10 矛盾 + 20 問題 |
| v1 實作（LLM 版 conviction detector） | 對照組 |
| v2 實作（embedding 版） | 實驗組 |
| 跑 benchmark，比較準確率 / 延遲 / token | 決定最終方案 |

### Phase 2+ — 依 benchmark 結果決定

可能的結果：
- **v2 夠好** → 全面採用 v2
- **v2 在某些場景不夠** → 混合：日常用 v2，關鍵場景用 v1
- **v1 明顯更好** → 用 v1，但借鑑 v2 的查詢優化（預計算 context + 1 次 LLM）
