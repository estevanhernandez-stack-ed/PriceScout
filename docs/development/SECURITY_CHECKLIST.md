# Pre-Deployment Security Checklist

**Version:** 1.0.0  
**Status:** Use this checklist before deploying to production

---

## 🔴 Critical (MUST Fix Before Deploy)

- [ ] **Change default admin credentials**
  - Location: `app/users.py`
  - Action: Remove hardcoded "admin"/"admin" account
  - Alternative: Force password change on first login
  - Time: ~2 hours
  - Reference: `SECURITY_AUDIT_REPORT.md` - CRITICAL-01

---

## 🟠 High Priority (Fix Before Deploy)

- [ ] **Implement login rate limiting**
  - Location: `app/users.py`
  - Action: Add account lockout after 5 failed attempts
  - Time: ~3 hours
  - Reference: `SECURITY_AUDIT_REPORT.md` - HIGH-02

- [ ] **Add session timeout**
  - Location: `.streamlit/config.toml` + `app/price_scout_app.py`
  - Action: Force re-login after 30 minutes idle
  - Time: ~2 hours
  - Reference: `SECURITY_AUDIT_REPORT.md` - MEDIUM-02

- [ ] **Pin dependency versions**
  - Location: `requirements.txt`
  - Action: Run `pip freeze > requirements.txt`
  - Time: ~1 hour
  - Reference: `SECURITY_AUDIT_REPORT.md` - LOW-01

- [ ] **Run security audit on dependencies**
  ```bash
  pip install safety pip-audit
  safety check
  pip-audit
  ```
  - Action: Fix any critical/high vulnerabilities
  - Time: ~2 hours

---

## 🟡 Medium Priority (Should Fix Before Deploy)

- [ ] **Add file upload validation**
  - Location: `app/data_management_v2.py`
  - Action: Implement size limits (50MB) and content validation
  - Time: ~4 hours
  - Reference: `SECURITY_AUDIT_REPORT.md` - MEDIUM-01

- [ ] **Review logging for sensitive data**
  - Location: `app/scraper.py`, `app/utils.py`
  - Action: Ensure no passwords/API keys in logs
  - Time: ~1 hour
  - Reference: `SECURITY_AUDIT_REPORT.md` - MEDIUM-03

- [ ] **Add SQL query security comments**
  - Location: `app/database.py` (lines 316, 1425)
  - Action: Document why f-string queries are safe
  - Time: ~1 hour
  - Reference: `SECURITY_AUDIT_REPORT.md` - HIGH-01

---

## 🔒 Deployment Configuration

