# 系统架构

## 整体分层
项目采用前后端分离架构，并以生成的 OpenAPI Client 作为唯一前端数据访问边界：

1. 前端展示层：`frontend/src/routes` 负责页面入口、权限守卫和标题元信息。
2. 前端功能层：`frontend/src/components` 和功能页面组件负责页面交互与表单。
3. 前端数据访问层：`frontend/src/client` 由后端 OpenAPI 契约统一生成，前端不维护第二套手写请求封装。
4. API 与协议层：`backend/app/api/routes` 按业务域组织 Web API；`backend/app/ai_connector` 提供 MCP 2026-07-28、OAuth/CIMD 和工具调用。
5. 任务与文件处理层：`backend/app/data_jobs.py` 负责 Excel 模板生成、工作簿解析、后台任务执行、错误明细导出与结果文件落盘。
6. 领域与持久化层：`backend/app/services` 复用分类、预算和交易用例，`models.py` 维护实体、枚举和 DTO，`crud.py` 保留用户共享操作。
7. 数据层：PostgreSQL 持久化用户、分类、预算、交易、AI 连接/OAuth 状态、幂等操作和数据任务；废弃 Token 表只保留历史记录，Alembic 负责迁移。

## 模块划分与依赖
```
[React Routes / Components] -> [Generated OpenAPI Client]
[HTTP API]     -> [Deps / Security]
[HTTP API]     -> [Domain Services]
[Domain Services] -> [Models]
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
[MCP Connector] -> [OAuth / AI Connections]
[MCP Tools]     -> [Domain Services]
[Data Jobs]    -> [Persistent Job File Volume]
```

## 依赖边界
- 认证统一通过 `backend/app/api/deps.py` 注入，优先读取 Session Cookie，其次读取 Bearer Token；两类 Token 使用独立类型声明并绑定用户 `auth_version`，当前前端主流程只使用 Bearer Token。
- 用户、分类、预算、交易、AI Connection 和 Dashboard 数据模型都集中在 `backend/app/models.py`。
- 数据导入导出任务由 `datajob` / `datajoberror` 持久化；Compose 运行时的源文件、结果文件和错误文件落到独立持久化任务卷，并按保留期限清理。
- 交易是财务域核心写模型，分类和预算都为交易提供约束与聚合基础；当前交易主语义字段为 `summary`，并通过 `detail` JSON 承载柔性详情和明细项。
- Dashboard 不直接写数据，只聚合分类、预算和交易结果。
- Data Jobs 不直接改变认证模型，只允许管理员发起，并通过后台任务方式按“分类 -> 预算 -> 交易”顺序写入财务数据。
- MCP 工具不单独拥有财务实体，与用户 API 复用相同领域服务；OAuth Access Token 固定解析为授权用户和连接，写工具在同一事务内提交领域变更与幂等记录。
- `/admin` 保留兼容路由，前端主导航使用 `/system/accounts` 与 `/system/data-management`。

## 关键架构决策
- Bearer Token 登录主路径保留：为减少认证层改动，前端继续使用 `localStorage.access_token + Authorization: Bearer ...`。
- Token 用途与版本隔离：Bearer、Cookie Session 和密码重置 Token 不能跨用途复用，密码变化后通过递增 `auth_version` 统一撤销旧 Token。
- AI 接入单轨化：外部 AI 只通过 MCP + OAuth/CIMD 接入，不保留 Agent REST API、长期 API Token 或等价 Skill。
- 服务端强制写确认：MCP 写工具先返回结构化 `input_required`，再校验加密且绑定用户、连接、工具、参数和资源指纹的短期 `confirmation_id`，并使用数据库幂等记录；不依赖服务器反向 elicitation。
- `login_name` 成为主登录标识：后端登录入口按 `login_name` 鉴权，并在需要时兼容邮箱形式输入。
- MFA 以可选 TOTP 方式接入：当用户存在 `mfa_secret` 时，登录需要额外提供 6 位 `mfa_code`。
- 单一 API 契约：前端全部接口通过 OpenAPI Client 生成，避免手写类型与后端 DTO 漂移。
- 导入导出任务化：为避免大批量账单 Excel 导入导出阻塞请求，当前通过 FastAPI `BackgroundTasks` + 数据任务表 + 受控任务文件目录完成异步处理；上传、归档展开、并发数、任务恢复和保留期限均有明确边界。
- Excel 作为唯一批量交换格式：系统统一以多页签 `.xlsx` 文件承载 `README / Categories / Budgets / Transactions`，其中 `Transactions` 当前使用 `summary / detail_note / detail_items` 作为主要可读交换字段。
- 兼容性边界：保留 `/users/signup`、`/login`、`/logout`、`/admin` 等兼容入口，但不再作为主路径。

