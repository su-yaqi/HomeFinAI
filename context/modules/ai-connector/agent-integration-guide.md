# HomeFin MCP / AI Agent 接入说明

本文面向需要把第三方 Agent、桌面 AI 客户端或自研 MCP Client 接入 HomeFin 的开发者。它描述当前实现的真实协议、权限、工具和写入确认方式，不包含已经退役的 Agent REST API、长期 API Token 或 Skill 方案。

## 1. 接入结论

HomeFin 对 AI 只提供一个标准入口：MCP Streamable HTTP + OAuth 2.0 Authorization Code + PKCE。

本地开发默认地址：

```text
MCP Resource:  http://127.0.0.1:8000/mcp
OAuth Issuer:  http://127.0.0.1:8000/
Frontend:      http://localhost:5173
```

发现端点：

```text
GET /.well-known/oauth-protected-resource/mcp
GET /.well-known/oauth-authorization-server
```

协议特征：

- MCP 协议版本：`2026-07-28`
- 传输：Streamable HTTP
- OAuth Grant：`authorization_code`、`refresh_token`
- PKCE：仅 `S256`
- Client Authentication：公开客户端，`token_endpoint_auth_method=none`
- Client Registration：CIMD（Client ID Metadata Document）
- DCR：不支持
- Access Token 默认有效期：15 分钟
- Refresh Token 默认有效期：30 天，且每次使用都会轮换
- 金额单位：人民币元
- 业务时区：默认 `Asia/Shanghai`

## 2. Agent 客户端能力要求

接入方必须同时具备以下能力：

1. 支持 MCP Streamable HTTP，并能执行 `tools/list` 和 `tools/call`。
2. 能读取 OAuth Protected Resource Metadata 和 Authorization Server Metadata。
3. 支持 Authorization Code + PKCE S256。
4. 能以 HTTPS URL 作为 `client_id`，并在该 URL 提供 CIMD JSON。
5. 能启动 `127.0.0.1` 或 `::1` 的随机端口 OAuth 回调监听。
6. 能保存和轮换 Refresh Token。
7. 能保留工具的结构化返回，并对写工具执行本文第 7 节的两阶段确认。

当前 OAuth 回调只接受桌面原生应用使用的 loopback URI。仅支持固定 HTTPS 回调、不能监听本机随机端口的纯云端 Agent，当前不能直接完成授权；这类客户端需要 HomeFin 后续增加新的回调模型，不能通过关闭校验绕过。

## 3. 网络与部署约束

`127.0.0.1` 仅适用于 Agent 和 HomeFin 在同一台机器运行的情况。

远程 Agent 接入时，部署方必须：

1. 为 HomeFin 提供 Agent 可访问的正式 HTTPS 地址。
2. 设置 `MCP_RESOURCE_URL=https://homefin.example.com/mcp`。
3. 设置 `OAUTH_ISSUER_URL=https://homefin.example.com/`，Issuer 不允许携带额外路径。
4. 确保前端授权页也能被用户浏览器访问。
5. 使用受信任 TLS 证书，并保证 DNS、反向代理和 Host 转发正确。
6. 将 Agent CIMD 的精确主机名加入 `AI_CIMD_ALLOWED_HOSTS`。

HomeFin 不会自动开放公网端口、创建隧道或跳过 TLS 校验。

## 4. CIMD 客户端元数据

Agent 的 `client_id` 必须是公开可读取的 HTTPS JSON URL，例如：

```text
https://agent.example.com/oauth/homefin/client.json
```

HomeFin 会主动读取该 URL。响应必须使用 JSON Content-Type，且大小不能超过 64 KiB。示例：

```json
{
  "client_id": "https://agent.example.com/oauth/homefin/client.json",
  "client_name": "Example Desktop Agent",
  "redirect_uris": [
    "http://127.0.0.1/callback/homefin"
  ],
  "response_types": ["code"],
  "grant_types": ["authorization_code", "refresh_token"],
  "token_endpoint_auth_method": "none"
}
```

Loopback URI 的注册值不能包含端口。实际授权时客户端必须使用相同 scheme、host、path 和 query，并增加随机端口，例如：

```text
注册值: http://127.0.0.1/callback/homefin
实际值: http://127.0.0.1:54824/callback/homefin
```

补充限制：

