# ai-connector 页面详情

| 页面 | 路由 | 权限 |
|------|------|------|
| OAuth 授权确认 | `/connect/authorize` | 已登录用户 |
| AI Connections | `/settings` 的 AI Connections 页签 | 已登录用户 |

- 授权页只展示服务端签名请求中的客户端、回调地址和 Scope，不允许前端覆盖。
- 连接列表展示客户端、Scope、状态和时间，不展示 Access/Refresh Token。
- 撤销只作用于当前用户连接。
- MCP 写入确认由兼容客户端承载，HomeFin 服务端仍强制确认，不依赖客户端自律。
