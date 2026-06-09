# 前端总览

> 本文件维护全局设计规范、页面树和导航结构，各页面详细定义见 `context/modules/*/ui.md`

## 设计规范
- 组件库：Radix UI primitives + 本地 `components/ui` 封装
- 样式系统：Tailwind CSS v4 + CSS 变量主题 token
- 视觉风格：后台工作台风格，以卡片式财务概览和表格式管理页为主
- 布局：未登录页使用认证布局；已登录页使用左侧侧边栏 + 顶部栏 + 内容区
- 响应式：支持桌面和移动端基础适配，侧边栏移动端可收起
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
| `DataTable` | 账户列表等通用表格 |
| `TablePagination` | 业务列表统一分页器，负责页码、每页条数和总数展示 |
| `Dialog` 相关封装 | CRUD 对话框基础交互 |
| `Tabs` | 设置页多分区切换 |
| `Toaster` | 全局 toast 反馈 |

## 路由与权限约定
- `/_layout` 及其子路由为受保护区域，未登录会重定向到 `/login`。
- 前端登录态基于 `localStorage.access_token` 判断，不依赖 Cookie Session。
- React Query 全局错误处理在遇到 401/403，或 `404 User not found` 时会清理 token 并跳转登录页。
- `/system/accounts`、`/system/api-tokens` 与 `/system/data-management` 在路由加载阶段会校验 `is_superuser`。
- `/signup`、`/items`、`/admin` 目前仅作为兼容入口，不再是主导航路径。
