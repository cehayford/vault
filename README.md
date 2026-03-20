# Vault

Vault is a Django-based secure voting platform for creating elections, managing ballots and candidates, inviting voters, collecting encrypted votes, and publishing verifiable results.

The codebase includes:

- Authentication with email verification, MFA, phone OTP, and security logging
- Election management for single choice, multiple choice, ranked choice, and proportional voting
- Invite-only and share-link voting flows
- Audit trails, vote receipts, and background notifications

## Core Roles

| Role | Main responsibility |
| --- | --- |
| `voter` | Vote in eligible elections, manage profile, verify receipts |
| `election_admin` | Create elections, add ballots/candidates, invite voters, manage results |
| `org_admin` | Manage organization-scoped election activity |
| `monitor` | Read-only monitoring access |
| `auditor` | Read-only audit and compliance access |
| `super_admin` | Platform-wide administration and governance |

## Main Workflows

### Election admins

1. Create an election
2. Add ballots
3. Add candidates
4. Invite voters or generate share links
5. Open voting and review results

### Voters

1. Sign in and verify account details
2. Open an invited or active election
3. Cast a vote on each ballot
4. Receive a receipt code
5. Verify participation later without exposing selections

### Platform operators

1. Review audit logs
2. Manage users and roles
3. Monitor election status and system health

## Project Layout

```text
engine/      Django settings, URL routing, middleware
userauth/    Authentication, MFA, phone verification, user profile, security logs
voting/      Elections, ballots, candidates, voting flows, results, background tasks
nominee/     Supplemental nominee-related views/models
templates/   HTML templates
static/      CSS, icons, frontend assets
docs/        Runbook, test users, auth credentials, handover and workflow notes
```

## Quick Start

### 1. Install dependencies

Preferred:

```bash
pipenv install
```

Alternative:

```bash
pip install -r requirements.txt
```

### 2. Create a local environment file

```bash
cp .env.example .env
```

Minimum values to review before running:

- `SECRET_KEY`
- `DEBUG`
- `ENCRYPTION_KEY`
- `EMAIL_*`
- `TWILIO_*`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

Generate a valid Fernet key for vote encryption:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Apply migrations

```bash
pipenv run python manage.py migrate
```

### 4. Create demo users

For local development, create the repo's `@vault.dev` users:

```bash
pipenv run python manage.py create_test_users
```

Default password:

```text
devpass123
```

Reference: [docs/TEST_USERS.md](docs/TEST_USERS.md)

### 5. Run the app

```bash
pipenv run python manage.py runserver
```

Useful entry points:

- `/`
- `/login/`
- `/profile/`
- `/voting/`
- `/voting/admin/`

## Optional Services

### Redis and Celery

Redis and Celery are recommended for production and useful locally when you want background notifications and scheduled work enabled.

Start a worker with:

```bash
pipenv run celery -A celery_app worker -l info
```

Notes:

- `PHONE_OTP_SYNC_SEND=True` lets phone OTP work without Celery
- Invite notifications and other async features are more reliable with Redis + Celery running
- Redis URLs must include credentials if your provider requires authentication

## Configuration Notes

### Vote encryption

Votes are encrypted with Fernet before being stored. A missing or invalid `ENCRYPTION_KEY` will break vote submission.

### Email

Email is used for account verification, password reset, invites, and OTP fallback delivery.

### Twilio

Twilio is used for SMS delivery. On a Twilio trial account, messages to unverified numbers will fail.

### Redis

The app reads Redis/Celery configuration from environment values in `engine/settings.py`. If Redis Cloud or Redis Enterprise is used, provide the full authenticated URL, for example:

```text
redis://default:<password>@host:port/0
```

Or TLS:

```text
rediss://default:<password>@host:port/0
```

## Testing

Run the default Django test suite:

```bash
pipenv run python manage.py test
```

Targeted examples:

```bash
pipenv run python manage.py test userauth.tests
pipenv run python manage.py test voting.tests
```

Generate demo data:

```bash
pipenv run python manage.py generate_test_data --voters 1000 --elections 5
```

## API

The repo includes a DRF router for election read APIs:

- `/voting/api/v1/elections/`

For the full web flow, most user-facing functionality is implemented through Django views and templates rather than a large standalone REST API surface.

## Operations and Docs

Use the `docs/` directory for deeper project guidance:

- [docs/RUNBOOK.md](docs/RUNBOOK.md) - deployment, recovery, health checks
- [docs/TEST_USERS.md](docs/TEST_USERS.md) - local demo users
- [docs/AUTH_CREDENTIALS.md](docs/AUTH_CREDENTIALS.md) - role credential command and defaults
- [docs/WORKFLOW_AND_QUALITY.md](docs/WORKFLOW_AND_QUALITY.md) - workflow and engineering guardrails
- [docs/PROJECT_AND_FAILURE_REPORT.md](docs/PROJECT_AND_FAILURE_REPORT.md) - handover and known issues

## Security Notes

- Do not commit `.env`, logs, database files, or provider credentials
- Do not use default demo passwords outside local development
- Use a valid `ENCRYPTION_KEY` in every non-trivial environment
- Set `DEBUG=False` in production
- Run Redis and Celery in production for background task reliability

## License

This repository references an MIT-style setup in prior docs, but verify the current license file in the branch before distributing or publishing the project.
