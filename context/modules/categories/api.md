# categories 接口详情

## 接口列表
| Method | Path | 描述 |
|--------|------|------|
| GET | /api/v1/categories/ | 分页读取当前用户分类列表 |
| POST | /api/v1/categories/ | 创建分类 |
| PUT | /api/v1/categories/{category_id} | 更新分类 |
| DELETE | /api/v1/categories/{category_id} | 删除分类 |

## 查询参数
- `page`
- `page_size`

## 业务规则
- 分类名称按用户维度唯一。
- `parent_id` 必须指向当前用户自己的分类。
- 分类不能将自己设为自己的父分类。
- 分类删除前不能有子分类，也不能已被交易引用。
- 颜色必须满足 `#RGB` 或 `#RRGGBB` 格式。
- 前端创建和编辑时提供可视化颜色选择器，同时保留十六进制色号输入框。
