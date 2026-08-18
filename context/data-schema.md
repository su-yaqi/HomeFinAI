# 数据模型

> v0.13 当前数据核心为 `user + category + budget + transaction + aiconnection + OAuth 状态表 + aioperation + datajob + datajoberror`。`apitoken + apitokennonce` 仅作为废弃历史表保留，运行时不再使用。

## 命名规范
- 表名：由 SQLModel 根据类名推导；AI Connector 使用 `aiconnection`、`aiauthorizationdecision`、`aiauthorizationcode`、`airefreshtoken` 与 `aioperation`。
- 字段名：Python 侧统一使用 snake_case
- 主键：统一使用 UUID
- 时间：统一使用 UTC 时间，`created_at` / `last_used_at` 为 timezone-aware datetime
- 金额：API 层使用元，数据库层统一以整数分存储

## 公共字段约定
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| created_at | timestamptz | 创建时间，默认当前 UTC |

> 当前仍未统一抽出 `updated_at` 或软删除字段。

## 实体关系概览
```
User 1 ──── N Category
User 1 ──── N Budget
User 1 ──── N Transaction(owner_id)
User 1 ──── N Transaction(handler_user_id)
User 1 ──── N ApiToken
User 1 ──── N AIConnection
User 1 ──── N DataJob
ApiToken 1 ──── N ApiTokenNonce
AIConnection 1 ──── N AIAuthorizationCode
AIConnection 1 ──── N AIRefreshToken
AIConnection 1 ──── N AIOperation

Category 1 ──── N Transaction
Budget   1 ──── N Transaction
Category 1 ──── N Category   (parent_id 自关联)
DataJob  1 ──── N DataJobError
```

## 表结构

### user
用户主表，承载登录、权限、展示信息与 MFA 状态。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | 否 | `uuid4()` | 主键 |
| email | varchar(255) | 否 | - | 唯一邮箱 |
| login_name | varchar(100) | 否 | - | 唯一登录名，当前主登录标识 |
| hashed_password | varchar | 否 | - | 密码哈希 |
| mfa_secret | varchar(255) | 是 | `null` | TOTP Secret，存在时登录需 MFA |
| auth_version | integer | 否 | `0` | 认证版本；密码变化时递增并撤销旧登录态和重置 Token |
| is_active | boolean | 否 | `true` | 是否可用 |
| is_superuser | boolean | 否 | `false` | 是否管理员 |
| full_name | varchar(255) | 是 | `null` | 展示名 |
| created_at | timestamptz | 是 | 当前 UTC 时间 | 创建时间 |

**索引**
| 字段 | 说明 |
|------|------|
| email | 唯一索引 |
| login_name | 唯一索引 |

### category
用户自有分类表，支持一层或多层父子关系。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | 否 | `uuid4()` | 主键 |
| name | varchar(100) | 否 | - | 分类名称，按用户维度唯一 |
| parent_id | UUID | 是 | `null` | 父分类，指向 `category.id` |
| color | varchar(20) | 否 | - | 分类颜色，要求 `#RGB` 或 `#RRGGBB` |
| owner_id | UUID | 否 | - | 归属用户 |
| created_at | timestamptz | 是 | 当前 UTC 时间 | 创建时间 |

**约束**
- `(owner_id, name)` 使用数据库唯一约束，防止并发创建同名分类。
- `color` 使用 PostgreSQL Check Constraint 限制为 `#RGB` 或 `#RRGGBB`。
- 应用层沿父分类链检查并拒绝自引用或多层级环。

### budget
用户预算表。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | 否 | `uuid4()` | 主键 |
| name | varchar(100) | 否 | - | 预算名称 |
| year | integer | 否 | - | 预算年份 |
| period | smallint | 否 | - | 周期枚举，`1=MONTH`、`2=QUARTER`、`3=YEAR` |
| amount_cents | integer | 否 | - | 预算金额，单位分 |
| owner_id | UUID | 否 | - | 归属用户 |
| created_at | timestamptz | 是 | 当前 UTC 时间 | 创建时间 |

