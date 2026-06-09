# budgets 接口详情

## 接口列表
| Method | Path | 描述 |
|--------|------|------|
| GET | /api/v1/budgets/ | 分页读取预算列表与已使用金额 |
| POST | /api/v1/budgets/ | 创建预算 |
| PUT | /api/v1/budgets/{budget_id} | 更新预算 |
| DELETE | /api/v1/budgets/{budget_id} | 删除预算 |

## 查询参数
- `page`
- `page_size`

## 业务规则
- API 输入输出金额单位为元，数据库存储单位为分。
- `period` 为枚举型 smallint：月、季、年。
- 删除预算前，若已有交易引用，则返回错误。
