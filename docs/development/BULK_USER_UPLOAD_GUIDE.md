# Bulk User Upload Guide

## Overview
Price Scout supports bulk user import via CSV or Excel files, making it easy to onboard multiple users at once.

## Template Files

### CSV Template: `bulk_user_upload_template.csv`
### Excel Template: `bulk_user_upload_template.xlsx`

Both templates contain the same structure with example data.

## Column Definitions

| Column | Required | Valid Values | Example | Notes |
|--------|----------|--------------|---------|-------|
| **username** | ✅ Yes | Any unique string | `jsmith` | Must be unique across all users |
| **password** | ✅ Yes | 8+ chars, uppercase, lowercase, number, special | `SecurePass123!` | Must meet complexity requirements |
| **role** | ✅ Yes | `admin`, `manager`, `user` | `manager` | Determines access permissions |
| **company** | ❌ No | Company name from your database | `AMC`, `Marcus` | Leave blank for admin users |
| **default_company** | ❌ No | Company name from your database | `AMC`, `Marcus` | Company shown on login |
| **home_location_type** | ❌ No | `none`, `director`, `market`, `theater` | `market` | User's default location filter |
| **home_location_value** | ❌ No | Location string | `Dallas > Dallas Metro` | Format depends on type (see below) |

## Home Location Formats

Home location allows users to automatically filter to their assigned region.

### Director Level
- **Format**: `Director Name`
- **Example**: `Dallas`
- **Effect**: User sees all markets/theaters under this director

### Market Level
- **Format**: `Director Name > Market Name`
- **Example**: `Dallas > Dallas Metro`
- **Effect**: User sees all theaters in this market

### Theater Level
- **Format**: `Director Name > Market Name > Theater Name`
- **Example**: `Milwaukee > Milwaukee Metro > Marcus Cinema`
- **Effect**: User sees only this specific theater

### None
- **Format**: Leave both `home_location_type` and `home_location_value` blank or set to `none`
- **Effect**: User has access to all locations in their company

## Password Requirements

All passwords must meet these requirements:
- ✅ Minimum 8 characters
- ✅ At least one uppercase letter (A-Z)
- ✅ At least one lowercase letter (a-z)
- ✅ At least one number (0-9)
- ✅ At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)

**Valid Examples**:
- `SecurePass123!`
- `Welcome2024@`
- `MyP@ssw0rd`

**Invalid Examples**:
- `password` (no uppercase, number, or special char)
- `Password` (no number or special char)
- `Pass123` (too short, no special char)

## Role Descriptions

### Admin
- Full access to all modes
- Can manage users, roles, and companies
- Can access all company data
- **Company fields**: Leave blank or set to specific company

### Manager
- Access to operational modes
- Can view and manage theater data
- Limited admin capabilities
- **Company fields**: Must assign to a company

### User
- Basic operational access
- Can view reports and run scrapes
- No admin access
- **Company fields**: Must assign to a company

## Example CSV File

```csv
username,password,role,company,default_company,home_location_type,home_location_value
jsmith,SecurePass123!,manager,AMC,AMC,market,Dallas > Dallas Metro
bdoe,AnotherPass456!,user,Marcus,Marcus,theater,Milwaukee > Milwaukee Metro > Marcus Cinema
admin2,AdminPass789!,admin,,,none,
testuser,TestPass999!,user,AMC,AMC,director,Dallas
regional_mgr,Manager2024!,manager,Marcus,Marcus,director,Milwaukee
```

## How to Use

### Step 1: Prepare Your File

1. **Download the template**:
   - CSV: `bulk_user_upload_template.csv`
   - Excel: `bulk_user_upload_template.xlsx`

2. **Fill in your users**:
   - Delete the example rows
   - Add your real user data
   - Ensure all required columns are filled
   - Verify passwords meet requirements

3. **Verify company names**:
   - Use exact company names from your Price Scout database
   - Company names are case-sensitive
   - Check Admin page to see available companies

### Step 2: Upload via Admin Interface

1. **Login as admin**
2. **Navigate to Admin page**
3. **Find "Bulk Import Users" section**
4. **Click "Upload Users CSV/Excel"**
5. **Select your file**
6. **Review the preview**
7. **Click "Import Users"**

