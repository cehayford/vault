# Operations runbook

Minimal runbook for deployment, recovery, and common operations. Aligned with Workflow Orchestration & Engineering Standards (persistence, recovery, DR).

---

## Pre-deploy checklist

- [ ] Run full test suite: `python manage.py test`
- [ ] Run workflow/DAG/definition-sealed validation: `python manage.py test voting.tests.WorkflowTests voting.tests.DefinitionSealedAndValidationTests voting.tests.DAGValidationTests`
- [ ] Migrations applied: `python manage.py migrate`
- [ ] Collect static (if applicable): `python manage.py collectstatic --noinput`
- [ ] Environment: `DEBUG=False`, strong `SECRET_KEY`, `ENCRYPTION_KEY` (Fernet), DB and Redis URLs set. Note: `collectstatic` runs at build time without `ENCRYPTION_KEY`; the key is required at runtime only.

---

## Key services

| Service | Role |
|--------|------|
| Django (WSGI/ASGI) | Web app; election and vote handling |
| PostgreSQL (or SQLite dev) | Primary data; elections, votes, audit |
| Redis | Cache, Celery broker (if used) |
| Celery worker | Background tasks (e.g. email, notifications) |

---

## Recovery

- **Database:** Restore from latest backup; run migrations if needed. Point app at restored DB.
- **Secrets:** Rotate `SECRET_KEY` and any API keys if a breach is suspected; update env and restart app.
- **Audit trail:** Security and vote-related events are in `userauth.SecurityLog` and vote/receipt models; do not modify.

---

## Health checks

- **App root:** `GET /` (userauth home; expect 200 or redirect).
- **Voting dashboard:** `GET /voting/` (expect 200 when authenticated, or redirect to login).
- **Status page (authenticated):** `GET /voting/status/` — account and election summary.
- **Admin:** `GET /admin/` and `GET /voting/admin/` (role-dependent).

---

## Troubleshooting

- **500 when submitting a vote:** Usually caused by a missing or invalid `ENCRYPTION_KEY` in production. Votes are encrypted with Fernet; the key must be set and valid. Generate one: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and set it as the `ENCRYPTION_KEY` environment variable. With the fix in place, the app will refuse to start in production without a valid key, and the vote view will show a friendly error if encryption still fails.

## Escalation

- Review `tasks/lessons.md` for known issues and fixes.
- Check audit logs and application logs for errors and security events.
