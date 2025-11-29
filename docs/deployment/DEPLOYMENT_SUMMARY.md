# Price Scout v2 - Deployment Summary

## Overview
This deployment will add Price Scout v2 as a second application on your DigitalOcean droplet alongside the original version.

## Configuration Details

| Setting | Value |
|---------|-------|
| **App Name** | pricescout-v2 |
| **Directory** | /root/pricescout-v2 |
| **Port** | 8502 |
| **Subdomain** | v2.marketpricescout.com |
| **Service Name** | pricescout-v2.service |
| **Droplet IP** | 134.199.207.21 |

## Quick Start

### 1. Run the Deployment Preparation Script

Double-click: `prepare_deployment.bat`

This will create a `deployment_pricescout_v2` folder with:
- All necessary application files
- Pre-configured systemd service file
- Pre-configured Nginx configuration
- Detailed deployment instructions
- Quick command reference

### 2. Follow the Generated Instructions

Open `deployment_pricescout_v2\DEPLOYMENT_INSTRUCTIONS.txt` for step-by-step instructions.

## What Gets Deployed

### Application Files
- `app/` directory (all Python modules)
- `app/modes/` (all mode modules)
- `app/assets/` (images, logos, etc.)
- `app/resources/` (additional resources)
- Configuration JSON files
- Requirements files

### System Configuration
- **Systemd Service**: Manages the app as a background service
- **Nginx Configuration**: Routes traffic from your subdomain to the app
- **SSL Certificate**: Will be configured via Certbot

## Architecture

```
Internet
    |
    v
DNS (v2.marketpricescout.com)
    |
    v
Nginx (Port 80/443)
    |
    v
Streamlit App (Port 8502)
```

## Important Notes

### 1. Database Considerations
- If you have a `users.db` file, you may want to:
  - Start fresh (don't upload it - new database will be created)
  - Or upload your existing database to preserve users

### 2. Environment Variables
- Check if you need any environment variables (API keys, etc.)
- Set them in the systemd service file if needed

### 3. File Permissions
- The service runs as `root` user
- Ensure all files have proper permissions after upload

### 4. Port Conflicts
- Port 8502 should be free (8501 is used by original app)
- Check with: `sudo netstat -tlnp | grep 8502`

## Deployment Checklist

- [ ] Run `prepare_deployment.bat`
- [ ] Review generated files in `deployment_pricescout_v2/`
- [ ] Create `/root/pricescout-v2` directory on droplet
- [ ] Upload files via SCP
- [ ] Install Python dependencies
- [ ] Install Playwright and dependencies
- [ ] Configure systemd service
- [ ] Start the service
- [ ] Configure Nginx
- [ ] Add DNS record
- [ ] Wait for DNS propagation (5-10 minutes)
- [ ] Run Certbot for SSL
- [ ] Test the deployment

## Testing Your Deployment

After deployment, verify:

1. **Service is running**:
   ```bash
   sudo systemctl status pricescout-v2
   ```

2. **App responds locally**:
   ```bash
   curl http://localhost:8502
   ```

3. **Nginx is configured**:
   ```bash
   sudo nginx -t
   ```

4. **Access via browser**:
   - Initially: `http://v2.marketpricescout.com`
   - After SSL: `https://v2.marketpricescout.com`

## Troubleshooting

### Service won't start
```bash
# Check logs
sudo journalctl -u pricescout-v2 -f

# Common issues:
# - Missing dependencies: pip3 install -r requirements.txt
# - Wrong working directory in service file
# - Port already in use
```

### Nginx errors
```bash
# Check configuration
sudo nginx -t

# View error logs
sudo tail -f /var/log/nginx/error.log

# Restart Nginx
sudo systemctl restart nginx
```

### DNS not resolving
- Wait 10-15 minutes for propagation
- Check DNS with: `nslookup v2.marketpricescout.com`
- Verify A record points to 134.199.207.21

### SSL issues
- Ensure DNS is fully propagated before running Certbot
- Check that port 80 is accessible (firewall)
- Try: `sudo certbot --nginx -d v2.marketpricescout.com --dry-run`

## Useful Commands

### Service Management
```bash
sudo systemctl start pricescout-v2      # Start the service
sudo systemctl stop pricescout-v2       # Stop the service
sudo systemctl restart pricescout-v2    # Restart the service
sudo systemctl status pricescout-v2     # Check status
sudo systemctl enable pricescout-v2     # Enable auto-start on boot
```

### View Logs
```bash
# Follow service logs in real-time
sudo journalctl -u pricescout-v2 -f

# View last 100 lines
sudo journalctl -u pricescout-v2 -n 100

# View Nginx access logs
sudo tail -f /var/log/nginx/access.log
```

### Update Application
```bash
# Stop service
sudo systemctl stop pricescout-v2

# Upload new files (from local machine)
scp -r deployment_pricescout_v2/app/* root@134.199.207.21:/root/pricescout-v2/app/

# Restart service
sudo systemctl start pricescout-v2
```

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review service logs with `journalctl`
3. Verify all steps in DEPLOYMENT_INSTRUCTIONS.txt
4. Check Nginx error logs

## File Structure After Deployment

```
/root/pricescout-v2/
├── app/
│   ├── price_scout_app.py (main app)
│   ├── modes/
│   ├── assets/
│   ├── resources/
│   └── [other Python modules]
├── requirements.txt
└── [other config files]

/etc/systemd/system/
└── pricescout-v2.service

/etc/nginx/sites-available/
└── v2.marketpricescout.com

/etc/nginx/sites-enabled/
└── v2.marketpricescout.com (symlink)
```

---

**Ready to deploy?** Run `prepare_deployment.bat` to get started!