### SSL/TLS Certificate
- [ ] Obtain SSL certificate (Let's Encrypt recommended)
- [ ] Configure reverse proxy (nginx/Apache)
- [ ] Force HTTPS redirect
- [ ] Test certificate validity: https://www.ssllabs.com/ssltest/

### Environment Variables
- [ ] Set `LOG_LEVEL=INFO` (not DEBUG)
- [ ] Configure `STREAMLIT_SERVER_ENABLE_CORS=false`
- [ ] Configure `STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true`

### Secrets Management
- [ ] Create `.streamlit/secrets.toml` (NOT in git)
- [ ] Add OMDb API key to secrets.toml
- [ ] Verify `.gitignore` includes `secrets.toml`

### Security Headers (via reverse proxy)
- [ ] X-Frame-Options: DENY
- [ ] X-Content-Type-Options: nosniff
- [ ] X-XSS-Protection: 1; mode=block
- [ ] Strict-Transport-Security: max-age=31536000
- [ ] Content-Security-Policy: (see nginx config)

### Firewall Configuration
- [ ] Allow inbound: HTTPS (443)
- [ ] Block direct access to Streamlit port (8501)
- [ ] Enable UFW/firewalld/iptables rules

---

## 🗄️ Database Security

- [ ] Set proper file permissions on SQLite database
  ```bash
  chmod 600 *.db  # Owner read/write only
  ```
- [ ] Configure automated daily backups
- [ ] Encrypt backups at rest
- [ ] Store backups off-site (S3, Google Cloud Storage)
- [ ] Test backup restoration process

---

## 🧪 Security Testing

### Automated Tests
- [ ] Run Bandit static analysis:
  ```bash
  pip install bandit
  bandit -r app/ -ll  # Medium/High severity only
  ```

- [ ] Scan for secrets in git history:
  ```bash
  docker run --rm -v $(pwd):/src trufflesecurity/trufflehog filesystem /src
  ```

- [ ] Check for outdated dependencies:
  ```bash
  pip list --outdated
  ```

### Manual Security Tests
- [ ] Test default admin login (should fail)
- [ ] Test SQL injection: `' OR '1'='1` in forms
- [ ] Test XSS: `<script>alert('XSS')</script>` in inputs
- [ ] Test brute force: 10 failed logins (should lock account)
- [ ] Test session timeout: Leave idle 30+ minutes
- [ ] Verify HTTPS certificate (no browser warnings)

---

## 📊 Monitoring & Logging

- [ ] Set up log aggregation (Papertrail, Loggly, etc.)
- [ ] Configure alerts for:
  - Failed login attempts (>5 in 1 minute)
  - SQL errors
  - File upload failures
  - Large file uploads (>50MB)
- [ ] Enable log rotation (max 100MB, keep 7 days)
- [ ] Review logs weekly for suspicious activity

---

## 📝 Documentation

- [ ] Document admin password change procedure
- [ ] Create incident response plan
- [ ] Document backup/restore procedures
- [ ] Update `README.md` with deployment instructions
- [ ] Add security contact email to `SECURITY.md`

---

## 🚀 Go-Live Checklist

### Final Pre-Launch
- [ ] All critical issues fixed (🔴)
- [ ] All high-priority issues fixed (🟠)
- [ ] Security tests passing
- [ ] HTTPS enabled and verified
- [ ] Backups configured and tested
- [ ] Monitoring/alerting configured

### Post-Launch (First 24 Hours)
- [ ] Monitor logs for errors
- [ ] Verify backups are running
- [ ] Test admin login with new credentials
- [ ] Verify no DEBUG logs in production
- [ ] Check security headers: https://securityheaders.com

### Post-Launch (First Week)
- [ ] Review access logs for suspicious activity
- [ ] Verify session timeout working
- [ ] Test rate limiting under load
- [ ] Review backup integrity
- [ ] Conduct internal security review

---

## ⏱️ Time Estimates

| Priority | Tasks | Estimated Time |
|----------|-------|----------------|
| 🔴 Critical | 1 | 2 hours |
| 🟠 High | 4 | 8 hours |
| 🟡 Medium | 3 | 6 hours |
| 🔒 Config | 15+ | 8 hours |
| 🧪 Testing | 10+ | 4 hours |
| **TOTAL** | **30+** | **~28 hours** |

**Recommended Timeline:**
- Week 1: Critical + High priority fixes (10 hours)
- Week 2: Medium priority + deployment config (14 hours)
- Week 3: Testing + monitoring + go-live (4 hours)

---

## 📞 Emergency Contacts

**Security Incident Response:**
- Project Lead: [Your name/email]
- Security Contact: [Security email]
- Hosting Provider Support: [Provider support info]

**Incident Response Steps:**
1. Identify the incident (logs, alerts, reports)
2. Contain the threat (disable accounts, block IPs)
3. Eradicate the vulnerability (patch, update)
4. Recover services (restore from backup if needed)
5. Document lessons learned (post-mortem)

---

## ✅ Checklist Completion

**Completed:** _____ / 30+  
**Completion Date:** __________  
**Reviewed By:** __________  
**Approved By:** __________  

---

**References:**
- Full Security Audit: `docs/SECURITY_AUDIT_REPORT.md`
- Security Policy: `SECURITY.md`
- Deployment Guide: `dev_docs/DEPLOYMENT_SUMMARY.md`

**Last Updated:** January 2025
