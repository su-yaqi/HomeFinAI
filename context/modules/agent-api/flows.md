# agent-api 业务流程

## 核心流程
1. 外部 Agent 携带 API Token 调用 `/agent/handler-options`、`/agent/transactions`、`/agent/budgets` 或 `/agent/categories`。
2. 后端根据 Bearer Token 或 `X-API-Token` 查找 `apitoken`。
3. 若请求携带 HMAC 相关头，则进一步校验签名。
4. 鉴权成功后更新 `last_used_at`。
5. Agent 如需代他人录入，可先读取 `/agent/handler-options`，选择一个激活中的经手人用户 ID。
6. 创建或更新交易时，若未显式指定经手人，或显式传入 `null`，后端都会回退到 Token 所属用户。
7. 交易读写操作落到 `transaction` 表，并以 `summary + detail` 作为当前主语义字段，按统一规则返回经手人展示名。
8. 预算读写操作落到 `budget` 表；预算列表会额外聚合关联支出的 `used_amount`。
9. 分类读写操作落到 `category` 表；分类删除前仍需检查子分类和关联交易。
