# Azure Resource Provisioning Guide

**Version:** 1.0.0  
**Last Updated:** November 13, 2025  
**Status:** Task 5 - Ready for Execution

---

## Overview

This guide walks through provisioning all required Azure resources for PriceScout deployment. The automated PowerShell script handles resource creation, configuration, and access management.

---

## Prerequisites

### 1. Azure CLI Installation

**Check if installed:**
```powershell
az --version
```

**Install (if needed):**
```powershell
# Download and run installer
winget install Microsoft.AzureCLI

# Or use MSI installer from:
# https://aka.ms/installazurecliwindows
```

**Verify installation:**
```powershell
az --version
# Expected: azure-cli 2.54.0+
```

### 2. Azure Account Setup

**Login to Azure:**
```powershell
az login
```

**Set subscription (if you have multiple):**
```powershell
# List subscriptions
az account list --output table

# Set active subscription
az account set --subscription "Your Subscription Name"

# Verify
az account show
```

### 3. Required Permissions

Your Azure account must have:
- **Contributor** role on the subscription (minimum)
- **Owner** role (recommended for full access management)

**Check your role:**
```powershell
az role assignment list --assignee $(az account show --query user.name -o tsv) --output table
```

---

## Quick Start

### Option 1: Production Deployment

```powershell
# Navigate to project
cd "c:\Users\estev\Desktop\Price Scout"

# Run provisioning script
.\deploy\provision-azure-resources.ps1 -Environment prod -Location eastus
```

**Resources created:**
- B2 App Service tier ($140/month)
- Standard_B2s PostgreSQL ($120/month)
- Standard Container Registry ($20/month)
- Application Insights + Log Analytics
- **Total: ~$280/month**

### Option 2: Development Deployment (Recommended First)

```powershell
.\deploy\provision-azure-resources.ps1 -Environment dev -Location eastus
```

**Resources created:**
- B1 App Service tier ($13/month)
- Standard_B1ms PostgreSQL ($18/month)
- Basic Container Registry ($5/month)
- Application Insights + Log Analytics
- **Total: ~$36/month**

### Option 3: Dry Run (No Resources Created)

```powershell
.\deploy\provision-azure-resources.ps1 -Environment dev -Location eastus -DryRun
```

Shows what would be created without actually provisioning resources.

---

## Script Parameters

| Parameter | Required | Values | Default | Description |
|-----------|----------|--------|---------|-------------|
| `-Environment` | Yes | `dev`, `staging`, `prod` | - | Deployment environment |
| `-Location` | No | Azure region | `eastus` | Azure datacenter location |
| `-SkipConfirmation` | No | Switch | False | Skip confirmation prompt |
| `-DryRun` | No | Switch | False | Preview without creating |

**Examples:**
```powershell
# Development in West US
.\deploy\provision-azure-resources.ps1 -Environment dev -Location westus

# Production with no prompts
.\deploy\provision-azure-resources.ps1 -Environment prod -SkipConfirmation

# Preview staging deployment
.\deploy\provision-azure-resources.ps1 -Environment staging -DryRun
```

---

## Resources Created

### 1. Resource Group
**Name:** `pricescout-{env}-rg-{location}`  
**Purpose:** Container for all PriceScout resources  
**Cost:** Free

### 2. PostgreSQL Flexible Server
**Name:** `pricescout-db-{env}-{location}`  
**SKU:** 
- Dev: Standard_B1ms (1 vCore, 2GB RAM)
- Prod: Standard_B2s (2 vCore, 4GB RAM)
  
**Storage:** 32GB (dev), 64GB (prod)  
**Version:** PostgreSQL 14  
**Cost:** $18/month (dev), $120/month (prod)

**Features:**
- SSL/TLS enforced
- Public access (configure firewall rules)
- Automated backups (7-day retention)
- Point-in-time restore

### 3. Azure Key Vault
**Name:** `pricescout-kv-{env}` (24 char limit)  
**Purpose:** Secure storage for secrets, connection strings, API keys  
**Cost:** $0.03 per 10,000 operations

