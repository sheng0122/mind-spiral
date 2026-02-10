# Mind Spiral MCP Server + 權限機制開發計畫

## 目標

將 Mind Spiral 五層認知引擎包成 MCP Server，讓任何 AI agent 都能呼叫，並加入完整的身份驗證 + 分層權限控制。

## 架構

```
外部 Agent（Claude Desktop / OpenClaw / LangChain / ...）
    │
    │ MCP stdio / SSE
    ▼
┌─────────────────────────────────────────────┐
│  mcp_server.py（MCP Server，官方 SDK）       │
│                                             │
│  ┌─ Auth Layer ──────────────────────────┐  │
│  │  Transport 驗證                        │  │
│  │  stdio → 自動 self                    │  │
│  │  SSE  → Bearer token → 查 token 表    │  │
│  └───────────────────────────────────────┘  │
│                    ▼                        │
│  ┌─ Access Control ──────────────────────┐  │
│  │  caller 身份 → 解析存取等級            │  │
│  │  資料層過濾（visibility × strength）    │  │
│  │  動作層權限（誰能做什麼）              │  │
│  └───────────────────────────────────────┘  │
│                    ▼                        │
│  ┌─ Confidence Envelope ─────────────────┐  │
│  │  response + grounding + citations      │  │
│  │  + access_level + redacted_count       │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
                     ▼
        engine/（現有五層引擎，核心不改）
```

---

## 權限模型：完整設計

### 設計原則

1. **三層分離**：身份驗證（你是誰）→ 存取等級（你能看什麼）→ 動作權限（你能做什麼）
2. **資料天生帶標籤**：Signal 已有 `audience.visibility`，Conviction/Trace 新增 `visibility`
3. **雙重過濾**：資料的 `visibility` 標籤 × caller 的存取等級，兩者交叉決定可見性
4. **Transport 決定信任基礎**：stdio = 本機 = 最高信任；SSE = 遠端 = 需要 token

### 第一層：身份驗證（Authentication）

#### stdio 模式（本機）

```
stdio 連線 → 自動識別為 owner → access_level = self
```

本機 stdio 不需要 caller 參數，因為能跑這個 process 的人就是 owner。
但仍可傳 `caller` 參數來「模擬其他人的視角」（用於測試）。

#### SSE 模式（遠端，Phase 4）

```
SSE 連線 → HTTP header: Authorization: Bearer <token>
         → 查 config/tokens.yaml → 解析 caller_id + access_level
```

Token 設定檔：

```yaml
# config/tokens.yaml（不進版控，在 .gitignore）
tokens:
  - token: "msp_abc123..."        # 前綴 msp_ 方便識別
    caller_id: "alice"
    access_level: "team"           # 發 token 時就決定等級
    expires: "2026-12-31"
    note: "Alice 的 AI agent"

  - token: "msp_pub456..."
    caller_id: "public_api"
    access_level: "public"
    expires: "2026-06-30"
    note: "對外 API"
```

Token 管理 CLI（Phase 4 實作）：

```bash
mind-spiral token create --caller alice --level team --expires 90d
mind-spiral token list --owner joey
mind-spiral token revoke msp_abc123
```

### 第二層：存取等級（Access Level）

三個等級，每個等級定義「能看到的資料範圍」：

| 等級 | 身份條件 | 資料可見範圍 |
|------|---------|-------------|
| `self` | owner 本人（stdio 或 self token） | 全部五層，含低 strength、private 標記、矛盾、原始 signal |
| `team` | config 中的 team_members | visibility ∈ {public, team} 且 strength ≥ team_min_strength |
| `public` | 其他所有人 | visibility = public 且 strength ≥ public_min_strength |

#### 存取等級解析邏輯

```python
def resolve_access_level(
    owner: str,
    caller: str | None,
    transport: Literal["stdio", "sse"],
    token_record: TokenRecord | None = None,
) -> Literal["self", "team", "public"]:

    # 1. stdio 且沒有 caller → self
    if transport == "stdio" and caller is None:
        return "self"

    # 2. stdio 有 caller → 模擬模式（用於測試）
    if transport == "stdio" and caller is not None:
        if caller == owner:
            return "self"
        if caller in config.team_members:
            return "team"
        return "public"

    # 3. SSE → 看 token 記錄
    if token_record:
        return token_record.access_level

    # 4. 無 token 的 SSE → public
    return "public"
```

### 第三層：資料層過濾（Data Filtering）

#### 五層資料的 visibility 對照

