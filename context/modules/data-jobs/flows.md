# data-jobs 业务流程

## 模板下载流程
1. 管理员进入 `/system/data-management`。
2. 点击“Download Template”。
3. 后端生成或复用当前版本的标准 Excel 模板。
4. 浏览器下载包含 `README / Categories / Budgets / Transactions` 的工作簿，当前版本为 `v2`。

## 导出流程
1. 管理员点击“Start Export”。
2. 后端创建 `datajob` 记录，初始状态为 `PENDING`。
3. `BackgroundTasks` 异步执行导出，按页签和批次读取数据。
4. `Transactions` 页签中的交易内容会导出为 `summary / detail_note / detail_items` 组合，而不是旧的单一 `description` 列。
5. 结果文件落到本地临时目录，并更新任务状态为 `SUCCEEDED` 或 `FAILED`。
6. 前端轮询任务列表，完成后展示下载入口。

## 导入流程
1. 管理员下载模板并填写数据后上传 `.xlsx` 文件。
2. 后端先做文件级校验，再创建 `datajob` 记录。
3. 任务按“分类 -> 预算 -> 交易”顺序解析页签。
4. 交易页签中的 `summary / detail_note / detail_items` 会被解析为交易摘要和柔性详情对象。
5. 交易数据按批次写入，行级失败写入 `datajoberror`。
6. 若存在失败行，则额外生成错误明细工作簿，并将任务标记为 `PARTIAL_SUCCESS`。

## 业务规则
- 导入导出任务结果文件当前落在本地临时目录，不做长期归档。
- `owner_login_name` 是模板中的归属用户定位字段，系统管理导入导出默认面向全系统账户。
- 错误明细只返回用户可读错误，不暴露内部堆栈。
