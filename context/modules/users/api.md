# users 接口详情

## 接口列表
| Method | Path | 描述 |
|--------|------|------|
| GET | /api/v1/users/ | 管理员分页读取账户列表 |
| GET | /api/v1/users/handler-options | 读取交易经手人候选列表 |
| POST | /api/v1/users/ | 管理员创建账户 |
| GET | /api/v1/users/me | 获取当前用户 |
| PATCH | /api/v1/users/me | 更新当前用户资料 |
| PATCH | /api/v1/users/me/password | 修改当前用户密码 |
| POST | /api/v1/users/me/mfa/setup | 获取当前用户 MFA 初始化 secret 与 otpauth URI |
| POST | /api/v1/users/me/mfa/enable | 校验验证码并启用当前用户 MFA |
| POST | /api/v1/users/me/mfa/reset | 重置当前用户 MFA |
| POST | /api/v1/users/me/mfa/disable | 禁用当前用户 MFA |
| DELETE | /api/v1/users/me | 删除当前用户账号 |
| GET | /api/v1/users/{user_id} | 获取指定用户 |
| PATCH | /api/v1/users/{user_id} | 管理员更新账户 |
| DELETE | /api/v1/users/{user_id} | 管理员删除账户 |
| POST | /api/v1/users/{user_id}/reset-password | 管理员重置密码 |
| POST | /api/v1/users/{user_id}/reset-mfa | 管理员重置 MFA Secret |

## 关键字段
- `UserPublic` 当前包含 `login_name` 和 `has_mfa`
- 当前用户资料可维护 `login_name`、`email`、`full_name`
- `HandlerUserOption` 提供 `id`、`full_name`、`login_name` 与回退后的 `display_name`
- `MFASetupPublic` 提供 `secret` 与 `otpauth_uri`

## 业务规则
- `email` 和 `login_name` 都要求唯一。
- 管理员不能删除自己。
- 管理员可直接重置任意账户密码。
- 当前用户修改密码或管理员重置密码时会递增 `auth_version`，使该账户已有 Bearer、Session 和密码重置 Token 失效。
- 当前用户启用 MFA 时必须提交当前 6 位验证码。
- 当前用户和管理员的 MFA reset 都采用清空 `mfa_secret`。
- 管理员可直接为任意账户执行 MFA 重置。
- 账户列表与经手人候选列表都遵守统一分页参数 `page` / `page_size`。
- 删除账户时，其创建的 API Token 及 HMAC Nonce 会按外键级联删除。
