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

- `compose.yml`
- `compose.intranet.yml`
- `compose.release.yml`
- `.env.intranet.example`

内网覆盖文件做了这些事情：

- 给前后端和数据库增加端口映射
- 给核心服务增加日志轮转
- 增加 `db-backup` 自动备份容器
- 把 `adminer` 改成按需启用
- 把基础服务与内网运维入口分层
- 取消发布运行时的 Backend/Frontend `build`，要求两个镜像都固定到 `sha256` digest

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
- `FRONTEND_URL=http://<frontend-host>:8080`
- `BACKEND_URL=http://<api-host>:8000`
- `HOMEFIN_BACKUP_DIR=/absolute/host/path`
- `HOMEFIN_DEPLOY_STATE_DIR=/absolute/host/path`

`BUSINESS_TIMEZONE=Asia/Shanghai` 可以作为 Environment Variable 保持默认。前端使用
同源 `/api` 并由 Nginx 在 Compose 网络内转发，不再写入环境专属 API 地址。

GitHub Staging/Production 工作流需要以下必填 Secret：

- `STACK_NAME`
- `SECRET_KEY`
- `FIRST_SUPERUSER`
- `FIRST_SUPERUSER_PASSWORD`
- `POSTGRES_PASSWORD`
- `FRONTEND_URL`
- `BACKEND_URL`
- `BACKEND_CORS_ORIGINS`
- `HOMEFIN_BACKUP_DIR`
- `HOMEFIN_DEPLOY_STATE_DIR`

邮件和监控相关的 `SMTP_*`、`EMAILS_FROM_EMAIL`、`SENTRY_DSN` 可按实际接入情况配置。
`POSTGRES_USER`、`POSTGRES_DB`、`BUSINESS_TIMEZONE` 可作为 Environment Variable；
未配置时分别使用 `postgres`、`app`、`Asia/Shanghai`。

执行节点还必须分别具备 `self-hosted + staging` 或 `self-hosted + production`
Runner 标签，并安装可用的 Docker、Docker Compose v2 和 curl。Runner 要有：

- 拉取对应 GHCR package 的权限
- 读写数据库持久化卷的 Docker 权限
- 读写 `HOMEFIN_BACKUP_DIR` 与 `HOMEFIN_DEPLOY_STATE_DIR` 的宿主机权限
- 访问固定内网健康检查地址的网络权限

工作流加载三个 Compose 文件，因此继续保持本文档定义的内网 HTTP、固定访问端口、
备份卷和按需 Adminer 语义，同时禁止目标 Runner 现场构建应用镜像。

### 当前自动化边界

仓库代码已实现以下门禁：

- `CI / CI Required` 通过后才构建以完整 SHA 标识的 GHCR 镜像
- Staging 使用构建步骤返回的同一镜像 digest
- Production Release 必须属于 `main`，并找到同一 SHA 的完整成功 CI/staging 运行
- 成功运行保存 90 天 digest 清单；Production 从该次运行下载清单，不重新解析可移动 tag
- Production 使用 GitHub `production` Environment 批准
- 发布前非空数据库备份、迁移失败停止、HTTP 健康检查和应用镜像回退

代码落地不代表外部环境已经就绪。首次启用前必须完成 GHCR 权限、两个 GitHub
Environment、production required reviewer、Environment Secrets/Variables、Runner
标签和 NAS/异机备份配置，并在真实 staging 运行本节验证清单。缺少任何一项时应让
工作流失败并报告，不得改用本地构建、可变 tag 或跳过门禁。

说明：

- `<frontend-host>` 和 `<api-host>` 应该替换成部署服务器在内网中的实际访问地址
- `FRONTEND_HOST` 是后端生成链接时使用的前端地址
- `BACKEND_CORS_ORIGINS` 至少要包含前端实际访问地址

## 5. 启动方式

正常发布入口：

- 合并到 `main` 后，由统一 CI 构建一次并自动部署 staging
- 发布 GitHub Release 后，Production 工作流验证相同 SHA 并等待 Environment 批准
- 已通过完整运行的 SHA 如需重部署 staging，手动运行 `Redeploy Verified Staging Image`

只有仓库变量 `STAGING_ENABLED` 明确设置为 `true` 时，统一 CI 才会构建发布镜像并自动
部署 staging，手动重部署任务也才会进入 `staging` Environment 并选择
`self-hosted + staging` Runner。未配置测试服务器时应保持该变量未设置或非 `true`，
此时相关任务会明确显示为 skipped；这只允许代码合并，不构成 staging 验证证据，
也不能满足 Production Release 的晋级条件。

不应在部署机直接执行 `docker compose build`。`scripts/deploy-release.sh` 是工作流的
受控执行单元，需要完整 SHA、两个 digest 镜像、运行 Secrets 和绝对备份/状态目录。

部署成功后访问：

- 前端：`http://<frontend-host>:8080`
- 后端文档：`http://<api-host>:8000/docs`

## 6. 按需启用 Adminer

仅在需要排障时启用：

```bash
docker compose -f compose.yml -f compose.intranet.yml \
  --project-name "$STACK_NAME" --profile ops up -d adminer
```

访问地址：

- `http://<admin-host>:8081`

建议用完即停：

```bash
docker compose -f compose.yml -f compose.intranet.yml \
  --project-name "$STACK_NAME" stop adminer
```

## 7. 备份策略

当前方案默认包含：

- 每日一次 PostgreSQL 逻辑备份
- 保留最近 7 天日备份
- 保留最近 4 周周备份
- 保留最近 3 个月月备份
- 每次迁移前在 `HOMEFIN_BACKUP_DIR` 新建并校验非空的 custom-format 逻辑备份

定时备份写入 Docker volume `app-db-backups`；迁移前备份写入明确的宿主机目录。

必须在启用 Production 前增加一层：

- 把备份目录同步到另一台内网机器或 NAS
- 定期做恢复演练

## 8. 上线验证清单

建议至少验证：

- 前端页面可访问
- 前端同源 `/api/v1/utils/health-check/` 可访问，证明 Nginx API 转发正常
- 后端 `/docs` 可访问
- 登录和登出正常
- 分类、预算、交易 CRUD 正常
- 导入模板可以下载
- 导入和导出文件在后端重启后仍可下载
- 备份目录有新增备份文件
- `HOMEFIN_DEPLOY_STATE_DIR/current.tsv` 记录本次 SHA 和两个 digest
- 使用可控的失败版本在 staging 验证健康失败会恢复上一组应用镜像
- 使用可控迁移失败在 staging 验证应用不会切换，数据库不会被自动降级

## 9. 注意事项

- 应用健康失败只回退镜像；迁移已经成功时数据库 schema 不会自动降级
- 迁移失败立即停止并保留原应用选择，后续需根据迁移内容制定人工恢复方案
- Production required reviewer 的可用数量和规则受 GitHub 账户/仓库计划限制，配置后
  必须在仓库 Settings 中实际验证
- GHCR、Environment Secrets、Runner、NAS 未配置时，代码准备完成但 H 级 staging
  证据仍缺失，不能宣称发布链路已经正式启用
- 这是内网 HTTP 部署，适合受控环境，不适合直接暴露到公网
- 如果以后需要多台机器访问，仍应保持稳定的内网访问地址