### transaction
核心交易表，记录收入/支出。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | 否 | `uuid4()` | 主键 |
| category_id | UUID | 否 | - | 分类 |
| transaction_type | smallint | 否 | - | 类型枚举，`1=INCOME`、`2=EXPENSE` |
| budget_id | UUID | 是 | `null` | 关联预算 |
| summary | varchar(255) | 是 | `null` | 交易摘要，当前主展示和主交换字段 |
| description | varchar(255) | 是 | `null` | [废弃] 旧描述字段，当前兼容映射到 `summary` |
| detail | jsonb | 是 | `null` | 柔性详情对象，支持补充说明和明细项列表 |
| entry_status | smallint | 否 | - | 入账状态，`1=PENDING`、`2=SKIPPED`、`3=ENTERED` |
| handler_name | varchar(100) | 是 | `null` | 遗留纯文本经手人字段，兼容历史数据与展示回退 |
| handler_user_id | UUID | 是 | `null` | 经手人用户，关联 `user.id`，当前默认回填为当前登录用户 |
| transaction_date | date | 否 | - | 交易日期 |
| amount_cents | integer | 否 | - | 金额，单位分 |
| owner_id | UUID | 否 | - | 归属用户 |
| created_at | timestamptz | 是 | 当前 UTC 时间 | 创建时间 |

### apitoken
[废弃] 旧外部 Agent 调用凭证表。v0.13 迁移统一停用，应用没有创建、认证或管理入口，仅供升级影响审计和历史定位。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | 否 | `uuid4()` | 主键 |
| name | varchar(100) | 否 | - | Token 名称 |
| expires_at | timestamptz | 是 | `null` | 过期时间 |
| token_prefix | varchar(20) | 否 | - | 明文 Token 前缀，用于识别 |
| token_hash | varchar(255) | 否 | - | 明文 Token 哈希 |
| secret_hash | varchar(255) | 是 | `null` | HMAC Secret 哈希 |
| is_active | boolean | 否 | `true` | 是否启用 |
| created_by | UUID | 否 | - | 创建人；用户删除时 Token 级联删除 |
| last_used_at | timestamptz | 是 | `null` | 最后一次成功使用时间 |
| created_at | timestamptz | 是 | 当前 UTC 时间 | 创建时间 |

### apitokennonce
[废弃] 旧 Agent HMAC 防重放表。v0.13 不再新增记录，后续物理清理需独立迁移和备份确认。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | 否 | `uuid4()` | 主键 |
| token_id | UUID | 否 | - | 关联 `apitoken.id`，Token 删除时级联删除 |
| nonce | varchar(128) | 否 | - | 单次请求随机值，与 `token_id` 组成唯一约束 |
| created_at | timestamptz | 否 | 当前 UTC 时间 | 接受请求的时间，用于清理过期 Nonce |

### aiconnection 与 OAuth 状态表
`aiconnection` 记录用户授权的客户端、Scope、状态、认证版本和最后使用时间；`aiauthorizationdecision` 使每个授权请求只能决定一次；`aiauthorizationcode` 保存一次性授权码哈希与 PKCE challenge；`airefreshtoken` 保存轮换 Token 哈希、family、替代关系、使用和撤销时间。所有凭证只保存哈希，不保存可复用明文。

### aioperation
AI 写工具的原子幂等记录表。

| 字段 | 类型 | 可空 | 说明 |
|------|------|------|------|
| id | UUID | 否 | 主键 |
| connection_id | UUID | 否 | 关联 AI Connection |
| tool_name | varchar(100) | 否 | MCP 工具名 |
| idempotency_key | varchar(100) | 否 | 客户端幂等键，与连接、工具组成唯一约束 |
| request_hash | varchar(255) | 否 | 规范化请求哈希 |
| resource_type | varchar(50) | 否 | transaction / budget / category |
| resource_id | UUID | 是 | 业务资源 ID |
| result_payload | jsonb | 否 | 安全重放所需结果摘要 |
| expires_at | timestamptz | 否 | 至少 30 天保留截止时间 |
| created_at | timestamptz | 否 | 创建时间 |

