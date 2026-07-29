# 工程流程

## 当前入口

- 仓库级安全、风险和完成规则：`AGENTS.md`
- 开发流程与证据契约：`docs/development-workflow.md`
- 架构和编码约定：`docs/development-guide.md`
- PR 交付清单：`.github/pull_request_template.md`
- 本地最低风险报告：`make change-plan`
- 完成声明检查：`make change-check`
- 规则脚本回归：`make test-change-policy`
- CI 路径/风险规划回归：`make test-ci-plan`
- Compose 与备份配置校验：`make validate-compose`
- 发布备份、迁移停止与镜像回退回归：`make test-release-deploy`

## S/M/H 风险等级

| 等级 | 当前定义 | 最低验证 |
| --- | --- | --- |
| S | 文档、文案、样式、测试或局部低风险微调 | 格式/静态检查与直接相关测试 |
| M | 普通功能、非安全 API、单模块重构或局部工程流程 | 受影响模块测试与 context impact |
| H | 认证、权限、模型/迁移、依赖、部署、正式配置或跨模块架构 | 完整相关测试、回滚/迁移验证与 staging |

`scripts/change-policy.sh` 根据路径给出最低等级：已知认证、权限、数据库、依赖和部署
边界直接判定为 H；普通生产代码和工程流程最低为 M；文档、context、测试和样式最低
可为 S。脚本不替代语义判断，人工只能提高等级。

## Context impact

每个变更都记录：

- `updated`：已实现语义事实变化，并修改对应 `context`。
- `none`：没有语义事实变化，并给出具体原因。

Context 不再作为所有改动的机械触碰项。根级文件、模块文件、PRD 和 changelog 继续
分别承载全局事实、模块事实、设计需求和实际交付。

## 完成证据

`make change-check` 要求风险等级、context impact 和测试证据完整。H 级还要求回滚、
迁移与 staging 证据。该工具验证声明完整性与自动风险下限，不声称替代实际测试或 CI。
无迁移时迁移证据可说明 N/A；回滚和 staging 不接受 N/A，缺少外部环境时保持阻塞。

完成状态同时要求范围收敛、风险匹配测试、context 处理、逻辑提交以及分支/提交/风险
可追溯。

## 分级 CI

`.github/workflows/ci.yml` 是 PR、`main`、夜间和手动完整检查的统一入口。PR 由
`scripts/ci-plan.sh` 根据路径推断最低风险并选择受影响检查；纯 S 文档变更不会运行
E2E，H 路径强制选择完整后端、前端、E2E、Compose 和制品校验。`main`、夜间和手动
运行始终执行全量检查。

分支保护的单一稳定门禁为 `CI / CI Required`。它汇总本次被选择的作业；路径跳过仅
允许发生在计划明确未选择的作业上。原有后端、Playwright、Compose 和 pre-commit
工作流仅保留为手动诊断，不再各自产生 PR/main required check。

制品校验覆盖冻结锁文件、生成客户端无漂移、Alembic 单一迁移头、开发/内网 Compose
渲染、内网固定端口、PostgreSQL 定时备份，以及 release 覆盖无构建定义、只引用
不可变镜像。

## 安全发布

`main` 完整 CI 通过后，统一 CI 工作流以完整 commit SHA 为 tag 各构建一次 Backend
和环境无关 Frontend 镜像，并推送 GHCR。Staging 直接使用构建步骤返回的 digest；
Production Release 先验证 tag 提交属于 `main` 且同一 SHA 的 CI、镜像构建和 staging
整体成功，再从该成功运行下载已保存的 digest 清单并等待 `production` Environment
批准。Production 不重新解析 tag。

`scripts/deploy-release.sh` 只接受 digest 镜像和稳定 Compose project name。它在迁移
前生成并校验宿主机 PostgreSQL 备份，迁移失败停止；启动或健康检查失败时使用记录的
上一组 digest 做应用镜像回退，不假设数据库可以自动回滚。正式执行仍依赖仓库
Environment、Secrets、GHCR 权限、Runner 标签和备份/NAS 目录完成外部配置。

## 分支与版本

- 当前分支目标与任务一致时继续，否则使用 `feat/`、`fix/` 或 `chore/` 短分支。
- 默认分支保持可发布。
- 获得推送授权时，在首个稳定提交和工作结束时推送。
- 只在确认合并并获得删除授权后删除短分支。
- 版本通过 tag/Release 表达，不建立新的长期版本开发分支。
