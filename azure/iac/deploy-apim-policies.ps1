# Deploy APIM Policies to Azure API Management
# This script automates the deployment of API Management policies

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,
    
    [Parameter(Mandatory=$true)]
    [string]$ApimServiceName,
    
    [Parameter(Mandatory=$true)]
    [string]$ApiId = "price-scout-api",
    
    [Parameter(Mandatory=$false)]
    [string]$TenantId,
    
    [Parameter(Mandatory=$false)]
    [string]$ClientId
)

$ErrorActionPreference = "Stop"

Write-Host "🚀 Deploying APIM Policies for PriceScout API" -ForegroundColor Cyan
Write-Host "=" * 60

# Verify Azure CLI is installed
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Azure CLI is not installed. Please install it first." -ForegroundColor Red
    exit 1
}

# Check if logged in
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "❌ Not logged in to Azure. Running 'az login'..." -ForegroundColor Yellow
    az login
}

Write-Host "✅ Logged in as: $($account.user.name)" -ForegroundColor Green
Write-Host "✅ Subscription: $($account.name) ($($account.id))" -ForegroundColor Green
Write-Host ""

# Paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$policiesDir = Join-Path $scriptDir "policies"
$apiPolicyPath = Join-Path $policiesDir "api-policy.xml"
$publicPolicyPath = Join-Path $policiesDir "public-endpoints-policy.xml"

# Verify policy files exist
if (-not (Test-Path $apiPolicyPath)) {
    Write-Host "❌ API policy file not found: $apiPolicyPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $publicPolicyPath)) {
    Write-Host "❌ Public endpoints policy file not found: $publicPolicyPath" -ForegroundColor Red
    exit 1
}

# Replace placeholders if TenantId and ClientId are provided
$apiPolicyContent = Get-Content $apiPolicyPath -Raw

if ($TenantId -and $ClientId) {
    Write-Host "🔧 Replacing placeholders with actual values..." -ForegroundColor Yellow
    $apiPolicyContent = $apiPolicyContent -replace '{{TENANT_ID}}', $TenantId
    $apiPolicyContent = $apiPolicyContent -replace '{{CLIENT_ID}}', $ClientId
    
    # Save temporary file with replacements
    $tempPolicyPath = Join-Path $env:TEMP "api-policy-temp.xml"
    $apiPolicyContent | Out-File -FilePath $tempPolicyPath -Encoding UTF8
    $apiPolicyPath = $tempPolicyPath
} else {
    Write-Host "⚠️  TenantId and ClientId not provided. JWT validation will need manual configuration." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "📋 Deployment Configuration:" -ForegroundColor Cyan
Write-Host "   Resource Group:   $ResourceGroup"
Write-Host "   APIM Service:     $ApimServiceName"
Write-Host "   API ID:           $ApiId"
Write-Host ""

# Deploy API-level policy
Write-Host "📤 Deploying API-level policy..." -ForegroundColor Yellow
try {
    az apim api policy create `
        --resource-group $ResourceGroup `
        --service-name $ApimServiceName `
        --api-id $ApiId `
        --xml-policy "@$apiPolicyPath" `
        --output none
    
    Write-Host "✅ API-level policy deployed successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to deploy API-level policy: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Get list of operations for the API
Write-Host "📋 Fetching API operations..." -ForegroundColor Yellow
$operations = az apim api operation list `
    --resource-group $ResourceGroup `
    --service-name $ApimServiceName `
    --api-id $ApiId `
    --query "[].{id:name, displayName:displayName}" `
    --output json | ConvertFrom-Json

if ($operations) {
    Write-Host "✅ Found $($operations.Count) operations" -ForegroundColor Green
    Write-Host ""
    
    # Apply public endpoint policy to specific operations
    $publicOperations = $operations | Where-Object { 
        $_.displayName -match "docs|openapi|health" 
    }
    
    if ($publicOperations) {
        Write-Host "📤 Applying public endpoint policy to:" -ForegroundColor Yellow
        foreach ($op in $publicOperations) {
            Write-Host "   - $($op.displayName) ($($op.id))"
            
            try {
                az apim api operation policy create `
                    --resource-group $ResourceGroup `
                    --service-name $ApimServiceName `
                    --api-id $ApiId `
                    --operation-id $op.id `
                    --xml-policy "@$publicPolicyPath" `
                    --output none
                
                Write-Host "     ✅ Policy applied" -ForegroundColor Green
            } catch {
                Write-Host "     ⚠️  Warning: Failed to apply policy: $_" -ForegroundColor Yellow
            }
        }
    }
} else {
    Write-Host "⚠️  No operations found. API might need to be imported first." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=" * 60
Write-Host "✅ Policy deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Verify policies in Azure Portal: https://portal.azure.com"
Write-Host "2. Test rate limiting with multiple requests"
Write-Host "3. Test JWT validation with and without tokens"
Write-Host "4. Monitor requests in APIM Analytics"
Write-Host ""

# Clean up temp file if created
if ($TenantId -and $ClientId -and (Test-Path $tempPolicyPath)) {
    Remove-Item $tempPolicyPath -Force
}
