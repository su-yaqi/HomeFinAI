# HomeFin 本地多实例开发

本文档描述本地 Docker Compose 开发环境。内网正式部署继续使用
`compose.yml + compose.intranet.yml`，不使用这里的 slot、开发 profile 或端口范围。

## 1. 统一入口

从仓库根目录运行：

```bash
make dev-up
```

常用命令：

| 命令 | 作用 |
| --- | --- |
| `make dev-env` | 显示项目名、slot 和全部稳定地址，不启动容器 |
| `make dev-check` | 检查项目归属和默认入口端口 |
| `make dev-config` | 验证开发 Compose 渲染结果 |
| `make dev-up` | 构建并启动当前 slot 的前后端核心服务 |
| `make dev-restart` | 使用当前代码重新创建核心应用服务 |
| `make dev-ps` | 只显示当前 slot 的容器 |
| `make dev-logs` | 显示当前 slot 最近 200 行日志 |
| `make dev-down` | 只停止当前 slot；保留数据库和依赖缓存卷 |

不要通过修改 Compose 文件或随机端口启动并行实例。为每个并行 worktree 选择固定
`DEV_SLOT`，并在后续命令中持续使用同一个值。

## 2. 项目名与端口契约

默认值：

```text
DEV_PROJECT=homefin
DEV_PORT_BASE=21000
DEV_SLOT=0
Compose project=homefin-dev-0
```

端口块计算方式：

```text
block_start = DEV_PORT_BASE + DEV_SLOT × 20
```

每个 slot 的映射：

| 偏移 | 服务 | slot 0 | 默认状态 |
| --- | --- | --- | --- |
| `+0` | Frontend | `21000` | 暴露到 `127.0.0.1` |
| `+1` | Backend | `21001` | 暴露到 `127.0.0.1` |
| `+2` | PostgreSQL 保留位 | `21002` | 不暴露 |
| `+3` | Adminer | `21003` | 按需 |
| `+4` | Mailcatcher UI | `21004` | 按需 |
| `+5` | Mailcatcher SMTP | `21005` | 按需 |
| `+6` | Playwright UI | `21006` | 按需 |
| `+7..+19` | 项目保留 | - | 不使用 |

例如：

```bash
make dev-up DEV_SLOT=1
```

会使用项目 `homefin-dev-1`、Frontend `21020` 和 Backend `21021`。
支持的 `DEV_SLOT` 范围是 `0..999`，默认 HomeFin 开发范围为 `21000..40999`。

如确需为另一个本地项目范围选择不同起点，应固定传入新的 `DEV_PROJECT` 和
`DEV_PORT_BASE`，而不是逐个覆盖服务端口：

```bash
make dev-env DEV_PROJECT=homefin-lab DEV_PORT_BASE=41000 DEV_SLOT=0
```

## 3. 启动前安全检查

`make dev-up` 在修改 Docker 状态前会检查：

1. Docker daemon 可用。
2. 同名 Compose 项目的容器和保留卷没有归属于另一个 worktree。
3. Frontend 和 Backend 宿主机端口没有被其他 Docker 项目或本机进程占用。

冲突时命令会报告容器名、Compose project/service 或本机监听进程，然后失败。
脚本不会自动停止、删除或重建占用端口的其他项目。

重复执行同一 worktree、同一 slot 的命令是允许的；该项目的现有容器不会被误判为
外部冲突。`make dev-down` 后保留的卷仍带有 worktree 归属标签，因此其他 worktree
也不能在原实例停止后静默接管同一 slot 的数据。

## 4. 默认暴露边界

默认 `make dev-up` 只启用：

- PostgreSQL（仅 Compose 内网）
- 数据库迁移和初始化任务
- Backend
- Frontend

宿主机仅监听 `127.0.0.1` 的 Frontend 和 Backend 端口。数据库、Adminer、
Mailcatcher 和 Playwright UI 默认都不暴露。

### Adminer

```bash
make adminer-up DEV_SLOT=0
make adminer-down DEV_SLOT=0
```

默认地址为 `http://127.0.0.1:21003`。

### Mailcatcher

```bash
make mail-up DEV_SLOT=0
make mail-down DEV_SLOT=0
```

默认 UI 为 `http://127.0.0.1:21004`，SMTP 为 `127.0.0.1:21005`。
Backend 在开发配置中使用 Compose 内部地址 `mailcatcher:1025`；未启用 Mailcatcher
时，普通非邮件功能不受影响，实际发送邮件会失败并明确暴露缺少邮件服务。

### Playwright UI

```bash
make playwright-ui DEV_SLOT=0
```

默认 UI 为 `http://127.0.0.1:21006`。该命令会按需启用 Playwright 与内部
Mailcatcher profile。

## 5. 测试隔离

```bash
make test-backend DEV_SLOT=0
make test-e2e DEV_SLOT=0
```

两类测试分别使用：

- `homefin-dev-0-test-backend`
- `homefin-dev-0-test-e2e`

测试栈不发布前后端端口。命令结束后只清理对应测试项目的容器、网络和测试卷，不会
执行宽泛的默认项目 `down -v`，也不会停止开发实例或其他仓库容器。

## 6. `.env` 与访问地址

`.env` 仍用于本地凭据、数据库名、邮件设置等应用参数，并继续保持不入库。
`scripts/dev.sh` 会在当前进程中设置与 slot 对应的：

- `FRONTEND_HOST`
- `BACKEND_CORS_ORIGINS`
- `INTRANET_API_URL`
- 前后端开发镜像名

Shell 环境优先于 `.env`，因此多 slot 地址不会被示例占位值覆盖。

## 7. 与内网正式部署的边界

本地命令使用：

```text
compose.yml + compose.override.yml
```

内网正式部署继续使用：

```text
compose.yml + compose.intranet.yml
```

`compose.intranet.yml` 的 HTTP、Frontend `8080`、Backend `8000`、按需 Adminer
`8081`、数据库备份和持久化卷语义保持独立，不读取 `DEV_SLOT`，也不使用本地 profile
覆盖文件。
