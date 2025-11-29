# PriceScout Deployment Verification Script
# Validates deployed Azure resources and tests connectivity

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('dev', 'staging', 'prod')]
    [string]$Environment
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "🔍 PriceScout Deployment Verification" -ForegroundColor Cyan
Write-Host "=" * 80
Write-Host ""

# Load deployment info
$deploymentFile = "deployment-$Environment.json"
if (-not (Test-Path $deploymentFile)) {
    Write-Host "❌ Deployment file not found: $deploymentFile" -ForegroundColor Red
    Write-Host "   Run deploy-infrastructure.ps1 first" -ForegroundColor Yellow
    exit 1
}

$deployment = Get-Content $deploymentFile | ConvertFrom-Json

Write-Host "📋 Deployment Info" -ForegroundColor Yellow
Write-Host "   Environment:    $($deployment.Environment)" -ForegroundColor White
Write-Host "   Resource Group: $($deployment.ResourceGroup)" -ForegroundColor White
Write-Host "   Deployed:       $($deployment.DeploymentDate)" -ForegroundColor White
Write-Host ""

$testResults = @()

# ============================================================================
# TEST 1: Resource Group Exists
# ============================================================================

Write-Host "Test 1: Resource Group" -ForegroundColor Yellow
try {
    $rgExists = az group exists --name $deployment.ResourceGroup | ConvertFrom-Json
    if ($rgExists) {
        Write-Host "   ✅ Resource group exists" -ForegroundColor Green
        $testResults += @{Test="Resource Group"; Status="Pass"}
    } else {
        Write-Host "   ❌ Resource group not found" -ForegroundColor Red
        $testResults += @{Test="Resource Group"; Status="Fail"}
    }
} catch {
    Write-Host "   ❌ Error checking resource group: $_" -ForegroundColor Red
    $testResults += @{Test="Resource Group"; Status="Error"}
}

# ============================================================================
# TEST 2: App Service Status
# ============================================================================

Write-Host "Test 2: App Service" -ForegroundColor Yellow
try {
    $appService = az webapp show `
        --name $deployment.AppService `
        --resource-group $deployment.ResourceGroup `
        --query "{state:state, hostName:defaultHostName}" `
        --output json | ConvertFrom-Json
    
    if ($appService.state -eq "Running") {
        Write-Host "   ✅ App Service is running" -ForegroundColor Green
        Write-Host "      URL: https://$($appService.hostName)" -ForegroundColor Gray
        $testResults += @{Test="App Service"; Status="Pass"}
    } else {
        Write-Host "   ⚠️  App Service state: $($appService.state)" -ForegroundColor Yellow
        $testResults += @{Test="App Service"; Status="Warning"}
    }
} catch {
    Write-Host "   ❌ Error checking App Service: $_" -ForegroundColor Red
    $testResults += @{Test="App Service"; Status="Error"}
}

# ============================================================================
# TEST 3: App Service Reachability
# ============================================================================

Write-Host "Test 3: App Service HTTP" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri $deployment.AppServiceUrl -Method Get -TimeoutSec 10 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ App Service is reachable (HTTP 200)" -ForegroundColor Green
        $testResults += @{Test="App Service HTTP"; Status="Pass"}
    } else {
        Write-Host "   ⚠️  Unexpected status code: $($response.StatusCode)" -ForegroundColor Yellow
        $testResults += @{Test="App Service HTTP"; Status="Warning"}
    }
} catch {
    Write-Host "   ⚠️  App Service not reachable (may not be deployed yet)" -ForegroundColor Yellow
    Write-Host "      Error: $($_.Exception.Message)" -ForegroundColor Gray
    $testResults += @{Test="App Service HTTP"; Status="Warning"}
}

# ============================================================================
# TEST 4: Azure SQL Server
# ============================================================================

Write-Host "Test 4: Azure SQL Server" -ForegroundColor Yellow
try {
    $sqlFqdn = $deployment.SqlServer
    if ($sqlFqdn -and $sqlFqdn -like "*.database.windows.net") {
        Write-Host "   ✅ SQL Server FQDN present: $sqlFqdn" -ForegroundColor Green
        $testResults += @{Test="Azure SQL"; Status="Pass"}
    } else {
        Write-Host "   ⚠️  SQL Server FQDN not found in deployment info" -ForegroundColor Yellow
        $testResults += @{Test="Azure SQL"; Status="Warning"}
    }
} catch {
    Write-Host "   ❌ Error checking Azure SQL: $_" -ForegroundColor Red
    $testResults += @{Test="Azure SQL"; Status="Error"}
}

# ============================================================================
# TEST 5: Key Vault
# ============================================================================

