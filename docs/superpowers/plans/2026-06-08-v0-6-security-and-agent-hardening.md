# v0.6 Security And Agent Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved v0.6 PRD so HomeFin supports deletable safe API tokens, Agent handler option discovery, and end-user plus admin MFA management.

**Architecture:** Extend existing FastAPI route modules in place so the new behavior stays aligned with current auth, token, and user-management patterns. Land behavior behind focused API additions first, prove it with targeted backend tests, then wire the existing React settings and admin pages to the new endpoints while preserving current local edits.

**Tech Stack:** FastAPI, SQLModel, Pytest, React 19, TanStack Query, TanStack Router, local Axios wrapper

---

### Task 1: Backend API Token Hardening

**Files:**
- Modify: `backend/tests/api/routes/test_api_tokens.py`
- Modify: `backend/app/api/routes/api_tokens.py`
- Modify: `backend/app/api/agent_auth.py`

- [ ] **Step 1: Write the failing tests**

Add tests that assert newly created tokens are URL/header safe, deleting a token removes it from listings, and a deleted token can no longer authenticate against an agent endpoint.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest backend/tests/api/routes/test_api_tokens.py -q`
Expected: FAIL because delete route and safe-token assertions are not implemented yet.

- [ ] **Step 3: Write the minimal implementation**

Update token generation to a restricted safe character set, add a delete route in `api_tokens.py`, and make sure agent auth naturally fails once the DB row is deleted.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest backend/tests/api/routes/test_api_tokens.py -q`
Expected: PASS

### Task 2: Agent Handler Options API

**Files:**
- Modify: `backend/tests/api/routes/test_agent_transactions.py`
- Modify: `backend/app/api/routes/agent_transactions.py`
- Modify: `backend/app/api/main.py` only if a new router module becomes necessary
- Optional modify: `backend/app/models.py` only if response DTO reuse requires it

- [ ] **Step 1: Write the failing tests**

Add a test that reads handler options through an API token and another that creates or updates a transaction using a returned `handler_user_id`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest backend/tests/api/routes/test_agent_transactions.py -q`
Expected: FAIL because the handler options endpoint does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Add an authenticated `GET /api/v1/agent/handler-options` endpoint that reuses the existing display-name rules and active-user filtering, while preserving default fallback to token owner when `handler_user_id` is omitted.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest backend/tests/api/routes/test_agent_transactions.py -q`
Expected: PASS

### Task 3: MFA Self-Service And Admin Reset Semantics

**Files:**
- Modify: `backend/tests/api/routes/test_users.py`
- Modify: `backend/tests/api/routes/test_login.py`
- Modify: `backend/app/api/routes/users.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/api/deps.py` only if current-user serialization needs new fields

- [ ] **Step 1: Write the failing tests**

Add tests for current-user MFA status, self-service MFA setup/reset/disable endpoints, admin reset semantics that clear MFA instead of minting a new secret, and login behavior after reset or disable.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest backend/tests/api/routes/test_users.py backend/tests/api/routes/test_login.py -q`
Expected: FAIL because self-service endpoints and reset semantics are missing.

- [ ] **Step 3: Write the minimal implementation**

Add DTOs and user routes for MFA setup/verify/disable/reset, change admin reset to clear the current MFA state instead of returning a new active secret, and keep login logic keyed off whether a confirmed MFA secret exists.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest backend/tests/api/routes/test_users.py backend/tests/api/routes/test_login.py -q`
Expected: PASS

### Task 4: Frontend Token And MFA UI Integration

**Files:**
- Modify: `frontend/src/features/homefin/api.ts`
- Modify: `frontend/src/routes/_layout/system.api-tokens.tsx`
- Modify: `frontend/src/routes/_layout/settings.tsx`
- Create or modify: `frontend/src/components/UserSettings/*` only as needed for MFA UI extraction
- Modify: `frontend/src/client/types.gen.ts` only if existing generated types are already relied on and a light local extension is not enough

- [ ] **Step 1: Write the failing UI-facing tests or identify existing coverage gaps**

If there are practical existing frontend tests for settings or login, extend them; otherwise rely on targeted build verification after wiring the UI because the repo currently appears backend-test heavy for these paths.

- [ ] **Step 2: Implement minimal API helpers**

Add client helpers for deleting API tokens and for MFA setup, confirm, disable, reset, and admin reset operations.

- [ ] **Step 3: Implement minimal UI changes**

Extend `/settings` with an MFA section that shows status and the setup/reset/disable flow, and extend `/system/api-tokens` with delete actions and updated copy about direct usability of new tokens.

- [ ] **Step 4: Run focused frontend verification**

Run the narrowest available frontend verification command that covers the touched code paths, then escalate to a build if needed.

### Task 5: Final Verification

**Files:**
- No code changes required unless verification exposes regressions

- [ ] **Step 1: Run the targeted backend suite**

Run: `python3 -m pytest backend/tests/api/routes/test_api_tokens.py backend/tests/api/routes/test_agent_transactions.py backend/tests/api/routes/test_users.py backend/tests/api/routes/test_login.py -q`
Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run the project’s frontend build or the narrowest stable check available for the modified files.

- [ ] **Step 3: Review changed files against the v0.6 PRD**

Confirm the implementation covers token deletion/safe generation, agent handler discovery, user MFA management, and admin MFA reset semantics.
