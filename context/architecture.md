# 系统架构

## 整体分层
项目采用前后端分离架构，并在 v0.2 后形成“两套前端数据访问方式并存”的现状：

1. 前端展示层：`frontend/src/routes` 负责页面入口、权限守卫和标题元信息。
2. 前端功能层：`frontend/src/components` 和 `frontend/src/features/homefin` 负责页面交互、表单和业务 API 封装。
3. 前端数据访问层：
   - 模板遗留认证/用户接口继续使用 `frontend/src/client` 生成客户端。
   - 新增财务域接口当前通过 `frontend/src/features/homefin/api.ts` 的 Axios 封装访问。
4. API 层：`backend/app/api/routes` 按业务域组织接口，数据导入导出通过管理员专用 `data-jobs` 路由暴露。
5. 任务与文件处理层：`backend/app/data_jobs.py` 负责 Excel 模板生成、工作簿解析、后台任务执行、错误明细导出与结果文件落盘。
6. 领域与持久化层：`backend/app/models.py` 维护实体、枚举和 DTO，`crud.py` 保留用户等共享操作。
7. 数据层：PostgreSQL 持久化用户、分类、预算、交易、API Token、数据任务及遗留 Item 数据，Alembic 负责迁移。

## 模块划分与依赖
```
[React Routes] -> [Feature Components / Feature API]
[Feature API]  -> [Generated Client or Axios Wrapper]
[HTTP API]     -> [Deps / Security]
[HTTP API]     -> [Models]
[HTTP API]     -> [CRUD (shared user cases)]
[Models]       -> [PostgreSQL]

[Transactions] -> [Categories]
[Transactions] -> [Budgets]
[Dashboard]    -> [Transactions]
[Dashboard]    -> [Budgets]
[Data Jobs]    -> [Users]
[Data Jobs]    -> [Categories]
[Data Jobs]    -> [Budgets]
[Data Jobs]    -> [Transactions]
[Agent API]    -> [API Tokens]
[Agent API]    -> [Transactions]
[Data Jobs]    -> [Local File Storage]
```

## 依赖边界
- 认证统一通过 `backend/app/api/deps.py` 注入，优先读取 Session Cookie，其次读取 Bearer Token；两类 Token 使用独立类型声明并绑定用户 `auth_version`，当前前端主流程只使用 Bearer Token。
- 用户、分类、预算、交易、API Token 和 Dashboard 数据模型都集中在 `backend/app/models.py`。
- 数据导入导出任务由 `datajob` / `datajoberror` 持久化，结果文件和错误文件落到本地临时目录。
- 交易是财务域核心写模型，分类和预算都为交易提供约束与聚合基础；当前交易主语义字段为 `summary`，并通过 `detail` JSON 承载柔性详情和明细项。
- Dashboard 不直接写数据，只聚合分类、预算和交易结果。
- Data Jobs 不直接改变认证模型，只允许管理员发起，并通过后台任务方式按“分类 -> 预算 -> 交易”顺序写入财务数据。
- Agent Transaction API 不单独拥有交易实体，而是代理写入和读取 `transaction` 表。
- `/items` 与 `/admin` 保留兼容路由，但前端主导航已迁移到 `/transactions`、`/system/accounts` 与 `/system/data-management`。

## 关键架构决策
- Bearer Token 登录主路径保留：为减少认证层改动，前端继续使用 `localStorage.access_token + Authorization: Bearer ...`。
- Token 用途与版本隔离：Bearer、Cookie Session 和密码重置 Token 不能跨用途复用，密码变化后通过递增 `auth_version` 统一撤销旧 Token。
- `login_name` 成为主登录标识：后端登录入口按 `login_name` 鉴权，并在需要时兼容邮箱形式输入。
- MFA 以可选 TOTP 方式接入：当用户存在 `mfa_secret` 时，登录需要额外提供 6 位 `mfa_code`。
- 生成客户端与手写封装并存：旧模板接口继续走生成客户端，新财务域先落在手写封装，后续如统一生成链路可再收敛。
- 导入导出任务化：为避免大批量账单 Excel 导入导出阻塞请求，当前通过 FastAPI `BackgroundTasks` + 数据任务表 + 本地文件存储完成异步处理。
- Excel 作为唯一批量交换格式：系统统一以多页签 `.xlsx` 文件承载 `README / Categories / Budgets / Transactions`，其中 `Transactions` 当前使用 `summary / detail_note / detail_items` 作为主要可读交换字段。
- 兼容性优先：保留 `/users/signup`、`/login`、`/logout`、`/items`、`/admin` 等兼容入口，但不再作为主路径。

## 部署拓扑
- 本地开发仍以 Docker Compose 为主，后端测试可通过 `docker compose run --no-deps ...` 挂载本地 `backend/` 执行。
- 前端可在本地通过 Vite 独立运行，也可构建进 Compose 栈。
- 邮件链路和 PostgreSQL 仍由 Compose 环境提供。

## 非功能性约束
| 类型 | 要求 |
|------|------|
| 安全 | 受保护接口需登录；管理员接口以 `is_superuser` 控制；MFA 开启用户必须提供有效 6 位验证码；API Token 仅返回一次明文 |
| 一致性 | 新增财务域数据均按“API 使用元金额，数据库存分”约定处理 |
| 大数据处理 | 导入导出需按批次处理交易数据，避免一次性全量加载工作簿或整表数据 |
| 兼容性 | `/items`、`/admin` 和 `/users/signup` 暂时保留，避免旧链路直接失效 |
| 可维护性 | 当前文档必须同时反映“主路径”和“兼容路径”，避免误把遗留接口当成主实现 |
| 可测试性 | 后端已有认证与财务域回归测试；前端已通过构建与 lint 校验 |
