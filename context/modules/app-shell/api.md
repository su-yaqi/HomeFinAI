# app-shell 接口详情

> 本模块主要承载应用框架与基础设施，不直接拥有核心业务实体。

## 接口列表
| Method | Path | 描述 |
|--------|------|------|
| GET | /api/v1/utils/health-check/ | 健康检查 |
| POST | /api/v1/utils/test-email/ | 管理员发送测试邮件 |
| POST | /api/v1/private/users/ | 本地环境下创建测试用户 |

## 说明
- `health-check` 用于本地联调、容器健康检查与基础可用性验证。
- `test-email` 主要服务邮件链路验证。
- `private/users/` 仅在 `ENVIRONMENT=local` 时挂载。
