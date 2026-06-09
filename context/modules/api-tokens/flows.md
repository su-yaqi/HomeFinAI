# api-tokens 业务流程

## 核心流程
1. 管理员进入 `/system/api-tokens`。
2. 页面按统一分页规则读取 Token 列表。
3. 管理员可创建新 Token，并选择是否生成 HMAC Secret。
4. 创建成功后，页面仅当次显示明文 Token 和 Secret。
5. 管理员可对启用中的 Token 执行禁用操作。