- `client_id` 必须使用 HTTPS，不能包含用户名、密码或 fragment。
- `client_id` 不能使用 IP 字面量。
- CIMD 域名必须精确出现在 `AI_CIMD_ALLOWED_HOSTS` 中。
- HomeFin 不跟随 CIMD URL 的 HTTP 重定向。
- `redirect_uri` 只能使用 `127.0.0.1` 或 `::1`，不能使用 `localhost`。

## 5. OAuth 授权流程

推荐让 MCP SDK 自动完成发现与授权。自行实现时，流程如下：

1. 请求 MCP Resource；未授权时读取资源元数据。
2. 读取 Authorization Server Metadata。
3. 生成 `state`、PKCE `code_verifier` 和 S256 `code_challenge`。
4. 启动随机 loopback 端口的回调监听器。
5. 打开 `/authorize`，参数至少包含：
   - `response_type=code`
   - `client_id=<CIMD HTTPS URL>`
   - `redirect_uri=<带随机端口的 loopback URI>`
   - `code_challenge`
   - `code_challenge_method=S256`
   - `scope`
   - `resource=<MCP_RESOURCE_URL>`
   - `state`
6. 用户在 HomeFin 登录并确认客户端和 Scope。
7. 客户端校验回调中的 `state` 和 `iss`，再用授权码、原 `code_verifier` 和 `resource` 请求 `/token`。
8. 将 Access Token 用于 MCP 请求；到期后使用 Refresh Token 换取新令牌。

Refresh Token 是一次性的轮换令牌。重复使用旧 Refresh Token 会被判定为重放，并撤销整个连接。

## 6. Scope 与工具可见性

可申请的 Scope：

| Scope | 能力 |
| --- | --- |
| `finance:read` | 财务概览、交易、预算、分类读取 |
| `transactions:write` | 创建和更新交易，以及读取交易候选项 |
| `transactions:delete` | 删除交易 |
| `budgets:write` | 创建和更新预算 |
| `budgets:delete` | 删除预算 |
| `categories:write` | 创建和更新分类 |
| `categories:delete` | 删除分类 |

所有写入或删除 Scope 都必须同时包含 `finance:read`。`tools/list` 会根据当前连接的 Scope 隐藏没有权限的工具，因此 Agent 不应假定所有工具始终存在。

建议权限组合：

```text
只读分析:
finance:read

记账助手:
finance:read transactions:write

完整管理:
finance:read transactions:write transactions:delete budgets:write budgets:delete categories:write categories:delete
```

## 7. 写工具的两阶段确认

HomeFin 不依赖 MCP `elicitation/create` 反向请求。所有写工具使用普通结构化结果完成可移植的两阶段确认。

### 第一阶段：生成预览

写工具第一次调用必须设置：

```json
{
  "idempotency_key": "agent-20260818-transaction-0001",
  "confirm": false
}
```

业务参数按具体工具一并提供。此调用不会改变数据库，返回示例：

```json
{
  "status": "input_required",
  "confirmation_id": "<opaque-signed-value>",
  "expires_at": "2026-08-18T13:49:25Z",
  "action": "create transaction ...",
  "preview": {
    "transaction": {},
    "category": {},
    "budget": {},
    "handler": {}
  },
  "instructions": "Ask the user to review this exact preview..."
}
```

Agent 必须向用户展示 `action` 和 `preview`，并等待用户确认。不能因为客户端自己的工具审批已经通过，就跳过 HomeFin 业务确认。

### 第二阶段：提交

用户确认后，在 5 分钟内调用同一个工具：

```json
{
  "idempotency_key": "agent-20260818-transaction-0001",
  "confirm": true,
  "confirmation_id": "<第一阶段原样返回的值>"
}
```

业务参数和 `idempotency_key` 必须与第一阶段保持相同。`confirmation_id` 会绑定：

- HomeFin 用户
- AI Connection
- 工具名称
- 业务参数哈希
- `idempotency_key`
- 资源快照指纹
- 5 分钟有效期

第二阶段会再次读取资源。若分类、预算、交易或依赖关系在确认期间发生变化，HomeFin 会拒绝写入，Agent 应重新执行第一阶段并展示新预览。

`confirmation_id` 应视为短期敏感值，不写入普通日志，不跨用户、连接或工具复用。

## 8. 幂等规则

所有写工具都要求 `idempotency_key`：

