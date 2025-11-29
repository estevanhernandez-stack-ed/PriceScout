# Installation Complete - Setup Guide

**Date:** November 13, 2025  
**Status:** Tools Installed - Ready for Setup

---

## ✅ Installed Successfully

### 1. Azure CLI 2.79.0
- **Location:** `C:\Program Files\Microsoft SDKs\Azure\CLI2\`
- **Status:** ✅ Installed and working
- **Next Step:** Login to Azure

### 2. Docker Desktop 4.50.0
- **Status:** ✅ Installed
- **Docker:** v28.5.1
- **Docker Compose:** v2.40.3
- **Next Step:** Start Docker Desktop

---

## 🚀 Quick Setup Steps

### Step 1: Start Docker Desktop

**Option A - Start Menu:**
1. Press Windows key
2. Type "Docker Desktop"
3. Click to open
4. Wait for Docker engine to start (whale icon in system tray)

**Option B - Command Line:**
```powershell
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
```

**Verify Docker is running:**
```powershell
docker ps
# Should show: CONTAINER ID   IMAGE   COMMAND   CREATED   STATUS   PORTS   NAMES
```

### Step 2: Login to Azure

```powershell
az login
```

**What happens:**
- Opens browser for authentication
- Login with your Microsoft/Azure account
- Returns to terminal with subscription info

**Select subscription (if you have multiple):**
```powershell
# List subscriptions
az account list --output table

# Set active subscription
az account set --subscription "Your Subscription Name"

# Verify
az account show
```

### Step 3: Verify Everything Works

```powershell
# Run verification script
.\verify-installation.ps1
```

**Expected output:**
- ✓ Docker installed
- ✓ Docker Compose installed
- ✓ Docker daemon running
- ✓ Azure CLI installed
- ✓ Logged in to Azure

---

## 🧪 Test Commands

### Test Docker
```powershell
# Check Docker version
docker --version

# Check Compose
docker compose version

# Run hello-world container
docker run hello-world

# List running containers
docker ps
```

### Test Azure CLI
```powershell
# Check version
az --version

# List resource groups
az group list --output table

# List locations
az account list-locations --query "[?metadata.regionCategory=='Recommended'].{Name:name, DisplayName:displayName}" --output table
```

### Test Docker Compose with PriceScout
```powershell
# Navigate to project
cd "C:\Users\estev\Desktop\Price Scout"

# Start services (PostgreSQL + PriceScout)
docker compose up -d

# View logs
docker compose logs -f pricescout

# Access app
# Open browser: http://localhost:8000

# Stop services
docker compose down
```

---

## 📋 Ready for Task 5: Azure Provisioning

Once both tools are working, you can proceed:

```powershell
# Run provisioning script (Development environment)
.\deploy\provision-azure-resources.ps1 -Environment dev -Location eastus

# Or preview without creating resources
.\deploy\provision-azure-resources.ps1 -Environment dev -DryRun
```

**This will create:**
- Resource Group
- PostgreSQL Flexible Server
- Azure Key Vault
- Container Registry
- App Service Plan
- App Service
- Application Insights
- Log Analytics

**Estimated time:** 30-45 minutes (PostgreSQL takes 5-10 minutes)  
**Cost:** ~$36/month for dev environment

---

## 🔧 Troubleshooting

### Issue: "Docker daemon not running"

**Solution:**
1. Start Docker Desktop from Start Menu
2. Wait 30-60 seconds for engine to start
3. Look for whale icon in system tray (should be white, not animating)
4. Run `docker ps` to verify

### Issue: "az: command not found" in new terminal

**Solution:**
The PATH variable needs to be refreshed. Either:
1. Close and reopen PowerShell, OR
2. Restart your computer, OR
3. Use full path: `& 'C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd'`

### Issue: Azure login fails

**Solution:**
```powershell
# Clear cached credentials
az account clear

# Try login again
az login --use-device-code

# Or with browser
az login
```

### Issue: Docker Desktop requires restart

**Solution:**
Docker Desktop may require a system restart after first install. If Docker daemon won't start:
1. Restart your computer
2. Open Docker Desktop
3. Wait for engine to start

---

## 📚 Next Steps

After setup is complete:

1. **Test local Docker deployment:**
   - `docker compose up -d`
   - Access http://localhost:8000
   - Login with admin/admin

2. **Provision Azure resources:**
   - `.\deploy\provision-azure-resources.ps1 -Environment dev`
   - Save credentials from `deploy/` folder
   - Store in Azure Key Vault

3. **Proceed to Task 6:**
   - Database Migration & Secrets
   - Apply schema to PostgreSQL
   - Migrate SQLite data

---

## 📞 Support Resources

**Docker Documentation:**
- https://docs.docker.com/desktop/install/windows-install/
- https://docs.docker.com/compose/

**Azure CLI Documentation:**
- https://learn.microsoft.com/cli/azure/install-azure-cli-windows
- https://learn.microsoft.com/cli/azure/get-started-with-azure-cli

**PriceScout Deployment Guides:**
- `deploy/AZURE_PROVISIONING_GUIDE.md` - Full Azure setup guide
- `deploy/TASK5_QUICK_REFERENCE.md` - Quick reference checklist
- `DOCKER_TESTING_GUIDE.md` - Docker testing guide
- `AZURE_DEPLOYMENT_PLAN.md` - Complete deployment plan
