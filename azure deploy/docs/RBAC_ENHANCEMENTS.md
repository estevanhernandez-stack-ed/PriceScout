# RBAC System Enhancements

## Overview
The Role-Based Access Control (RBAC) system has been redesigned for simplicity and centralized management. Mode permissions are now configured per role (not per user), making it easier to manage access across your organization.

## Key Features

### 1. **Role-Based Mode Permissions**
- Configure which modes each role can access **once**
- Changes apply to all users with that role automatically
- No need to set permissions for each individual user
- Located at the top of the Admin Page

### 2. **Three User Roles**
- **Admin**: Full system access (default: all 8 modes)
- **Manager**: Theater operations (default: 5 modes - no Admin, Data Management, Theater Matching)
- **User**: Basic functionality (default: 3 modes - Market Mode, CompSnipe Mode, Poster Board)

### 3. **Bulk User Import**
Upload a JSON file to create multiple users at once

**Example JSON format** (`example_users.json`):
```json
{
  "users": [
    {
      "username": "jsmith",
      "password": "SecurePass123!",
      "role": "manager",
      "company": "AMC",
      "default_company": "AMC"
    },
    {
      "username": "bdoe",
      "password": "AnotherPass456!",
      "role": "user",
      "company": "Marcus",
      "default_company": "Marcus"
    }
  ]
}
```

**Required fields:**
- `username` - User login name
- `password` - Initial password (must meet complexity requirements)
- `role` - "admin", "manager", or "user"

**Optional fields:**
- `company` - Assigned company (null for all companies)
- `default_company` - Default company on login (null for all companies)

## Admin Page Layout

The Admin Page now has 5 sections in this order:

1. **Role Permissions** - Configure modes for each role (NEW)
2. **Bulk Import Users** - Upload JSON file to create multiple users (NEW)
3. **User Management** - View and edit existing users (SIMPLIFIED - no per-user modes)
4. **Add New User** - Create single user (SIMPLIFIED)
5. **Company Management** - Delete company data (UNCHANGED)

## How It Works

### Setting Up Role Permissions

1. Go to Admin Page
2. In the "Role Permissions" section at the top, you'll see three columns:
   - **Admin Role**: Select which modes admins can access
   - **Manager Role**: Select which modes managers can access
   - **User Role**: Select which modes regular users can access
3. Click "Save Role Permissions"
4. Changes apply immediately to all users with that role

**Note**: Role permissions are stored in `role_permissions.json` in your project directory.

### Adding Individual Users

1. Scroll to "Add New User" section
2. Enter username, password, and select role
3. Assign company (optional)
4. Click "Add User"
5. User automatically gets the modes configured for their role

### Bulk Importing Users

1. Create a JSON file following the `example_users.json` format
2. Go to Admin Page → "Bulk Import Users" section
3. Click "Upload Users JSON"
4. Select your JSON file
5. Review the preview
6. Click "Import Users"
7. System will report how many succeeded and any errors

### Managing Existing Users

The user management table now shows:
- Username (editable)
- Role (changeable - modes update automatically)
- Company
- Default Company
- Update/Delete buttons

**Removed**: Per-user mode selection (modes are now role-based)

## Migration from Old System

If you have existing users with individual mode permissions:
- Run `update_user_modes.py` to migrate them to role-based permissions
- Old `allowed_modes` column is no longer used
- Users will get modes based on their role from `role_permissions.json`

## Benefits

✅ **Simpler management** - Set permissions once per role, not per user  
✅ **Consistency** - All users with same role have same permissions  
✅ **Bulk operations** - Import many users at once from JSON  
✅ **Cleaner UI** - Removed complex per-user mode selection dropdowns  
✅ **Easier onboarding** - New users automatically get correct permissions  
✅ **Audit trail** - Role permission changes are logged

## Available Sidebar Modes

1. **Market Mode** - View market pricing
2. **Operating Hours Mode** - Theater hours management
3. **CompSnipe Mode** - Competitive analysis
4. **Historical Data and Analysis** - Historical trends
5. **Data Management** - Data import/export (typically admin only)
6. **Theater Matching** - Theater configuration (typically admin only)
7. **Admin** - User and system management (admin only)
8. **Poster Board** - Movie poster display

## Security

- All user creation/modification is logged via `security_config.py`
- Role permission changes are logged
- Bulk imports validate all fields before creating users
- Password complexity requirements still enforced
- Failed bulk imports provide detailed error messages

## Files

- `role_permissions.json` - Central role permission configuration
- `example_users.json` - Template for bulk user import
- `app/users.py` - Enhanced with `load_role_permissions()`, `save_role_permissions()`, `bulk_import_users()`
- `app/admin.py` - Redesigned UI with role permissions and bulk import sections