| 層 | Model | 現有 visibility | 改動 |
|----|-------|----------------|------|
| Signal | `SignalAudience.visibility` | public / team_internal / management_only / one_on_one_private / self_only | **不改**，做映射 |
| Conviction | `Conviction` | 無 | **新增** `visibility` 欄位 |
| Trace | `ReasoningTrace` | 無 | **新增** `visibility` 欄位 |
| Frame | `ContextFrame` | 無 | 不加（frame 本身是聚類結果，過濾其內容即可） |
| Identity | `IdentityCore` | 無 | 不加（identity 都是高 strength 公開信念） |

#### Signal visibility 映射

Signal 已有五種 visibility，映射到三層存取等級：

```python
SIGNAL_VISIBILITY_MAP = {
    "public":              "public",   # 公開內容
    "team_internal":       "team",     # 團隊內部
    "management_only":     "team",     # 管理層（視為 team）
    "one_on_one_private":  "self",     # 一對一私人
    "self_only":           "self",     # 自己的反思
}
```

#### Conviction / Trace 新增欄位

```python
class Conviction(BaseModel):
    # ... 現有欄位 ...
    visibility: Literal["public", "team", "private"] = "team"

class ReasoningTrace(BaseModel):
    # ... 現有欄位 ...
    visibility: Literal["public", "team", "private"] = "team"
```

預設 `"team"` — 現有資料不需遷移，自動被 team 和 self 看到。

#### Conviction visibility 自動推斷

新 conviction 產生時，根據其 source signals 的 visibility 推斷：

```python
def infer_conviction_visibility(source_signals: list[Signal]) -> str:
    """從 source signals 的 visibility 推斷 conviction 應有的 visibility。
    取最嚴格的那個。"""
    levels = {"public": 0, "team": 1, "private": 2}
    mapped = [
        SIGNAL_VISIBILITY_MAP.get(
            s.audience.visibility if s.audience else None,
            "team"  # 沒有 audience 標記的預設 team
        )
        for s in source_signals
    ]
    strictest = max(mapped, key=lambda v: levels[v])
    return strictest
```

#### 過濾函數

```python
def filter_convictions(
    convictions: list[Conviction],
    access_level: Literal["self", "team", "public"],
    thresholds: AccessThresholds,
) -> list[Conviction]:
    """根據存取等級過濾 convictions。"""

    if access_level == "self":
        return convictions  # 全部可見

    min_strength = (
        thresholds.team_min_strength if access_level == "team"
        else thresholds.public_min_strength
    )

    allowed_visibility = (
        {"public", "team"} if access_level == "team"
        else {"public"}
    )

    return [
        c for c in convictions
        if c.visibility in allowed_visibility
        and c.strength.score >= min_strength
    ]
```

Trace 的過濾邏輯相同。

### 第四層：動作權限（Action Permissions）

不同存取等級能執行的 MCP tool 不同：

| Tool | self | team | public | 說明 |
|------|------|------|--------|------|
| `ask` | ✅ | ✅ | ✅ | 結果按等級過濾 |
| `query` | ✅ | ✅ | ✅ | 結果按等級過濾 |
| `generate` | ✅ | ✅ | ❌ | 生成需要深層資料，public 不開放 |
| `ingest` | ✅ | ❌ | ❌ | 只有 owner 能餵資料 |
| `profile` | ✅ | ✅ | ✅ | 結果按等級過濾 |
| `stats` | ✅ | ✅ | ✅ | 只顯示數量，無敏感資訊 |

未授權的呼叫回傳：

```json
{
  "error": "permission_denied",
  "message": "generate requires 'team' or higher access level",
  "your_level": "public"
}
```

### 設定檔

`config/default.yaml` 新增：

```yaml
engine:
  access_control:
    team_members: ["alice", "bob"]
    thresholds:
      team_min_strength: 0.6       # team 看到的最低 conviction strength
      public_min_strength: 0.8     # public 看到的最低 conviction strength
    action_permissions:
      generate: ["self", "team"]   # 允許呼叫的等級
      ingest: ["self"]
      # ask, query, profile, stats 預設全開，不用列
```

### 存取等級對每層資料的影響摘要

```
                    self          team              public
                    ─────         ─────             ─────
Signal              全部          public+team映射    public映射
Conviction          全部          vis∈{public,team}  vis=public
                                 + str≥0.6          + str≥0.8
Trace               全部          vis∈{public,team}  vis=public
Frame               全部          全部（內容已過濾）  全部（內容已過濾）
Identity            全部          全部               全部
Contradictions      ✅ 可見       ❌ 隱藏            ❌ 隱藏
Tensions            ✅ 可見       ⚠️ 僅 resolved     ❌ 隱藏
Outcome (pending)   ✅ 可見       ❌ 隱藏            ❌ 隱藏
```

---

## MCP Tools 設計（6 個工具）

### 核心互動（3 個）

