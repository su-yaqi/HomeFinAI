# 前端总览

> 本文件维护全局设计规范、页面树和导航结构，各页面详细定义见 `context/modules/*/ui.md`

## 设计规范
- 组件库：Radix UI primitives + 本地 `components/ui` 封装
- 样式系统：Tailwind CSS v4 + CSS 变量主题 token
- 视觉风格：后台工作台风格，以卡片式财务概览和表格式管理页为主
- 布局：未登录页使用认证布局；已登录页在桌面端使用左侧侧边栏 + 顶部栏 + 内容区，在移动端使用顶部菜单触发器 + 抽屉侧边栏 + 单列内容区
- 响应式：支持 320px 及以上视口；移动端优先使用卡片列表、折叠筛选、纵向操作区和紧凑分页，桌面端保留表格与原有信息密度
- 触控：移动端主要按钮、菜单触发器和分页按钮按不小于 44px 的触控区域设计
- 内容安全：长 Token、Secret、邮箱、金额与任务错误信息允许换行，不得造成页面级横向滚动
- 主题：支持 Light / Dark / System 三种模式，并持久化到本地存储
- 列表分页：所有业务列表页默认启用分页，默认每页 10 条；用户可切换 `10 / 20 / 50 / 100 / 200` 条每页；分页器需展示当前页、总条数、页码跳转能力，并在筛选条件变更后回到第 1 页

## 页面树
```
/                              # 财务 Dashboard（需登录）
├── /login                     # 登录页
├── /signup                    # 兼容路由，当前直接跳转 /login
├── /recover-password          # 找回密码页
├── /reset-password?token=...  # 重置密码页
├── /transactions              # 交易管理页
├── /budgets                   # 预算管理页
├── /system/categories         # 分类管理页
├── /system/accounts           # 账户管理页（管理员）
├── /system/api-tokens         # API Token 管理页（管理员）
├── /system/data-management    # 数据导入导出页（管理员）
├── /settings                  # 用户设置页
├── /items                     # 兼容路由，当前跳转 /transactions
└── /admin                     # 兼容路由，当前跳转 /system/accounts
```

## 导航结构
| 导航项 | 路径 | 权限 |
|--------|------|------|
| Dashboard | / | 所有已登录用户 |
| Transactions | /transactions | 所有已登录用户 |
| Budgets | /budgets | 所有已登录用户 |
| Categories | /system/categories | 所有已登录用户 |
| Accounts | /system/accounts | 管理员 |
| API Tokens | /system/api-tokens | 管理员 |
| Data Management | /system/data-management | 管理员 |
| Settings | /settings | 所有已登录用户 |

## 公共组件
| 组件名 | 用途 |
|--------|------|
| `AuthLayout` | 登录、找回密码、重置密码等未登录页面的统一布局 |
| `AppSidebar` | 已登录区域导航、主题切换与用户菜单 |
| `PageHeader` | 页面标题、说明与主要操作的响应式排列 |
| `DataTable` | 桌面表格与移动卡片列表的统一数据容器 |
| `TablePagination` | 桌面完整页码与移动端紧凑翻页、每页条数和总数展示 |
| `Dialog` 相关封装 | CRUD 对话框基础交互，移动端限制在动态视口内并允许内容滚动 |
| `Tabs` | 设置页多分区切换 |
| `Toaster` | 全局 toast 反馈 |

## 路由与权限约定
- `/_layout` 及其子路由为受保护区域，未登录会重定向到 `/login`。
- 前端登录态基于 `localStorage.access_token` 判断，不依赖 Cookie Session。
- React Query 全局错误处理在遇到 401/403，或 `404 User not found` 时会清理 token 并跳转登录页。
- `/system/accounts`、`/system/api-tokens` 与 `/system/data-management` 在路由加载阶段会校验 `is_superuser`。
- `/signup`、`/items`、`/admin` 目前仅作为兼容入口，不再是主导航路径。

## 响应式页面约定
- 断点以 Tailwind `md` 为桌面表格与移动卡片的主要切换点；移动端内容保持单列，页面级操作允许占满可用宽度。
- 交易、预算、分类、账户、API Token 与数据任务列表在移动端显示语义化卡片；同一数据源和业务操作在桌面端继续使用表格。
- 交易筛选器在移动端默认折叠并显示已启用条件数量；批量操作栏固定在可见区域底部，仍只作用于当前页选中项。
- 认证页、设置页 Tab 和所有长表单在窄屏下使用安全边距与纵向布局；弹窗内部滚动，不推动页面产生横向溢出。