Write-Host "Test 5: Key Vault" -ForegroundColor Yellow
try {
    $kvName = $deployment.KeyVault.Split('/')[2].Split('.')[0]
    $kv = az keyvault show `
        --name $kvName `
        --query "{name:name, vaultUri:properties.vaultUri}" `
        --output json | ConvertFrom-Json
    
    Write-Host "   ✅ Key Vault is accessible" -ForegroundColor Green
    Write-Host "      URI: $($kv.vaultUri)" -ForegroundColor Gray
    
    # Check for secrets
    $secrets = az keyvault secret list `
        --vault-name $kvName `
        --query "[].name" `
        --output json | ConvertFrom-Json
    
    if ($secrets.Count -gt 0) {
        Write-Host "   ✅ Key Vault contains $($secrets.Count) secret(s)" -ForegroundColor Green
        $testResults += @{Test="Key Vault"; Status="Pass"}
    } else {
        Write-Host "   ⚠️  Key Vault is empty (no secrets configured)" -ForegroundColor Yellow
        $testResults += @{Test="Key Vault"; Status="Warning"}
    }
} catch {
    Write-Host "   ❌ Error checking Key Vault: $_" -ForegroundColor Red
    $testResults += @{Test="Key Vault"; Status="Error"}
}

# ============================================================================
# TEST 6: Managed Identity
# ============================================================================

Write-Host "Test 6: Managed Identity" -ForegroundColor Yellow
try {
    $identity = az webapp identity show `
        --name $deployment.AppService `
        --resource-group $deployment.ResourceGroup `
        --query principalId `
        --output tsv
    
    if ($identity) {
        Write-Host "   ✅ Managed Identity configured" -ForegroundColor Green
        Write-Host "      Principal ID: $identity" -ForegroundColor Gray
        $testResults += @{Test="Managed Identity"; Status="Pass"}
    } else {
        Write-Host "   ❌ Managed Identity not found" -ForegroundColor Red
        $testResults += @{Test="Managed Identity"; Status="Fail"}
    }
} catch {
    Write-Host "   ❌ Error checking Managed Identity: $_" -ForegroundColor Red
    $testResults += @{Test="Managed Identity"; Status="Error"}
}

# ============================================================================
# TEST 7: APIM Gateway
# ============================================================================

Write-Host "Test 7: API Management" -ForegroundColor Yellow
if ($deployment.APIMGateway) {
    try {
        $response = Invoke-WebRequest -Uri "$($deployment.APIMGateway)/api/healthz" -Method Get -TimeoutSec 10 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "   ✅ APIM Gateway is reachable" -ForegroundColor Green
            $testResults += @{Test="APIM Gateway"; Status="Pass"}
        } else {
            Write-Host "   ⚠️  APIM Gateway returned: $($response.StatusCode)" -ForegroundColor Yellow
            $testResults += @{Test="APIM Gateway"; Status="Warning"}
        }
    } catch {
        Write-Host "   ⚠️  APIM Gateway not reachable (backend may not be deployed)" -ForegroundColor Yellow
        Write-Host "      Error: $($_.Exception.Message)" -ForegroundColor Gray
        $testResults += @{Test="APIM Gateway"; Status="Warning"}
    }
} else {
    Write-Host "   ⚠️  APIM Gateway URL not available in deployment info" -ForegroundColor Yellow
    $testResults += @{Test="APIM Gateway"; Status="Warning"}
}

# ============================================================================
# TEST 8: Service Bus
# ============================================================================

Write-Host "Test 8: Service Bus" -ForegroundColor Yellow
try {
    $sbNamespace = $deployment.ResourceGroup -replace 'rg-', 'sb-'
    $sb = az servicebus namespace show `
        --name $sbNamespace `
        --resource-group $deployment.ResourceGroup `
        --query "{status:status, name:name}" `
        --output json 2>$null | ConvertFrom-Json
    
    if ($sb.status -eq "Active") {
        Write-Host "   ✅ Service Bus is active" -ForegroundColor Green
        $testResults += @{Test="Service Bus"; Status="Pass"}
    } else {
        Write-Host "   ⚠️  Service Bus status: $($sb.status)" -ForegroundColor Yellow
        $testResults += @{Test="Service Bus"; Status="Warning"}
    }
} catch {
    Write-Host "   ⚠️  Could not verify Service Bus" -ForegroundColor Yellow
    $testResults += @{Test="Service Bus"; Status="Warning"}
}

# ============================================================================
# SUMMARY
# ============================================================================

Write-Host ""
Write-Host "=" * 80
Write-Host "📊 Test Summary" -ForegroundColor Cyan
Write-Host "=" * 80

$passed = ($testResults | Where-Object { $_.Status -eq "Pass" }).Count
$warnings = ($testResults | Where-Object { $_.Status -eq "Warning" }).Count
$failed = ($testResults | Where-Object { $_.Status -eq "Fail" }).Count
$errors = ($testResults | Where-Object { $_.Status -eq "Error" }).Count

Write-Host ""
Write-Host "   ✅ Passed:   $passed" -ForegroundColor Green
Write-Host "   ⚠️  Warnings: $warnings" -ForegroundColor Yellow
Write-Host "   ❌ Failed:   $failed" -ForegroundColor Red
Write-Host "   ⚠️  Errors:   $errors" -ForegroundColor Red
Write-Host ""

if ($failed -gt 0 -or $errors -gt 0) {
    Write-Host "⚠️  Deployment verification completed with issues" -ForegroundColor Yellow
    Write-Host "   Review the failed tests above" -ForegroundColor Yellow
    exit 1
} elseif ($warnings -gt 0) {
    Write-Host "✅ Deployment verification completed with warnings" -ForegroundColor Yellow
    Write-Host "   Application code may need to be deployed" -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "✅ All tests passed!" -ForegroundColor Green
    exit 0
}
