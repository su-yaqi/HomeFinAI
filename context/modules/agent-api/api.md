# agent-api 接口详情

## 接口列表
| Method | Path | 描述 |
|--------|------|------|
| GET | /api/v1/agent/handler-options | 读取可选经手人列表 |
| GET | /api/v1/agent/transactions/ | 分页读取 Token 所属账户的交易列表 |
| POST | /api/v1/agent/transactions/ | 创建交易 |
| GET | /api/v1/agent/transactions/{transaction_id} | 获取单笔交易 |
| PUT | /api/v1/agent/transactions/{transaction_id} | 更新交易 |
| DELETE | /api/v1/agent/transactions/{transaction_id} | 删除交易 |
| GET | /api/v1/agent/budgets/ | 分页读取 Token 所属账户的预算列表与已使用金额 |
| POST | /api/v1/agent/budgets/ | 创建预算 |
| PUT | /api/v1/agent/budgets/{budget_id} | 更新预算 |
| DELETE | /api/v1/agent/budgets/{budget_id} | 删除预算 |
| GET | /api/v1/agent/categories/ | 分页读取 Token 所属账户的分类列表 |
| POST | /api/v1/agent/categories/ | 创建分类 |
| PUT | /api/v1/agent/categories/{category_id} | 更新分类 |
| DELETE | /api/v1/agent/categories/{category_id} | 删除分类 |

## 认证方式
- `Authorization: Bearer <plain_token>`
- 或 `X-API-Token: <plain_token>`
- Token 创建时若生成 HMAC Secret，后续每次请求都必须携带
  `X-API-Secret`、Unix 秒级 `X-Timestamp`、随机 `X-Nonce`、`X-Signature`；
  时间戳仅允许与服务端相差 5 分钟，Nonce 不得重复使用

## 业务规则
- Token 无效、禁用或过期时返回 401。
- `GET /agent/handler-options` 返回当前可用用户列表，供 Agent 在录入交易前选择经手人。
- 交易归属按 `ApiToken.created_by` 绑定到创建该 Token 的管理员账号。
- 预算归属同样按 `ApiToken.created_by` 绑定到创建该 Token 的管理员账号。
- 分类归属同样按 `ApiToken.created_by` 绑定到创建该 Token 的管理员账号。
- Agent API 的金额单位统一为元。
- Agent 交易接口支持 `page` / `page_size`，并返回 `summary`、`detail`、`handler_user_id` 与 `handler_display_name`。
- Agent 交易写接口当前以 `summary` / `detail` 为主字段，并继续兼容旧 `description` 作为摘要别名。
- Agent 交易写接口若显式提交 `handler_user_id: null`，会回退为当前 Token 所属用户。
- Agent 交易中的 `detail` 必须为对象；若包含 `items`，每条明细至少要有非空 `name`。
- Agent 预算接口支持 `page` / `page_size`，并返回 `used_amount` 聚合结果。
- Agent 分类接口支持 `page` / `page_size`，并复用普通分类接口的颜色、父分类与删除前约束规则。
- 当前 Agent API 仍不提供预算详情接口。
- 当前 Agent API 仍不提供分类详情接口。
