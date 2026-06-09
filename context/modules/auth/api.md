# auth 接口详情

## 接口列表
| Method | Path | 描述 |
|--------|------|------|
| POST | /api/v1/login/access-token | Bearer 登录入口 |
| POST | /api/v1/login | 兼容 Cookie Session 登录 |
| POST | /api/v1/logout | 清理 Session Cookie |
| POST | /api/v1/login/test-token | 返回当前登录用户 |
| POST | /api/v1/password-recovery/{email} | 发起密码找回 |
| POST | /api/v1/reset-password/ | 重置密码 |
| POST | /api/v1/password-recovery-html-content/{email} | 管理员查看找回密码邮件 HTML |
| POST | /api/v1/users/signup | 兼容保留的公开注册接口 |

## 接口详情

### Bearer 登录
- **Method**：POST
- **Path**：`/api/v1/login/access-token`
- **描述**：使用 `login_name` 和密码登录；当用户配置了 `mfa_secret` 时，需同时提交 `mfa_code`
- **权限**：匿名可访问

**请求体**：`application/x-www-form-urlencoded`
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 登录名；后端按 `login_name` 处理 |
| password | string | 是 | 明文密码 |
| mfa_code | string | 否 | 6 位 MFA 验证码 |

**业务错误**
| HTTP 状态码 | detail |
|------------|--------|
| 400 | Incorrect login name or password |
| 400 | Invalid MFA code |
| 400 | Inactive user |

### Cookie Session 登录
- **Method**：POST
- **Path**：`/api/v1/login`
- **描述**：兼容性 Session 登录接口，成功后写入 Session Cookie 与 CSRF Cookie
- **权限**：匿名可访问

### 登出
- **Method**：POST
- **Path**：`/api/v1/logout`
- **描述**：清理 Session Cookie

### Token 校验
- **Method**：POST
- **Path**：`/api/v1/login/test-token`
- **描述**：返回当前 Bearer Token 或 Session 对应的用户

### 密码找回
- **Method**：POST
- **Path**：`/api/v1/password-recovery/{email}`
- **描述**：统一返回成功消息，避免邮箱枚举

### 重置密码
- **Method**：POST
- **Path**：`/api/v1/reset-password/`
- **描述**：使用找回邮件中的 token 设置新密码

### 兼容注册
- **Method**：POST
- **Path**：`/api/v1/users/signup`
- **描述**：后端兼容保留；前端已不再暴露公开注册入口
