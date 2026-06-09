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
