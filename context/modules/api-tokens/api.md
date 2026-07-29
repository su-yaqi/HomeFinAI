# api-tokens 接口详情

## 接口列表
| Method | Path | 描述 |
|--------|------|------|
| GET | /api/v1/system/api-tokens/ | 分页读取 API Token 列表 |
| POST | /api/v1/system/api-tokens/ | 创建 API Token |
| POST | /api/v1/system/api-tokens/{token_id}/disable | 禁用 API Token |
| DELETE | /api/v1/system/api-tokens/{token_id} | 删除 API Token |

## 查询参数
- `page`
- `page_size`

## 业务规则
- 仅管理员可访问。
- 明文 token 只在创建时返回一次。
- 可选生成 HMAC Secret；生成 Secret 的 Token 后续请求必须使用完整 HMAC 头，不能回退为仅 Token 调用。
- 支持彻底删除 Token，而不仅是停用。
- Token 成功被 Agent 使用后会更新 `last_used_at`。
- HMAC 请求使用数据库唯一 Nonce 阻止重放，Nonce 会在 Token 或所属账户删除时级联清理。
