# HomeFin Template Development Guide

## Purpose
This guide defines how to extend the current project template safely and consistently. It focuses on engineering rules, not feature inventory. The current implemented state lives in the `context/` directory.

## Project Positioning
- The repository is a full-stack template based on FastAPI + React.
- It already includes authentication, password recovery, user self-service, admin user management, financial management, theme switching, generated API client support, backend tests, and Playwright E2E coverage.
- Future work should extend these patterns instead of introducing parallel abstractions.

## Tech Stack
| Layer | Stack |
|------|------|
| Workspace | Bun workspace at root, frontend managed from `frontend/` |
| Frontend runtime | React 19 + TypeScript + Vite 7 |
| Frontend routing | TanStack Router (file-based route generation) |
| Frontend data | TanStack Query |
| Forms and validation | React Hook Form + Zod |
| UI primitives | Radix UI |
| UI styling | Tailwind CSS v4 + `tw-animate-css` |
| UI composition | shadcn-style component organization in `frontend/src/components/ui` |
| Tables | TanStack Table |
| Notifications | Sonner |
| Backend runtime | FastAPI |
| Backend models | Pydantic v2 + SQLModel |
| Database | PostgreSQL |
| Migrations | Alembic |
| Auth | JWT bearer token |
| Password hashing | `pwdlib` with Argon2/Bcrypt support |
| Backend tooling | `uv`, Ruff, MyPy, Ty, Pytest, Coverage |
| Frontend tooling | Biome, Playwright, OpenAPI client generation |
| Infra/ops | Docker Compose, GitHub Actions, optional Sentry |

## Source Of Truth
- Engineering rules and collaboration guidance: `docs/development-guide.md`
- Current implemented product state: `context/*.md` and `context/modules/*`
- Backend API contracts: backend code plus generated OpenAPI schema
- Frontend API usage: generated client in `frontend/src/client`

## Directory Responsibilities
| Path | Responsibility |
|------|------|
| `backend/app/api/routes` | FastAPI route handlers grouped by resource |
| `backend/app/api/deps.py` | auth/session dependency injection |
| `backend/app/core` | settings, DB bootstrapping, security helpers |
| `backend/app/models.py` | SQLModel entities plus request/response schemas |
| `backend/app/crud.py` | shared persistence operations for reused user logic |
| `backend/app/email-templates` | email source and built HTML templates |
| `backend/tests` | API, CRUD, and startup test coverage |
| `frontend/src/routes` | route files and page entry points |
| `frontend/src/components/ui` | reusable low-level UI primitives |
| `frontend/src/components/*` | domain-level components grouped by feature |
| `frontend/src/hooks` | reusable hooks for auth, mobile, toast, clipboard |
| `frontend/src/client` | generated OpenAPI client, do not hand-edit |
| `frontend/tests` | Playwright E2E coverage |
| `context` | living implementation documentation |

## Architecture Rules
### Full-stack boundary
- The frontend must consume backend data through the generated client in `frontend/src/client`.
- Do not introduce handwritten fetch wrappers for endpoints already represented in the generated client.
- If backend request/response models change, regenerate the client before touching consuming UI.

### Backend layering
- Keep request validation and HTTP concerns in route handlers.
- Keep reusable persistence logic in `crud.py` only when it is shared across routes or startup flows.
- Put entity and DTO definitions in `models.py` unless the file becomes too large to reason about; if split later, split by domain, not by schema type.
- Use FastAPI dependencies for auth, DB session, and role checks. Do not duplicate token parsing inside routes.

### Frontend layering
- Route files should stay thin: page title metadata, route guards, query bootstrapping, and high-level layout only.
- Move forms, dialogs, tables, and menus into feature components under `frontend/src/components/<Feature>`.
- Keep app-wide primitives under `frontend/src/components/ui` and shared shells under `frontend/src/components/Common` or `Sidebar`.
- Query keys should remain stable and human-readable, following the current pattern such as `["users"]`, `["transactions"]`, `["currentUser"]`.

## UI And Component Style
### Existing style direction
- The template uses a dashboard shell with sidebar navigation, sticky top bar, roomy content spacing, and card/dialog-driven CRUD interactions.
- Visual language is neutral and clean, with teal primary accents defined in CSS variables.
- Light and dark mode are first-class and must remain supported.

