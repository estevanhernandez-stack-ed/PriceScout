# PriceScout Infrastructure Deployment Script
# Deploys all Azure resources using Bicep templates

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('dev', 'staging', 'prod')]
    [string]$Environment = 'dev',
    
    [Parameter(Mandatory=$false)]
    [string]$Location = 'eastus',
    
    [Parameter(Mandatory=$false)]
    [string]$SubscriptionId,
    
    [Parameter(Mandatory=$false)]
    [switch]$WhatIf,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipValidation
)

$ErrorActionPreference = "Stop"

# ============================================================================
# CONFIGURATION
# ============================================================================

$config = @{
    dev = @{
        ResourceGroup = "rg-pricescout-dev"
        AppServicePlan = "plan-pricescout-dev"
        AppService = "pricescout-dev"
        SqlServer   = "sql-pricescout-dev"
        SqlDatabase = "pricescout"
        KeyVault = "kv-pricescout-dev"
        APIM = "apim-pricescout-dev"
        ServiceBus = "sb-pricescout-dev"
        AppServiceSku = "B1"
        SqlSku        = "S0"
    }
    staging = @{
        ResourceGroup = "rg-pricescout-staging"
        AppServicePlan = "plan-pricescout-staging"
        AppService = "pricescout-staging"
        SqlServer   = "sql-pricescout-staging"
        SqlDatabase = "pricescout"
        KeyVault = "kv-pricescout-stg"
        APIM = "apim-pricescout-staging"
        ServiceBus = "sb-pricescout-staging"
        AppServiceSku = "S1"
        SqlSku        = "S1"
    }
    prod = @{
        ResourceGroup = "rg-pricescout-prod"
        AppServicePlan = "plan-pricescout-prod"
        AppService = "pricescout-prod"
        SqlServer   = "sql-pricescout-prod"
        SqlDatabase = "pricescout"
        KeyVault = "kv-pricescout-prod"
        APIM = "apim-pricescout-prod"
        ServiceBus = "sb-pricescout-prod"
        AppServiceSku = "P1v2"
        SqlSku        = "GP_Gen5_2"
    }
}

$envConfig = $config[$Environment]

Write-Host ""
Write-Host "🚀 PriceScout Infrastructure Deployment" -ForegroundColor Cyan
Write-Host "=" * 80
Write-Host ""

# ============================================================================
# PREREQUISITES CHECK
# ============================================================================

Write-Host "📋 Prerequisites Check" -ForegroundColor Yellow

# Check Azure CLI
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Azure CLI is not installed" -ForegroundColor Red
    Write-Host "   Install from: https://aka.ms/installazurecliwindows" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Azure CLI installed" -ForegroundColor Green

# Check login status
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "❌ Not logged in to Azure" -ForegroundColor Red
    Write-Host "   Running 'az login'..." -ForegroundColor Yellow
    az login
    $account = az account show | ConvertFrom-Json
}

Write-Host "✅ Logged in as: $($account.user.name)" -ForegroundColor Green

# Set subscription if specified
if ($SubscriptionId) {
    az account set --subscription $SubscriptionId
    $account = az account show | ConvertFrom-Json
}

Write-Host "✅ Using subscription: $($account.name)" -ForegroundColor Green
Write-Host "   Subscription ID: $($account.id)" -ForegroundColor Gray
Write-Host ""

# Generate a strong SQL admin password for this run (saved in deployment json)
function New-StrongPassword {
    param([int]$Length = 24)
    $upper = 65..90 | ForEach-Object {[char]$_}
    $lower = 97..122 | ForEach-Object {[char]$_}
    $digits = 48..57 | ForEach-Object {[char]$_}
    $symbols = '!@#$%^&*()-_=+[]{}' .ToCharArray()
    $all = $upper + $lower + $digits + $symbols
    $rand = -join (1..($Length-4) | ForEach-Object { $all | Get-Random })
    # Ensure complexity
    $pick = (Get-Random $upper) + (Get-Random $lower) + (Get-Random $digits) + (Get-Random $symbols)
    -join ((($rand + $pick).ToCharArray() | Sort-Object {Get-Random}))
}

$SqlAdminPasswordPlain = New-StrongPassword

# ============================================================================
# CONFIGURATION SUMMARY
# ============================================================================

Write-Host "📝 Deployment Configuration" -ForegroundColor Yellow
Write-Host "   Environment:       $Environment" -ForegroundColor White
Write-Host "   Location:          $Location" -ForegroundColor White
Write-Host "   Resource Group:    $($envConfig.ResourceGroup)" -ForegroundColor White
Write-Host "   App Service:       $($envConfig.AppService)" -ForegroundColor White
Write-Host "   SQL Server:        $($envConfig.SqlServer)" -ForegroundColor White
Write-Host "   SQL Database:      $($envConfig.SqlDatabase)" -ForegroundColor White
Write-Host "   Key Vault:         $($envConfig.KeyVault)" -ForegroundColor White
Write-Host "   APIM:              $($envConfig.APIM)" -ForegroundColor White
Write-Host "   Service Bus:       $($envConfig.ServiceBus)" -ForegroundColor White
Write-Host ""

