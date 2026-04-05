# Lessons Log

## 2026-04-05 - Candidate privacy leak across creators

Issue:
- One creator could see candidates created by another creator.

Root cause:
- Candidate list/detail/create form queries were not scoped to manageable elections.

Fix:
- Added scoped election helper and enforced it in candidate list/detail/create.
- Added regression tests for cross-creator candidate access.

Rule:
- Any resource list/detail/create endpoint must enforce scope at the queryset level, not only at the UI level.

## 2026-04-05 - Election/result URL access not fully isolated

Issue:
- Cross-creator direct URL access to election and results pages was possible for election admins.

Root cause:
- Election/result read views lacked explicit role/scope access checks.

Fix:
- Added centralized election access/result visibility helpers.
- Applied guards to election detail, ballot results, and election results.
- Added regression tests for cross-creator URL probing.

Rule:
- Sensitive read views require the same strict policy enforcement as write views.

## 2026-04-05 - API read exposure and inconsistent list controls

Issue:
- Election API allowed unauthenticated reads and lacked standardized pagination/filter/search ordering.

Root cause:
- API permission class was read-only for anonymous users and no filter backends were configured.

Fix:
- Switched API to authenticated-only.
- Added filter/search/ordering support and default page pagination in DRF settings.
- Added API privacy tests for authentication and creator scoping.

Rule:
- Every externally reachable list API must have authentication, pagination, and explicit filtering behavior.

## 2026-04-05 - Test instability due HTTPS redirects

Issue:
- Tests returned `301` instead of expected responses when production SSL redirect settings were active.

Root cause:
- Test runs used HTTP client requests while `SECURE_SSL_REDIRECT` remained enabled by production-like env settings.

Fix:
- Added `RUNNING_TESTS` override in settings to disable HTTPS redirect and secure cookies during test execution.

Rule:
- Test runtime must explicitly neutralize environment-dependent redirect/security toggles that change response codes.

