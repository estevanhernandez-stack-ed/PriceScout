# Price Scout - Production Deployment Guide

## Table of Contents
- [Prerequisites](#prerequisites)
- [Server Setup](#server-setup)
- [Application Deployment](#application-deployment)
- [Security Configuration](#security-configuration)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
- **Operating System**: Ubuntu 20.04+ LTS or similar Linux distribution
- **Python**: 3.9 or higher
- **Nginx**: 1.18 or higher
- **Supervisor** (optional but recommended): For process management
- **Certbot**: For SSL certificate management

### Required Accounts
- **OMDB API Key**: Register at http://www.omdbapi.com/apikey.aspx
- **Domain Name**: Registered domain pointing to your server

---

## Server Setup

### 1. Initial Server Configuration

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required system packages
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx supervisor

# Install Playwright dependencies
sudo apt install -y \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2
```

### 2. Create Application User

```bash
# Create dedicated user for Price Scout
sudo useradd -m -s /bin/bash pricescout

# Add user to necessary groups
sudo usermod -aG www-data pricescout

# Switch to pricescout user
sudo su - pricescout
```

### 3. Application Directory Setup

```bash
# Create application directory
mkdir -p ~/pricescout
cd ~/pricescout

# Clone or upload your application
# Option 1: Git clone (recommended)
git clone https://github.com/yourusername/price-scout.git .

# Option 2: Upload via SCP
# (run from local machine)
# scp -r /path/to/price-scout pricescout@your-server:~/pricescout
```

---

## Application Deployment

### 1. Python Environment Setup

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit configuration (use nano, vim, or your preferred editor)
nano .env

# Required settings to configure:
# - OMDB_API_KEY: Your OMDB API key
# - ENVIRONMENT: Set to "production"
# - DEBUG_MODE: Set to "false"
# - LOG_LEVEL: Set to "INFO"
# - SECRET_KEY: Generate using: python -c "import secrets; print(secrets.token_hex(32))"
# - SESSION_TIMEOUT: 1800 (30 minutes)
# - DOMAIN_NAME: Your domain (e.g., pricescout.example.com)
# - SERVER_ADDRESS: 0.0.0.0
# - SCRAPE_HEADLESS: true
```

### 3. Initialize Database & Users

```bash
# Create data directory
mkdir -p data

# Initialize database (if needed)
# python scripts/init_db.py  # If you have an initialization script

# Create admin user
python -c "
from app.users import create_user
create_user('admin', 'CHANGE_THIS_PASSWORD_IMMEDIATELY', 'admin')
print('Admin user created - CHANGE PASSWORD ON FIRST LOGIN!')
"
```

### 4. Test Application Locally

```bash
# Test that the application starts
streamlit run app/price_scout_app.py --server.port 8501 --server.address 127.0.0.1

# In another terminal, test access
curl http://localhost:8501

# If working, stop the test (Ctrl+C)
```

---

## Security Configuration

### 1. SSL Certificate Setup

```bash
# Exit pricescout user
exit

# Obtain Let's Encrypt certificate
sudo certbot certonly --nginx -d pricescout.example.com

# Certificates will be saved to:
# /etc/letsencrypt/live/pricescout.example.com/fullchain.pem
# /etc/letsencrypt/live/pricescout.example.com/privkey.pem

# Set up automatic renewal
sudo certbot renew --dry-run

# Add to crontab for auto-renewal
sudo crontab -e
# Add this line:
# 0 3 * * * /usr/bin/certbot renew --quiet --post-hook "systemctl reload nginx"
```

### 2. Nginx Configuration

```bash
# Copy nginx configuration
sudo cp /home/pricescout/pricescout/deploy/nginx.conf /etc/nginx/sites-available/pricescout

# Edit the configuration
sudo nano /etc/nginx/sites-available/pricescout

# Update these values:
# - server_name: Your domain
# - ssl_certificate paths: Should match your Let's Encrypt paths
# - upstream server: Verify port matches (default 8501)

# Test nginx configuration
sudo nginx -t

# Enable site
sudo ln -s /etc/nginx/sites-available/pricescout /etc/nginx/sites-enabled/

# Remove default site (if present)
sudo rm -f /etc/nginx/sites-enabled/default

# Reload nginx
sudo systemctl reload nginx
```

### 3. Firewall Configuration

```bash
# Enable UFW firewall
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable

# Verify firewall rules
sudo ufw status
```

### 4. Supervisor Configuration

Create supervisor config to keep app running:

```bash
sudo nano /etc/supervisor/conf.d/pricescout.conf
```

Add this configuration:

```ini
[program:pricescout]
directory=/home/pricescout/pricescout
command=/home/pricescout/pricescout/venv/bin/streamlit run app/price_scout_app.py --server.port 8501 --server.address 127.0.0.1 --server.headless true
user=pricescout
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/pricescout/app.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
environment=HOME="/home/pricescout",USER="pricescout",PATH="/home/pricescout/pricescout/venv/bin:%(ENV_PATH)s"
```

Start the service:

```bash
# Create log directory
sudo mkdir -p /var/log/pricescout
sudo chown pricescout:pricescout /var/log/pricescout

# Reload supervisor
sudo supervisorctl reread
sudo supervisorctl update

# Start application
sudo supervisorctl start pricescout

# Check status
sudo supervisorctl status pricescout
```

---

## Monitoring & Maintenance

### 1. Security Monitoring

```bash
# Run security monitor daily via cron
sudo su - pricescout
crontab -e

# Add this line to check security events daily at 8 AM:
0 8 * * * /home/pricescout/pricescout/venv/bin/python /home/pricescout/pricescout/scripts/security_monitor.py --days 1 --alert >> /home/pricescout/pricescout/data/security_audit.log 2>&1
```

### 2. Log Rotation

Create log rotation config:

```bash
sudo nano /etc/logrotate.d/pricescout
```

Add:

```
/var/log/pricescout/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 pricescout pricescout
    sharedscripts
    postrotate
        /usr/bin/supervisorctl restart pricescout > /dev/null
    endscript
}
```

### 3. Database Backups

```bash
# Add to crontab (run daily at 2 AM)
crontab -e

# Add:
0 2 * * * /home/pricescout/pricescout/venv/bin/python -c "from app.database import backup_database; backup_database()" >> /home/pricescout/pricescout/data/backup.log 2>&1
```

### 4. System Monitoring

```bash
# Monitor application
sudo supervisorctl tail -f pricescout

# Monitor nginx access
sudo tail -f /var/log/nginx/pricescout_access.log

# Monitor nginx errors
sudo tail -f /var/log/nginx/pricescout_error.log

# Monitor security events
tail -f /home/pricescout/pricescout/security_events.log
```

---

## Troubleshooting

### Application Won't Start

```bash
# Check supervisor status
sudo supervisorctl status pricescout

# View application logs
sudo supervisorctl tail pricescout stderr

# Check if port is in use
sudo netstat -tulpn | grep 8501

# Restart application
sudo supervisorctl restart pricescout
```

### Nginx Issues

```bash
# Test nginx configuration
sudo nginx -t

# Check nginx status
sudo systemctl status nginx

# Restart nginx
sudo systemctl restart nginx

# Check nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### SSL Certificate Issues

```bash
# Check certificate expiration
sudo certbot certificates

# Manually renew certificate
sudo certbot renew

# Test renewal process
sudo certbot renew --dry-run
```

### Database Issues

```bash
# Check database file permissions
ls -la /home/pricescout/pricescout/data/

# Fix permissions if needed
chmod 644 /home/pricescout/pricescout/data/*.db
chown pricescout:pricescout /home/pricescout/pricescout/data/*.db

# Check database integrity
sqlite3 /home/pricescout/pricescout/data/price_scout.db "PRAGMA integrity_check;"
```

### Performance Issues

```bash
# Check system resources
top
htop
df -h  # Disk usage
free -m  # Memory usage

# Check application logs for slow queries
grep "slow" /var/log/pricescout/app.log

# Restart application to clear memory
sudo supervisorctl restart pricescout
```

---

## Post-Deployment Checklist

- [ ] Admin password changed from default
- [ ] OMDB API key configured
- [ ] SSL certificate installed and working
- [ ] HTTPS redirect working (test http:// → https://)
- [ ] Security headers present (check with: https://securityheaders.com)
- [ ] File upload limits enforced (test with >50MB file)
- [ ] Login rate limiting working (test with 5+ failed attempts)
- [ ] Session timeout working (wait 30 min idle)
- [ ] Security monitoring script running daily
- [ ] Log rotation configured
- [ ] Database backups running daily
- [ ] Firewall enabled and configured
- [ ] Application auto-restarts on failure
- [ ] Error messages don't expose sensitive info
- [ ] Security event logging working

---

## Support & Maintenance

### Regular Maintenance Tasks

**Daily:**
- Review security monitor reports
- Check application logs for errors

**Weekly:**
- Review system resource usage
- Check disk space
- Verify backups are working

**Monthly:**
- Review and update dependencies
- Security patch updates
- Review user access logs

### Updating the Application

```bash
# Switch to pricescout user
sudo su - pricescout
cd ~/pricescout

# Pull latest changes
git pull

# Activate venv
source venv/bin/activate

# Update dependencies
pip install -r requirements.txt --upgrade

# Exit pricescout user
exit

# Restart application
sudo supervisorctl restart pricescout

# Verify application is running
sudo supervisorctl status pricescout
```

---

## Emergency Contacts

**Security Issues:**
- Report via: security@example.com (update with your email)
- See SECURITY.md for vulnerability disclosure process

**Application Support:**
- GitHub Issues: https://github.com/yourusername/price-scout/issues
- Documentation: https://github.com/yourusername/price-scout/wiki

---

**Last Updated:** October 26, 2025  
**Version:** 1.0  
**Deployment Guide Version:** Based on Security Audit Implementation