1. **`ask`** — 統一入口（自動判斷 query/generate）
   - params: `owner`, `text`, `caller?`, `context?`
   - 回傳: response + confidence envelope + citations

2. **`query`** — 直接提問
   - params: `owner`, `question`, `caller?`
   - 回傳: response + grounding metadata

3. **`generate`** — 生成內容
   - params: `owner`, `task`, `output_type`, `caller?`, `extra_instructions?`
   - 回傳: content + grounding metadata
   - 權限: self / team

### 資料操作（2 個）

4. **`ingest`** — 餵入新 signal
   - params: `owner`, `signals`（JSON array）
   - 權限: 僅 self

5. **`profile`** — 取認知摘要
   - params: `owner`, `caller?`
   - 回傳: identity cores + top convictions（依權限過濾）+ stats

### 系統（1 個）

6. **`stats`** — 系統狀態
   - params: `owner`
   - 回傳: signal/conviction/trace/frame 數量

---

## 輸出 Confidence Envelope

所有查詢類 tool 回傳結構化 metadata：

```json
{
  "response": "...",
  "confidence": 0.82,
  "grounding": {
    "frame": "商業決策",
    "match_method": "embedding",
    "match_score": 0.85,
    "convictions_used": 3,
    "traces_used": 5,
    "identity_check": "pass"
  },
  "citations": [
    {"type": "conviction", "id": "conv_pricing_001", "text": "...", "strength": 0.91}
  ],
  "access_level": "team",
  "redacted_count": 2,
  "warning": null
}
```

`redacted_count`：因權限被過濾掉的資料筆數，讓 caller 知道「有更多資料但你看不到」。

### Confidence 計算

```python
confidence = (
    frame_match_score * 0.3 +
    avg_conviction_strength * 0.3 +
    trace_coverage * 0.2 +      # min(traces_found / 3, 1.0)
    identity_pass * 0.2          # 1.0 if pass, 0.5 if no identity loaded
)
```

---

## 實作檔案

| 檔案 | 內容 | 新增/修改 |
|------|------|----------|
| `mcp_server.py` | MCP Server 主程式（6 tools） | 新增 |
| `engine/access_control.py` | 三層權限（auth + filtering + action check） | 新增 |
| `engine/confidence.py` | Confidence 計算 + envelope 組裝 | 新增 |
| `engine/models.py` | Conviction/Trace 加 `visibility` 欄位 | 修改 |
| `engine/query_engine.py` | QueryContext 加 match_score + redacted_count | 小改 |
| `engine/conviction_detector.py` | 新 conviction 自動推斷 visibility | 小改 |
| `config/default.yaml` | 加 `access_control` 區塊 | 修改 |
| `config/tokens.yaml` | Token 設定檔（Phase 4，不進版控） | 新增 |
| `schemas/conviction.json` | 加 `visibility` 欄位 | 修改 |
| `schemas/reasoning_trace.json` | 加 `visibility` 欄位 | 修改 |

---

## 開發順序

### Step 1: 權限基礎（Phase 2）
1. `engine/models.py` — Conviction/Trace 加 `visibility` 欄位（預設 `"team"`）
2. `schemas/conviction.json` + `schemas/reasoning_trace.json` — 同步 schema
3. `config/default.yaml` — 加 `access_control` 設定
4. `engine/access_control.py` — resolve_access_level + filter 函數（stdio 模式）
5. `engine/conviction_detector.py` — 新 conviction 自動推斷 visibility

### Step 2: Confidence Envelope（Phase 2）
6. `engine/confidence.py` — confidence 計算 + envelope 組裝 + redacted_count
7. `engine/query_engine.py` — QueryContext 加 `frame_match_score`，query/generate 回傳 envelope

### Step 3: MCP Server（Phase 2）
8. `mcp_server.py` — 6 個 tools，Anthropic 官方 MCP SDK
9. 整合 access_control + confidence 到每個 tool
10. stdio 模式下 access_level 自動為 self

### Step 4: 驗證 + Token 機制（Phase 4）
11. `config/tokens.yaml` — token 設定結構
12. `engine/access_control.py` — 加 SSE token 驗證
13. `mind-spiral token` CLI — create / list / revoke
14. 手動測試三種 caller 等級的回傳差異

---

## 技術決策

- **MCP SDK**: Anthropic 官方 `mcp` 套件
- **Transport**: Phase 2 = stdio（本機）；Phase 4 = 加 SSE（遠端）
- **不改引擎核心**: 權限過濾在 MCP 層 / access_control 模組做
- **向後相容**: `visibility` 預設 `"team"`，現有資料不需遷移
- **Token 格式**: `msp_` 前綴 + 隨機字串，方便在 log 中識別
- **Signal visibility 不改**: 已有五種 visibility，做映射而非修改
