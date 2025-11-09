#!/bin/bash
# ====================================================================
# Price Scout - Migrate Main Domain to Subdomain
# ====================================================================
# This script migrates the original Price Scout deployment from
# marketpricescout.com to pricescout.marketpricescout.com
# ====================================================================

echo "==========================================="
echo "  Price Scout Domain Migration Script"
echo "==========================================="
echo ""
echo "This will migrate your Price Scout app from:"
echo "  FROM: marketpricescout.com"
echo "  TO:   pricescout.marketpricescout.com"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Migration cancelled."
    exit 1
fi

echo ""
echo "[1/6] Checking current configuration..."

# Check if old config exists
if [ ! -f /etc/nginx/sites-available/marketpricescout.com ]; then
    echo "ERROR: /etc/nginx/sites-available/marketpricescout.com not found!"
    echo "Please verify your current Nginx configuration."
    exit 1
fi

echo "  ✓ Found existing configuration"

echo ""
echo "[2/6] Renaming Nginx configuration file..."
sudo mv /etc/nginx/sites-available/marketpricescout.com /etc/nginx/sites-available/pricescout.marketpricescout.com

if [ $? -eq 0 ]; then
    echo "  ✓ Configuration file renamed"
else
    echo "  ✗ Failed to rename configuration file"
    exit 1
fi

echo ""
echo "[3/6] Updating server_name in configuration..."

# Update the server_name directive
sudo sed -i 's/server_name marketpricescout.com www.marketpricescout.com;/server_name pricescout.marketpricescout.com;/g' /etc/nginx/sites-available/pricescout.marketpricescout.com

# Also handle cases where it might be on separate lines or different formats
sudo sed -i 's/server_name marketpricescout.com;/server_name pricescout.marketpricescout.com;/g' /etc/nginx/sites-available/pricescout.marketpricescout.com
sudo sed -i 's/www.marketpricescout.com //g' /etc/nginx/sites-available/pricescout.marketpricescout.com

echo "  ✓ Server name updated"

echo ""
echo "[4/6] Updating symlinks..."

# Remove old symlink
if [ -L /etc/nginx/sites-enabled/marketpricescout.com ]; then
    sudo rm /etc/nginx/sites-enabled/marketpricescout.com
    echo "  ✓ Removed old symlink"
fi

# Create new symlink
sudo ln -s /etc/nginx/sites-available/pricescout.marketpricescout.com /etc/nginx/sites-enabled/

if [ $? -eq 0 ]; then
    echo "  ✓ Created new symlink"
else
    echo "  ✗ Failed to create symlink"
    exit 1
fi

echo ""
echo "[5/6] Testing Nginx configuration..."
sudo nginx -t

if [ $? -ne 0 ]; then
    echo "  ✗ Nginx configuration test failed!"
    echo "  Please review the configuration manually."
    exit 1
fi

echo "  ✓ Nginx configuration is valid"

echo ""
echo "[6/6] Obtaining new SSL certificate..."
echo ""
echo "IMPORTANT: Make sure DNS is configured first!"
echo "  Add an A record for: pricescout.marketpricescout.com"
echo "  Pointing to: 134.199.207.21"
echo ""
read -p "DNS configured and propagated? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo ""
    echo "Migration paused. Complete these steps manually:"
    echo "  1. Add DNS A record: pricescout.marketpricescout.com -> 134.199.207.21"
    echo "  2. Wait for DNS propagation (5-10 minutes)"
    echo "  3. Run: sudo certbot --nginx -d pricescout.marketpricescout.com"
    echo "  4. Run: sudo systemctl restart nginx"
    exit 0
fi

# Get SSL certificate
sudo certbot --nginx -d pricescout.marketpricescout.com

if [ $? -eq 0 ]; then
    echo "  ✓ SSL certificate obtained"
else
    echo "  ✗ Failed to obtain SSL certificate"
    echo "  You may need to wait for DNS propagation or check your DNS settings."
    exit 1
fi

echo ""
echo "==========================================="
echo "  Restarting Nginx..."
echo "==========================================="
sudo systemctl restart nginx

if [ $? -eq 0 ]; then
    echo "  ✓ Nginx restarted successfully"
else
    echo "  ✗ Failed to restart Nginx"
    exit 1
fi

echo ""
echo "==========================================="
echo "  MIGRATION COMPLETE!"
echo "==========================================="
echo ""
echo "Your Price Scout app is now accessible at:"
echo "  https://pricescout.marketpricescout.com"
echo ""
echo "Next steps:"
echo "  1. Test the new URL in your browser"
echo "  2. Deploy v2 to v2.marketpricescout.com (using prepare_deployment.bat)"
echo "  3. Update your DNS for the main domain (marketpricescout.com) as needed"
echo ""
echo "Verification commands:"
echo "  curl -I https://pricescout.marketpricescout.com"
echo "  systemctl status pricescout"
echo ""
