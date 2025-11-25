# Azure Resource Verification Script
# Version: 1.0.0
# Purpose: Verify all Azure resources are properly provisioned and configured

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('dev', 'staging', 'prod')]
    [string]$Environment,
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus"
)

$ErrorActionPreference = "Continue"

# Configuration
$config = @{
    ResourceGroup = "pricescout-$Environment-rg-$Location"
    PostgresServer = "pricescout-db-$Environment-$Location"
    KeyVault = "pricescout-kv-$Environment"
    ContainerRegistry = "pricescoutacr$Environment"
    AppService = "pricescout-app-$Environment-$Location"
    AppInsights = "pricescout-ai-$Environment"
}

$results = @{
    Passed = @()
    Failed = @()
    Warnings = @()
}

function Write-TestHeader {
    param([string]$Title)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Test-Check {
    param(
        [string]$Name,
        [scriptblock]$Test,
        [string]$SuccessMessage,
        [string]$FailureMessage
    )
    
    Write-Host "`nTesting: $Name..." -ForegroundColor Yellow -NoNewline
    
    try {
        $result = & $Test
        if ($result) {
            Write-Host " ✓" -ForegroundColor Green
            Write-Host "  $SuccessMessage" -ForegroundColor Gray
            $results.Passed += $Name
            return $true
        } else {
            Write-Host " ✗" -ForegroundColor Red
            Write-Host "  $FailureMessage" -ForegroundColor Red
            $results.Failed += $Name
            return $false
        }
    } catch {
        Write-Host " ✗" -ForegroundColor Red
        Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
        $results.Failed += $Name
        return $false
    }
}

# Start verification
Write-Host @"
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║          PriceScout Azure Resource Verification                ║
║                     Version 1.0.0                              ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

Write-Host "`nEnvironment: $Environment" -ForegroundColor White
Write-Host "Location: $Location" -ForegroundColor White

# Test Azure CLI
Write-TestHeader "Prerequisites"

Test-Check -Name "Azure CLI Installed" -Test {
    $null -ne (Get-Command az -ErrorAction SilentlyContinue)
} -SuccessMessage "Azure CLI is available" -FailureMessage "Azure CLI not found"

Test-Check -Name "Azure Login Status" -Test {
    $account = az account show 2>$null | ConvertFrom-Json
    $null -ne $account
} -SuccessMessage "Logged in as: $(az account show --query user.name -o tsv)" -FailureMessage "Not logged in to Azure"

# Test Resource Group
Write-TestHeader "Resource Group"

Test-Check -Name "Resource Group Exists" -Test {
    $exists = az group exists --name $config.ResourceGroup
    $exists -eq "true"
} -SuccessMessage "Resource group: $($config.ResourceGroup)" -FailureMessage "Resource group not found"

if ($results.Passed -contains "Resource Group Exists") {
    $resources = az resource list --resource-group $config.ResourceGroup | ConvertFrom-Json
    Write-Host "`n  Resources in group: $($resources.Count)" -ForegroundColor Gray
}

# Test PostgreSQL
Write-TestHeader "PostgreSQL Flexible Server"

Test-Check -Name "PostgreSQL Server Exists" -Test {
    $server = az postgres flexible-server show `
        --resource-group $config.ResourceGroup `
        --name $config.PostgresServer `
        2>$null | ConvertFrom-Json
    $null -ne $server
} -SuccessMessage "Server: $($config.PostgresServer).postgres.database.azure.com" -FailureMessage "PostgreSQL server not found"

if ($results.Passed -contains "PostgreSQL Server Exists") {
    Test-Check -Name "PostgreSQL Server Running" -Test {
        $server = az postgres flexible-server show `
            --resource-group $config.ResourceGroup `
            --name $config.PostgresServer `
            --query state -o tsv
        $server -eq "Ready"
    } -SuccessMessage "Server state: Ready" -FailureMessage "Server not ready"
    
    Test-Check -Name "Database Exists" -Test {
        $dbs = az postgres flexible-server db list `
            --resource-group $config.ResourceGroup `
            --server-name $config.PostgresServer `
            --query "[?name=='pricescout_db']" | ConvertFrom-Json
        $dbs.Count -gt 0
    } -SuccessMessage "Database: pricescout_db" -FailureMessage "Database 'pricescout_db' not found"
    
    $firewallRules = az postgres flexible-server firewall-rule list `
        --resource-group $config.ResourceGroup `
        --name $config.PostgresServer `
        2>$null | ConvertFrom-Json
    
    if ($firewallRules.Count -gt 0) {
        Write-Host "  ℹ Firewall rules configured: $($firewallRules.Count)" -ForegroundColor Blue
    } else {
        Write-Host "  ⚠ Warning: No firewall rules configured" -ForegroundColor Yellow
        $results.Warnings += "No PostgreSQL firewall rules"
    }
}

# Test Key Vault
Write-TestHeader "Azure Key Vault"

Test-Check -Name "Key Vault Exists" -Test {
    $vault = az keyvault show `
        --name $config.KeyVault `
        --resource-group $config.ResourceGroup `
        2>$null | ConvertFrom-Json
    $null -ne $vault
} -SuccessMessage "Key Vault: https://$($config.KeyVault).vault.azure.net" -FailureMessage "Key Vault not found"

if ($results.Passed -contains "Key Vault Exists") {
    Test-Check -Name "Key Vault Accessible" -Test {
        $secrets = az keyvault secret list --vault-name $config.KeyVault 2>$null
        $null -ne $secrets
    } -SuccessMessage "Can list secrets" -FailureMessage "Access denied to Key Vault"
    
    if ($results.Passed -contains "Key Vault Accessible") {
        $secretList = az keyvault secret list --vault-name $config.KeyVault | ConvertFrom-Json
        Write-Host "  ℹ Secrets stored: $($secretList.Count)" -ForegroundColor Blue
        
        if ($secretList.Count -eq 0) {
            Write-Host "  ⚠ Warning: No secrets stored yet" -ForegroundColor Yellow
            $results.Warnings += "No secrets in Key Vault"
        }
    }
}

# Test Container Registry
Write-TestHeader "Azure Container Registry"

Test-Check -Name "Container Registry Exists" -Test {
    $acr = az acr show `
        --name $config.ContainerRegistry `
        --resource-group $config.ResourceGroup `
        2>$null | ConvertFrom-Json
    $null -ne $acr
} -SuccessMessage "Registry: $($config.ContainerRegistry).azurecr.io" -FailureMessage "Container Registry not found"

if ($results.Passed -contains "Container Registry Exists") {
    Test-Check -Name "Admin User Enabled" -Test {
        $acr = az acr show `
            --name $config.ContainerRegistry `
            --query adminUserEnabled -o tsv
        $acr -eq "true"
    } -SuccessMessage "Admin user is enabled" -FailureMessage "Admin user not enabled"
    
    $repos = az acr repository list --name $config.ContainerRegistry 2>$null | ConvertFrom-Json
    if ($repos -and $repos.Count -gt 0) {
        Write-Host "  ℹ Repositories: $($repos.Count)" -ForegroundColor Blue
    } else {
        Write-Host "  ℹ No images pushed yet" -ForegroundColor Blue
    }
}

# Test Application Insights
Write-TestHeader "Application Insights"

Test-Check -Name "Application Insights Exists" -Test {
    $ai = az monitor app-insights component show `
        --app $config.AppInsights `
        --resource-group $config.ResourceGroup `
        2>$null | ConvertFrom-Json
    $null -ne $ai
} -SuccessMessage "App Insights: $($config.AppInsights)" -FailureMessage "Application Insights not found"

if ($results.Passed -contains "Application Insights Exists") {
    $connString = az monitor app-insights component show `
        --app $config.AppInsights `
        --resource-group $config.ResourceGroup `
        --query connectionString -o tsv 2>$null
    
    if ($connString) {
        Write-Host "  ℹ Connection string available" -ForegroundColor Blue
    }
}

# Test App Service
Write-TestHeader "App Service"

Test-Check -Name "App Service Exists" -Test {
    $webapp = az webapp show `
        --name $config.AppService `
        --resource-group $config.ResourceGroup `
        2>$null | ConvertFrom-Json
    $null -ne $webapp
} -SuccessMessage "App Service: https://$($config.AppService).azurewebsites.net" -FailureMessage "App Service not found"

if ($results.Passed -contains "App Service Exists") {
    Test-Check -Name "App Service Running" -Test {
        $state = az webapp show `
            --name $config.AppService `
            --resource-group $config.ResourceGroup `
            --query state -o tsv
        $state -eq "Running"
    } -SuccessMessage "App state: Running" -FailureMessage "App not running"
    
    Test-Check -Name "Managed Identity Enabled" -Test {
        $identity = az webapp identity show `
            --name $config.AppService `
            --resource-group $config.ResourceGroup `
            2>$null | ConvertFrom-Json
        $null -ne $identity.principalId
    } -SuccessMessage "Managed identity configured" -FailureMessage "Managed identity not enabled"
    
    $settings = az webapp config appsettings list `
        --name $config.AppService `
        --resource-group $config.ResourceGroup `
        2>$null | ConvertFrom-Json
    
    if ($settings) {
        Write-Host "  ℹ App settings configured: $($settings.Count)" -ForegroundColor Blue
    }
}

# Test connectivity
Write-TestHeader "Connectivity Tests"

if ($results.Passed -contains "App Service Running") {
    $url = "https://$($config.AppService).azurewebsites.net"
    Write-Host "`nTesting: App Service URL..." -ForegroundColor Yellow -NoNewline
    
    try {
        $response = Invoke-WebRequest -Uri $url -TimeoutSec 10 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host " ✓" -ForegroundColor Green
            Write-Host "  App is accessible (HTTP 200)" -ForegroundColor Gray
            $results.Passed += "App Service Accessible"
        } else {
            Write-Host " ⚠" -ForegroundColor Yellow
            Write-Host "  App returned HTTP $($response.StatusCode)" -ForegroundColor Yellow
            $results.Warnings += "App Service returned non-200 status"
        }
    } catch {
        Write-Host " ⚠" -ForegroundColor Yellow
        Write-Host "  App not responding (may need container deployment)" -ForegroundColor Yellow
        $results.Warnings += "App Service not responding"
    }
}

