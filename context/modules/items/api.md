# items 接口详情

> `items` 现为兼容遗留模块，后端 API 仍保留，但不再是主业务对象。

## 接口列表
| Method | Path | 描述 |
|--------|------|------|
| GET | /api/v1/items/ | 读取遗留 Item 列表 |
| GET | /api/v1/items/{id} | 获取单个遗留 Item |
| POST | /api/v1/items/ | 创建遗留 Item |
| PUT | /api/v1/items/{id} | 更新遗留 Item |
| DELETE | /api/v1/items/{id} | 删除遗留 Item |

## 当前状态
- 前端主导航已不再暴露 Item。
- `/items` 路由当前跳转到 `/transactions`。
- 若未来确认不再需要模板兼容，可考虑在后续版本移除整套 Item 能力。
