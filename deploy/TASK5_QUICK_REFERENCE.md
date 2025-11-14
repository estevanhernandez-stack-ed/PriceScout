# Task 5: Azure Resource Provisioning - Quick Reference

**Status:** Ready for Execution  
**Estimated Time:** 30-45 minutes  
**Cost:** $36/month (dev) or $226/month (prod)

---

## Prerequisites Checklist

- [ ] Azure CLI installed (`az --version`)
- [ ] Logged into Azure (`az login`)
- [ ] Subscription selected (`az account show`)
- [ ] Contributor/Owner role verified
- [ ] PowerShell 7+ available

---

## Execution Steps

### 1. Run Provisioning Script (5 minutes)

```powershell
cd "c:\Users\estev\Desktop\Price Scout"

# Development environment (recommended first)
.\deploy\provision-azure-resources.ps1 -Environment dev -Location eastus

# OR Production environment
.\deploy\provision-azure-resources.ps1 -Environment prod -Location eastus
```

**What happens:**
- Creates resource group
- Provisions PostgreSQL server (5-10 min wait)
- Creates Key Vault
- Creates Container Registry
- Creates Log Analytics + App Insights
- Creates App Service Plan + App Service
- Configures managed identity and access

### 2. Save Credentials (2 minutes)

Script saves to `deploy/` folder:
- `postgres-credentials-dev.txt` - Database password
- `acr-credentials-dev.txt` - Registry credentials

**Store in Key Vault immediately:**
```powershell
$pgPassword = Get-Content .\deploy\postgres-credentials-dev.txt | Select-String "Admin Password:"

az keyvault secret set `
  --vault-name pricescout-kv-dev `
  --name "postgresql-admin-password" `
  --value "YourPasswordFromFile"

# Delete local files
Remove-Item .\deploy\*-credentials-*.txt
```

### 3. Configure PostgreSQL Firewall (2 minutes)

```powershell
# Allow your IP
$myIp = (Invoke-WebRequest -Uri "https://api.ipify.org").Content

az postgres flexible-server firewall-rule create `
  --resource-group pricescout-dev-rg-eastus `
  --name pricescout-db-dev-eastus `
  --rule-name "AllowMyIP" `
  --start-ip-address $myIp `
  --end-ip-address $myIp

# Allow Azure services
az postgres flexible-server firewall-rule create `
  --resource-group pricescout-dev-rg-eastus `
  --name pricescout-db-dev-eastus `
  --rule-name "AllowAzureServices" `
  --start-ip-address 0.0.0.0 `
  --end-ip-address 0.0.0.0
```

### 4. Test Database Connection (3 minutes)

```powershell
# Test connection
psql "host=pricescout-db-dev-eastus.postgres.database.azure.com port=5432 dbname=pricescout_db user=pricescout_admin sslmode=require"

# Run test query
SELECT version();
\l
\q
```

### 5. Verify All Resources (5 minutes)

```powershell
# List all resources
az resource list `
  --resource-group pricescout-dev-rg-eastus `
  --output table

# Should show 8 resources:
# - PostgreSQL Flexible Server
# - Key Vault
# - Container Registry
# - Log Analytics Workspace
# - Application Insights
# - App Service Plan
# - App Service
```

---

## Verification Checklist

- [ ] Resource group created: `pricescout-dev-rg-eastus`
- [ ] PostgreSQL server status: Available
- [ ] Database `pricescout_db` exists
- [ ] Key Vault accessible
- [ ] Container Registry admin enabled
- [ ] App Service running (placeholder)
- [ ] Managed identity enabled on App Service
- [ ] Key Vault access granted to App Service
- [ ] Application Insights connected
- [ ] Credentials stored in Key Vault
- [ ] Local credential files deleted
- [ ] PostgreSQL firewall configured
- [ ] Database connection successful

---

## Resource Names (Development)

| Resource Type | Name | URL/Connection |
|--------------|------|----------------|
| Resource Group | `pricescout-dev-rg-eastus` | - |
| PostgreSQL | `pricescout-db-dev-eastus` | `pricescout-db-dev-eastus.postgres.database.azure.com` |
| Key Vault | `pricescout-kv-dev` | `https://pricescout-kv-dev.vault.azure.net/` |
| Container Registry | `pricescoutacrdev` | `pricescoutacrdev.azurecr.io` |
| App Service | `pricescout-app-dev-eastus` | `https://pricescout-app-dev-eastus.azurewebsites.net` |

---

## Common Issues & Quick Fixes

### Issue: Name Already Taken
```powershell
# Edit script to add unique suffix
# Line ~50: $config.KeyVault = "pricescout-kv-dev-$(Get-Random -Max 999)"
```

### Issue: PostgreSQL Creation Slow
```
# Normal - takes 5-10 minutes
# Check portal: https://portal.azure.com
```

### Issue: Can't Connect to PostgreSQL
```powershell
# Check firewall rules
az postgres flexible-server firewall-rule list `
  --resource-group pricescout-dev-rg-eastus `
  --name pricescout-db-dev-eastus `
  --output table
```

### Issue: Key Vault Access Denied
```powershell
# Grant yourself access
az keyvault set-policy `
  --name pricescout-kv-dev `
  --upn $(az account show --query user.name -o tsv) `
  --secret-permissions get list set delete
```

---

## Cost Summary

**Development Environment: ~$36/month**
- App Service B1: $13
- PostgreSQL B1ms: $18
- ACR Basic: $5
- Other: $1-2

**To minimize costs:**
```powershell
# Stop when not in use
az postgres flexible-server stop --name pricescout-db-dev-eastus --resource-group pricescout-dev-rg-eastus
az webapp stop --name pricescout-app-dev-eastus --resource-group pricescout-dev-rg-eastus

# Delete when done testing
az group delete --name pricescout-dev-rg-eastus --yes
```

---

## Next Steps After Task 5

1. **Mark Task 5 complete** ✓
2. **Proceed to Task 6:** Database Migration & Secrets
   - Apply schema.sql to Azure PostgreSQL
   - Migrate SQLite data
   - Configure connection strings
3. **Test deployment:**
   - Build Docker image
   - Push to ACR
   - Configure App Service

---

## Emergency Rollback

```powershell
# Delete everything (use with caution!)
az group delete --name pricescout-dev-rg-eastus --yes --no-wait

# Verify deletion
az group exists --name pricescout-dev-rg-eastus
# Should return: false
```

---

## Support

- **Full Guide:** `deploy/AZURE_PROVISIONING_GUIDE.md`
- **Deployment Plan:** `AZURE_DEPLOYMENT_PLAN.md`
- **Azure Portal:** https://portal.azure.com
- **Azure Status:** https://status.azure.com