## 部署拓扑
- 本地 Docker 开发通过根目录 `Makefile` 和 `scripts/dev.sh` 统一进入。Compose project
  固定为 `${DEV_PROJECT}-dev-${DEV_SLOT}`，每个 slot 从 `DEV_PORT_BASE` 起按 20
  个端口分块，避免多个 worktree 共用项目名、网络、卷或镜像标签。
- 启动前会核对同名项目的容器和保留卷 worktree 归属，并检测当前 slot 的宿主机
  入口端口。冲突时报告占用容器、卷、Compose service 或宿主机监听进程后失败，
  不自动停止其他项目。
- 默认开发栈仅向 `127.0.0.1` 暴露 Frontend 与 Backend；PostgreSQL 只保留 Compose
  内网访问。Adminer、Mailcatcher 宿主机端口和 Playwright UI 通过独立 profile
  按需启用。
- Backend 与 E2E 测试使用当前 slot 派生出的独立 Compose project，且不发布前后端
  宿主机端口；测试结束只清理对应测试项目的容器、网络和卷。
- 内网正式部署继续显式使用 `compose.yml + compose.intranet.yml`，保持 HTTP、
  Frontend `8080`、Backend `8000`、按需 Adminer `8081` 以及正式持久化和备份语义，
  不继承本地 slot 或开发 profile。
- 发布运行时额外加载 `compose.release.yml`，取消前后端的构建定义，只接受
  `sha256` digest 固定的 GHCR 镜像。前端镜像使用同源 `/api`，由容器内 Nginx
  转发到 Backend，因此 staging 与 production 晋级同一镜像，不写入环境专属 API
  地址。
- `main` 的单一 CI 门禁通过后，只有仓库变量 `STAGING_ENABLED=true` 时才构建本次
  不可变镜像并由 staging 消费对应 digest。变量未启用时镜像构建和 staging 部署明确
  跳过，不产生 staging 证据，也不允许后续 Production Release 晋级。
  Production Release 必须指向 `main` 提交，并找到同一 SHA 的完整成功 CI/staging
  运行、下载该运行保存的 digest 清单后才能进入 GitHub `production` Environment
  批准，不能在发布时重新解析可移动 tag。
- 发布脚本按“拉取不可变镜像 -> 启动并检查数据库 -> 宿主机预迁移备份 -> 单次迁移
  -> 应用切换 -> HTTP 健康检查”执行。迁移失败不切换应用；应用健康失败只回退上一组
  镜像，不自动降级数据库 schema。

## 非功能性约束
| 类型 | 要求 |
|------|------|
| 安全 | Web 受保护接口需登录；管理员接口以 `is_superuser` 控制；MFA 开启用户必须提供有效 6 位验证码；MCP 使用短期、受众绑定、可撤销的独立 OAuth Token |
| 一致性 | 新增财务域数据均按“API 使用元金额，数据库存分”约定处理 |
| 大数据处理 | 导入导出需按批次处理交易数据，避免一次性全量加载工作簿或整表数据 |
| 兼容性 | `/admin` 和 `/users/signup` 暂时保留，避免旧链路直接失效 |
| 可维护性 | Web API 与 MCP 工具必须复用领域服务，前端只使用生成客户端 |
| 可测试性 | 后端已有认证与财务域回归测试；前端已通过构建与 lint 校验 |