# Final Summary
Write-TestHeader "Verification Summary"

Write-Host "`nResults:" -ForegroundColor White
Write-Host "  Passed:   " -NoNewline -ForegroundColor Gray
Write-Host "$($results.Passed.Count)" -ForegroundColor Green

Write-Host "  Failed:   " -NoNewline -ForegroundColor Gray
Write-Host "$($results.Failed.Count)" -ForegroundColor $(if ($results.Failed.Count -gt 0) { "Red" } else { "Green" })

Write-Host "  Warnings: " -NoNewline -ForegroundColor Gray
Write-Host "$($results.Warnings.Count)" -ForegroundColor $(if ($results.Warnings.Count -gt 0) { "Yellow" } else { "Green" })

if ($results.Failed.Count -gt 0) {
    Write-Host "`nFailed Checks:" -ForegroundColor Red
    foreach ($fail in $results.Failed) {
        Write-Host "  ✗ $fail" -ForegroundColor Red
    }
}

if ($results.Warnings.Count -gt 0) {
    Write-Host "`nWarnings:" -ForegroundColor Yellow
    foreach ($warn in $results.Warnings) {
        Write-Host "  ⚠ $warn" -ForegroundColor Yellow
    }
}

# Next steps
Write-Host "`nNext Steps:" -ForegroundColor Yellow

if ($results.Failed.Count -eq 0) {
    Write-Host "  ✓ All critical resources provisioned successfully!" -ForegroundColor Green
    Write-Host "`n  Ready for Task 6: Database Migration & Secrets" -ForegroundColor Cyan
    Write-Host "    1. Apply schema.sql to PostgreSQL" -ForegroundColor White
    Write-Host "    2. Migrate data from SQLite" -ForegroundColor White
    Write-Host "    3. Store connection strings in Key Vault" -ForegroundColor White
} else {
    Write-Host "  ⚠ Please fix failed checks before proceeding" -ForegroundColor Yellow
    Write-Host "    - Review deploy/AZURE_PROVISIONING_GUIDE.md" -ForegroundColor White
    Write-Host "    - Re-run provision-azure-resources.ps1 if needed" -ForegroundColor White
}

# Return exit code
if ($results.Failed.Count -eq 0) {
    exit 0
} else {
    exit 1
}
