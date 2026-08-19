# dashboard 接口详情

## 接口列表
| Method | Path | 描述 |
|--------|------|------|
| GET | /api/v1/dashboard/ | 返回财务首页聚合数据 |

## 响应组成
- `summary`：本月收入、支出、结余
- `trends`：最近 6 个月收入与支出趋势
- `category_shares`：本月支出分类占比
- `budget_usage`：当年预算与已使用金额

## 时间边界
- “今天”“本月”和“当年”依据 `BUSINESS_TIMEZONE` 计算，默认时区为 `Asia/Shanghai`。
- 所有聚合仅统计当前业务日期及以前的交易，不把未来日期交易提前计入。
