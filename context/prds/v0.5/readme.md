# v0.5 PRD

## 版本说明
- 版本：v0.5
- 状态：待实现
- 创建时间：2026-06-01

## 本版本目标
将交易记录从单一 `description` 字段升级为“摘要 + 柔性详情”双层模型，让用户能快速看懂每笔账，也能在需要时维护更丰富的详单信息，并保持批量导入导出与 Agent 集成链路一致。

## 文件组织
| 文件 | 说明 |
|------|------|
| transaction-summary-detail-management.md | 用户在交易页维护摘要与结构化详情的交互和数据设计 |
| transaction-summary-detail-data-exchange.md | 管理员导入导出与 Agent API 对摘要和详情的读写约定 |