- 长度：8 到 100 个字符
- 允许字符：字母、数字、`.`、`_`、`:`、`-`
- 同一连接、同一工具、同一 key、相同参数：返回首次提交结果，不重复写入
- 同一连接、同一工具、同一 key、不同参数：返回冲突错误
- 幂等结果默认保留 30 天

推荐格式：

```text
<agent>:<conversation-or-job>:<operation>:<sequence>
```

例如：

```text
myagent:job-8f31:create-transaction:0001
```

网络超时后应使用原 key 和原参数重试，不能生成新 key，否则可能产生重复数据。

## 9. 工具清单

### 只读工具

| 工具 | 主要输入 | 说明 |
| --- | --- | --- |
| `get_financial_overview` | `period`、`start_date?`、`end_date?` | 收入、支出、结余、趋势、分类占比和预算使用 |
| `search_transactions` | 关键词、日期、类型、分类、预算、状态、经手人、分页 | 查询当前授权用户的交易 |
| `get_budget_status` | `year?`、分页 | 预算金额、已用、剩余和使用率 |
| `list_categories` | 分页 | 分类及稳定的父级路径 |
| `get_transaction_options` | 无 | 返回创建交易可使用的分类、预算、经手人和枚举；需要 `transactions:write` |

`get_financial_overview.period` 可选值：

```text
current_month | last_month | current_year | last_6_months | custom
```

仅当 `period=custom` 时提供 `start_date` 和 `end_date`，范围最长 366 天。

分页 `page_size` 只接受：

```text
10 | 20 | 50 | 100
```

### 交易工具

| 工具 | 业务输入 |
| --- | --- |
| `create_transaction` | `transaction` |
| `update_transaction` | `transaction_id`、`changes` |
| `delete_transaction` | `transaction_id` |

创建交易的 `transaction`：

```json
{
  "category_id": "<uuid>",
  "transaction_type": 2,
  "amount": 88.88,
  "budget_id": "<uuid-or-null>",
  "summary": "午餐",
  "description": "工作日午餐",
  "detail": {
    "note": "测试",
    "items": [{"name": "套餐"}]
  },
  "entry_status": 3,
  "handler_user_id": "<uuid-or-null>",
  "transaction_date": "2026-08-18"
}
```

建议在创建或修改交易前先调用 `get_transaction_options`，不要猜测 UUID。

### 预算工具

| 工具 | 业务输入 |
| --- | --- |
| `create_budget` | `budget` |
| `update_budget` | `budget_id`、`changes` |
| `delete_budget` | `budget_id` |

创建预算的 `budget`：

```json
{
  "name": "月度餐饮预算",
  "amount": 1000,
  "period": 1,
  "year": 2026
}
```

### 分类工具

| 工具 | 业务输入 |
| --- | --- |
| `create_category` | `category` |
| `update_category` | `category_id`、`changes` |
| `delete_category` | `category_id` |

创建分类的 `category`：

```json
{
  "name": "餐饮",
  "parent_id": null,
  "color": "#f97316"
}
```

分类颜色应使用 `#RGB` 或 `#RRGGBB`。删除分类前，服务端会检查子分类和交易引用；删除预算前会检查关联交易。

## 10. 枚举与数据约定

```text
TransactionType:
1 = INCOME
2 = EXPENSE

EntryStatus:
1 = PENDING
2 = SKIPPED
3 = ENTERED

BudgetPeriod:
1 = MONTH
2 = QUARTER
3 = YEAR
```

其他约定：

- 日期使用 ISO `YYYY-MM-DD`。
- 未提供交易日期时，创建预览会使用业务时区的当天日期。
- 金额输入和输出都使用元，必须大于 0。
- `summary` 是简短识别文本，`description` 是说明；只提供其中一个时，HomeFin 会兼容性补齐另一个。
- 更新工具的 `changes` 只应包含确实要修改的字段；“省略字段”和“显式传 null”可能具有不同业务含义。
- 所有资源读取和写入都限定在完成 OAuth 授权的 HomeFin 用户范围内。

## 11. 通用 Agent 行为建议

推荐系统提示或工具策略包含以下规则：

