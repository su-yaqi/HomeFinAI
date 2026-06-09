# Transaction Summary Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade transactions from a single description field to a `summary + detail` model with structured UI editing, API support, and data import/export compatibility.

**Architecture:** Add `summary` and `detail` to the transaction model while keeping `description` as a temporary compatibility field. Normalize all read/write paths through shared serializers so the main API, agent API, and data jobs reuse the same contract. Update the transactions UI to edit `detail` as note + line items rather than raw JSON.

**Tech Stack:** FastAPI, SQLModel, Alembic, PostgreSQL JSONB, Pytest, React 19, TypeScript, TanStack Query/Router, Playwright

---

### Task 1: Backend schema and compatibility contract

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/api/routes/transactions.py`
- Modify: `backend/app/api/routes/agent_transactions.py`
- Create: `backend/app/alembic/versions/*_add_transaction_summary_and_detail.py`
- Test: `backend/tests/api/routes/test_transactions.py`
- Test: `backend/tests/api/routes/test_agent_transactions.py`

- [ ] Step 1: Write failing backend API tests for `summary` and `detail`
- [ ] Step 2: Run targeted pytest cases and verify they fail for missing fields/serialization
- [ ] Step 3: Add schema fields, response serialization, and migration with compatibility handling
- [ ] Step 4: Re-run targeted pytest cases and make them pass

### Task 2: Data jobs import/export support

**Files:**
- Modify: `backend/app/data_jobs.py`
- Test: `backend/tests/api/routes/test_data_jobs.py`

- [ ] Step 1: Write failing tests for template/export/import behavior with `summary` and detail payloads
- [ ] Step 2: Run targeted pytest cases and verify failure
- [ ] Step 3: Implement workbook/template/parser/export updates with compatibility mapping
- [ ] Step 4: Re-run targeted pytest cases and make them pass

### Task 3: Frontend transaction editing and viewing

**Files:**
- Modify: `frontend/src/features/homefin/api.ts`
- Modify: `frontend/src/routes/_layout/transactions.tsx`
- Modify: `frontend/src/client/types.gen.ts` (only if regenerated or manually aligned where needed)
- Test: `frontend/tests/transactions*.spec.ts` or existing relevant coverage

- [ ] Step 1: Add failing frontend coverage or at minimum targeted assertions for summary/detail UI behavior
- [ ] Step 2: Run frontend tests and verify failure
- [ ] Step 3: Implement typed `summary/detail` client contract and structured editor/viewer UI
- [ ] Step 4: Re-run frontend tests and make them pass

### Task 4: Final compatibility verification

**Files:**
- Modify: any touched docs or generated artifacts only if needed by tests/build

- [ ] Step 1: Run targeted backend tests for transactions, agent transactions, and data jobs
- [ ] Step 2: Run targeted frontend tests or build verification for transactions UI
- [ ] Step 3: Sanity check no raw JSON is exposed in transaction UI and compatibility fields still round-trip
