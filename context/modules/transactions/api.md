# transactions 接口详情

## 接口列表
| Method | Path | 描述 |
|--------|------|------|
| GET | /api/v1/transactions/ | 分页读取交易列表，支持筛选 |
| POST | /api/v1/transactions/ | 创建交易 |
| GET | /api/v1/transactions/{transaction_id} | 获取单笔交易 |
| PUT | /api/v1/transactions/{transaction_id} | 更新交易 |
| DELETE | /api/v1/transactions/{transaction_id} | 删除交易 |
| POST | /api/v1/transactions/batch-enter | 批量标记为已入账 |

## 筛选参数
- `page`
- `page_size`
- `start_date`
- `end_date`
- `transaction_type`
- `category_id`
- `entry_status`
- `handler_user_id`

## 业务规则
- 创建和更新交易时，分类和预算都必须属于当前用户。
- 金额 API 单位为元，数据库存储为分。
- 列表按 `transaction_date desc, created_at desc` 排序。
- 创建和更新交易时，`handler_user_id` 默认使用当前登录用户；若显式传入则必须指向存在的系统用户。
- 列表与单笔详情返回 `handler_display_name`，展示规则为 `full_name || login_name || handler_name`。
- 交易当前以 `summary` 作为主摘要字段，并返回可选的 `detail` 柔性详情对象。
- `detail` 需为对象；若包含 `items`，则每条明细至少需要非空 `name`。
- `description` 当前仅作为兼容字段返回，并默认与 `summary` 对齐。
