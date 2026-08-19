# ai-connector 接口详情

第三方 Agent 的完整接入方法、客户端能力要求、工具参数和错误处理见 [HomeFin MCP / AI Agent 接入说明](agent-integration-guide.md)。

## 协议入口

| Method | Path | 用途 |
|--------|------|------|
| GET | `/.well-known/oauth-authorization-server` | OAuth/CIMD 元数据 |
| GET | `/.well-known/oauth-protected-resource/mcp` | MCP Resource 元数据 |
| GET | `/authorize` | Authorization Code + PKCE 授权 |
| POST | `/token` | 授权码兑换与 Refresh Token 轮换 |
| POST | `/mcp` | MCP 2026-07-28 Streamable HTTP |

## Web 管理接口

| Method | Path | 用途 |
|--------|------|------|
| GET | `/api/v1/ai-connections/` | 当前用户连接列表 |
| GET | `/api/v1/ai-connections/authorization-request` | 授权预览 |
| POST | `/api/v1/ai-connections/authorization-request` | 一次性同意或拒绝 |
| DELETE | `/api/v1/ai-connections/{connection_id}` | 撤销连接 |

## MCP 工具

- 读取：`get_financial_overview`、`search_transactions`、`get_budget_status`、`list_categories`。
- 交易：`get_transaction_options`、`create_transaction`、`update_transaction`、`delete_transaction`。
- 预算：`create_budget`、`update_budget`、`delete_budget`。
- 分类：`create_category`、`update_category`、`delete_category`。
- `tools/list` 按连接 Scope 隐藏无权工具；所有写工具要求结构化 `input_required` 两阶段确认、资源指纹和 `idempotency_key`。

旧 `/api/v1/agent/*` 与 `/api/v1/system/api-tokens/*` 不注册，也不提供兼容代理。
