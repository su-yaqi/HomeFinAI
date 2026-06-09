# v0.6 PRD

## 版本说明
- 版本：v0.6
- 状态：已完成
- 创建时间：2026-06-02

## 本版本目标
补齐 HomeFin 在外部 Agent 接入和账户安全上的关键短板：让 API Token 更易用且可彻底删除，让 Agent 在录入账单前能查询可选经手人，并让用户与管理员都具备可落地的 MFA 管理能力。

## 文件组织
| 文件 | 说明 |
|------|------|
| `agent-token-management-hardening.md` | 管理员创建、禁用、删除 API Token，并确保新 Token 可直接用于 Agent 调用 |
| `agent-handler-options-for-transaction-entry.md` | Agent 查询可用 handler 候选列表，并在交易录入时可靠传入 `handler_user_id` |
| `mfa-self-service-and-admin-reset.md` | 用户自助启用和重置 MFA，管理员可对指定账户执行 MFA 重置 |
