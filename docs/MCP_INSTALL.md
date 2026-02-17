# Joey MCP Server — 安裝指南

Joey 是一個思維引擎 MCP Server，讓你的 AI 助手能用 Joey 的思維方式回答問題、產出內容、搜尋記憶、追蹤觀點演變。

```
MCP Server URL: http://joey.shifu-ai.org:8001/mcp
Transport: Streamable HTTP
認證: 不需要（所有 tools 皆為唯讀）
```

---

## 快速安裝

### Claude Code（終端機）

```bash
claude mcp add --transport http joey http://joey.shifu-ai.org:8001/mcp --scope user
```

安裝後重啟 Claude Code，輸入 `/mcp` 確認 joey 狀態為 connected。

移除：`claude mcp remove joey --scope user`

### Claude.ai（網頁版 / 手機版）

需要 Pro、Max、Team 或 Enterprise 方案。

1. 點擊右上角頭像 → **Settings**
2. 左側選 **Connectors**
3. 滾到底部，點 **Add custom connector**
4. 貼上 URL：`http://joey.shifu-ai.org:8001/mcp`
5. 點 **Add** 完成
6. 在對話中點左下角 **＋** → **Connectors** → 開啟 **joey**

### ChatGPT

需要 Plus、Pro、Business 或 Enterprise 方案。

1. **Settings** → **Connectors** → **Advanced** → 開啟 **Developer mode**
2. 回到 **Connectors** → 點 **Create**
3. 填入：
   - Name：`Joey`
   - Description：`Joey 的五層認知思維引擎 — 回答問題、產出內容、搜尋記憶`
   - Connector URL：`http://joey.shifu-ai.org:8001/mcp`
   - Authentication：None
4. 勾選信任，點 **Create**
5. 在對話中從 **＋** 選單選擇 **Developer mode** → 啟用 **Joey**

### Cursor

點擊下方連結一鍵安裝：

[Install Joey MCP in Cursor](cursor://anysphere.cursor-deeplink/mcp/install?name=Joey&config=eyJ0eXBlIjoiaHR0cCIsInVybCI6Imh0dHA6Ly9qb2V5LnNoaWZ1LWFpLm9yZzo4MDAxL21jcCJ9)

或手動設定：Settings → Cascade → MCP → Add Server → HTTP：

```json
{
  "joey": {
    "type": "http",
    "url": "http://joey.shifu-ai.org:8001/mcp"
  }
}
```

### Windsurf

Cmd/Ctrl + Shift + P → `MCP: Add Server` → HTTP，或編輯 `~/.codeium/windsurf/mcp_config.json`：

```json
{
  "mcpServers": {
    "joey": {
      "serverUrl": "http://joey.shifu-ai.org:8001/mcp"
    }
  }
}
```

### VS Code (Copilot)

Cmd/Ctrl + Shift + P → `MCP: Add Server` → HTTP，或編輯 `.vscode/mcp.json`：

```json
{
  "servers": {
    "joey": {
      "type": "http",
      "url": "http://joey.shifu-ai.org:8001/mcp"
    }
  }
}
```

### 其他支援 MCP 的工具

使用 Streamable HTTP transport 連接即可：

```
URL: http://joey.shifu-ai.org:8001/mcp
Transport: Streamable HTTP
認證: 不需要
```

---

## 可用 Tools（11 個）

| Tool | 用途 | 速度 |
|------|------|------|
| `joey_ask` | 統一入口 — 自動判斷回答問題或產出內容 | ~10s |
| `joey_context` | 原料包 — 只取五層思維原料，不呼叫 LLM | < 1s |
| `joey_query` | 用 Joey 的思維方式回答問題 | ~10s |
| `joey_generate` | 產出內容（文章/貼文/腳本/決策分析） | ~13s |
| `joey_recall` | 搜尋原話記憶 | ~1s |
| `joey_explore` | 展開某主題的完整思維 | ~1s |
| `joey_evolution` | 追蹤某主題的觀點演變 | ~1s |
| `joey_blindspots` | 偵測思維盲區 | < 0.5s |
| `joey_connections` | 找兩個主題之間的隱性關聯 | ~1s |
| `joey_simulate` | 模擬情境，預測 Joey 會怎麼反應 | ~30s |
| `joey_stats` | 查看五層數據統計 | < 0.5s |

## 使用範例

安裝完成後，直接在對話中提到 Joey 即可。AI 會自動判斷何時該呼叫 Joey tools。

| 你說的話 | AI 會呼叫 |
|---------|----------|
| Joey 怎麼看定價策略？ | `joey_ask` |
| 用 Joey 的風格寫一篇短影音腳本 | `joey_generate`（script） |
| Joey 什麼時候講過 AI？ | `joey_recall` |
| 幫我取 Joey 關於「個人品牌」的思維原料 | `joey_context` |
| Joey 對短影音的看法有什麼變化？ | `joey_evolution` |
| 如果有人找 Joey 合作但要求砍價，他會怎麼反應？ | `joey_simulate` |
| Joey 有什麼思維盲區？ | `joey_blindspots` |
| Joey 的「定價」和「個人品牌」有什麼關聯？ | `joey_connections` |

## output_type 說明（joey_generate）

| 類型 | 說明 | 字數 |
|------|------|------|
| `article` | 完整文章 | 1500-3000 字 |
| `post` | 社群貼文 | 400-800 字 |
| `script` | 短影音腳本（60-90 秒） | 400-800 字 |
| `decision` | 決策分析 | 600-1200 字 |

## 注意事項

- 所有 tools 都是**唯讀**的，不會修改 Joey 的資料
- 回答都是第一人稱「我」，模擬 Joey 的思維方式
- 回傳 `low_confidence: true` 表示證據不足，回答可能不準確
- Server 在新加坡，首次請求可能需要幾秒載入時間

## 問題排除

| 狀況 | 解法 |
|------|------|
| 連不上 / disconnected | 確認網路能連到 `joey.shifu-ai.org:8001`，重啟工具 |
| tool 回應很慢（> 30s） | Server 可能剛重啟，embedding model 載入中，等 30 秒再試 |
| 回答內容跟 Joey 無關 | 確認有帶 `owner_id: "joey"` |

## 技術細節

- **協議**: [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) over Streamable HTTP
- **Server**: FastMCP + Python
- **引擎**: Mind Spiral 五層認知架構（Signal → Conviction → Reasoning Trace → Context Frame → Identity Core）
- **資料量**: 2,700+ signals、369 convictions、254 traces、5 frames、2 identity cores