```text
- 查询时优先调用 HomeFin MCP，不编造余额、分类、预算或资源 ID。
- 创建交易前先读取 get_transaction_options。
- 写工具先使用 confirm=false 获取预览。
- 向用户展示完整预览；只有用户批准后才使用 confirm=true 和 confirmation_id。
- 第二阶段必须复用完全相同的业务参数和 idempotency_key。
- 工具未返回已提交资源时，不得声称写入成功。
- 网络错误使用相同幂等键重试。
- 删除操作必须明确说明目标和不可逆影响。
```

## 12. 客户端配置示意

不同 Agent 的配置字段不同，核心只需要把一个 Streamable HTTP MCP Server 指向：

```json
{
  "mcpServers": {
    "homefin": {
      "transport": "streamable-http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

该 JSON 仅表达通用含义，不保证是某一具体 Agent 的原样配置格式。应使用目标 Agent 官方提供的 MCP 添加命令或设置页面，并确认它支持本文第 2 节的 OAuth/CIMD 能力。

Codex CLI 示例：

```bash
codex mcp add homefin --url http://127.0.0.1:8000/mcp
codex mcp login homefin --oauth-client-registration cimd
codex mcp list
```

## 13. 常见错误

### `Client ID ... not found`

检查：

- CIMD URL 是否可从 HomeFin 后端访问。
- 域名是否在 `AI_CIMD_ALLOWED_HOSTS`。
- 是否返回 `application/json`。
- JSON 中的 `client_id` 是否与请求 URL 完全一致。
- 是否包含 loopback `redirect_uris`。

### `Invalid redirect URI`

检查注册 URI 是否无端口，实际 URI 是否使用同一 host、path 和 query，并增加随机端口。不要把 `localhost` 与 `127.0.0.1` 混用。

### MCP 返回 401

Access Token 可能已过期、连接已撤销、用户认证版本已变化，或 Token 的 issuer/audience 与当前部署 URL 不一致。先正常刷新；不要改用旧 API Token。

### 工具没有出现在 `tools/list`

当前连接没有相应 Scope。重新授权所需 Scope，不要尝试直接调用被隐藏的工具。

### `The write confirmation is invalid or expired`

确认超过 5 分钟，或确认值不完整。重新执行 `confirm=false`，展示新预览后再确认。

### `does not match ... exact operation`

第二阶段的用户、连接、工具、业务参数或幂等键发生了变化。不能修改签名状态；重新生成预览。

### `idempotency_key was already used with different parameters`

该 key 已绑定另一组参数。若是在重试，恢复原参数；若是新业务操作，生成新的 key。

### `Cannot send elicitation/create`

说明运行的仍是旧版 HomeFin MCP。当前版本的写工具应返回结构化 `status=input_required`，不需要反向 elicitation 通道。升级并重启后端，不要绕过确认。

## 14. 撤销与安全运维

- 用户可以在 HomeFin AI Connections 页面撤销连接。
- 撤销后 Access Token 和 Refresh Token 都不能继续使用。
- 密码或认证版本变化也会使已有连接失效。
- 不记录 Access Token、Refresh Token、Authorization Header 或完整 `confirmation_id`。
- 生产环境必须使用足够强的 `SECRET_KEY`、数据库密码和管理员密码。
- Scope、工具确认和 Agent 自身审批是三层独立控制，不能互相替代。

## 15. 接入验收清单

- [ ] Agent 能发现 OAuth 和 MCP 元数据。
- [ ] CIMD URL、域名允许列表和随机 loopback 回调验证通过。
- [ ] 用户能查看并批准 Scope。
- [ ] `tools/list` 只显示已授权工具。
- [ ] 只读工具返回当前授权用户的数据。
- [ ] 写工具第一阶段不改变数据库并返回 `status=input_required`。
- [ ] 第二阶段使用相同参数、幂等键和 `confirmation_id` 后只写入一次。
- [ ] 同键同参重试不重复写入，同键异参明确冲突。
- [ ] 确认过期、资源变化和用户拒绝均不会写入。
- [ ] Access Token 到期后 Refresh Token 正常轮换。
- [ ] 重用旧 Refresh Token 会撤销连接。
- [ ] 用户撤销连接后读取、写入和刷新全部失败。
- [ ] Agent 重启后可以从安全凭据存储恢复连接。

当前实现已使用 Codex Desktop/CLI 完成 OAuth、工具发现、分类、预算、交易写入及只读核验。其他 Agent 是否兼容，应按照本清单独立验收，不能仅以“支持 MCP”作为结论。
