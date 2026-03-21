# Test User Credentials

## 🔑 Login Credentials

All test users use the same password: **`devpass123`**

### 👤 User Roles

| Role | Email | Permissions | Tenant |
|------|-------|-------------|---------|
| **Super Admin** | `superadmin@vault.dev` | Full system access | Global |
| **Election Admin** | `electionadmin@vault.dev` | Create/manage elections | Test Organization |
| **Organization Admin** | `orgadmin@vault.dev` | Manage organization | Test Organization |
| **Monitor** | `monitor@vault.dev` | Monitor elections | Global |
| **Auditor** | `auditor@vault.dev` | Audit logs & compliance | Global |
| **Voter** | `voter@vault.dev` | Vote in elections | Global |

## 🏢 Test Organization

- **Name**: Test Organization
- **Slug**: `test-org`
- **Plan**: Pro
- **Billing Email**: `admin@testorg.dev`

## 🚀 Quick Start

### 1. Super Admin Access
```bash
# Login as Super Admin
Email: superadmin@vault.dev
Password: devpass123
```

### 2. Run Management Command
```bash
# Create/reset test users
python manage.py create_test_users

# Reset existing users
python manage.py create_test_users --reset

# Custom password
python manage.py create_test_users --password "custom123"
```

## 📋 Role Permissions

### Super Admin
- ✅ Full system administration
- ✅ Manage all users
- ✅ Create organizations
- ✅ System configuration
- ✅ Access to all features

### Election Admin
- ✅ Create elections
- ✅ Manage ballots
- ✅ Add candidates
- ✅ View results
- ✅ Limited to organization

### Organization Admin
- ✅ Manage organization settings
- ✅ Manage organization users
- ✅ Create elections
- ✅ View organization analytics

### Monitor
- ✅ View active elections
- ✅ Monitor voting progress
- ✅ View public results
- ✅ Limited administrative access

### Auditor
- ✅ Access audit logs
- ✅ Review compliance
- ✅ Generate reports
- ✅ Read-only access to sensitive data

### Voter
- ✅ Vote in eligible elections
- ✅ View voting history
- ✅ Manage profile
- ✅ Standard user features

## 🔧 Test Data

### Voter Details
- **Voter ID**: VOTER001
- **Citizenship**: US
- **Eligibility**: Verified
- **Registration**: Complete

### Organization Structure
```
Test Organization
├── Election Admin (electionadmin@vault.dev)
└── Organization Admin (orgadmin@vault.dev)
```

## 🌐 Access URLs

### Local Development
- **Main App**: http://localhost:8000/
- **Admin Panel**: http://localhost:8000/admin/
- **API**: http://localhost:8000/api/

### Production
- **Main App**: https://your-domain.com/
- **Admin Panel**: https://your-domain.com/admin/
- **API**: https://your-domain.com/api/

## 🛠️ Management Commands

### Available Options
```bash
# Default setup (creates users if they don't exist)
python manage.py create_test_users

# Reset all test users (delete and recreate)
python manage.py create_test_users --reset

# Custom password
python manage.py create_test_users --password "yourpassword"

# Help
python manage.py create_test_users --help
```

## 🔒 Security Notes

- ⚠️ **For development/testing only**
- 🔐 All users share the same password
- 🚫 Do not use in production
- 📝 Consider changing passwords for demos
- 🔑 MFA is disabled for all test users

## 📞 Support

If you encounter issues:
1. Check Django settings
2. Verify database connection
3. Run migrations: `python manage.py migrate`
4. Reset with `--reset` flag if needed

---

*Generated on: $(date)*
*Environment: Development*
