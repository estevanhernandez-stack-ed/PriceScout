# Migration Guide: Main Domain to Subdomain

## Overview

This guide helps you migrate your original Price Scout deployment from the main domain to a subdomain to make room for v2.

**Migration Path:**
- FROM: `marketpricescout.com`
- TO: `pricescout.marketpricescout.com`

This frees up the main domain for future use and allows v2 to run on `v2.marketpricescout.com`.

---

## Before You Begin

### Prerequisites
- SSH access to your droplet (root@134.199.207.21)
- Current Price Scout running on port 8501
- DNS access to add new A record

### Time Required
- 15-20 minutes (including DNS propagation wait)

### Backup Checklist
Before making changes, verify you have:
- ✅ Latest code pushed to GitHub
- ✅ Database backup (`users.db`)
- ✅ Current Nginx config backed up

---

## Option 1: Automated Migration (Recommended)

### Step 1: Upload Migration Script

From your local machine:

```bash
scp migrate_to_subdomain.sh root@134.199.207.21:/root/
```

### Step 2: Make Script Executable

SSH into your droplet:

```bash
ssh root@134.199.207.21
chmod +x migrate_to_subdomain.sh
```

### Step 3: Run Migration Script

```bash
./migrate_to_subdomain.sh
```

The script will:
1. Check current configuration
2. Rename Nginx config file
3. Update server_name directive
4. Update symlinks
5. Test Nginx configuration
6. Prompt for DNS confirmation
7. Obtain new SSL certificate
8. Restart Nginx

### Step 4: Verify

```bash
# Check Nginx status
systemctl status nginx

# Check app status
systemctl status pricescout

# Test the URL
curl -I https://pricescout.marketpricescout.com
```

---

## Option 2: Manual Migration

If you prefer manual control or the script fails, follow these steps:

### Step 1: Configure DNS

**IMPORTANT: Do this first and wait for propagation**

1. Go to your DNS provider (DigitalOcean, GoDaddy, etc.)
2. Add new A record:
   - **Host**: `pricescout`
   - **Type**: A
   - **Value**: `134.199.207.21`
   - **TTL**: 3600 (or default)

3. Wait 5-10 minutes for DNS propagation
4. Test: `nslookup pricescout.marketpricescout.com`

### Step 2: Backup Current Configuration

```bash
# SSH into droplet
ssh root@134.199.207.21

# Backup current Nginx config
cp /etc/nginx/sites-available/marketpricescout.com /root/marketpricescout.com.backup
```

### Step 3: Rename Nginx Configuration File

```bash
sudo mv /etc/nginx/sites-available/marketpricescout.com \
        /etc/nginx/sites-available/pricescout.marketpricescout.com
```

### Step 4: Edit Configuration

```bash
sudo nano /etc/nginx/sites-available/pricescout.marketpricescout.com
```

**Find this line:**
```nginx
server_name marketpricescout.com www.marketpricescout.com;
```

**Change to:**
```nginx
server_name pricescout.marketpricescout.com;
```

**Save and exit:** `Ctrl+O`, `Enter`, `Ctrl+X`

### Step 5: Update Symlink

```bash
# Remove old symlink
sudo rm /etc/nginx/sites-enabled/marketpricescout.com

# Create new symlink
sudo ln -s /etc/nginx/sites-available/pricescout.marketpricescout.com \
            /etc/nginx/sites-enabled/
```

### Step 6: Test Nginx Configuration

```bash
sudo nginx -t
```

**Expected output:**
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

If you see errors, review your configuration changes.

### Step 7: Obtain New SSL Certificate

```bash
sudo certbot --nginx -d pricescout.marketpricescout.com
```

**Follow the prompts:**
1. Enter email (if first time)
2. Agree to terms
3. Choose to redirect HTTP to HTTPS (recommended: Yes)

Certbot will automatically update your Nginx configuration with SSL settings.

### Step 8: Restart Nginx

```bash
sudo systemctl restart nginx
```

### Step 9: Verify Migration

```bash
# Check Nginx status
sudo systemctl status nginx

# Check app is running
sudo systemctl status pricescout

# Check if app responds
curl http://localhost:8501

# Test new URL (HTTP)
curl -I http://pricescout.marketpricescout.com

# Test new URL (HTTPS)
curl -I https://pricescout.marketpricescout.com
```

### Step 10: Test in Browser

1. Open browser
2. Navigate to: `https://pricescout.marketpricescout.com`
3. Verify app loads correctly
4. Test login functionality
5. Run a quick scrape to verify everything works

---

## Troubleshooting

### DNS Not Resolving

**Problem:** `nslookup pricescout.marketpricescout.com` fails

**Solutions:**
1. Wait longer (DNS can take up to 24 hours, usually 5-10 minutes)
2. Check DNS record is correct:
   - Host: `pricescout`
   - Value: `134.199.207.21`
