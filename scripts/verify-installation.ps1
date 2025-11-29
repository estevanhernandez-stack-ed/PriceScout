# Installation Verification Script
# Verifies Docker and Azure CLI are properly installed

Write-Host @"
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║          PriceScout Installation Verification                  ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

$allGood = $true

# Check Docker
Write-Host "`nChecking Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "  ✓ Docker installed: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Docker not found" -ForegroundColor Red
    $allGood = $false
}

# Check Docker Compose
Write-Host "`nChecking Docker Compose..." -ForegroundColor Yellow
try {
    $composeVersion = docker compose version
    Write-Host "  ✓ Docker Compose installed: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Docker Compose not found" -ForegroundColor Red
    $allGood = $false
}

# Check Docker daemon
Write-Host "`nChecking Docker daemon..." -ForegroundColor Yellow
try {
    $null = docker ps 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Docker daemon is running" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ Docker daemon not running - Please start Docker Desktop" -ForegroundColor Yellow
        Write-Host "    Open Docker Desktop from Start Menu" -ForegroundColor Gray
        $allGood = $false
    }
} catch {
    Write-Host "  ⚠ Cannot connect to Docker daemon" -ForegroundColor Yellow
    $allGood = $false
}

# Check Azure CLI
Write-Host "`nChecking Azure CLI..." -ForegroundColor Yellow
try {
    $azVersion = az version --query '"azure-cli"' -o tsv 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Azure CLI installed: $azVersion" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Azure CLI not responding" -ForegroundColor Red
        $allGood = $false
    }
} catch {
    Write-Host "  ✗ Azure CLI not found" -ForegroundColor Red
    $allGood = $false
}

# Check Azure login status
Write-Host "`nChecking Azure login..." -ForegroundColor Yellow
try {
    $account = az account show 2>$null | ConvertFrom-Json
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Logged in as: $($account.user.name)" -ForegroundColor Green
        Write-Host "    Subscription: $($account.name)" -ForegroundColor Gray
    } else {
        Write-Host "  ℹ Not logged in to Azure (run: az login)" -ForegroundColor Blue
    }
} catch {
    Write-Host "  ℹ Not logged in to Azure (run: az login)" -ForegroundColor Blue
}

# Summary
Write-Host "`n" + "="*60 -ForegroundColor Cyan
if ($allGood) {
    Write-Host "✓ All tools installed and ready!" -ForegroundColor Green
    Write-Host "`nNext steps:" -ForegroundColor Yellow
    Write-Host "  1. Login to Azure: az login" -ForegroundColor White
    Write-Host "  2. Test Docker: docker compose up -d" -ForegroundColor White
    Write-Host "  3. Run Task 5: .\deploy\provision-azure-resources.ps1 -Environment dev" -ForegroundColor White
} else {
    Write-Host "⚠ Some tools need attention" -ForegroundColor Yellow
    Write-Host "`nActions needed:" -ForegroundColor Yellow
    Write-Host "  - If Docker daemon not running: Start Docker Desktop" -ForegroundColor White
    Write-Host "  - You may need to restart PowerShell" -ForegroundColor White
    Write-Host "  - You may need to logout/login for Docker" -ForegroundColor White
}
Write-Host "="*60 + "`n" -ForegroundColor Cyan