### Component rules
- Reuse existing `ui` primitives before creating new low-level controls.
- Reuse the existing dialog + form + loading button pattern for CRUD workflows.
- Prefer composition over one-off page-specific markup when interaction patterns already exist in `Admin`, `Transactions`, or `UserSettings`.
- Empty states should be explicit and friendly, following the current financial management pages.
- New navigation entries should be added through the sidebar item config, not hard-coded in multiple locations.

### Styling rules
- Use Tailwind utility classes with existing token variables from `frontend/src/index.css`.
- Keep colors theme-aware by relying on semantic tokens like `bg-background`, `text-muted-foreground`, `border-border`, `text-destructive`.
- Avoid hard-coded hex values inside components unless introducing a deliberate new design token.
- Prefer `cn()` from `frontend/src/lib/utils.ts` for conditional class composition.

## Frontend Coding Conventions
- Use TypeScript throughout; avoid `any` unless the generated client or library limitation leaves no better option.
- Prefer feature-local Zod schemas for form validation.
- Keep form submission data explicit; strip UI-only fields like `confirm_password` before mutation calls.
- Use TanStack Query mutations for server writes and invalidate the smallest practical query key.
- Surface backend errors through `handleError` and toast helpers instead of custom inline parsing.
- Route protection should live in `beforeLoad` where possible.
- Auth token storage currently uses `localStorage`. Any future auth refactor must update guards, API token resolution, and logout behavior together.

## Backend Coding Conventions
- Use typed response models for public routes.
- Keep error behavior consistent with FastAPI `HTTPException(detail=...)` semantics already used across the codebase.
- Follow the current security posture: generic recovery responses, privilege checks via dependencies, and no data leakage across roles.
- Preserve the current UUID primary-key approach and UTC timestamp handling.
- When changing password or token logic, verify both security behavior and user-facing flows.

## Data And API Evolution Rules
- Treat `backend/app/models.py` as the canonical source for entity shape.
- Database changes must be additive and migration-backed via Alembic.
- Do not silently change the meaning of existing fields.
- If a new field affects frontend forms or tables, update:
  - backend schema/model
  - route contract
  - OpenAPI client generation
  - consuming form/table UI
  - `context/data-schema.md`
  - relevant `context/modules/*` docs
- Collection responses currently use `{ data, count }`; message-only responses use `{ message }`; token responses use `{ access_token, token_type }`. Keep new endpoints consistent unless a clear exception is justified.

## Testing Expectations
### Frontend
- For user-facing behavior changes, add or update Playwright coverage in `frontend/tests`.
- Prefer extending the existing flow-based specs for auth, admin, transactions, and settings before creating scattered one-off files.

### Backend
- Add or update Pytest coverage for new API behavior, startup logic, or CRUD branches.
- Maintain the existing coverage discipline; GitHub Actions enforces backend coverage thresholds.

### End-to-end contract changes
- When changing backend contracts used by the frontend, verify both:
  - backend tests
  - Playwright paths touching the changed behavior

## Tooling And Commands
### Common commands
```bash
bun install
bun run dev
bun run lint
bun run test

cd backend
uv sync
source .venv/bin/activate
bash scripts/test.sh
bash scripts/lint.sh
```

### Client regeneration
```bash
bash scripts/generate-client.sh
```
Run this whenever backend OpenAPI changes. The generated files under `frontend/src/client` should not be manually edited.

## Documentation Update Rules
Every meaningful feature change should update two layers:
1. Code and tests
2. `context` documentation for the implemented state

Minimum expected documentation updates:
- New module or page: update `context/ui.md` and relevant `context/modules/*/ui.md`
- New endpoint or response change: update `context/apis.md` and relevant `context/modules/*/api.md`
- New entity or field: update `context/data-schema.md`
- New cross-cutting behavior or boundaries: update `context/architecture.md`
- Shipped version scope: update the latest changelog entry

## Recommended Development Workflow
1. Check `context/` first to understand the current implemented shape.
2. Extend existing feature patterns instead of inventing a new structure.
3. Update backend contract first when the feature is server-driven.
4. Regenerate the frontend client if OpenAPI changed.
5. Implement UI using existing shared primitives and feature patterns.
6. Add or update automated tests.
7. Refresh `context` documentation to match the new state.

## Anti-Patterns To Avoid
- Bypassing the generated API client for standard backend calls
- Introducing a second form pattern beside React Hook Form + Zod
- Mixing raw color values with token-based styling in ordinary components
- Adding parallel admin or dashboard layouts instead of extending the existing shell
- Editing generated client files manually
- Changing route, API, or schema behavior without reflecting it in `context`
