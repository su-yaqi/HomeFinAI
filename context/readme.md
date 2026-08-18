# context 目录说明

本目录是项目的状态工作区，记录当前代码库的已实现能力、结构边界和版本演进信息。

## 目录结构
```
context/
├── readme.md
├── project.md
├── architecture.md
├── data-schema.md
├── apis.md
├── ui.md
├── prds/
│   ├── v0.1/
│   └── v0.2/
├── changelogs/
│   ├── v0.1.md
│   ├── v0.2.md
│   ├── v0.3.md
│   ├── v0.4.md
│   ├── v0.5.md
│   ├── v0.6.md
│   ├── v0.7.md
│   └── v0.8.md
└── modules/
    ├── app-shell/
    ├── auth/
    ├── users/
    ├── categories/
    ├── budgets/
    ├── transactions/
    ├── dashboard/
    └── ai-connector/
```

## 文件层级职责
- 根目录文件：记录全局当前状态、通用规范和模块索引。
- `modules/*`：记录模块级接口、页面和流程细节。
- `prds/*`：记录版本需求或历史需求文档。
- `changelogs/*`：记录某一版本已实际交付的内容。

## 使用规则
- 当前代码实现发生变化时，应优先更新对应 `context` 文件。
- 全局变化更新根目录文件；模块细节变化更新对应 `modules/*`。
- 新增业务模块时，在 `modules/` 下建立同名目录，并补齐 `api.md`、`flows.md`、`ui.md`。
- PRD 可以保留历史设计信息，但版本状态和最终交付结果要在 `changelogs/` 中明确落地。

## 当前状态说明
- `root + modules/*`：表示当前代码已实现状态。
- `prds/v0.9/`：表示当前 MCP / AI Connector 需求与退役边界。
- `changelogs/v0.8.md`：仍是最近已正式发布版本；v0.9 完成真实客户端验收后再补交付记录。

第三方 Agent 接入 HomeFin MCP 时，使用 [`modules/ai-connector/agent-integration-guide.md`](modules/ai-connector/agent-integration-guide.md) 作为实现与验收说明。
