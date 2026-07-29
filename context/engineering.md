# 工程流程

## 当前入口

- 仓库级安全、风险和完成规则：`AGENTS.md`
- 开发流程与证据契约：`docs/development-workflow.md`
- 架构和编码约定：`docs/development-guide.md`
- PR 交付清单：`.github/pull_request_template.md`
- 本地最低风险报告：`make change-plan`
- 完成声明检查：`make change-check`
- 规则脚本回归：`make test-change-policy`

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

## 分支与版本

- 当前分支目标与任务一致时继续，否则使用 `feat/`、`fix/` 或 `chore/` 短分支。
- 默认分支保持可发布。
- 获得推送授权时，在首个稳定提交和工作结束时推送。
- 只在确认合并并获得删除授权后删除短分支。
- 版本通过 tag/Release 表达，不建立新的长期版本开发分支。