**Access:**
- RBAC disabled (policy-based for simplicity)
- Current user: Full secret permissions
- App Service managed identity: Get/List secrets

### 4. Azure Container Registry (ACR)
**Name:** `pricescoutacr{env}` (alphanumeric only)  
**SKU:**
- Dev: Basic ($5/month, 10GB storage)
- Prod: Standard ($20/month, 100GB storage)

**Features:**
- Admin user enabled
- Docker image storage
- Webhook support for CI/CD

### 5. Log Analytics Workspace
**Name:** `pricescout-logs-{env}`  
**Purpose:** Centralized logging and monitoring  
**Cost:** $2.76/GB (first 5GB/month free)

**Retention:** 30 days (default)

### 6. Application Insights
**Name:** `pricescout-ai-{env}`  
**Purpose:** APM, metrics, distributed tracing  
**Cost:** $2.88/GB after free tier

**Features:**
- Request tracking
- Exception logging
- Performance monitoring
- User analytics

### 7. App Service Plan
**Name:** `pricescout-plan-{env}`  
**SKU:**
- Dev: B1 (1 core, 1.75GB RAM)
- Prod: B2 (2 cores, 3.5GB RAM)

**Platform:** Linux  
**Cost:** $13/month (B1), $54/month (B2)

### 8. App Service (Web App)
**Name:** `pricescout-app-{env}-{location}`  
**Type:** Container-based deployment  
**Cost:** Included in App Service Plan

**Features:**
- Managed identity enabled
- HTTPS enforced
- Always On enabled (B2+)
- Health check on /_stcore/health

**URL:** `https://pricescout-app-{env}-{location}.azurewebsites.net`

---

## Post-Provisioning Tasks

### 1. Secure Credentials

The script saves credentials to `deploy/` folder:
- `postgres-credentials-{env}.txt` - Database admin password
- `acr-credentials-{env}.txt` - Container registry credentials

**⚠️ IMPORTANT:** These files contain sensitive data!

**Action Items:**
```powershell
# Store PostgreSQL password in Key Vault
az keyvault secret set `
  --vault-name pricescout-kv-dev `
  --name "postgresql-admin-password" `
  --value "YourPasswordHere"

# Store ACR password (for GitHub Actions)
az keyvault secret set `
  --vault-name pricescout-kv-dev `
  --name "acr-password" `
  --value "YourACRPasswordHere"

# Delete local credential files
Remove-Item .\deploy\*-credentials-*.txt
```

### 2. Configure PostgreSQL Firewall

**Allow your IP:**
```powershell
# Get your public IP
$myIp = (Invoke-WebRequest -Uri "https://api.ipify.org").Content

# Add firewall rule
az postgres flexible-server firewall-rule create `
  --resource-group pricescout-dev-rg-eastus `
  --name pricescout-db-dev-eastus `
  --rule-name "AllowMyIP" `
  --start-ip-address $myIp `
  --end-ip-address $myIp
```

**Allow Azure services:**
```powershell
az postgres flexible-server firewall-rule create `
  --resource-group pricescout-dev-rg-eastus `
  --name pricescout-db-dev-eastus `
  --rule-name "AllowAzureServices" `
  --start-ip-address 0.0.0.0 `
  --end-ip-address 0.0.0.0
```

### 3. Test Database Connection

```powershell
# Install PostgreSQL client (if needed)
# winget install PostgreSQL.PostgreSQL

# Connect to database
psql "host=pricescout-db-dev-eastus.postgres.database.azure.com port=5432 dbname=pricescout_db user=pricescout_admin sslmode=require"

# Test query
SELECT version();
\l
\q
```

### 4. Test Container Registry

```powershell
# Login to ACR
az acr login --name pricescoutacrdev

# Build and push test image
docker build -t pricescout:latest .
docker tag pricescout:latest pricescoutacrdev.azurecr.io/pricescout:latest
docker push pricescoutacrdev.azurecr.io/pricescout:latest
```

