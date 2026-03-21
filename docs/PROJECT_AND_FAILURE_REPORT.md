# Project and Failure Report — Handover for Continuation

**Purpose:** So that any developer joining the project can quickly understand what the project is, what works, what has failed and how it was fixed, and how to continue.

**Last updated:** 2026-03 (from session work on auth, deployment, i18n, and reporting).

---

## Table of contents

1. [Project overview](#1-project-overview)
2. [Documentation index](#2-documentation-index)
3. [Tech stack and structure](#3-tech-stack-and-structure)
4. [What works](#4-what-works)
5. [Known failures and fixes](#5-known-failures-and-fixes)
6. [Deployment and build](#6-deployment-and-build)
7. [Auth and email flows](#7-auth-and-email-flows)
8. [How to continue](#8-how-to-continue)

---

## 1. Project overview

**Vault** is a secure electronic voting platform. Organisations run elections (draft → scheduled → active → closed → completed) with encrypted votes, verifiable receipts, and full audit trails.

- **Definition flow:** Admins create elections, add ballots and candidates, invite voters, open/close voting.
- **Execution flow:** Voters authenticate (email, optional MFA, optional phone verification), cast encrypted votes per ballot, receive a receipt.
- **Roles:** Voter (default), Creator (election_admin / org_admin / creator), Super Admin, Auditor, Monitor. See [AUTH_CREDENTIALS.md](AUTH_CREDENTIALS.md) for dev logins.

---

## 2. Documentation index

| Document | Use |
|----------|-----|
| **README.md** (root) | High-level features, roles, architecture, install, config. |
| **PRD.md** | Product requirements, goals, user roles, core features. |
| **RUNBOOK.md** | Pre-deploy checklist, services, recovery, health checks, troubleshooting. |
| **WORKFLOW_AND_QUALITY.md** | Definition vs execution flow, state machine, testing gates. |
| **AUDIT_AND_RESTRUCTURE_PLAN.md** | Plan A/B/C (auditor/monitor, Super Admin in-app, UI restructure). Plans marked completed in tasks/todo.md. |
| **AUTH_CREDENTIALS.md** | Dev users per role; `create_role_credentials` command. |
| **DEPLOY.md** (root) | Railway deploy: Nixpacks, env vars, start command. |
| **tasks/todo.md** | Active/completed objectives; Definition of Done; plan-first mandate. |
| **tasks/lessons.md** | Past failures and fixes (update after every correction). |
| **CONTRIBUTING.md** (root) | DoD, task protocol, references todo.md and lessons.md. |
| **locale/README.md** | How to add translations (makemessages / compilemessages). |

---

## 3. Tech stack and structure

- **Backend:** Django 5.x, Python 3.12. WSGI entry: `engine.wsgi`. Settings: `engine/settings.py`.
- **Database:** PostgreSQL (production) or SQLite (dev). Migrations per app.
- **Cache / broker:** Redis (cache, Celery broker when used).
- **Frontend:** Tailwind CSS, design tokens (`vault-design-system.css`), Plus Jakarta Sans / DM Sans.
- **Auth:** CustomUser (email as USERNAME_FIELD), MFA (TOTP), phone OTP verification. Rate limiting via django-ratelimit.
- **Voting:** Encrypted vote storage (Fernet), receipt codes, optional invite-only ballots, proportional representation (largest-remainder seat allocation).

**Key directories:**

```
engine/           # Django project: settings, urls, wsgi, middleware
userauth/         # Auth: CustomUser, MFA, SecurityLog, login/signup, password reset, phone OTP
voting/           # Elections, ballots, votes, results, invite voters, shareable link, Celery tasks
nominee/          # Candidate/nominee management
templates/        # Global templates; components/ for nav, footer
locale/           # i18n message files (en, es, fr)
tasks/            # todo.md, lessons.md (plan, track, evolve)
docs/             # This report, PRD, RUNBOOK, workflow, audit plan, auth credentials
management/       # Django management commands (e.g. create_role_credentials, generate_test_data)
```

**Important modules:**

- `voting/workflow.py` — Election status transitions (single source of truth).
- `voting/views.py` — Election CRUD, vote casting, eligibility, shareable link, invite voters, ballot results.
- `userauth/views.py` — Login, signup, MFA, password reset, phone verify, OTP send.
- `voting/tasks.py` — Celery: invite emails, vote confirmation, share link to email/SMS, phone OTP SMS, result calculation.

---

## 4. What works

- **Election lifecycle:** Draft → scheduled → active → closed → completed (or cancelled). Definition sealed once not draft; no add/remove ballots or candidates after that.
- **Voting:** Single choice, multiple choice, ranked choice, proportional representation (with optional multi-seat allocation). Invite-only elections with per-voter tokens; shareable link with copy, QR, and “send by email/phone” (bulk).
- **Auth:** Email signup/login, email verification, MFA (TOTP), phone OTP verification. Password reset (forgot password) with email link. Role-based access; `@require_not_voter` on management views.
- **Admin:** In-app admin dashboard, user list and role change (super_admin / org_admin), audit logs (filter, paginate). Design system used on dashboard, election list, status, login/signup, password reset, phone verify, shareable link.
- **i18n:** LANGUAGE_CODE and LANGUAGES (en, es, fr); LocaleMiddleware; footer language switcher (set_language); LOCALE_PATHS; `makemessages`/`compilemessages` for adding translations.
- **Tests:** Django test runner; workflow/DAG/definition-sealed tests; pytest + test_system with conftest and django_db (see lessons.md).

---

## 5. Known failures and fixes

These are issues that have occurred and how they were fixed. When continuing, run through **tasks/lessons.md** as well.

### 5.1 Deployment build failure (ENCRYPTION_KEY)

- **Symptom:** Build fails during `python manage.py collectstatic --noinput` with `ImproperlyConfigured: ENCRYPTION_KEY must be set...`
- **Cause:** At **build** time (e.g. Railway/Nixpacks), env vars are often not available. Settings required a valid `ENCRYPTION_KEY` whenever `DEBUG=False`, and collectstatic runs at build with production settings.
- **Fix:** In `engine/settings.py`, the strict `ENCRYPTION_KEY` check is **skipped when the management command is `collectstatic`** (detected via `sys.argv`). So the build can complete without the key; the key is still **required at runtime** for voting.
- **Action for deploy:** Set `ENCRYPTION_KEY` in the deployment environment (e.g. Railway Variables). Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

### 5.2 Password reset request fails

- **Symptom:** Submitting the “forgot password” form returns 500 or an error.
- **Cause:** `send_mail(..., fail_silently=False)` so any email backend failure (e.g. SMTP not configured, invalid from_email) raised an exception.
- **Fix:** In `userauth/views.py` password_reset view: use `fail_silently=True`, wrap `send_mail` in try/except and log; derive `from_email` safely (DEFAULT_FROM_EMAIL or EMAIL_FROM_ADDRESS or fallback). User is always redirected to “check your email” so behaviour is consistent.

### 5.3 OTP (phone verification) not received or request fails

- **Symptom:** User clicks “Send new code” but never gets the code, or the request fails.
- **Cause:** OTP was sent only via Celery task. If Celery wasn’t running or the task failed, no code was delivered. Task `.delay()` could also raise if the broker was unreachable.
- **Fix:** In `userauth/views.py` send_phone_otp_view: send the **OTP email synchronously** when the user has an email (`_send_phone_otp_email_sync`), so the user always gets the code by email even without Celery/Twilio. The Celery task is still called with `recipient_email=None` so it only sends SMS (no duplicate email). Task call is in try/except so queue failures don’t break the request. Rate limit on “Send new code” (10/h per IP). `@csrf_protect` added to phone_verify view.

### 5.4 Shareable link QR code not showing

- **Symptom:** QR code section empty on the shareable link page.
- **Cause:** `qr.make_image(fill_color='black', back_color='white')` requires the PIL image factory. Without `qrcode[pil]` (or if the default factory doesn’t support those args), it raised and the exception was swallowed.
- **Fix:** In `voting/views.py` shareable_link view use `qr.make_image()` with no arguments (works with or without PIL). Log any exception. Template only shows the QR block when `qr_code_image` is non-empty.

### 5.5 Forgot password “complete” page showed wrong content

- **Symptom:** After setting a new password, user saw “check your email” instead of “password reset complete”.
- **Cause:** The URL `password-reset/complete/` was wired to the same view as `password-reset/done/` (both rendered the “done” template).
- **Fix:** Separate views: `password_reset_done` (check your email) and `password_reset_complete` (password set, can log in). After a successful SetPasswordForm save, redirect to `password_reset_complete`. Both redirects (after submit email and after set password) use redirect() so the URL bar matches the page.

### 5.6 Internationalization (LOCALE_PATHS typo)

- **Symptom:** Translations not found or settings error.
- **Cause:** Setting was named `LOCAL_PATHS` instead of `LOCALE_PATHS`, and it must be a list.
- **Fix:** Use `LOCALE_PATHS = [BASE_DIR / 'locale']`. Add i18n context processor; LocaleMiddleware after SessionMiddleware; language cookie settings; `set_language` URL and footer switcher (see “What works” above).

### 5.7 Other lessons (from tasks/lessons.md)

- Vote model: must call `encrypt_selections()` before save; build vote in memory then save once.
- Use `ballot.candidates` (not `candidate_set`) for ballot candidates.
- Definition sealing: add_ballot / delete_ballot / create_candidate rejected when `is_definition_sealed(status)`; at least one ballot required before scheduled/active.
- Status transitions live in `voting/workflow.py` only.
- Voter must not access management views: `@require_not_voter` on those views.
- Pagination and “Create election” for org_admin on election list (see todo.md completed summary).

---

## 6. Deployment and build

- **Platform used:** Railway (Nixpacks builder, region e.g. us-west1).
- **Build:** Nixpacks runs `pip install` (from Pipfile) and, per `nixpacks.toml`, `python manage.py collectstatic --noinput` during the image build. No Dockerfile in repo; Nixpacks generates the image.
- **Start command:** `python manage.py migrate --noinput && gunicorn engine.wsgi:application --bind 0.0.0.0:$PORT`.
- **Env vars (production):** `DEBUG=False`, `SECRET_KEY`, `ENCRYPTION_KEY` (Fernet), `DATABASE_URL`, `ALLOWED_HOSTS`. Optional: email (EMAIL_HOST_USER, EMAIL_HOST_PASSWORD), Twilio (for SMS), Redis/Celery.
- **Build failure log:** If you see a JSON log (e.g. `logs.*.json`) with `ImproperlyConfigured: ENCRYPTION_KEY` during the step that runs `collectstatic`, the fix is the collectstatic exception in §5.1. Ensure `ENCRYPTION_KEY` is set in the **runtime** environment (not only build, if the platform separates them).

See **DEPLOY.md** (root) and **RUNBOOK.md** for the full checklist and recovery.

---

## 7. Auth and email flows

- **Password reset:** Form (email) → redirect to done → user clicks link in email → set new password form → redirect to complete. All use same card UI and safe from_email / fail_silently so the request doesn’t fail on email errors.
- **Phone OTP:** User must have a phone number on profile. “Send new code” (or “Verify phone”) → OTP generated and saved; email sent synchronously if user has email; SMS queued via Celery (optional). User enters code on phone_verify page; on success, `phone_verified=True` and redirect to dashboard or to pending ballot (`vote_after_mfa` session) or `login_next`. Rate limit 10/h per IP on send code.
- **MFA (TOTP):** Separate from phone OTP. Setup and verify in userauth (mfa_setup, mfa_verify). Elections can require `phone_verified` and/or MFA depending on `election.require_mfa` and voter state.

If “request fails” on any of these, check: (1) email backend and from_email (password reset, OTP email); (2) Celery/broker only for SMS, not for OTP email (OTP email is sync now); (3) ENCRYPTION_KEY at runtime for vote encryption.

---

## 8. How to continue

### First steps

1. **Read** this file, then **RUNBOOK.md** and **tasks/lessons.md**.
2. **Setup:** Clone, `pip install` (or pipenv), copy `.env.example` to `.env`, set `SECRET_KEY` and optionally `ENCRYPTION_KEY`, run migrations. For dev users: `python manage.py create_role_credentials` (see AUTH_CREDENTIALS.md).
3. **Run tests:** `python manage.py test`; workflow/definition tests: `python manage.py test voting.tests.WorkflowTests voting.tests.DefinitionSealedAndValidationTests voting.tests.DAGValidationTests`. If you use pytest for test_system: `pytest test_system.py` with conftest and `@pytest.mark.django_db`.
4. **Run app:** `python manage.py runserver`. Optional: Redis and Celery for background tasks (invite emails, share link SMS, OTP SMS).

### When fixing a bug

- Reproduce, then check **tasks/lessons.md** and this report for similar past issues.
- After fixing, add an entry to **tasks/lessons.md** (what happened, root cause, fix) so the next person benefits.

### When adding a feature

- Check **PRD.md** and **tasks/todo.md** for scope and acceptance criteria.
- Use the existing design system (tokens, card, buttons) and existing patterns (e.g. redirect with message, rate limit on sensitive actions).

### Key files to touch by area

| Area | Main files |
|------|------------|
| Election state, transitions | `voting/workflow.py`, `voting/views.py` (status change, eligibility) |
| Vote casting, encryption | `voting/views.py` (_vote_ballot_impl, _parse_vote_selections), `voting/models.py` (Vote, encrypt/decrypt) |
| Auth, password reset, OTP | `userauth/views.py`, `userauth/models.py` (CustomUser, verify_phone_otp, generate_phone_otp) |
| Invite / share link | `voting/views.py` (invite_voters, shareable_link), `voting/tasks.py` (send_voter_invite_notification, send_share_link_to_recipients) |
| Results, proportional | `voting/views.py` (ballot_results), `voting/models.py` (ElectionResult.calculate_results), `voting/proportional.py` |
| Settings, deploy | `engine/settings.py`, `nixpacks.toml`, DEPLOY.md |

---

**End of report.** For living updates, keep **tasks/lessons.md** and **RUNBOOK.md** in sync with changes and incidents.
