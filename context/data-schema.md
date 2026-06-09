# 数据模型

> v0.5 后，项目的数据核心已经从 `user + item` 扩展到 `user + category + budget + transaction + apitoken + datajob + datajoberror`，其中 `item` 仍作为模板兼容表保留；`transaction` 额外通过 `handler_user_id` 关联经手人用户，并使用 `summary + detail` 承载账单摘要和柔性详情；`datajob` / `datajoberror` 承载系统级导入导出任务。

## 命名规范
- 表名：由 SQLModel 根据类名推导，当前实际为 `user`、`item`、`category`、`budget`、`transaction`、`apitoken`、`datajob`、`datajoberror`
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
User 1 ──── N Item
User 1 ──── N Category
User 1 ──── N Budget
User 1 ──── N Transaction(owner_id)
User 1 ──── N Transaction(handler_user_id)
User 1 ──── N ApiToken
User 1 ──── N DataJob

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
| is_active | boolean | 否 | `true` | 是否可用 |
| is_superuser | boolean | 否 | `false` | 是否管理员 |
| full_name | varchar(255) | 是 | `null` | 展示名 |
| created_at | timestamptz | 是 | 当前 UTC 时间 | 创建时间 |

**索引**
| 字段 | 说明 |
|------|------|
| email | 唯一索引 |
| login_name | 唯一索引 |

### item
模板遗留示例表，当前不再作为主业务对象。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | 否 | `uuid4()` | 主键 |
| title | varchar(255) | 否 | - | 标题 |
| description | varchar(255) | 是 | `null` | 描述 |
| created_at | timestamptz | 是 | 当前 UTC 时间 | 创建时间 |
| owner_id | UUID | 否 | - | 归属用户 |

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
管理员创建的外部 Agent 调用凭证表。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | 否 | `uuid4()` | 主键 |
| name | varchar(100) | 否 | - | Token 名称 |
| expires_at | timestamptz | 是 | `null` | 过期时间 |
| token_prefix | varchar(20) | 否 | - | 明文 Token 前缀，用于识别 |
| token_hash | varchar(255) | 否 | - | 明文 Token 哈希 |
| secret_hash | varchar(255) | 是 | `null` | HMAC Secret 哈希 |
| is_active | boolean | 否 | `true` | 是否启用 |
| created_by | UUID | 否 | - | 创建人 |
| last_used_at | timestamptz | 是 | `null` | 最后一次成功使用时间 |
| created_at | timestamptz | 是 | 当前 UTC 时间 | 创建时间 |

### datajob
系统级数据导入导出任务表。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | UUID | 否 | `uuid4()` | 主键 |
| job_type | varchar(20) | 否 | - | 任务类型，当前为 `EXPORT` 或 `IMPORT` |
| status | varchar(30) | 否 | `PENDING` | 任务状态，支持 `PENDING / PROCESSING / SUCCEEDED / PARTIAL_SUCCESS / FAILED / CANCELLED` |
| template_version | varchar(20) | 否 | `v2` | Excel 模板或导出格式版本 |
| created_by | UUID | 否 | - | 发起任务的管理员用户 |
| source_file_path | varchar(500) | 是 | `null` | 导入源文件落盘路径 |
| result_file_path | varchar(500) | 是 | `null` | 导出结果文件路径 |
| error_file_path | varchar(500) | 是 | `null` | 导入错误明细文件路径 |
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
- API Token：`ApiTokenCreate`、`ApiTokenPublic`、`ApiTokenSecretPublic`
- 数据任务：`DataJobPublic`、`DataJobsPublic`

## DTO 补充说明
- `TransactionCreate` 与 `TransactionUpdate` 现支持 `handler_user_id`。
- `TransactionCreate` 与 `TransactionUpdate` 当前以 `summary` / `detail` 为主字段，并继续兼容接收旧 `description` 作为摘要别名。
- `TransactionPublic` 当前返回 `summary`、`detail`、`description`、`handler_user_id` 和 `handler_display_name`；其中 `description` 为兼容回写字段，默认与 `summary` 对齐。
- `HandlerUsersPublic` 供交易表单与筛选器读取经手人候选列表，返回值同样遵循统一分页结构。
- `DataJobPublic` 现返回 `has_result_file` 与 `has_error_file`，供前端决定是否展示下载入口；当前 Excel 模板版本为 `v2`。
