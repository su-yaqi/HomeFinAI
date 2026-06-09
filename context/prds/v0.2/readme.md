# v0.2 PRD

## 版本说明
- **版本**：v0.2
- **状态**：已实现
- **创建时间**：2026-05-28
- **完成时间**：2026-05-29

## 本版本目标
将模板型全栈项目演进为 HomeFin 家庭记账系统，补齐认证安全、账目/预算/分类核心业务、首页看板、管理员能力与外部 Agent 交易接口。

## 实现备注
- 认证层最终选择保留 `access-token + bearer` 主路径，以减少现有链路改动。
- `authentication-and-session-hardening.md` 中关于 Cookie Session 的设计仅部分落地为兼容接口，未替代前端主登录模式。
- 实际交付结果以 `context/changelogs/v0.2.md` 和根级 `context/*.md` 为准。

## 文件组织
| 文件 | 说明 |
|------|------|
| `authentication-and-session-hardening.md` | 登录、MFA、Cookie Session、CSRF 与登出 |
| `category-management.md` | 分类树 CRUD 与颜色配置 |
| `budget-management.md` | 预算 CRUD 与已使用金额统计 |
| `transaction-management.md` | 账目 CRUD、筛选、分页与批量入账 |
| `financial-dashboard.md` | 首页收支、趋势、分类占比与预算使用看板 |
| `account-administration.md` | 管理员账户管理、密码重置与 MFA Secret 管理 |
| `agent-api-token-management.md` | 外部 Agent API Token 管理 |
| `agent-transaction-api.md` | 外部 Agent 交易与预算查询和 CRUD 接口 |
