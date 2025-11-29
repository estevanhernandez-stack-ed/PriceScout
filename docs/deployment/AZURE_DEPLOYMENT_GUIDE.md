# PriceScout Azure Deployment Guide

**Last Updated:** November 27, 2025  
**Target Environment:** Azure Cloud  
**Prerequisites:** Azure CLI, Active Azure Subscription

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Detailed Deployment Steps](#detailed-deployment-steps)
4. [Post-Deployment Configuration](#post-deployment-configuration)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools

- **Azure CLI**: Version 2.50.0 or higher
  ```powershell
  az --version
  ```
  Install from: https://aka.ms/installazurecliwindows

- **PowerShell**: Version 7.0+ recommended
  ```powershell
  $PSVersionTable.PSVersion
  ```

- **Git**: For version control
  ```powershell
  git --version
  ```

### Azure Requirements

- **Active Subscription**: With Contributor or Owner role
- **Resource Quota**: Ensure sufficient quota for:
  - App Service Plans
  - PostgreSQL Flexible Servers
  - API Management (Consumption tier)
  - Service Bus Namespaces

### Login to Azure

```powershell
# Login to Azure
az login

# Verify active subscription
az account show

# (Optional) Set specific subscription
az account set --subscription "<subscription-id>"
```

---

## Quick Start

For a dev environment deployment:

```powershell
# Navigate to project root
cd "C:\Users\estev\Desktop\Price Scout"

# Run deployment (dev environment)
.\azure\deploy-infrastructure.ps1 -Environment dev

# Verify deployment
.\azure\verify-deployment.ps1 -Environment dev
```

**Estimated Time:** 10-15 minutes

---

## Detailed Deployment Steps

### Step 1: Review Configuration

The deployment script uses environment-specific configurations:

| Environment | SKU | Use Case |
|-------------|-----|----------|
| **dev** | B1 App Service, B1ms PostgreSQL | Development/Testing |
| **staging** | S1 App Service, B2s PostgreSQL | Pre-production |
| **prod** | P1v2 App Service, D2s PostgreSQL | Production |

### Step 2: Run What-If Analysis (Optional)

Preview changes before deployment:

```powershell
.\azure\deploy-infrastructure.ps1 `
    -Environment dev `
    -WhatIf
```

This shows what resources will be created without actually deploying them.

### Step 3: Deploy Infrastructure

```powershell
.\azure\deploy-infrastructure.ps1 `
    -Environment dev `
    -Location eastus
```

**Parameters:**
- `-Environment`: Choose `dev`, `staging`, or `prod`
- `-Location`: Azure region (default: `eastus`)
- `-SubscriptionId`: (Optional) Specific subscription ID
- `-WhatIf`: Preview mode only
- `-SkipValidation`: Skip Bicep template validation

**What Gets Deployed:**
✅ Resource Group  
✅ App Service Plan  
✅ App Service (with Managed Identity)  
✅ PostgreSQL Flexible Server  
✅ Key Vault  
✅ API Management (Consumption tier)  
✅ Service Bus Namespace + Queue  

### Step 4: Verify Deployment

```powershell
.\azure\verify-deployment.ps1 -Environment dev
```

This runs 8 tests to verify:
- Resource group existence
- App Service status
- PostgreSQL connectivity
- Key Vault access
- Managed Identity configuration
- APIM gateway
- Service Bus status

---

## Post-Deployment Configuration

### 1. Configure Key Vault Secrets

The application requires several secrets in Key Vault:

```powershell
$kvName = "kv-pricescout-dev"  # Adjust for your environment

# Database connection string
$dbConnStr = "Host=psql-pricescout-dev.postgres.database.azure.com;Database=pricescout;Username=psqladmin;Password=YOUR_PASSWORD;SSL Mode=Require"
az keyvault secret set --vault-name $kvName --name DATABASE-URL --value $dbConnStr

# JWT secret key (generate a strong random key)
$jwtSecret = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
az keyvault secret set --vault-name $kvName --name JWT-SECRET-KEY --value $jwtSecret

# Secret key for application
az keyvault secret set --vault-name $kvName --name SECRET-KEY --value $jwtSecret

# (Optional) External API keys
az keyvault secret set --vault-name $kvName --name OMDB-API-KEY --value "YOUR_OMDB_KEY"

# Application Insights connection string (if using)
$appInsightsConnStr = az monitor app-insights component show `
    --app pricescout-insights-dev `
    --resource-group rg-pricescout-dev `
    --query connectionString `
    --output tsv
az keyvault secret set --vault-name $kvName --name APPLICATIONINSIGHTS-CONNECTION-STRING --value $appInsightsConnStr

# Service Bus connection string
$sbConnStr = az servicebus namespace authorization-rule keys list `
    --resource-group rg-pricescout-dev `
    --namespace-name sb-pricescout-dev `
    --name RootManageSharedAccessKey `
    --query primaryConnectionString `
    --output tsv
az keyvault secret set --vault-name $kvName --name AZURE-SERVICE-BUS-CONNECTION-STRING --value $sbConnStr
```

### 2. Deploy APIM Policies

```powershell
# Get your tenant ID and client ID (for JWT validation)
$tenantId = az account show --query tenantId --output tsv
$clientId = "YOUR_APP_REGISTRATION_CLIENT_ID"  # If using Entra ID

# Deploy policies
.\azure\iac\deploy-apim-policies.ps1 `
    -ResourceGroup rg-pricescout-dev `
    -ApimServiceName apim-pricescout-dev `
    -TenantId $tenantId `
    -ClientId $clientId
```

### 3. Configure App Service Environment Variables

```powershell
$appName = "pricescout-dev"
$rgName = "rg-pricescout-dev"

# Set required environment variables
az webapp config appsettings set `
    --name $appName `
    --resource-group $rgName `
    --settings `
        DEPLOYMENT_ENV=azure `
        ENVIRONMENT=development `
        AZURE_KEY_VAULT_URL=https://kv-pricescout-dev.vault.azure.net/ `
        APIM_GATEWAY_URL=https://apim-pricescout-dev.azure-api.net `
        WEBSITE_RUN_FROM_PACKAGE=1
```

### 4. Deploy Application Code

#### Option A: ZIP Deployment

```powershell
# Create deployment package
$excludeDirs = @('.git', '__pycache__', 'tests', 'debug_snapshots', '.venv', 'venv')
Compress-Archive -Path .\* -DestinationPath .\app.zip -Force

# Deploy to App Service
az webapp deployment source config-zip `
    --resource-group rg-pricescout-dev `
    --name pricescout-dev `
    --src app.zip
```

#### Option B: GitHub Actions (CI/CD)

See `.github/workflows/azure-deployment.yml` for automated deployment pipeline.

### 5. Initialize Database

```powershell
# SSH into App Service
az webapp ssh --name pricescout-dev --resource-group rg-pricescout-dev

# Run migrations
python -m alembic upgrade head

# Create initial admin user (if needed)
python scripts/create_admin_user.py
```

### 6. Deploy Azure Function (Service Bus Consumer)

```powershell
cd azure/functions

# Create function app
az functionapp create `
    --name pricescout-functions-dev `
    --resource-group rg-pricescout-dev `
    --consumption-plan-location eastus `
    --runtime python `
    --runtime-version 3.11 `
    --functions-version 4 `
    --storage-account pricescoutstorage

# Deploy function code
func azure functionapp publish pricescout-functions-dev
```

---

## Verification

### 1. Test App Service Health

```powershell
$appUrl = "https://pricescout-dev.azurewebsites.net"
Invoke-RestMethod -Uri "$appUrl/healthz" -Method Get
```

Expected response:
```json
{
  "status": "healthy",
  "version": "2.0.0"
}
```

### 2. Test API Through APIM

```powershell
$apimUrl = "https://apim-pricescout-dev.azure-api.net"
Invoke-RestMethod -Uri "$apimUrl/api/v1/docs" -Method Get
```

### 3. Test Database Connection

```powershell
# From App Service SSH
python -c "from app.db_session import get_session; print('DB Connected')"
```

### 4. Test Key Vault Access

```powershell
# View App Service logs
az webapp log tail --name pricescout-dev --resource-group rg-pricescout-dev
```

Look for: `Loaded X secrets from Key Vault`

### 5. Run Full Verification

```powershell
.\azure\verify-deployment.ps1 -Environment dev
```

---

## Troubleshooting

### Issue: App Service Not Starting

**Symptoms:** HTTP 503 errors, app shows "Stopped" state

**Solutions:**
1. Check application logs:
   ```powershell
   az webapp log tail --name pricescout-dev --resource-group rg-pricescout-dev
   ```

2. Verify environment variables:
   ```powershell
   az webapp config appsettings list --name pricescout-dev --resource-group rg-pricescout-dev
   ```

3. Check for Python errors in startup:
   ```powershell
   az webapp log download --name pricescout-dev --resource-group rg-pricescout-dev
   ```

### Issue: Key Vault Access Denied

**Symptoms:** `403 Forbidden` errors when accessing secrets

**Solutions:**
1. Verify Managed Identity is enabled:
   ```powershell
   az webapp identity show --name pricescout-dev --resource-group rg-pricescout-dev
   ```

2. Check Key Vault access policies:
   ```powershell
   az keyvault show --name kv-pricescout-dev --query properties.accessPolicies
   ```

3. Grant access if missing:
   ```powershell
   $principalId = az webapp identity show --name pricescout-dev --resource-group rg-pricescout-dev --query principalId --output tsv
   
   az keyvault set-policy `
       --name kv-pricescout-dev `
       --object-id $principalId `
       --secret-permissions get list
   ```

### Issue: Database Connection Failed

**Symptoms:** `Connection refused` or `SSL required` errors

**Solutions:**
1. Enable Azure Services access:
   ```powershell
   az postgres flexible-server firewall-rule create `
       --resource-group rg-pricescout-dev `
       --name psql-pricescout-dev `
       --rule-name AllowAzureServices `
       --start-ip-address 0.0.0.0 `
       --end-ip-address 0.0.0.0
   ```

2. Verify connection string format includes SSL:
   ```
   SSL Mode=Require
   ```

### Issue: APIM Returns 404

**Symptoms:** APIM gateway returns 404 for valid endpoints

**Solutions:**
1. Verify API is imported:
   ```powershell
   az apim api list --resource-group rg-pricescout-dev --service-name apim-pricescout-dev
   ```

2. Re-import API:
   ```powershell
   az apim api import `
       --resource-group rg-pricescout-dev `
       --service-name apim-pricescout-dev `
       --path api `
       --specification-url https://pricescout-dev.azurewebsites.net/api/v1/openapi.json `
       --specification-format OpenApi
   ```

### Issue: High Costs

**Solutions:**
1. Use dev environment for testing (cheapest)
2. Stop App Service when not in use:
   ```powershell
   az webapp stop --name pricescout-dev --resource-group rg-pricescout-dev
   ```

3. Delete entire environment:
   ```powershell
   az group delete --name rg-pricescout-dev --yes --no-wait
   ```

---

## Cost Estimation

### Development Environment (dev)

| Resource | SKU | Estimated Monthly Cost |
|----------|-----|------------------------|
| App Service Plan | B1 (Basic) | ~$13 |
| PostgreSQL | B1ms | ~$12 |
| API Management | Consumption | ~$3.50 per million calls |
| Service Bus | Standard | ~$10 |
| Key Vault | Standard | ~$0.03 per operation |
| **Total** | | **~$40-50/month** |

### Production Environment (prod)

| Resource | SKU | Estimated Monthly Cost |
|----------|-----|------------------------|
| App Service Plan | P1v2 (Premium) | ~$84 |
| PostgreSQL | D2s (General Purpose) | ~$146 |
| API Management | Consumption | ~$3.50 per million calls |
| Service Bus | Standard | ~$10 |
| Application Insights | | ~$2.30/GB |
| **Total** | | **~$250-300/month** |

*Prices are estimates for US East region and may vary.*

---

## Additional Resources

- **Azure Documentation:** https://docs.microsoft.com/azure
- **Bicep Reference:** https://docs.microsoft.com/azure/azure-resource-manager/bicep
- **App Service Docs:** https://docs.microsoft.com/azure/app-service
- **PostgreSQL Docs:** https://docs.microsoft.com/azure/postgresql
- **API Management Docs:** https://docs.microsoft.com/azure/api-management

---

## Next Steps

After successful deployment:

1. ✅ **Configure CI/CD Pipeline** - Set up GitHub Actions for automated deployments
2. ✅ **Enable Monitoring** - Configure Application Insights dashboards
3. ✅ **Set Up Alerts** - Create alerts for critical errors and high resource usage
4. ✅ **Configure Backup** - Set up automated database backups
5. ✅ **Implement Entra ID SSO** - Add enterprise authentication (Task 2.6)
6. ✅ **Performance Testing** - Run load tests to verify scaling
7. ✅ **Security Review** - Run security scan and penetration testing

---

**Support:** For issues or questions, refer to the [Troubleshooting](#troubleshooting) section or create an issue in the repository.