### 5. Verify Key Vault Access

```powershell
# Test secret storage
az keyvault secret set `
  --vault-name pricescout-kv-dev `
  --name "test-secret" `
  --value "Hello World"

# Test secret retrieval
az keyvault secret show `
  --vault-name pricescout-kv-dev `
  --name "test-secret" `
  --query value -o tsv
```

---

## Verification Checklist

Use this checklist to confirm successful provisioning:

### Azure Portal Verification

1. **Navigate to Resource Group:**
   - Go to: https://portal.azure.com
   - Search for: `pricescout-{env}-rg-{location}`
   - Verify 8 resources listed

2. **PostgreSQL Server:**
   - [ ] Server status: Available
   - [ ] Database `pricescout_db` created
   - [ ] Firewall rules configured
   - [ ] SSL enforcement: Enabled

3. **Key Vault:**
   - [ ] Access policies configured
   - [ ] Can list secrets
   - [ ] App Service has access

4. **Container Registry:**
   - [ ] Admin user enabled
   - [ ] Can login via `az acr login`
   - [ ] Ready to receive images

5. **App Service:**
   - [ ] Status: Running
   - [ ] Managed identity: Enabled
   - [ ] Configuration settings present
   - [ ] URL accessible (may show placeholder)

6. **Application Insights:**
   - [ ] Linked to Log Analytics
   - [ ] Connection string stored in Key Vault
   - [ ] Live metrics available

### CLI Verification

```powershell
# Check all resources
az resource list `
  --resource-group pricescout-dev-rg-eastus `
  --output table

# Check PostgreSQL
az postgres flexible-server show `
  --resource-group pricescout-dev-rg-eastus `
  --name pricescout-db-dev-eastus `
  --query "{Name:name, Status:state, Version:version}" `
  --output table

# Check Key Vault
az keyvault show `
  --name pricescout-kv-dev `
  --query "{Name:name, URI:properties.vaultUri}" `
  --output table

# Check App Service
az webapp show `
  --resource-group pricescout-dev-rg-eastus `
  --name pricescout-app-dev-eastus `
  --query "{Name:name, State:state, URL:defaultHostName}" `
  --output table
```

---

## Troubleshooting

### Issue: Resource Name Already Taken

**Symptom:**
```
ERROR: The name 'pricescout-kv-dev' is already in use.
```

**Cause:** Global namespace conflict (Key Vault, App Service, Container Registry have globally unique names)

**Solution:**
```powershell
# Option 1: Use a unique prefix
# Edit script line: $config.KeyVault = "ps-yourname-kv-$Environment"

# Option 2: Add random suffix
$suffix = Get-Random -Maximum 9999
$config.KeyVault = "pricescout-kv-$Environment-$suffix"
```

### Issue: Insufficient Permissions

**Symptom:**
```
ERROR: The client does not have authorization to perform action
```

**Solution:**
```powershell
# Check your role
az role assignment list --assignee $(az account show --query user.name -o tsv)

# Request Contributor or Owner role from subscription admin
```

### Issue: PostgreSQL Creation Timeout

**Symptom:**
```
ERROR: Long-running operation failed with status 'Failed'
```

**Solution:**
```powershell
# Check quota limits
az postgres flexible-server list-skus --location eastus --output table

# Try different region
.\deploy\provision-azure-resources.ps1 -Environment dev -Location westus

# Or retry (transient errors are common)
```

### Issue: Key Vault Access Denied

**Symptom:**
```
ERROR: Caller is not authorized to perform action on resource
```

**Solution:**
```powershell
# Grant yourself full permissions
az keyvault set-policy `
  --name pricescout-kv-dev `
  --upn $(az account show --query user.name -o tsv) `
  --secret-permissions get list set delete backup restore recover purge
```

### Issue: Container Registry Login Fails

**Symptom:**
```
Error: unauthorized: authentication required
```

