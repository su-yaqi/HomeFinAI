# 接口总览

> 本文件维护全局接口规范和接口目录，各接口详细定义见 `context/modules/*/api.md`

## 全局规范

### 基础约定
- Base URL：`/api/v1`
- 协议：本地开发默认为 HTTP，部署场景应使用 HTTPS
- 主认证方式：Bearer Token，Header 为 `Authorization: Bearer <token>`
- 主登录入口：`POST /api/v1/login/access-token`
- 兼容 Session 入口：`POST /api/v1/login`、`POST /api/v1/logout`
- Bearer、Cookie Session 与密码重置 Token 使用独立类型声明，并绑定用户认证版本。
- OpenAPI 文档：`/api/v1/openapi.json`

### 响应约定
- 单资源：如 `UserPublic`、`CategoryPublic`、`BudgetPublic`、`TransactionPublic`
- 集合资源：`{ data: [...], count: number }`
- 消息响应：`{ message: string }`
- Token 响应：`{ access_token: string, token_type: "bearer" }`
- API Token 创建响应：`{ token, secret, token_prefix }`
- Dashboard 响应：`{ summary, trends, category_shares, budget_usage }`
- 数据任务响应：`DataJobPublic` 或 `{ data: DataJobPublic[], count: number }`

### 错误约定
- 使用 FastAPI 默认错误格式：
```json
{
  "detail": "具体错误信息"
}
```
- 表单校验失败时，`detail` 可能为数组，前端统一展示首条错误。

### 权限约定
- 未登录：返回 401 或 403，前端统一清理 token 并跳转 `/login`
- 登录 token 指向已删除用户时：后端当前返回 `404 User not found`，前端同样视为登录失效并清理 token 后跳转 `/login`
- 登录 token 的类型不匹配或认证版本过期时：后端返回 401，前端清理 token 后跳转 `/login`
- 管理员接口：通过 `is_superuser` 控制
- 普通用户财务资源：仅可访问自己的分类、预算、交易和 Dashboard 聚合
- Agent 接口：通过 API Token 认证，不走普通用户 Bearer Token

### 分页约定
- 业务列表接口统一支持 `page` 与 `page_size` 查询参数。
- 默认 `page=1`、`page_size=10`。
- `page_size` 允许值为 `10 / 20 / 50 / 100 / 200`。
- 兼容保留的 `skip` / `limit` 仅用于遗留调用，不再作为前端主路径约定。

## 接口目录

### auth
> 详情见 `context/modules/auth/api.md`

| Method | Path | 描述 |
|--------|------|------|
| POST | /login/access-token | 使用 `login_name + password + 可选 mfa_code` 获取 Bearer Token |
| POST | /login | 创建兼容 Cookie Session |
| POST | /logout | 清理 Session Cookie |
| POST | /login/test-token | 校验当前登录态并返回当前用户 |
| POST | /password-recovery/{email} | 发起密码找回 |
| POST | /reset-password/ | 使用 token 重置密码 |
| POST | /password-recovery-html-content/{email} | 管理员查看密码找回邮件 HTML |
| POST | /users/signup | 兼容保留的公开注册接口 |

### users
> 详情见 `context/modules/users/api.md`

| Method | Path | 描述 |
|--------|------|------|
| GET | /users/ | 管理员分页读取账户列表 |
| GET | /users/handler-options | 读取交易经手人候选列表 |
| POST | /users/ | 管理员创建账户 |
| GET | /users/me | 获取当前登录用户 |
| PATCH | /users/me | 更新当前用户资料 |
| PATCH | /users/me/password | 修改当前用户密码 |
| POST | /users/me/mfa/setup | 生成当前用户 MFA 绑定信息 |
| POST | /users/me/mfa/enable | 校验验证码并启用当前用户 MFA |
| POST | /users/me/mfa/reset | 清除当前用户 MFA 绑定 |
| POST | /users/me/mfa/disable | 禁用当前用户 MFA |
| DELETE | /users/me | 普通用户删除自己的账号 |
| GET | /users/{user_id} | 获取指定用户详情 |
| PATCH | /users/{user_id} | 管理员更新账户 |
| DELETE | /users/{user_id} | 管理员删除账户 |
| POST | /users/{user_id}/reset-password | 管理员重置指定账户密码 |
| POST | /users/{user_id}/reset-mfa | 管理员重置指定账户 MFA Secret |

### categories
> 详情见 `context/modules/categories/api.md`

