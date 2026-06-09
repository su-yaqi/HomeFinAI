# HomeFin Agent API Reference

## Quick Start

This skill uses a consumer-project local config file as the source of truth for API access:

- Runtime config in the target project root: `.homefin-agent-api.json`
- Example config bundled with the skill: `assets/homefin-agent-api.config.example.json`

If you are writing another skill or agent prompt around this API:

1. Read `.homefin-agent-api.json` from the current project root
2. If the file is missing, stop and ask the user for `base_url` and `api_token`
3. If `api_token` is empty, stop and ask the user for the token
4. Write or update `.homefin-agent-api.json` in the target project before attempting any API call

Recommended consumer-project config shape:

```json
{
  "base_url": "http://127.0.0.1:8000",
  "api_token": "your-token",
  "auth_header": "Authorization"
}
```

Optional environment variables if a caller insists on using them:

```bash
export HOMEFIN_BASE_URL="http://127.0.0.1:8000"
export HOMEFIN_API_TOKEN="<PLAIN_API_TOKEN>"
```

## Authentication

Use one of these headers. Default to `Authorization` unless config says otherwise:

```http
Authorization: Bearer <API_TOKEN>
```

or:

```http
X-API-Token: <API_TOKEN>
```

Optional HMAC headers:

```http
X-API-Secret: <SECRET>
X-Timestamp: <TIMESTAMP>
X-Signature: <SIGNATURE>
```

If any HMAC header is present, the full HMAC set must be valid.

## Transaction Endpoints

### List Transactions

```bash
curl -sS "$HOMEFIN_BASE_URL/api/v1/agent/transactions/" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN"
```

### Create Transaction

```bash
curl -sS -X POST "$HOMEFIN_BASE_URL/api/v1/agent/transactions/" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "category_id": "<CATEGORY_ID>",
    "transaction_type": 2,
    "amount": 18.88,
    "entry_status": 1,
    "transaction_date": "2026-05-29",
    "summary": "打车",
    "detail": {
      "note": "晚高峰",
      "items": [
        { "name": "出租车", "remark": "机场回家" }
      ]
    }
  }'
```

Notes:
- `transaction_type`: `1` = income, `2` = expense
- `entry_status`: `1` = pending, `2` = skipped, `3` = entered
- `amount` uses yuan, not cents
- `summary` is the primary short description field
- `detail` must be an object; if it contains `items`, each item needs a non-empty `name`
- Legacy `description` is still accepted as a summary alias during the compatibility period, but new callers should prefer `summary`

### Get Transaction Detail

```bash
curl -sS "$HOMEFIN_BASE_URL/api/v1/agent/transactions/<TRANSACTION_ID>" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN"
```

### Update Transaction

```bash
curl -sS -X PUT "$HOMEFIN_BASE_URL/api/v1/agent/transactions/<TRANSACTION_ID>" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 25.50,
    "summary": "充电",
    "detail": {
      "items": [
        { "name": "国网快充", "remark": "80%" }
      ]
    }
  }'
```

### Delete Transaction

```bash
curl -sS -X DELETE "$HOMEFIN_BASE_URL/api/v1/agent/transactions/<TRANSACTION_ID>" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN"
```

## Budget Endpoints

### List Budgets

```bash
curl -sS "$HOMEFIN_BASE_URL/api/v1/agent/budgets/" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN"
```

Supports normal pagination query params such as `page` and `page_size`.

### Create Budget

```bash
curl -sS -X POST "$HOMEFIN_BASE_URL/api/v1/agent/budgets/" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Agent Budget",
    "year": 2026,
    "period": 1,
    "amount": 300.50
  }'
```

Notes:
- `period`: `1` = month, `2` = quarter, `3` = year
- No agent budget detail endpoint exists

### Update Budget

```bash
curl -sS -X PUT "$HOMEFIN_BASE_URL/api/v1/agent/budgets/<BUDGET_ID>" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Agent Budget",
    "amount": 450
  }'
```

### Delete Budget

```bash
curl -sS -X DELETE "$HOMEFIN_BASE_URL/api/v1/agent/budgets/<BUDGET_ID>" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN"
```

Deletion will fail if the budget is already linked to transactions.

## Category Endpoints

### List Categories

```bash
curl -sS "$HOMEFIN_BASE_URL/api/v1/agent/categories/" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN"
```

