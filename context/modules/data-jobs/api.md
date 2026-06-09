# data-jobs 接口详情

## 接口列表
| Method | Path | 描述 |
|--------|------|------|
| GET | /api/v1/system/data-jobs/ | 分页读取最近导入导出任务 |
| POST | /api/v1/system/data-jobs/export | 创建导出任务 |
| POST | /api/v1/system/data-jobs/import | 上传 Excel 并创建导入任务 |
| GET | /api/v1/system/data-jobs/template | 下载标准导入模板 |
| GET | /api/v1/system/data-jobs/{job_id}/result | 下载导出结果文件 |
| GET | /api/v1/system/data-jobs/{job_id}/errors | 下载导入错误明细文件 |

## 查询参数
- `page`
- `page_size`

## 业务规则
- 仅管理员可访问全部接口。
- 模板与导出文件统一为多页签 `.xlsx`。
- 当前模板固定包含 `README`、`Categories`、`Budgets`、`Transactions` 四个页签。
- 当前模板版本为 `v2`。
- `Transactions` 页签当前以 `summary` 作为主交易摘要列，并使用 `detail_note`、`detail_items` 交换可读详情内容。
- 导入文件仅支持 `.xlsx`，且要求模板版本与服务端当前版本一致。
- 导入任务按“分类 -> 预算 -> 交易”顺序处理，账单按批次写入，单行错误不会阻断其他合法记录。
- 任务列表返回 `has_result_file` 与 `has_error_file`，前端据此展示下载入口。
