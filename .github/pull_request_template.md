## Scope

<!-- Describe the single goal, affected modules, and explicit non-goals. -->

## Risk level

- [ ] S — low-risk adjustment
- [ ] M — ordinary feature or module change
- [ ] H — auth, permissions, database/migration, dependencies, deployment, or cross-module architecture

Reason:

<!-- Run `make change-plan`. The reported level is a minimum; raise it for semantic risk. -->

## Context impact

- [ ] `updated`
- [ ] `none`

Updated files or reason for no context change:

<!-- Update context only when implemented semantic facts changed. -->

## Verification

Commands and results:

<!-- S: formatting/static + directly related tests
     M: affected module tests and contract paths
     H: complete affected suites -->

Known failures or skipped checks:

## H-level evidence

<!-- Required for H. Migration may be N/A only when no migration exists.
     Rollback and staging cannot be N/A; missing external staging means the H change is not complete. -->

- Rollback plan and verification:
- Migration upgrade/downgrade verification:
- Staging health/smoke verification:

## Traceability

- Related issue/requirement:
- Logical commits:
- Remaining risks/follow-up:

## Completion checklist

- [ ] Scope is focused and contains no unrelated changes.
- [ ] Risk-matched verification is recorded accurately.
- [ ] Context impact is recorded and handled.
- [ ] Generated code, lock files, migrations, and Compose changes were checked when applicable.
- [ ] Commits are logically scoped and the default branch remains releasable.