Supports normal pagination query params such as `page` and `page_size`.

### Create Category

```bash
curl -sS -X POST "$HOMEFIN_BASE_URL/api/v1/agent/categories/" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Agent Category",
    "color": "#654321"
  }'
```

Notes:
- `color` must be `#RGB` or `#RRGGBB`
- `parent_id` is optional
- No agent category detail endpoint exists

### Update Category

```bash
curl -sS -X PUT "$HOMEFIN_BASE_URL/api/v1/agent/categories/<CATEGORY_ID>" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Agent Category",
    "color": "#123456"
  }'
```

### Delete Category

```bash
curl -sS -X DELETE "$HOMEFIN_BASE_URL/api/v1/agent/categories/<CATEGORY_ID>" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN"
```

Deletion will fail if the category still has child categories or linked transactions.

## Combined Flow Example

### Create a Category, Then Create a Transaction Under It

This is the most common chained workflow for a fresh agent integration:

1. Create a category
2. Read the returned `id`
3. Use that `id` as `category_id` when creating a transaction

Example shell flow:

```bash
CATEGORY_JSON=$(curl -sS -X POST "$HOMEFIN_BASE_URL/api/v1/agent/categories/" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Agent Meals",
    "color": "#ff6600"
  }')

CATEGORY_ID=$(printf '%s' "$CATEGORY_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -sS -X POST "$HOMEFIN_BASE_URL/api/v1/agent/transactions/" \
  -H "Authorization: Bearer $HOMEFIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"category_id\": \"$CATEGORY_ID\",
    \"transaction_type\": 2,
    \"amount\": 42.80,
    \"entry_status\": 1,
    \"transaction_date\": \"2026-05-29\",
    \"summary\": \"晚饭\",
    \"detail\": {
      \"note\": \"外部 agent 创建\",
      \"items\": [
        { \"name\": \"双层吉士汉堡套餐\" }
      ]
    }
  }"
```

Typical result:

```json
{
  "id": "...",
  "category_id": "...",
  "transaction_type": 2,
  "summary": "晚饭",
  "amount": 42.8
}
```

### Practical Guidance for External Agents

- If the target category may already exist, list categories first and reuse the existing `id` when possible.
- If category creation returns `409 Category name already exists`, fetch the category list and match by `name`.
- Do not hardcode category IDs across environments; always read them from the current HomeFin instance.

## Common Response Shapes

Transaction list:

```json
{
  "data": [],
  "count": 0
}
```

Budget list:

```json
{
  "data": [],
  "count": 0
}
```

Category list:

```json
{
  "data": [],
  "count": 0
}
```

Delete message:

```json
{
  "message": "..."
}
```

## Common Failures

- `401 Missing API token`: no agent token was sent
- `401 Invalid API token`: token not found or disabled
- `401 Expired API token`: token expired
- `401 Invalid HMAC signature`: partial or invalid HMAC headers
- `404 Transaction not found`: wrong transaction id or wrong owner scope
- `404 Budget not found`: wrong budget id or wrong owner scope
- `404 Category not found`: wrong category id or wrong owner scope
- `400 Budget has related transactions`: trying to delete a linked budget
- `400 Invalid parent category`: parent category does not belong to the token owner
- `400 Category has child categories`: trying to delete a parent category
- `400 Category has related transactions`: trying to delete a category still used by transactions
- `409 Category name already exists`: duplicate category name under the same owner

## Source of Truth

Backend routes:
- `backend/app/api/routes/agent_transactions.py`
- `backend/app/api/routes/agent_budgets.py`
- `backend/app/api/routes/agent_categories.py`
- `backend/app/api/routes/api_tokens.py`
- `backend/app/api/agent_auth.py`

## Prompting Another Agent

If another installed skill or external agent should use this API, give it a prompt shaped like this:

```text
Use $homefin-agent-api at /Users/suyaqi/Desktop/HomeFin/skills/homefin-agent-api.
Read .homefin-agent-api.json from the current project root first.
If the config file is missing, or api_token is empty, stop and ask the user for the HomeFin API token and write .homefin-agent-api.json before proceeding.
Then call the requested HomeFin agent category, budget, or transaction endpoint.
Return the exact curl command or the final HTTP request code.
```
