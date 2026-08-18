# v0.13 PRD

## 版本说明
- 版本：v0.13
- 状态：开发中，待真实客户端验收
- 创建时间：2026-08-18

## 本版本目标
以标准 MCP / OAuth AI Connector 取代旧的“Agent REST API + 手工 API Token + Skill”接入方式，让用户可以把 HomeFin 安全连接到兼容的 AI 客户端，并通过语义化工具查询和维护自己的财务数据。

## 版本范围
- 提供符合 MCP `2026-07-28` 的 HTTP Connector，并以结构化工具作为唯一 AI 能力入口。
- 使用用户授权、细粒度 Scope、短期 Access Token 和可撤销连接替代管理员复制长期 API Token。
- 覆盖财务洞察、交易、预算与分类能力，保持旧 Agent API 的核心业务覆盖范围。
- 移除 `/api/v1/agent/*`、API Token/HMAC 管理功能和 `homefin-agent-api` Skill。
- HomeFin 不自动开放公网端口、不创建隧道；云端 AI 平台只能连接部署方正式提供且可达的 HTTPS MCP 地址。
- 明确兼容 Codex Desktop 的 CIMD + PKCE 注册方式、RFC 8252 随机 loopback 回调端口，以及 Mac 到 MCP 地址的 DNS、网络和 TLS 信任要求。

## 设计原则
- **单一 AI 入口**：发布后的 AI 能力只通过 MCP 暴露，不保留平行的 Agent REST API 或专用 Skill。
- **用户即主体**：所有读取和写入都绑定实际完成授权的 HomeFin 用户，不以管理员创建 Token 的身份代替用户。
- **最小权限**：读取、写入和删除使用明确 Scope；工具发现和调用都受 Scope 限制。
- **服务端安全兜底**：财务写操作由服务端执行确认、幂等和资源归属校验，不能只依赖客户端提示。
- **领域服务复用**：MCP 工具和 Web API 复用相同领域服务，不直接操作数据库，也不在 Connector 中复制业务规则。
- **不使用降级通道**：客户端不支持所需协议、OAuth 或确认能力时明确失败，不回退到长期 Token、无确认写入或旧 Agent API。

## 文件组织
| 文件 | 说明 |
|------|------|
| `ai-connection-management.md` | 用户授权、查看和撤销 AI 连接，并建立 MCP/OAuth 协议与权限基础 |
| `ai-financial-insights.md` | AI 以只读工具查询财务概览、交易、预算和分类 |
| `ai-transaction-management.md` | AI 在确认和幂等保护下创建、修改和删除交易 |
| `ai-budget-and-category-management.md` | AI 在确认和约束保护下维护预算与分类 |
| `legacy-ai-access-retirement.md` | 退役旧 Agent API、API Token/HMAC 和 HomeFin Agent Skill |

## 实施与发布顺序
1. 先完成 AI 连接、OAuth 和 MCP 协议基础。
2. 完成只读财务工具，并验证至少两个独立 MCP 客户端可以发现和调用工具。
3. 完成交易写工具及统一确认、幂等机制。
4. 完成预算与分类写工具。
5. 在前四项全部通过验收后移除旧链路，并以同一个 v0.13 发布包完成切换。

Codex Desktop 是 v0.13 必测客户端：必须使用计划发布时的实际桌面版本完成连接、授权、Token 轮换、`input_required`、重启重连和撤销失效测试，不能只依赖协议单元测试。

开发过程中允许旧代码在分支内短暂存在，但 v0.13 对外发布状态不得同时提供两套同定位 AI 接入能力。

## 当前实现状态（2026-08-18）

- 已完成官方 MCP SDK 接入、CIMD + PKCE OAuth、Scope 工具过滤、连接管理、Refresh Token 轮换与重复使用检测。
- 已完成 4 个只读工具、交易候选和 9 个交易/预算/分类写工具；写入使用可移植的结构化 `input_required`、5 分钟签名 `confirmation_id`、资源指纹和原子幂等事务，不依赖客户端反向 elicitation 通道。
- 已完成旧 Agent API、API Token 管理页、生成客户端入口和 `homefin-agent-api` Skill 退役，并加入部署前影响审计门禁；废弃表仍保留。
- 已通过协议级自动化、后端全量回归、前端 lint 与生产构建。
- 尚未完成计划发布版 Codex Desktop 的真实添加服务器、OAuth 回调、重启重连、确认拒绝/超时和撤销验收，因此 v0.13 不能标记为已发布完成。
