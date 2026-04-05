# Vault Production Readiness Backlog

Last updated: 2026-04-05
Project phase: pre-production hardening

## Scope
This backlog follows `engineering_orchestration_v4.md` and targets production readiness for:
- privilege/RBAC correctness
- privacy and tenant isolation
- pagination/filter/search consistency
- reliability, observability, and release controls

## Current status snapshot
- [x] Candidate creator isolation fixed (list/detail/create scope)
- [x] Cross-creator election/result URL access blocked for election admins
- [x] Election API hardened to authenticated-only with pagination/filter/search/order
- [ ] Unified authorization policy matrix documented per endpoint
- [ ] Full privacy lifecycle (DSAR, retention job, deletion/export workflow)
- [ ] CI/CD quality gates and deployment safety controls

## Phase 1 - Define (requirements + acceptance criteria)

### 1.1 Authorization matrix
- [ ] Document all web/API endpoints with required access scopes: `own`, `org`, `tenant`, `platform`
- [ ] Define allowed roles per operation (`create`, `read`, `update`, `delete`, `export`, `audit`)
- [ ] Add explicit deny behavior for out-of-scope access (redirect vs 404 vs 403)
Acceptance:
- [ ] Endpoint matrix reviewed and approved
- [ ] Every sensitive endpoint mapped to policy rule

### 1.2 Privacy requirements
- [ ] Define data classes: public, internal, sensitive, regulated
- [ ] Define masking/redaction rules by role and screen/API
- [ ] Define retention timelines and legal deletion exceptions
Acceptance:
- [ ] Privacy policy-to-code mapping complete
- [ ] Audit events defined for all sensitive reads/exports

### 1.3 Performance and UX list contracts
- [ ] Standardize list params: `page`, `per_page`, `search`, `ordering`, `filters`
- [ ] Set max page size and safe defaults for web/API
Acceptance:
- [ ] Common contract published and applied to all list views

## Phase 2 - Explore (architecture + platform decisions)

### 2.1 Authorization architecture
- [ ] Centralize scoping helpers into one policy module (single source of truth)
- [ ] Remove duplicated inline permission checks in views
Acceptance:
- [ ] All election/candidate/user/result views call shared policy layer

### 2.2 Observability architecture
- [ ] Standardize structured security events for access deny, role change, export, bulk invite
- [ ] Define dashboards/alerts for suspicious spikes and failed auth
Acceptance:
- [ ] Runbook includes alert thresholds and response steps

## Phase 3 - Design (module-level design + test strategy)

### 3.1 RBAC module design
- [ ] Define policy function signatures and return semantics
- [ ] Design test matrix for each role and scope
Acceptance:
- [ ] Test cases cover happy path, deny path, cross-tenant/cross-creator probes

### 3.2 Pagination/filter module design
- [ ] Add shared utility for parsing and validating query params
- [ ] Add canonical filter forms for web lists
Acceptance:
- [ ] Candidate, election, user, audit lists share normalized behavior

## Phase 4 - Build (implementation + unit/integration tests)

### 4.1 Privilege and privacy hardening
- [ ] Enforce access checks on all results export and verification paths
- [ ] Add organization-boundary tests for org admins and members
- [ ] Add monitor/auditor explicit read boundaries
Acceptance:
- [ ] Unauthorized URL probes denied across all protected routes
- [ ] Regression tests added for every fixed leak

### 4.2 Pagination/filter completion
- [ ] Candidate list: search + party filter + per-page (done)
- [ ] Election list: add ordering and creator/org filters
- [ ] User list: add search by name/email and date filters
- [ ] Audit logs: add date range and actor filters
Acceptance:
- [ ] All list pages retain query state across pagination
- [ ] API and web list behavior aligned

### 4.3 Operational hardening
- [ ] Add CI workflow: lint, tests, coverage threshold, dependency audit
- [ ] Add pre-deploy check command and release checklist
- [ ] Disable dev-only apps/middleware in production settings
Acceptance:
- [ ] CI required checks block merges on failure
- [ ] Production config validated by startup checks

## Phase 5 - Integrate (system and staging validation)
- [ ] Full regression in staging with production-like settings
- [ ] Security test pass: access-control probes and result-visibility checks
- [ ] Load test on list endpoints and vote submission path
Acceptance:
- [ ] No high/critical security findings
- [ ] No P95 latency regressions vs baseline

## Phase 6 - Deliver (UAT + deployment)
- [ ] UAT pass on role workflows (super_admin, election_admin, org_admin, auditor, monitor, voter)
- [ ] Rollback drill completed and documented
- [ ] Final architecture drift review and ADR updates
Acceptance:
- [ ] Go-live signoff from product + engineering + security

