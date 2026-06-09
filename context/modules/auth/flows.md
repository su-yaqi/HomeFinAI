# auth 业务流程

## 核心流程

### Bearer 登录流程
1. 用户在 `/login` 输入 `login_name`、密码和可选 `mfa_code`。
2. 前端调用 `POST /login/access-token`。
3. 后端校验登录名、密码和激活状态。
4. 若用户存在 `mfa_secret`，继续校验 6 位 `mfa_code`。
5. 成功后返回 JWT，前端写入 `localStorage.access_token`。
6. 前端跳转到 `/`。

### 密码找回流程
1. 用户在 `/recover-password` 输入邮箱。
2. 后端始终返回统一成功消息。
3. 若用户存在，则发送找回邮件。
4. 用户通过邮件链接进入 `/reset-password?token=...`。
5. 提交新密码后，后端校验 token 并更新密码。

## 业务规则
- 主登录标识是 `login_name`，不是邮箱。
- MFA 仅在用户已配置 `mfa_secret` 时强制要求。
- 当前前端不使用 Cookie Session 登录路径。
- 公开注册在前端已隐藏，但后端兼容接口保留。
