# app-shell 业务流程

## 核心流程

### 受保护页面初始化
1. 用户进入 `/_layout` 下任意页面。
2. 路由守卫先检查本地是否存在 `access_token`。
3. 若无 token，前端立即重定向到 `/login`。
4. 若有 token，页面继续加载，并通过 `/users/me` 获取当前用户。
5. 若任意后续请求返回 401/403，或 `/users/me` 等鉴权相关请求返回 `404 User not found`，全局错误处理清理 token 并回到登录页。

### 导航生成
1. 当前用户信息加载完成后，侧边栏根据 `is_superuser` 生成导航项。
2. 普通用户看到 `Dashboard / Transactions / Budgets / Categories`。
3. 管理员额外看到 `Accounts / API Tokens / Data Management`。

### 主题切换
1. 用户点击主题切换入口。
2. 在 Light / Dark / System 中选择主题。
3. 选择结果写入本地存储。
4. `ThemeProvider` 更新根节点样式状态。

## 业务规则
- `admin` 仅为兼容路径，不属于主导航。
- 路由守卫只基于 Bearer Token 登录态判断，不依赖 Cookie Session。
- 主题模式刷新后必须保持一致。
- 所有业务列表页都遵守统一分页规范：默认每页 10 条，可切换 `10 / 20 / 50 / 100 / 200`。
