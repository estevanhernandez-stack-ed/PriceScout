# Self-Service Password Reset

## Overview
Users can now reset their passwords without admin intervention using secure, time-limited reset codes.

## Features

### ✅ **Security Features**
- **Time-limited codes**: 15-minute expiration
- **Hashed storage**: Codes are bcrypt-hashed (same security as passwords)
- **Rate limiting**: Maximum 3 attempts per code
- **Auto-expiry**: Codes invalidated after successful use or expiration
- **No user enumeration**: System doesn't reveal if username exists
- **Audit logging**: All reset attempts logged in security.log

### 🔐 **How It Works**

**Step 1: Request Reset Code**
1. Click "🔑 Forgot Password?" on login page
2. Enter your username
3. System generates 6-digit numeric code (e.g., `123456`)
4. Code is valid for **15 minutes**

**Step 2: Reset Password**
1. Enter the 6-digit code
2. Enter new password (must meet complexity requirements)
3. Confirm new password
4. Submit to complete reset

**Password Requirements:**
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)

### 📧 **Production Deployment Note**

**Current Implementation (Development):**
- Reset code is displayed on screen
- User must copy and use immediately

**Production Enhancement (Future):**
Replace the code display with email/SMS delivery:

```python
# In users.py, generate_reset_code() function
# Instead of returning the code, send it via:
# - Email (using SMTP/SendGrid/SES)
# - SMS (using Twilio/SNS)
# - Both (multi-factor)

# Example with email:
import smtplib
from email.mime.text import MIMEText

def send_reset_email(username, reset_code):
    user = get_user(username)
    email = user.get('email')  # Add email column to users table
    
    msg = MIMEText(f"Your password reset code is: {reset_code}\n\nThis code expires in 15 minutes.")
    msg['Subject'] = 'Price Scout - Password Reset Code'
    msg['From'] = 'noreply@yourcompany.com'
    msg['To'] = email
    
    with smtplib.SMTP('smtp.yourprovider.com', 587) as server:
        server.starttls()
        server.login('your_email', 'your_password')
        server.send_message(msg)
```

### 🛡️ **Security Benefits**

1. **No admin bottleneck**: Users reset passwords 24/7 without admin
2. **Time-limited exposure**: Codes expire in 15 minutes
3. **Attempt limiting**: Max 3 wrong codes before invalidation
4. **Cryptographic security**: Codes hashed with bcrypt
5. **Audit trail**: All attempts logged with timestamps
6. **No password transmission**: Reset happens client-side

### 📊 **Rate Limiting**

- **Maximum attempts**: 3 per reset code
- **Code expiration**: 15 minutes
- **Auto-invalidation**: After max attempts or expiry
- **New code generation**: User can request new code anytime

### 🔍 **Security Events Logged**

All password reset activity is logged in `security.log`:

- `password_reset_requested` - User requests reset code
- `password_reset_code_verified` - Valid code entered
- `password_reset_invalid_code` - Wrong code attempted
- `password_reset_max_attempts` - Too many failed attempts
- `password_reset_expired` - Expired code used
- `password_reset_completed` - Password successfully changed

### 📝 **Database Schema**

New columns added to `users` table:

```sql
reset_code TEXT            -- Bcrypt hash of the 6-digit code
reset_code_expiry INTEGER  -- Unix timestamp of expiration
reset_attempts INTEGER     -- Failed verification attempts (max 3)
```

### 🎯 **User Flow**

```
Login Page
    ↓ (Click "Forgot Password?")
Password Reset Request
    ↓ (Enter username)
Reset Code Generated
    ↓ (Display code - or send via email/SMS in production)
Enter Code & New Password
    ↓ (Verify code)
Code Validation (max 3 attempts)
    ↓ (Success)
Password Updated
    ↓ (Auto-redirect)
Login Page
```

### ⚙️ **Configuration**

Edit constants in `app/users.py`:

```python
RESET_CODE_LENGTH = 6              # Length of numeric code
RESET_CODE_EXPIRY_MINUTES = 15     # How long code is valid
RESET_CODE_MAX_ATTEMPTS = 3        # Max verification attempts
```

### 🧪 **Testing**

```python
from app import users

# Generate code
success, code = users.generate_reset_code('testuser')
print(f"Code: {code}")

# Verify code
valid, msg = users.verify_reset_code('testuser', code)
print(msg)

# Reset password
success, msg = users.reset_password_with_code('testuser', code, 'NewPass123!')
print(msg)
```

### 🚀 **Production Checklist**

Before deploying to production:

- [ ] Add email/SMS delivery for reset codes
- [ ] Add email column to users table
- [ ] Configure SMTP/email service credentials
- [ ] Test email delivery on test account
- [ ] Remove on-screen code display
- [ ] Update user documentation
- [ ] Test full flow end-to-end
- [ ] Monitor security.log for abuse

### 🔒 **Admin Override**

Admins can still reset user passwords manually via the Admin panel:
1. Go to Admin page
2. Find user in User Management
3. Update their details
4. Set new password directly

This provides a backup if email/SMS fails or user has no access to their contact method.

## Benefits Over Email-Only Reset

✅ **Immediate**: No email delays  
✅ **Simple**: 6-digit code (no link clicking)  
✅ **Mobile-friendly**: Easy to copy/paste on phones  
✅ **Works offline**: Email not required (in dev mode)  
✅ **Auditable**: All attempts logged  
✅ **Secure**: Time-limited + hashed + rate-limited