3. Try `dig pricescout.marketpricescout.com` for more details
4. Clear local DNS cache (on Windows: `ipconfig /flushdns`)

### Certbot Fails

**Problem:** Certbot can't obtain certificate

**Solutions:**
1. Ensure DNS is fully propagated
2. Check port 80 is open: `sudo ufw status`
3. Verify Nginx is running: `sudo systemctl status nginx`
4. Try dry run first: `certbot --nginx -d pricescout.marketpricescout.com --dry-run`
5. Check existing certificates: `certbot certificates`

### Nginx Configuration Error

**Problem:** `nginx -t` shows errors

**Solutions:**
1. Check syntax carefully (semicolons, brackets)
2. Restore backup: `cp /root/marketpricescout.com.backup /etc/nginx/sites-available/pricescout.marketpricescout.com`
3. Review changes you made
4. Check for typos in server_name

### App Not Loading

**Problem:** Browser shows error or can't connect

**Solutions:**
1. Check app is running: `systemctl status pricescout`
2. Restart app: `systemctl restart pricescout`
3. Check app logs: `journalctl -u pricescout -n 50`
4. Verify port 8501 is responding: `curl http://localhost:8501`
5. Check Nginx error log: `tail -f /var/log/nginx/error.log`

### 502 Bad Gateway

**Problem:** Nginx is running but shows 502 error

**Solutions:**
1. App not running: `systemctl start pricescout`
2. Wrong port in Nginx config (should be 8501)
3. Firewall blocking internal connection
4. Check app logs: `journalctl -u pricescout -f`

---

## Verification Checklist

After migration, verify:

- [ ] DNS resolves: `nslookup pricescout.marketpricescout.com`
- [ ] Nginx configuration valid: `nginx -t`
- [ ] Nginx is running: `systemctl status nginx`
- [ ] App service is running: `systemctl status pricescout`
- [ ] HTTP redirects to HTTPS
- [ ] HTTPS loads correctly in browser
- [ ] SSL certificate is valid (check browser padlock)
- [ ] Login works
- [ ] Can run a test scrape
- [ ] Can export reports

---

## Post-Migration

### Update Bookmarks
Update any bookmarks from `marketpricescout.com` to `pricescout.marketpricescout.com`

### Notify Users
If you have other users, notify them of the new URL:
```
The Price Scout URL has changed:
Old: https://marketpricescout.com
New: https://pricescout.marketpricescout.com

Please update your bookmarks!
```

### Deploy v2
Now you can deploy v2 to `v2.marketpricescout.com`:
1. Run `prepare_deployment.bat`
2. Follow deployment instructions
3. Both versions will run side-by-side

### Main Domain
The main domain `marketpricescout.com` is now free for:
- A marketing landing page
- Documentation site
- Redirect to one of the subdomains
- Future use

---

## Rollback Plan

If something goes wrong and you need to rollback:

### Quick Rollback

```bash
# Restore backup config
sudo cp /root/marketpricescout.com.backup /etc/nginx/sites-available/marketpricescout.com

# Recreate symlink
sudo rm /etc/nginx/sites-enabled/pricescout.marketpricescout.com
sudo ln -s /etc/nginx/sites-available/marketpricescout.com /etc/nginx/sites-enabled/

# Test and restart
sudo nginx -t
sudo systemctl restart nginx
```

### Restore SSL
If you need the old SSL cert back:
```bash
sudo certbot --nginx -d marketpricescout.com -d www.marketpricescout.com
```

---

## Architecture After Migration

```
┌─────────────────────────────────────────────┐
│         DNS: marketpricescout.com           │
└─────────────────────────────────────────────┘
                    │
        ┌───────────┴────────────┬────────────┐
        │                        │            │
        ▼                        ▼            ▼
pricescout.              v2.            (main domain)
marketpricescout.com     marketpricescout.com
   │                        │
   ▼                        ▼
Nginx:80/443            Nginx:80/443
   │                        │
   ▼                        ▼
App:8501               App:8502
(Original)             (Version 2)
```

---

## Support

If you encounter issues:
1. Check this troubleshooting guide
2. Review Nginx error logs: `/var/log/nginx/error.log`
3. Review app logs: `journalctl -u pricescout`
4. Restore from backup if needed

---

## Summary

**What Changed:**
- Domain: `marketpricescout.com` → `pricescout.marketpricescout.com`
- Nginx config file renamed
- New SSL certificate for subdomain
- New DNS A record

**What Stayed the Same:**
- App runs on port 8501
- Service name: `pricescout`
- App directory: `/root/pricescout` (or original location)
- Database and user data intact

**Next Steps:**
- Deploy v2 to `v2.marketpricescout.com`
- Both apps run simultaneously
- Users access original via `pricescout.marketpricescout.com`
- Users access v2 via `v2.marketpricescout.com`

---

**Version:** 1.0
**Last Updated:** 2025-01-09
