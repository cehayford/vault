# Workflow & Quality Reference

This document maps the **Vault** (Secure Voting System) project to the **Workflow Orchestration & Engineering Standards** dual-flow model, state management, and quality guardrails.

---

## I. Dual-Flow Model

The platform exposes two primary, decoupled flows.

### 1. Definition Flow (Workflow Creation)

*Authoring and validating the election setup.*

```
Admin/Creator → Create Election → Add Ballots → Add Candidates → Validate → Schedule (status: draft → scheduled)
```

| Stage | Responsibility |
|-------|----------------|
| **Admin/Creator** | Authors election (title, type, dates, eligibility), ballots, and candidates. |
| **Election** | DAG-like structure: Election → Ballots → Candidates; immutable once voting is active. |
| **Validator** | Schema correctness (model `clean()`), date ordering, status transition rules. |
| **Scheduler** | Status transitions: draft → scheduled → active (open) → closed → completed. |

- **Immutability:** Once an election is **active** or **closed**, structure (ballots/candidates) is not modified; only status and results change.
- **Sealing (enforced):** The backend rejects add_ballot, delete_ballot, and create_candidate when `is_definition_sealed(election.status)` is true. Transition to `scheduled` or `active` requires at least one ballot.
- **Sealing:** Moving from `draft` to `scheduled`/`active` effectively “seals” the definition.

### 2. Execution Flow (Workflow Running)

*Runtime: voting and tallying.*

```
Voter → Auth/MFA → Ballot(s) → Cast Vote → Receipt → Tally → Results
```

| Stage | Responsibility |
|-------|----------------|
| **Voter** | Triggers a vote via dashboard, shareable link, or invite. |
| **Auth** | Login, verification, MFA if required by election. |
| **Ballot** | One or more ballots per election; one vote per ballot per voter. |
| **Cast** | Encrypted vote stored; receipt issued; idempotent (duplicate prevented). |
| **Tally** | Results computed from votes; optional delayed publication. |

- **Idempotency:** One vote per (ballot, voter); enforced at DB and view layer.
- **Isolation:** Each election run has its own votes and results; no cross-election leakage.

---

## II. State Management

### Election state machine

| State | Allowed next states |
|-------|----------------------|
| `draft` | `scheduled`, `cancelled` |
| `scheduled` | `active`, `cancelled` |
| `active` | `closed`, `cancelled` |
| `closed` | `completed` |
| `completed` | — |
| `cancelled` | — |

- State is persisted in the **Election** model (`status` field).
- Transitions are enforced in **views** via `voting.workflow.ELECTION_STATUS_TRANSITIONS` (single source of truth).
- **Run-level isolation:** Each election is one “run”; no backfill/catchup in the current design.

### Task-level (Celery) state

- Background tasks (e.g. email, notifications) use Celery; retry and error handling follow Celery best practices.
- For critical paths (vote cast, receipt), the web request is synchronous; async is for non-blocking side effects.

---

## III. Error Handling & Validation

- **Retry:** Celery tasks use retry with backoff where configured.
- **Validation:** Election/ballot/candidate use Django model `clean()` and form validation; date ordering and business rules enforced before save.
- **Access control:** Voters cannot perform CRUD on elections/ballots/candidates (`require_not_voter`); managers use `can_manage_election` / `user_can_manage`.
- **Partial failure:** A failed vote submission does not change state; user can retry. No saga/compensation in current scope.

---

## IV. Monitoring & Observability

- **Audit log:** Security and material actions logged (e.g. vote cast, eligibility denied, admin actions).
- **Audit logs view:** Available to auditors/super_admin.
- **Status page:** Account and (for admins) election counts by status.

---

## V. Testing & Quality

- **Unit tests:** Per-app tests; mock external and DB where appropriate.
- **Integration:** Use Django test client and DB; test state transitions and permission checks.
- **CI gate:** `WorkflowTests`; `DefinitionSealedAndValidationTests` (add_ballot/status_change rejected when sealed or no ballots); `DAGValidationTests`. Run: `python manage.py test voting.tests.WorkflowTests voting.tests.DefinitionSealedAndValidationTests voting.tests.DAGValidationTests`
- **Definition of Done:** See `CONTRIBUTING.md` and `tasks/todo.md` (proof over promise, simplicity first, self-correction via `tasks/lessons.md`).

---

## VI. References

- **Task protocol:** `tasks/todo.md`, `tasks/lessons.md`
- **Contributing & DoD:** `CONTRIBUTING.md`
- **Operations runbook:** `docs/RUNBOOK.md`
- **Source of truth for status transitions:** `voting/workflow.py`
