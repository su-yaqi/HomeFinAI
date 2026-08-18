# ai-connector 业务流程

## 连接

1. MCP 客户端发现 Resource 与 Authorization Server 元数据。
2. HomeFin 从允许的 HTTPS CIMD `client_id` 读取客户端元数据，并校验 RFC 8252 loopback redirect。
3. 用户登录 HomeFin，查看客户端和 Scope 后决定一次性授权请求。
4. 客户端使用 PKCE 兑换短期 Access Token 与轮换 Refresh Token。

## 写入

1. 客户端只会发现连接 Scope 允许的工具。
2. 写工具读取实时资源并生成确定性预览和指纹。
3. 工具返回结构化 `status=input_required` 和预览；签名 `confirmation_id` 绑定请求、用户、连接、工具与资源指纹并在 5 分钟后过期，客户端确认后重试同一工具。
4. 重试时再次验证资源指纹；业务写入和 `aioperation` 在同一数据库事务提交。
5. 同键同参返回首次结果，同键异参返回冲突。

## 撤销

用户在 Settings 撤销连接后，Access Token 校验立即失败，Refresh Token 不能恢复连接。密码或认证版本变化也会使连接需要重新授权。