### Step 3: Verify Import

The system will display:
- ✅ Number of users successfully imported
- ❌ Any errors encountered with details

Check the User Management section to verify all users were created correctly.

## Error Messages

### Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| "Username already exists" | Duplicate username in database | Use unique usernames |
| "Password does not meet requirements" | Weak password | Use 8+ chars with complexity |
| "Invalid role" | Role not in [admin, manager, user] | Use only valid roles |
| "Company not found" | Company name doesn't exist | Check exact company name |
| "Invalid home location format" | Wrong format for location type | Follow format examples above |
| "Missing required field" | username or password blank | Fill all required fields |

## Tips & Best Practices

### 1. Start Small
- Test with 2-3 users first
- Verify they import correctly
- Then import larger batches

### 2. Use Template
- Always start from the provided template
- Don't remove or reorder columns
- Column headers must match exactly

### 3. Password Management
- Generate secure passwords using a password manager
- Don't reuse passwords across users
- Consider forcing password change on first login

### 4. Company Assignment
- Verify company names in Admin page first
- Use copy-paste to avoid typos
- Company names are case-sensitive

### 5. Home Locations
- Start with `none` if unsure
- Admins can update individual users later
- Use exact location names from your markets.json

### 6. Excel vs CSV
- Excel: Better for editing, preserves formatting
- CSV: Simpler, works with any text editor
- Both produce same result

## Bulk Update Existing Users

To update existing users in bulk:

1. **Export current users** (if feature available) or manually document
2. **Create CSV/Excel** with same usernames
3. **Include new values** for fields you want to update
4. **Upload file** - system will update existing users

**Note**: Usernames cannot be changed via bulk update. To rename a user, use the individual user editor.

## Security Notes

⚠️ **Important Security Considerations**:

1. **Protect the upload file**
   - Contains plaintext passwords
   - Delete after import
   - Don't email or share publicly

2. **Initial passwords**
   - Use temporary passwords
   - Force users to change on first login
   - Document password requirements

3. **Access control**
   - Only admins can bulk import
   - All imports are logged
   - Review imported users immediately

4. **Password storage**
   - Passwords are bcrypt-hashed immediately
   - Plain text never stored in database
   - Upload file can be safely deleted after import

## Troubleshooting

### Import fails with no error message
- Check file encoding (should be UTF-8)
- Verify CSV uses comma separators
- Ensure no extra blank rows at end

### Some users import, others fail
- Review error messages for each failed user
- Fix issues and re-run import for failed users only
- Successfully imported users won't be duplicated

### Special characters in usernames/passwords
- Ensure CSV is UTF-8 encoded
- Avoid quotes, commas, and newlines in usernames
- Special characters in passwords are fine

### Home location not working
- Verify exact spelling of director/market/theater
- Check your markets.json file for correct names
- Use the format: `Director > Market > Theater`

## Advanced Features

### CSV Generation from Existing Systems

If you have user data in another system (HR database, Active Directory, etc.), you can export to CSV and format it to match this template.

**Example Python script**:
```python
import pandas as pd

# Read your existing user data
existing_users = pd.read_csv('hr_users.csv')

# Transform to Price Scout format
pricescout_users = pd.DataFrame({
    'username': existing_users['employee_id'],
    'password': 'Welcome2024!',  # Default password
    'role': existing_users['job_title'].map({
        'Theater Manager': 'manager',
        'Regional Director': 'admin',
        'Staff': 'user'
    }),
    'company': 'AMC',
    'default_company': 'AMC',
    'home_location_type': 'theater',
    'home_location_value': existing_users['assigned_theater']
})

# Save to Price Scout template format
pricescout_users.to_csv('bulk_user_upload_template.csv', index=False)
```

## Support

If you encounter issues:
1. Check this guide for common solutions
2. Verify template format matches exactly
3. Test with small batch first
4. Contact your Price Scout administrator

## Template Download

Templates are located in the Price Scout root directory:
- `bulk_user_upload_template.csv`
- `bulk_user_upload_template.xlsx`

Both can be opened and edited in Microsoft Excel, Google Sheets, or any CSV editor.

---

**Version**: 1.0.0
**Last Updated**: 2025-11-06
