# Role-Based Access Control (RBAC) System - Price Scout

**Implementation Date:** October 26, 2025  
**Version:** 3.0.0  
**Status:** ✅ Production Ready

---

## Overview

Price Scout implements a three-tier role-based access control system to enforce the principle of least privilege and provide granular permissions for different user types.

---

## User Roles

### 1. Admin Role
**Role ID:** `admin`  
**Allowed Modes:** `["Corp", "DD", "AM", "User"]`

**Capabilities:**
- ✅ Full system access
- ✅ User management (create, update, delete users)
- ✅ Role and permission management
- ✅ Access to admin panel
- ✅ All theater management modes (Corp, DD, AM)
- ✅ User mode access
- ✅ Company data management
- ✅ Configuration changes

**Use Cases:**
- System administrators
- IT staff
- Application owners

---

### 2. Manager Role (NEW)
**Role ID:** `manager`  
**Allowed Modes:** `["Corp", "DD", "AM"]`

**Capabilities:**
- ✅ Corporate theater management (Corp mode)
- ✅ District Director functions (DD mode)
- ✅ Area Manager functions (AM mode)
- ❌ No admin panel access
- ❌ Cannot create/modify users
- ❌ Cannot access User mode (restricted to management modes)

**Use Cases:**
- Corporate managers
- District Directors
- Area Managers
- Operations staff
- Business users managing multiple theaters

**Key Restriction:** Managers have elevated access to theater data but cannot perform administrative functions or access the basic user interface.

---

### 3. User Role
**Role ID:** `user`  
**Allowed Modes:** `["User"]`

**Capabilities:**
- ✅ User mode access (search, view pricing)
- ✅ Basic theater information lookup
- ✅ Price comparison tools
- ❌ No admin panel access
- ❌ Cannot create/modify users
- ❌ Cannot access Corp/DD/AM modes

**Use Cases:**
- Standard users
- External users
- Viewers
- Auditors (read-only access)

---

## Permission Matrix

| Feature / Mode | Admin | Manager | User |
|---------------|-------|---------|------|
| **Admin Panel** | ✅ | ❌ | ❌ |
| **User Management** | ✅ | ❌ | ❌ |
| **Role Management** | ✅ | ❌ | ❌ |
| **Corp Mode** | ✅ | ✅ | ❌ |
| **DD Mode** | ✅ | ✅ | ❌ |
| **AM Mode** | ✅ | ✅ | ❌ |
| **User Mode** | ✅ | ❌ | ✅ |
| **Market Mode** | ✅ | ❌ | ✅ |
| **Analysis Mode** | ✅ | ❌ | ✅ |
| **Poster Lookup** | ✅ | ❌ | ✅ |

---

## Technical Implementation

### Database Schema

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT 0,      -- Legacy field (synced with role)
    role TEXT DEFAULT 'user',                  -- 'admin', 'manager', or 'user'
    allowed_modes TEXT DEFAULT '["User"]',    -- JSON array of mode names
    company TEXT,
    default_company TEXT
);
```

### Role Constants (app/users.py)

```python
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_USER = "user"

VALID_ROLES = [ROLE_ADMIN, ROLE_MANAGER, ROLE_USER]

ALL_MODES = ["Corp", "DD", "AM", "User"]
MANAGER_MODES = ["Corp", "DD", "AM"]
USER_MODES = ["User"]
```

### Permission Helper Functions

```python
# Get user's role
role = users.get_user_role(username)
# Returns: 'admin', 'manager', 'user', or None

# Get allowed modes
modes = users.get_user_allowed_modes(username)
# Returns: ['Corp', 'DD', 'AM', 'User'] or subset

# Check specific mode access
can_access = users.user_can_access_mode(username, 'Corp')
# Returns: True or False

# Role checks
is_admin = users.is_admin(username)
is_manager = users.is_manager(username)  # True for admin OR manager
```

---

## User Management UI

### Admin Panel Features

**View All Users:**
- Username
- Role (admin/manager/user)
- Company assignment
- Default company
- Allowed modes (multiselect)

**Create New User:**
1. Enter username and password
2. Select role (admin/manager/user)
3. Assign company (optional)
4. Set default company (optional)
5. Choose allowed modes (defaults based on role, customizable)

**Update Existing User:**
- Change username
- Change role (automatically updates allowed modes)
- Modify company assignments
- Customize allowed modes (override role defaults)

**Delete User:**
- Remove user from system
- Security event logged

---

## Security Features

### 1. Security Event Logging
All role and permission changes are logged:

```json
{
  "timestamp": "2025-10-26T12:00:00",
  "event_type": "user_created",
  "username": "john.manager",
  "details": {
    "role": "manager",
    "allowed_modes": ["Corp", "DD", "AM"]
  }
}

