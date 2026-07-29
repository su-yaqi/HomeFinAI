# HomeFin 开发流程

本文档定义从接收任务到形成可追溯提交的统一流程。仓库级强制边界见
[`AGENTS.md`](../AGENTS.md)。

## 1. 开始前核实

每次任务开始时依次确认：

1. 当前分支、HEAD、远端和工作区是否存在未提交改动。
2. 当前分支目标是否与任务一致。一致则继续；不一致则创建 `feat/`、`fix/` 或
   `chore/` 短分支。
3. 相关 `context/`、模块文档、Compose 和现有自动化的真实状态。
4. 本次变更边界、风险等级、验证计划和明确不处理的事项。

不要为了得到干净工作区而 stash、reset 或覆盖他人的改动。

## 2. S/M/H 风险分级

风险取“自动推断下限”和“语义判断”中的较高者。路径脚本不能识别业务语义，因此
跨模块架构、权限扩大、兼容性破坏等情况必须人工提高等级。

| 等级 | 适用范围 | 最低验证 | Context | 额外证据 |
| --- | --- | --- | --- | --- |
| S | 文案、文档、样式、测试、局部低风险微调 | 格式/静态检查 + 直接相关测试 | 记录 impact；语义变化才更新 | 无 |
| M | 普通功能、非安全 API、单模块重构、局部工程流程 | 受影响模块测试；契约变化需前后端联测 | 记录 impact；更新受影响事实 | 测试命令和结果 |
| H | 认证、权限、模型/迁移、依赖、部署、正式配置、跨模块架构 | 完整相关测试 | 更新受影响事实，或说明无影响原因 | 回滚、迁移、staging |

以下路径会被检查脚本直接提升为 H：

- `backend/app/alembic/**`、`backend/app/models.py`
- 认证、权限和安全入口
- 依赖清单、锁文件和 Dockerfile
- `compose.yml`、`compose.intranet.yml`、正式环境示例
- Staging/Production 部署工作流

普通生产代码最低为 M。纯文档、context、测试和样式变更最低可为 S。自动结果只是
最低等级，不是降低风险的依据。

## 3. Context impact

所有变更都必须选择一种：

- `updated`：已实现的产品语义、接口、数据、架构或运行边界发生变化。更新准确的
  `context` 文件和实际交付 changelog。
- `none`：没有上述变化。记录具体原因，例如“仅补充测试”“只调整格式”“重构未改变
  外部行为”。

不要机械触碰所有 context 文件。根级文件记录全局事实，`modules/*` 记录模块细节，
`prds/*` 记录需求与设计，`changelogs/*` 只记录实际交付。

## 4. 本地检查入口

查看当前工作区的自动最低风险：

```bash
make change-plan
```

检查一个分支相对基线的变更：

```bash
BASE_REF=main make change-plan
```

完成前验证声明。环境变量作为数据传入，不会被当作 Shell 命令重新解析：

```bash
CHANGE_RISK=M \
CONTEXT_IMPACT=updated \
TEST_EVIDENCE="bash -n scripts/change-policy.sh; policy tests passed" \
make change-check
```

无 context 变化时必须说明原因：

```bash
CHANGE_RISK=S \
CONTEXT_IMPACT=none \
CONTEXT_REASON="Only test assertions changed; implemented behavior is unchanged." \
TEST_EVIDENCE="targeted test passed" \
make change-check
```

H 级必须额外提供：

```bash
CHANGE_RISK=H \
CONTEXT_IMPACT=updated \
TEST_EVIDENCE="full affected suites passed" \
ROLLBACK_EVIDENCE="rollback procedure exercised" \
MIGRATION_EVIDENCE="upgrade/downgrade rehearsal passed, or N/A with reason" \
STAGING_EVIDENCE="staging health and smoke checks passed" \
make change-check
```

只有本次不包含数据库迁移时，迁移证据可以使用带具体原因的 `N/A`。回滚与 staging
不能使用 `N/A` 代替；缺少可用 staging 或相应权限时，H 级变更应保持未完成并报告
外部阻塞。

`BASE_REF` 未设置时，工具检查暂存、未暂存和未跟踪文件；设置后检查
`BASE_REF...HEAD`。Phase 3 会在此契约上接入 PR 分级 CI，本阶段不会把本地声明
误当成 CI 已通过。

## 5. 分支与提交

- 当前分支与任务一致时继续，避免没有收益的分支搬运。
- 新任务使用短分支；默认分支保持可发布。
- 提交按逻辑目标拆分，不按文件类型机械拆分。
- 在远端操作已获授权时，于首个稳定提交和工作结束时推送。
- 合并确认后、且删除操作已获授权时，删除短分支。
- 版本通过 tag/Release 表达，不建立新的长期 `vX.Y` 开发分支。

## 6. 完成与交付

交付报告至少包含：

1. 实际修改范围。
2. 风险等级及理由。
3. 验证命令、通过项和失败项。
4. Context impact 和更新文件。
5. 逻辑提交 ID、推送状态。
6. 剩余风险、外部配置或下一阶段。

任何失败、跳过或缺少外部条件都必须明确写出，不能使用“整体通过”掩盖。
