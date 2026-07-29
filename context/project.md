# 项目概述

## 项目名称
HomeFin

## 背景
HomeFin 是一个从 FastAPI 全栈模板演进而来的家庭记账与财务管理系统。项目已经从“认证 + 用户管理 + Item 示例 CRUD”的模板基线，进入以账户、分类、预算、交易、财务看板和外部 Agent 接口为核心的业务化阶段。

## 目标
- 提供面向个人或家庭场景的基础记账能力，包括分类、预算、交易录入与财务概览。
- 提供管理员账户管理、密码重置、MFA Secret 重置与 API Token 管理能力。
- 提供系统级账单、预算、分类数据的 Excel 模板导入、备份导出与任务结果追踪能力。
- 保持 Bearer Token 登录主路径稳定，在尽量少改现有认证链路的前提下补齐 `login_name` 和可选 MFA。
- 通过 `context/` 文档持续描述当前实现状态，支持后续 v0.8+ 迭代。

## 技术栈
| 层次 | 技术选型 |
|------|--------|
| 后端 | Python + FastAPI + SQLModel + Pydantic v2 |
| 前端 | React 19 + TypeScript + Vite + TanStack Router + TanStack Query |
| 数据库 | PostgreSQL |
| 样式与组件 | Tailwind CSS v4 + Radix UI + 本地 `components/ui` |
| 测试 | Pytest + Playwright |
| 工具链 | uv + Bun + npm + Biome + Ruff + MyPy |
| 部署 | Docker Compose + GitHub Actions |

## 核心模块
| 模块 | 描述 |
|------|------|
| app-shell | 登录后应用框架、响应式导航、主题切换、全局错误跳转与统一列表分页约定 |
| auth | `login_name` 登录、Bearer 鉴权、可选 MFA、找回密码与兼容 Session API |
| users | 当前用户设置、管理员账户管理、密码重置、MFA Secret 重置与交易经手人候选读取 |
| categories | 用户自有分类树维护与颜色配置，支持可视化选色 |
| budgets | 用户预算维护、已使用金额聚合与统一分页浏览 |
| transactions | 用户交易 CRUD、分页筛选、当前页全选、批量入账状态更新与经手人用户关联 |
| dashboard | 财务首页概览、趋势、分类支出占比、预算使用情况 |
| api-tokens | 管理员 API Token 创建、禁用与一次性明文返回 |
| data-jobs | 管理员数据备份导出、Excel 模板下载、批量导入、结果文件下载与错误明细追踪 |
| agent-api | 外部 Agent 基于 Token 的交易、预算、分类查询和 CRUD |
| items | 模板遗留模块，后端 API 仍保留，前端主路径已迁移到交易模块 |
| shared-infra | OpenAPI Client、邮件模板、迁移、测试与 CI 支撑 |

## 版本状态
| 版本 | 状态 | 说明 |
|------|------|------|
| v0.1 | 已完成 | 模板基线版本，包含认证、用户管理、Item 管理和基础工程能力 |
| v0.2 | 已完成 | 完成 HomeFin 业务化改造，补齐账户、分类、预算、交易、Dashboard、API Token 和 Agent API |
| v0.3 | 已完成 | 统一业务列表分页、优化分类颜色输入、增强交易列表体验，并将交易经手人切换为用户 ID 关联 |
| v0.4 | 已完成 | 新增系统管理中的数据导入导出能力，支持多页签 Excel 模板、后台数据任务、结果文件与错误明细下载 |
| v0.5 | 已完成 | 交易模型升级为摘要 `summary` + 柔性详情 `detail`，并同步更新交易页、Agent API 与 Excel 模板导入导出 |
| v0.6 | 已完成 | 补齐用户 MFA 自助管理、管理员 MFA 重置、Agent handler 候选查询，以及 API Token 删除与更稳健的 Agent 调用链路 |
| v0.7 | 已完成 | 完成全站移动端响应式改造，为财务与管理列表提供移动卡片视图，并建立 Chrome、Safari 和桌面端响应式回归基线 |
| v0.8 | 已完成 | 增加 Token 用途与版本隔离、Agent HMAC 防重放、分类数据库约束、账户关联完整性、数据任务资源边界和看板业务时区 |
| v0.9 | 已完成 | 建立确定性的本地多实例 Compose 项目与端口契约、冲突门禁、按需工具 profile、隔离测试栈及统一 Make 入口 |
| v0.10 | 已完成 | 建立 S/M/H 风险分级、context impact、完成定义、PR 证据模板和本地规则检查入口 |