{
  "timestamp": "2025-10-26T12:05:00",
  "event_type": "user_updated",
  "username": "john.manager",
  "details": {
    "role": "manager",
    "allowed_modes": ["Corp", "AM"]
  }
}
```

### 2. Mode Access Enforcement

The sidebar only shows modes the user can access:

```python
# In render_sidebar_modes()
user_allowed_modes = users.get_user_allowed_modes(username)

for mode in all_modes:
    if mode not in user_allowed_modes:
        continue  # Don't show button
```

### 3. Backwards Compatibility

The `is_admin` flag is automatically synced with role:
- `role='admin'` → `is_admin=True`
- `role='manager'` → `is_admin=False`
- `role='user'` → `is_admin=False`

Existing code that checks `is_admin` continues to work.

---

## Migration Guide

### Automatic Migration

When `users.init_database()` runs, it automatically:

1. **Adds new columns** if they don't exist:
   - `role` (TEXT, default 'user')
   - `allowed_modes` (TEXT, default '["User"]')

2. **Migrates existing users:**
   - Users with `is_admin=1` → `role='admin'`, `allowed_modes='["Corp","DD","AM","User"]'`
   - Users with `is_admin=0` → `role='user'`, `allowed_modes='["User"]'`

3. **No data loss** - All existing users are preserved

### Manual User Updates

To upgrade an existing user to manager:

```python
from app import users

# Update via admin panel UI (recommended)
# Or programmatically:
users.update_user(
    user_id=123,
    username="john.manager",
    is_admin=False,
    company="AMC Theatres",
    default_company="AMC Theatres",
    role="manager",
    allowed_modes=["Corp", "DD", "AM"]
)
```

---

## Best Practices

### 1. Principle of Least Privilege
- Start users with minimal permissions (user role)
- Promote to manager only when needed
- Limit admin role to true administrators

### 2. Regular Access Reviews
- Quarterly review of user roles
- Remove users who no longer need access
- Downgrade roles when responsibilities change

### 3. Security Monitoring
Use the security monitor to track:
- Role changes (who, when, what role)
- Failed permission checks
- Unusual access patterns

```bash
python scripts/security_monitor.py --days 30
```

### 4. Custom Permissions
While roles have defaults, you can customize allowed_modes:
- Manager who only handles Corp and DD (not AM)
- Power user who gets Corp access but not DD/AM
- Auditor role with read-only User mode

---

## Troubleshooting

### User Can't Access Expected Mode

**Check:**
1. User's role: `users.get_user_role(username)`
2. Allowed modes: `users.get_user_allowed_modes(username)`
3. Mode in list: `users.user_can_access_mode(username, 'Corp')`

**Fix via Admin Panel:**
1. Log in as admin
2. Navigate to Admin Panel
3. Find user in user list
4. Update "Allowed Modes" multiselect
5. Click "Update"

### Migration Didn't Run

**Force migration:**
```python
from app import users
users.init_database()
```

### Role Shows as None

**Likely cause:** User created before RBAC implementation

**Fix:**
```python
from app import users
users.update_user(user_id, username, is_admin, company, default_company, role='user')
```

---

## Future Enhancements

Potential additions to the RBAC system:

1. **Custom Roles:** Allow admins to create custom roles
2. **Permission Groups:** Group permissions for easier management
3. **Time-Based Access:** Temporary role elevation
4. **IP-Based Restrictions:** Limit certain roles to specific IPs
5. **Two-Factor Authentication:** Require 2FA for admin/manager roles
6. **Audit Mode:** Read-only role with full system visibility

---

## API Reference

### users.py Functions

```python
# Role Management
get_user_role(username: str) -> str | None
get_user_allowed_modes(username: str) -> list[str]
user_can_access_mode(username: str, mode: str) -> bool
is_admin(username: str) -> bool
is_manager(username: str) -> bool

# User CRUD
create_user(username, password, is_admin=False, company=None, 
            default_company=None, role=None, allowed_modes=None)
update_user(user_id, username, is_admin, company, default_company,
            role=None, allowed_modes=None)
get_all_users() -> list[dict]
delete_user(user_id: int)
```

---

**Last Updated:** October 26, 2025  
**Document Version:** 1.0  
**Maintained By:** Price Scout Development Team
