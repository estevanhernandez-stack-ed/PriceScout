# Security Policy

## Supported Versions

Price Scout follows semantic versioning. Security updates are provided for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | ✅ Yes (Current)   |
| 0.x.x   | ❌ No (Pre-production) |

---

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in Price Scout, please follow these guidelines:

### 📧 Contact Information

**DO NOT** open a public GitHub issue for security vulnerabilities.

Instead, please report security issues via:
- **Email:** [Your security email here]
- **Subject:** `[SECURITY] Price Scout - [Brief Description]`

### 📝 What to Include

Please provide:
1. **Description** of the vulnerability
2. **Steps to reproduce** the issue
3. **Potential impact** (who is affected, what data is at risk)
4. **Suggested fix** (if you have one)
5. **Your contact information** for follow-up

Example:
```
Subject: [SECURITY] Price Scout - SQL Injection in Theater Search

Description:
Found a potential SQL injection vulnerability in the theater search function.

Steps to Reproduce:
1. Navigate to Data Management > Theater Matching
2. Enter the following in the theater name field: ' OR '1'='1
3. Observe database error message

Potential Impact:
Unauthenticated users could access or modify database records.

Suggested Fix:
Use parameterized queries instead of string concatenation.

Contact: researcher@example.com
```

---

## Response Timeline

We aim to respond to security reports within:
- **Initial Response:** 48 hours
- **Severity Assessment:** 5 business days
- **Patch Development:** 2-4 weeks (depending on severity)
- **Public Disclosure:** After patch is released (coordinated disclosure)

---

## Security Best Practices for Users

If you're deploying Price Scout, please follow these security guidelines:

### ✅ Pre-Deployment Checklist

1. **Change Default Credentials**
   - ⚠️ **CRITICAL:** Change the default admin password immediately
   - Use a strong password (12+ characters, mixed case, numbers, symbols)

2. **Use HTTPS**
   - Deploy behind a reverse proxy with SSL/TLS
   - Obtain a valid certificate (Let's Encrypt is free)

3. **Secure API Keys**
   - Store OMDb API key in `.streamlit/secrets.toml`
   - Never commit `secrets.toml` to version control

4. **Update Dependencies**
   - Run `pip install --upgrade -r requirements.txt`
   - Check for known vulnerabilities: `pip install safety && safety check`

5. **Configure Firewall**
   - Only expose HTTPS port (443)
   - Block direct access to Streamlit port (8501)

### 🔒 Production Security

1. **Environment Variables**
   ```bash
   # Set in production environment
   export LOG_LEVEL=INFO  # Not DEBUG
   export STREAMLIT_SERVER_ENABLE_CORS=false
   export STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true
   ```

2. **Database Backups**
   - Schedule automated daily backups
   - Encrypt backups at rest
   - Store backups off-site

3. **Access Control**
   - Limit admin access to trusted personnel
   - Use VPN for remote admin access
   - Enable session timeout (30 minutes)

4. **Monitoring**
   - Monitor failed login attempts
   - Alert on suspicious activity (rapid logins, SQL errors)
   - Review logs weekly

---

## Known Security Considerations

### Authentication
- Default admin credentials must be changed before production use
- No built-in 2FA (enhancement planned for v3.0)
- Session timeout: 30 minutes (configurable)

### Data Protection
- Passwords: bcrypt hashing with salt
- API keys: Streamlit secrets (encrypted at rest)
- Database: SQLite (file-based, ensure proper file permissions)

### File Uploads
- Accepted formats: `.json` (markets), `.db` (database backups)
- File size limits: Recommended 50MB max
- Validation: File extension checking only (content validation recommended)

### SQL Queries
- All user input uses parameterized queries
- Some dynamic query construction exists but is mitigated

---

## Security Audit History

| Date | Version | Auditor | Findings | Status |
|------|---------|---------|----------|--------|
| 2025-10 | 1.0.0 | GitHub Copilot | Production security review | ✅ Documented |
| 2025-01 | 0.8.0 | Internal | Pre-production audit | ✅ Fixed |

See full audit reports in `docs/SECURITY_AUDIT_REPORT.md`

---

## Security Hall of Fame

We appreciate security researchers who responsibly disclose vulnerabilities. Contributors will be listed here (with permission):

- *No vulnerabilities reported yet*

---

## Vulnerability Disclosure Policy

### Coordinated Disclosure
We follow coordinated disclosure principles:
1. Researcher reports vulnerability privately
2. We confirm and assess severity
3. We develop and test a patch
4. We release the patch
5. Public disclosure after 90 days (or sooner if agreed)

### Bounty Program
Currently, Price Scout does not offer a bug bounty program. However, we deeply appreciate security research and will:
- Publicly credit researchers (if desired)
- Prioritize fixes for reported vulnerabilities
- Consider future bounty program if funding allows

---

## Security Contacts

- **Security Email:** [Your email]
- **Project Lead:** [Your name]
- **Repository:** https://github.com/[your-username]/price-scout

---

## Additional Resources

- [OWASP Top 10](https://owasp.org/Top10/)
- [Streamlit Security Best Practices](https://docs.streamlit.io/library/advanced-features/security)
- [Python Security Guidelines](https://python.readthedocs.io/en/latest/library/security_warnings.html)
- [SQLite Security](https://www.sqlite.org/security.html)

---

**Last Updated:** October 26, 2025  
**Version:** 1.0.0
