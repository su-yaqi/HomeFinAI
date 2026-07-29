---
name: homefin-agent-api
description: Use when Codex needs to read local HomeFin agent API config, build or troubleshoot requests to `/api/v1/agent/transactions/*`, `/api/v1/agent/budgets/*`, or `/api/v1/agent/categories/*`, or explain API-token based access from another repo, agent, or script.
---

# HomeFin Agent API

## Overview

Use this skill when you need to operate HomeFin through its API-token based agent endpoints instead of the normal user JWT business APIs.

Read [references/agent-api.md](references/agent-api.md) before generating requests or code that calls these endpoints.
Read the consumer project's local config file at `.homefin-agent-api.json` before making any request.

## Workflow

1. Confirm the HomeFin base URL.
2. Open `.homefin-agent-api.json` in the current project root.
3. If the file does not exist, stop and ask the user for the API token and base URL, then write the file in the current project root.
4. If the file exists but `api_token` is empty, stop and ask the user for the API token, then update the file.
5. Use the configured `base_url` and `api_token` for all requests.
6. Call agent endpoints with either:
   - `Authorization: Bearer <API_TOKEN>`
   - `X-API-Token: <API_TOKEN>`
7. If the config contains `api_secret`, sign every request using a fresh random
   nonce, timestamp, and the HMAC-SHA256 contract in the reference. A token issued
   with a secret cannot fall back to unsigned requests or reuse a nonce.

## Required Inputs

The skill cannot guess secrets. It must read them from the local config file or ask the user for them.

Required config keys:
- `base_url`
- `api_token`

Optional config key:
- `api_secret` (required by the server when the token was issued with a secret)

If the config file is missing or incomplete, stop and ask the user for the missing value instead of trying to derive it from another credential flow.

## Endpoints

Supported transaction endpoints:
- `GET /api/v1/agent/transactions/`
- `POST /api/v1/agent/transactions/`
- `GET /api/v1/agent/transactions/{transaction_id}`
- `PUT /api/v1/agent/transactions/{transaction_id}`
- `DELETE /api/v1/agent/transactions/{transaction_id}`

Supported budget endpoints:
- `GET /api/v1/agent/budgets/`
- `POST /api/v1/agent/budgets/`
- `PUT /api/v1/agent/budgets/{budget_id}`
- `DELETE /api/v1/agent/budgets/{budget_id}`

Supported category endpoints:
- `GET /api/v1/agent/categories/`
- `POST /api/v1/agent/categories/`
- `PUT /api/v1/agent/categories/{category_id}`
- `DELETE /api/v1/agent/categories/{category_id}`

## Guidance

- Prefer `Authorization: Bearer <API_TOKEN>` unless the caller specifically wants `X-API-Token`.
- Treat returned money fields as yuan values; the backend converts them to cents internally.
- Treat transaction `summary` as the primary short description field and `detail` as the optional structured detail object.
- When creating or updating agent transactions, prefer `summary` / `detail` over legacy `description`.
- Do not invent a budget detail endpoint; the current agent budget API does not provide one.
- Do not invent a category detail endpoint; the current agent category API does not provide one.
- Prefer the checked-in example config plus an untracked local config file over ad-hoc environment variables.
- Treat `.homefin-agent-api.json` as consumer-project state, not as a HomeFin repo file.
- If the task is to diagnose a failed request, include expected 401, 404, and 400 failure modes from the reference.
- When invoked from another repo or agent, first determine whether the local config file already contains a usable token.
- Read the reference before emitting code so request bodies and enum values match the backend contract.