**Solution:**
```powershell
# Ensure admin user is enabled
az acr update --name pricescoutacrdev --admin-enabled true

# Get credentials
az acr credential show --name pricescoutacrdev

# Login with username/password
docker login pricescoutacrdev.azurecr.io -u <username> -p <password>
```

---

## Cost Management

### Monthly Cost Breakdown

**Development Environment:**
| Resource | SKU | Cost/Month |
|----------|-----|------------|
| App Service B1 | 1 core, 1.75GB | $13 |
| PostgreSQL B1ms | 1 core, 2GB | $18 |
| ACR Basic | 10GB storage | $5 |
| Key Vault | Pay-per-use | $1 |
| App Insights | First 5GB free | $0 |
| **Total** | | **~$37** |

**Production Environment:**
| Resource | SKU | Cost/Month |
|----------|-----|------------|
| App Service B2 | 2 cores, 3.5GB | $54 |
| PostgreSQL B2s | 2 cores, 4GB | $120 |
| ACR Standard | 100GB storage | $20 |
| Key Vault | Pay-per-use | $2 |
| App Insights | ~10GB/month | $30 |
| **Total** | | **~$226** |

### Cost Optimization Tips

1. **Use B-tier for dev/staging** - Burstable performance at lower cost
2. **Stop dev resources when not in use:**
   ```powershell
   # Stop App Service (doesn't reduce cost but saves compute)
   az webapp stop --name pricescout-app-dev-eastus --resource-group pricescout-dev-rg-eastus
   
   # Stop PostgreSQL (stops billing compute)
   az postgres flexible-server stop --name pricescout-db-dev-eastus --resource-group pricescout-dev-rg-eastus
   ```

3. **Delete entire dev environment when not needed:**
   ```powershell
   az group delete --name pricescout-dev-rg-eastus --yes --no-wait
   ```

4. **Set up budgets and alerts:**
   ```powershell
   az consumption budget create `
     --budget-name "pricescout-monthly-limit" `
     --amount 100 `
     --time-period start=2025-11-01 end=2026-11-01 `
     --resource-group pricescout-dev-rg-eastus
   ```

---

## Cleanup

### Delete All Resources

```powershell
# WARNING: This deletes EVERYTHING including data!

# Delete resource group (removes all resources)
az group delete `
  --name pricescout-dev-rg-eastus `
  --yes `
  --no-wait

# Verify deletion
az group exists --name pricescout-dev-rg-eastus
# Returns: false
```

### Delete Specific Resources

```powershell
# Delete App Service only
az webapp delete --name pricescout-app-dev-eastus --resource-group pricescout-dev-rg-eastus

# Delete PostgreSQL only
az postgres flexible-server delete --name pricescout-db-dev-eastus --resource-group pricescout-dev-rg-eastus --yes

# Delete Container Registry only
az acr delete --name pricescoutacrdev --yes
```

---

## Next Steps

After successful provisioning:

1. **Proceed to Task 6:** Database Migration & Secrets
   - Apply schema.sql to PostgreSQL
   - Migrate data from SQLite
   - Store all secrets in Key Vault

2. **Build and Deploy Container:**
   - Build Docker image locally
   - Push to Azure Container Registry
   - Configure App Service container settings

3. **Test Deployment:**
   - Access App Service URL
   - Verify database connectivity
   - Check Application Insights logs

4. **Production Readiness:**
   - Configure custom domain
   - Enable SSL certificate
   - Set up CI/CD pipeline (Task 8)

---

## Support Resources

**Azure CLI Reference:**
- https://learn.microsoft.com/cli/azure/

**Azure PostgreSQL:**
- https://learn.microsoft.com/azure/postgresql/flexible-server/

**App Service for Containers:**
- https://learn.microsoft.com/azure/app-service/quickstart-custom-container

**Key Vault:**
- https://learn.microsoft.com/azure/key-vault/

**Pricing Calculator:**
- https://azure.microsoft.com/pricing/calculator/
