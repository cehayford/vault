# Authentication credentials (dev/demo)

Predefined users for each application role, for local development and demos. **Do not use these in production.**

---

## How to create the users

Run the management command (creates or updates one user per role with the same password):

```bash
python manage.py create_role_credentials
```

Optional: set password via env or flag:

```bash
python manage.py create_role_credentials --password mysecret
# or
DEV_PASSWORD=mysecret python manage.py create_role_credentials
```

Default password when not set: **`devpass123`**.

---

## Role credentials

| Role            | Email                      | Default password | Capabilities |
|-----------------|----------------------------|------------------|--------------|
| **Super Admin** | `super_admin@example.com` | `devpass123`     | Full platform access; create/edit/delete any election; admin dashboard; audit logs; manage tenants. |
| **Election Admin** | `election_admin@example.com` | `devpass123`  | Create and manage elections (no org scope); invite voters; export results. |
| **Org Admin**   | `org_admin@example.com`   | `devpass123`     | Create organisations; manage org elections and members; create elections for their orgs. |
| **Voter**       | `voter@example.com`       | `devpass123`     | View elections; cast votes; view own votes and profile. No CRUD on elections/ballots/candidates. |
| **Auditor**     | `auditor@example.com`     | `devpass123`     | Read-only audit logs (filter and paginate). No write access. |
| **Monitor**     | `monitor@example.com`     | `devpass123`     | Read-only monitoring role (see PRD for observability). |

All dev users are created with:

- `is_verified=True`
- `citizenship_country=US` (voter is eligible where citizenship is required)
- `is_active=True`

---

## Login

1. Run `python manage.py create_role_credentials` if you have not already.
2. Open the app login page (e.g. `/userauth/login/` or `/accounts/login/`).
3. Use **Email** = one of the addresses above, **Password** = `devpass123` (or the value you passed to the command).

---

## Production

- **Do not** use these emails or the default password in production.
- Create real users via your auth flow (registration, SSO, or admin) and assign roles as needed.
- Use strong, unique passwords and MFA for admin and auditor accounts.

---

*Generated for the Vault secure voting project. See PRD and CONTRIBUTING for role definitions.*