if ($WhatIf) {
    Write-Host "⚠️  WHAT-IF MODE: No resources will be created" -ForegroundColor Yellow
    Write-Host ""
}

# Confirm deployment
if (-not $WhatIf) {
    Write-Host "⚠️  This will create Azure resources and incur costs" -ForegroundColor Yellow
    $confirm = Read-Host "Continue with deployment? (yes/no)"
    if ($confirm -ne 'yes') {
        Write-Host "Deployment cancelled" -ForegroundColor Yellow
        exit 0
    }
    Write-Host ""
}

# ============================================================================
# RESOURCE GROUP
# ============================================================================

Write-Host "📦 Creating Resource Group" -ForegroundColor Yellow

$rgExists = az group exists --name $envConfig.ResourceGroup | ConvertFrom-Json

if ($rgExists) {
    Write-Host "✅ Resource group already exists: $($envConfig.ResourceGroup)" -ForegroundColor Green
} else {
    if ($WhatIf) {
        Write-Host "   [WHAT-IF] Would create resource group: $($envConfig.ResourceGroup)" -ForegroundColor Gray
    } else {
        az group create `
            --name $envConfig.ResourceGroup `
            --location $Location `
            --output none
        
        Write-Host "✅ Resource group created: $($envConfig.ResourceGroup)" -ForegroundColor Green
    }
}
Write-Host ""

# ============================================================================
# BICEP VALIDATION
# ============================================================================

if (-not $SkipValidation) {
    Write-Host "🔍 Validating Bicep Templates" -ForegroundColor Yellow
    
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $iacDir = Join-Path $scriptDir "iac"
    $mainBicep = Join-Path $iacDir "main.bicep"
    
    if (-not (Test-Path $mainBicep)) {
        Write-Host "❌ Main Bicep template not found: $mainBicep" -ForegroundColor Red
        exit 1
    }
    
    try {
        az deployment group validate `
            --resource-group $envConfig.ResourceGroup `
            --template-file $mainBicep `
            --parameters location=$Location `
                        appServicePlanName=$envConfig.AppServicePlan `
                        appServiceName=$envConfig.AppService `
                        sqlServerName=$envConfig.SqlServer `
                        sqlDatabaseName=$envConfig.SqlDatabase `
                        sqlAdminPassword=$SqlAdminPasswordPlain `
                        keyVaultName=$envConfig.KeyVault `
                        apimServiceName=$envConfig.APIM `
                        serviceBusNamespaceName=$envConfig.ServiceBus `
            --output none
        
        Write-Host "✅ Bicep validation passed" -ForegroundColor Green
    } catch {
        Write-Host "❌ Bicep validation failed" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        exit 1
    }
    Write-Host ""
}

# ============================================================================
# INFRASTRUCTURE DEPLOYMENT
# ============================================================================

if ($WhatIf) {
    Write-Host "🔍 What-If Analysis" -ForegroundColor Yellow
    
    az deployment group what-if `
        --resource-group $envConfig.ResourceGroup `
        --template-file $mainBicep `
        --parameters location=$Location `
                    appServicePlanName=$envConfig.AppServicePlan `
                    appServiceName=$envConfig.AppService `
                    sqlServerName=$envConfig.SqlServer `
                    sqlDatabaseName=$envConfig.SqlDatabase `
                    sqlAdminPassword=$SqlAdminPasswordPlain `
                    keyVaultName=$envConfig.KeyVault `
                    apimServiceName=$envConfig.APIM `
                    serviceBusNamespaceName=$envConfig.ServiceBus
    
    Write-Host ""
    Write-Host "✅ What-If analysis complete" -ForegroundColor Green
    exit 0
}

Write-Host "🚀 Deploying Infrastructure" -ForegroundColor Yellow
Write-Host "   This may take 10-15 minutes..." -ForegroundColor Gray
Write-Host ""

$deploymentName = "pricescout-$Environment-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

try {
    $deployment = az deployment group create `
        --name $deploymentName `
        --resource-group $envConfig.ResourceGroup `
        --template-file $mainBicep `
        --parameters location=$Location `
                    appServicePlanName=$envConfig.AppServicePlan `
                    appServiceName=$envConfig.AppService `
                    sqlServerName=$envConfig.SqlServer `
                    sqlDatabaseName=$envConfig.SqlDatabase `
                    sqlAdminPassword=$SqlAdminPasswordPlain `
                    keyVaultName=$envConfig.KeyVault `
                    apimServiceName=$envConfig.APIM `
                    serviceBusNamespaceName=$envConfig.ServiceBus `
        --output json | ConvertFrom-Json
    
    Write-Host "✅ Infrastructure deployment complete" -ForegroundColor Green
    Write-Host ""
    
} catch {
    Write-Host "❌ Deployment failed" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

# ============================================================================
# POST-DEPLOYMENT CONFIGURATION
# ============================================================================

Write-Host "⚙️  Post-Deployment Configuration" -ForegroundColor Yellow

# Get App Service principal ID
Write-Host "   Retrieving App Service Managed Identity..." -ForegroundColor Gray
$appServiceId = az webapp identity show `
    --name $envConfig.AppService `
    --resource-group $envConfig.ResourceGroup `
    --query principalId `
    --output tsv

if ($appServiceId) {
    Write-Host "   ✅ Managed Identity: $appServiceId" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  Warning: Could not retrieve Managed Identity" -ForegroundColor Yellow
}

# Get APIM Gateway URL
Write-Host "   Retrieving APIM Gateway URL..." -ForegroundColor Gray
$apimGateway = az apim show `
    --name $envConfig.APIM `
    --resource-group $envConfig.ResourceGroup `
    --query gatewayUrl `
    --output tsv

if ($apimGateway) {
    Write-Host "   ✅ APIM Gateway: $apimGateway" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  Warning: Could not retrieve APIM Gateway URL" -ForegroundColor Yellow
}

# Compute SQL Server FQDN
Write-Host "   Computing SQL Server FQDN..." -ForegroundColor Gray
$sqlFqdn = "$($envConfig.SqlServer).database.windows.net"
Write-Host "   ✅ SQL Server: $sqlFqdn" -ForegroundColor Green

Write-Host ""

# ============================================================================
# DEPLOYMENT SUMMARY
# ============================================================================

Write-Host "=" * 80
Write-Host "✅ Deployment Complete!" -ForegroundColor Green
Write-Host "=" * 80
Write-Host ""
Write-Host "📋 Resource Summary:" -ForegroundColor Cyan
Write-Host "   Resource Group:    $($envConfig.ResourceGroup)" -ForegroundColor White
Write-Host "   App Service:       https://$($envConfig.AppService).azurewebsites.net" -ForegroundColor White
Write-Host "   APIM Gateway:      $apimGateway" -ForegroundColor White
Write-Host "   SQL Server:        $sqlFqdn" -ForegroundColor White
Write-Host "   Key Vault:         https://$($envConfig.KeyVault).vault.azure.net" -ForegroundColor White
Write-Host ""

Write-Host "🔑 Next Steps:" -ForegroundColor Cyan
Write-Host "   1. Populate Key Vault with secrets:" -ForegroundColor White
Write-Host "      az keyvault secret set --vault-name $($envConfig.KeyVault) --name DATABASE-URL --value 'mssql+pyodbc://<user>:<pass>@$($envConfig.SqlServer).database.windows.net:1433/$($envConfig.SqlDatabase)?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes;TrustServerCertificate=no'" -ForegroundColor Gray
Write-Host "      az keyvault secret set --vault-name $($envConfig.KeyVault) --name JWT-SECRET-KEY --value '<secret>'" -ForegroundColor Gray
Write-Host ""
Write-Host "   2. Deploy APIM policies:" -ForegroundColor White
Write-Host "      .\azure\iac\deploy-apim-policies.ps1 -ResourceGroup $($envConfig.ResourceGroup) -ApimServiceName $($envConfig.APIM)" -ForegroundColor Gray
Write-Host ""
Write-Host "   3. Deploy application code:" -ForegroundColor White
Write-Host "      az webapp deployment source config-zip --resource-group $($envConfig.ResourceGroup) --name $($envConfig.AppService) --src app.zip" -ForegroundColor Gray
Write-Host ""
Write-Host "   4. Verify deployment:" -ForegroundColor White
Write-Host "      .\azure\verify-deployment.ps1 -Environment $Environment" -ForegroundColor Gray
Write-Host ""

# Save deployment info to file
$deploymentInfo = @{
    Environment = $Environment
    DeploymentName = $deploymentName
    DeploymentDate = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    ResourceGroup = $envConfig.ResourceGroup
    AppService = $envConfig.AppService
    AppServiceUrl = "https://$($envConfig.AppService).azurewebsites.net"
    APIMGateway = $apimGateway
    SqlServer = $sqlFqdn
    KeyVault = "https://$($envConfig.KeyVault).vault.azure.net"
    ManagedIdentity = $appServiceId
}

$deploymentInfo | ConvertTo-Json | Out-File -FilePath "deployment-$Environment.json" -Encoding UTF8

Write-Host "💾 Deployment info saved to: deployment-$Environment.json" -ForegroundColor Gray
Write-Host ""