### datajob
系统级数据导入导出任务表。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | 否 | `uuid4()` | 主键 |
| job_type | varchar(20) | 否 | - | 任务类型，当前为 `EXPORT` 或 `IMPORT` |
| status | varchar(30) | 否 | `PENDING` | 任务状态，支持 `PENDING / PROCESSING / SUCCEEDED / PARTIAL_SUCCESS / FAILED / CANCELLED` |
| template_version | varchar(20) | 否 | `v2` | Excel 模板或导出格式版本 |
| created_by | UUID | 否 | - | 发起任务的管理员用户 |
| source_file_path | varchar(500) | 是 | `null` | 导入源文件在受控任务目录中的落盘路径 |
| result_file_path | varchar(500) | 是 | `null` | 导出结果在受控任务目录中的文件路径 |
| error_file_path | varchar(500) | 是 | `null` | 导入错误明细在受控任务目录中的文件路径 |
| total_rows | integer | 否 | `0` | 任务识别到的总数据行数 |
| success_rows | integer | 否 | `0` | 成功处理行数 |
| failed_rows | integer | 否 | `0` | 失败处理行数 |
| skipped_rows | integer | 否 | `0` | 跳过行数 |
| progress_percent | integer | 否 | `0` | 粗粒度进度百分比 |
| failure_reason | varchar(500) | 是 | `null` | 文件级失败原因摘要 |
| started_at | timestamptz | 是 | `null` | 开始处理时间 |
| finished_at | timestamptz | 是 | `null` | 结束处理时间 |
| created_at | timestamptz | 是 | 当前 UTC 时间 | 创建时间 |

### datajoberror
数据导入任务中的行级错误明细表。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | 否 | `uuid4()` | 主键 |
| job_id | UUID | 否 | - | 关联 `datajob.id` |
| sheet_name | varchar(100) | 否 | - | 出错页签名 |
| row_number | integer | 否 | - | Excel 行号 |
| field_name | varchar(100) | 否 | - | 出错字段 |
| error_message | varchar(500) | 否 | - | 用户可读错误原因 |
| raw_key | varchar(255) | 是 | `null` | 原始业务定位键，例如分类名或交易摘要 |
| created_at | timestamptz | 是 | 当前 UTC 时间 | 创建时间 |

## 主要 DTO / 非表结构模型
- 用户：`UserCreate`、`UserRegister`、`UserUpdate`、`UserUpdateMe`、`UserPublic`
- 认证：`LoginRequest`、`Token`、`TokenPayload`、`UpdatePassword`、`NewPassword`
- 分类：`CategoryCreate`、`CategoryUpdate`、`CategoryPublic`
- 预算：`BudgetCreate`、`BudgetUpdate`、`BudgetPublic`
- 交易：`TransactionCreate`、`TransactionUpdate`、`TransactionPublic`、`TransactionBatchEnter`
- 经手人候选：`HandlerUserOption`、`HandlerUsersPublic`
- 看板：`DashboardSummary`、`DashboardTrendPoint`、`DashboardCategoryShare`、`DashboardBudgetUsage`、`DashboardPublic`
- AI Connector：`AIConnectionPublic`、`AIConnectionsPublic` 以及 MCP 工具输入/确认模型
- 数据任务：`DataJobPublic`、`DataJobsPublic`

## DTO 补充说明
- `TransactionCreate` 与 `TransactionUpdate` 现支持 `handler_user_id`。
- `TransactionCreate` 与 `TransactionUpdate` 当前以 `summary` / `detail` 为主字段，并继续兼容接收旧 `description` 作为摘要别名。
- `TransactionPublic` 当前返回 `summary`、`detail`、`description`、`handler_user_id` 和 `handler_display_name`；其中 `description` 为兼容回写字段，默认与 `summary` 对齐。
- `HandlerUsersPublic` 供交易表单与筛选器读取经手人候选列表，返回值同样遵循统一分页结构。
- `DataJobPublic` 现返回 `has_result_file` 与 `has_error_file`，供前端决定是否展示下载入口；当前 Excel 模板版本为 `v2`。
- Compose 运行时将数据任务目录挂载为独立持久化卷；任务记录及关联文件默认保留 30 天。