| Method | Path | 描述 |
|--------|------|------|
| GET | /categories/ | 分页读取当前用户分类列表 |
| POST | /categories/ | 创建分类 |
| PUT | /categories/{category_id} | 更新分类 |
| DELETE | /categories/{category_id} | 删除分类 |

### budgets
> 详情见 `context/modules/budgets/api.md`

| Method | Path | 描述 |
|--------|------|------|
| GET | /budgets/ | 分页读取预算列表及已使用金额 |
| POST | /budgets/ | 创建预算 |
| PUT | /budgets/{budget_id} | 更新预算 |
| DELETE | /budgets/{budget_id} | 删除预算 |

### transactions
> 详情见 `context/modules/transactions/api.md`

| Method | Path | 描述 |
|--------|------|------|
| GET | /transactions/ | 分页读取交易列表，支持筛选 |
| POST | /transactions/ | 创建交易 |
| GET | /transactions/{transaction_id} | 获取单笔交易 |
| PUT | /transactions/{transaction_id} | 更新交易 |
| DELETE | /transactions/{transaction_id} | 删除交易 |
| POST | /transactions/batch-enter | 批量标记为已入账 |

### dashboard
> 详情见 `context/modules/dashboard/api.md`

| Method | Path | 描述 |
|--------|------|------|
| GET | /dashboard/ | 返回财务首页聚合数据 |

### api-tokens
> 详情见 `context/modules/api-tokens/api.md`

| Method | Path | 描述 |
|--------|------|------|
| GET | /system/api-tokens/ | 管理员分页读取 API Token 列表 |
| POST | /system/api-tokens/ | 管理员创建 API Token |
| POST | /system/api-tokens/{token_id}/disable | 管理员禁用 API Token |
| DELETE | /system/api-tokens/{token_id} | 管理员彻底删除 API Token |

### data-jobs
> 详情见 `context/modules/data-jobs/api.md`

| Method | Path | 描述 |
|--------|------|------|
| GET | /system/data-jobs/ | 管理员分页读取最近导入导出任务 |
| POST | /system/data-jobs/export | 管理员创建导出任务 |
| POST | /system/data-jobs/import | 管理员上传 Excel 并创建导入任务 |
| GET | /system/data-jobs/template | 下载标准多页签 Excel 模板 |
| GET | /system/data-jobs/{job_id}/result | 下载导出结果文件 |
| GET | /system/data-jobs/{job_id}/errors | 下载导入错误明细文件 |

### agent-api
> 详情见 `context/modules/agent-api/api.md`

| Method | Path | 描述 |
|--------|------|------|
| GET | /agent/handler-options | Agent 读取可选经手人列表 |
| GET | /agent/transactions/ | Agent 分页读取所属交易列表（含 `summary` / `detail`） |
| POST | /agent/transactions/ | Agent 创建交易 |
| GET | /agent/transactions/{transaction_id} | Agent 获取单笔交易 |
| PUT | /agent/transactions/{transaction_id} | Agent 更新交易 |
| DELETE | /agent/transactions/{transaction_id} | Agent 删除交易 |
| GET | /agent/budgets/ | Agent 分页读取所属预算列表及已使用金额 |
| POST | /agent/budgets/ | Agent 创建预算 |
| PUT | /agent/budgets/{budget_id} | Agent 更新预算 |
| DELETE | /agent/budgets/{budget_id} | Agent 删除预算 |
| GET | /agent/categories/ | Agent 分页读取所属分类列表 |
| POST | /agent/categories/ | Agent 创建分类 |
| PUT | /agent/categories/{category_id} | Agent 更新分类 |
| DELETE | /agent/categories/{category_id} | Agent 删除分类 |

### items
> 详情见 `context/modules/items/api.md`

| Method | Path | 描述 |
|--------|------|------|
| GET | /items/ | 读取遗留 Item 列表 |
| POST | /items/ | 创建遗留 Item |
| GET | /items/{id} | 获取遗留 Item |
| PUT | /items/{id} | 更新遗留 Item |
| DELETE | /items/{id} | 删除遗留 Item |

### shared utilities
> 详情见 `context/modules/app-shell/api.md`

| Method | Path | 描述 |
|--------|------|------|
| GET | /utils/health-check/ | 健康检查 |
| POST | /utils/test-email/ | 管理员发送测试邮件 |
| POST | /private/users/ | 本地环境下快速创建测试用户 |
