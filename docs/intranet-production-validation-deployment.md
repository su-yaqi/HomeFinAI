# HomeFin 内网生产验证部署方案

本文档适用于以下场景：

- 服务只在内网使用
- 不需要公网域名
- 不需要 HTTPS
- 仍然要求全 Docker 部署
- 仍然要求数据库、导入导出文件、备份持久化

这会比公网方案简单很多，不依赖公网域名、HTTPS 证书和反向代理入口。

## 1. 推荐拓扑

单机部署，开放少量内网端口：

- `frontend`: `8080`
- `backend`: `8000`
- `adminer`: `8081`，仅运维时按需启用

容器包括：

- `frontend`
- `backend`
- `db`
- `prestart`
- `db-backup`
- `adminer`，使用 `ops` profile 控制

## 2. 持久化设计

当前方案保留以下持久化卷：

- `app-db-data`: PostgreSQL 数据
- `app-data-jobs-data`: Excel 导入导出相关文件
- `app-db-backups`: PostgreSQL 逻辑备份

其中数据任务文件已经配置为写入后端容器内的 `/data/homefin-data-jobs`，容器重建后不会丢失。

## 3. 使用的 Compose 文件

内网部署使用：

- [`compose.yml`](/Users/suyaqi/Desktop/HomeFin/compose.yml:1)
- [`compose.intranet.yml`](/Users/suyaqi/Desktop/HomeFin/compose.intranet.yml:1)
- [`.env.intranet.example`](/Users/suyaqi/Desktop/HomeFin/.env.intranet.example:1)

内网覆盖文件做了这些事情：

- 给前后端和数据库增加端口映射
- 给核心服务增加日志轮转
- 增加 `db-backup` 自动备份容器
- 把 `adminer` 改成按需启用
- 把基础服务与内网运维入口分层

## 4. 部署前需要设置的变量

至少需要在部署机的 `.env` 中设置这些值：

- `ENVIRONMENT=production`
- `FRONTEND_HOST=http://<frontend-host>:8080`
- `BACKEND_CORS_ORIGINS=http://<frontend-host>:8080`
- `SECRET_KEY=<strong-random-value>`
- `POSTGRES_PASSWORD=<strong-random-value>`
- `FIRST_SUPERUSER=<admin-email>`
- `FIRST_SUPERUSER_PASSWORD=<strong-random-value>`
- `POSTGRES_USER=postgres`
- `POSTGRES_DB=app`

另外，构建前端时还需要一个额外环境变量：

- `INTRANET_API_URL=http://<api-host>:8000`
- `BUSINESS_TIMEZONE=Asia/Shanghai`

GitHub Staging/Production 工作流需要以下必填 Secret：

- 通用或对应 GitHub Environment 内同名配置：
  `SECRET_KEY`、`FIRST_SUPERUSER`、`FIRST_SUPERUSER_PASSWORD`、`POSTGRES_PASSWORD`
- 环境专用项目名：
  `STACK_NAME_STAGING` / `STACK_NAME_PRODUCTION`
- 环境专用访问地址：
  `FRONTEND_HOST_STAGING` / `FRONTEND_HOST_PRODUCTION`
- 环境专用 CORS：
  `BACKEND_CORS_ORIGINS_STAGING` / `BACKEND_CORS_ORIGINS_PRODUCTION`
- 环境专用 API 地址：
  `INTRANET_API_URL_STAGING` / `INTRANET_API_URL_PRODUCTION`

邮件和监控相关的 `SMTP_*`、`EMAILS_FROM_EMAIL`、`SENTRY_DSN` 可按实际接入情况配置。
执行节点还必须分别具备 `self-hosted + staging` 或 `self-hosted + production`
Runner 标签，并安装可用的 Docker Compose。

工作流会同时加载 `compose.yml` 与 `compose.intranet.yml`，因此继续保持本文档定义的
内网 HTTP、固定访问端口、备份卷和按需 Adminer 语义。

### 当前自动化边界

现有工作流仍是在目标 Runner 上现场构建并直接 `up -d` 的过渡实现，尚未提供：

- 等待同一提交完整 CI 通过的单一门禁
- 以 Commit SHA 标识、只构建一次并在 Staging/Production 间晋级的不可变镜像
- 部署后的完整健康检查与冒烟测试
- 可靠的应用镜像回退，以及数据库迁移失败后的人工处置门禁

在这些能力完成并验证前，不应把当前工作流视为最终安全发布链路，也不应仅凭本地
配置解析通过就启用正式环境部署。

说明：

- `<frontend-host>` 和 `<api-host>` 应该替换成部署服务器在内网中的实际访问地址
- `INTRANET_API_URL` 是前端构建时写入的 API 地址
- `FRONTEND_HOST` 是后端生成链接时使用的前端地址
- `BACKEND_CORS_ORIGINS` 至少要包含前端实际访问地址

建议直接把 `INTRANET_API_URL` 写入部署机 `.env`，不需要额外 `export`。

## 5. 启动方式

构建并启动：

```bash
docker compose -f compose.yml -f compose.intranet.yml build
docker compose -f compose.yml -f compose.intranet.yml up -d
```

启动后访问：

- 前端：`http://<frontend-host>:8080`
- 后端文档：`http://<api-host>:8000/docs`

## 6. 按需启用 Adminer

仅在需要排障时启用：

```bash
docker compose -f compose.yml -f compose.intranet.yml --profile ops up -d adminer
```

访问地址：

- `http://<admin-host>:8081`

建议用完即停：

```bash
docker compose -f compose.yml -f compose.intranet.yml stop adminer
```

## 7. 备份策略

当前方案默认包含：

- 每日一次 PostgreSQL 逻辑备份
- 保留最近 7 天日备份
- 保留最近 4 周周备份
- 保留最近 3 个月月备份

备份写入 Docker volume `app-db-backups`。

建议再增加一层：

- 把备份目录同步到另一台内网机器或 NAS
- 定期做恢复演练

## 8. 上线验证清单

建议至少验证：

- 前端页面可访问
- 后端 `/docs` 可访问
- 登录和登出正常
- 分类、预算、交易 CRUD 正常
- 导入模板可以下载
- 导入和导出文件在后端重启后仍可下载
- 备份目录有新增备份文件

## 9. 注意事项

- 前端 API 地址是在镜像构建阶段写进去的，如果访问地址变化，需要重新构建前端镜像
- 这是内网 HTTP 部署，适合受控环境，不适合直接暴露到公网
- 如果以后需要多台机器访问，建议保持稳定的内网访问地址，避免前端 API 地址漂移
