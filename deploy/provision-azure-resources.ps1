# PriceScout Azure Resource Provisioning Script
# Version: 1.0.0
# Date: November 13, 2025
# Purpose: Create all required Azure resources for PriceScout deployment
#
# Prerequisites:
#   - Azure CLI installed (az --version)
#   - Azure subscription with Owner/Contributor role
#   - PowerShell 7+
#
# Usage:
#   .\provision-azure-resources.ps1 -Environment prod -Location eastus
#   .\provision-azure-resources.ps1 -Environment dev -Location eastus -SkipConfirmation

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('dev', 'staging', 'prod')]
    [string]$Environment,
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus",
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipConfirmation,
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun
)

# =============================================================================
# CONFIGURATION
# =============================================================================

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Base naming convention: pricescout-{resource}-{env}-{location}
$config = @{
    ResourceGroup = "pricescout-$Environment-rg-$Location"
    PostgresServer = "pricescout-db-$Environment-$Location"
    KeyVault = "pricescout-kv-$Environment"  # 24 char limit, no location
    ContainerRegistry = "pricescoutacr$Environment"  # alphanumeric only
    AppServicePlan = "pricescout-plan-$Environment"
    AppService = "pricescout-app-$Environment-$Location"
    LogAnalytics = "pricescout-logs-$Environment"
    AppInsights = "pricescout-ai-$Environment"
    
    # Database configuration
    PostgresAdminUser = "pricescout_admin"
    PostgresVersion = "14"
    PostgresSku = if ($Environment -eq "prod") { "Standard_B2s" } else { "Standard_B1ms" }
    PostgresStorageGB = if ($Environment -eq "prod") { 64 } else { 32 }
    
    # Container registry
    AcrSku = if ($Environment -eq "prod") { "Standard" } else { "Basic" }
    
    # App Service
    AppServiceSku = if ($Environment -eq "prod") { "B2" } else { "B1" }
    
    # Tags
    Tags = @{
        Environment = $Environment
        Application = "PriceScout"
        ManagedBy = "PowerShell"
        CostCenter = "Engineering"
        DeploymentDate = (Get-Date -Format "yyyy-MM-dd")
    }
}

# =============================================================================
# FUNCTIONS
# =============================================================================

function Write-Section {
    param([string]$Title)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
}

function Write-Step {
    param([string]$Message)
    Write-Host "▶ $Message" -ForegroundColor Yellow
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Blue
}

function Test-AzureCLI {
    Write-Step "Checking Azure CLI installation..."
    try {
        $version = az version --query '\"azure-cli\"' -o tsv 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Azure CLI version: $version"
            return $true
        }
    } catch {
        Write-Error "Azure CLI not found. Install from: https://aka.ms/installazurecliwindows"
        return $false
    }
}

function Test-AzureLogin {
    Write-Step "Checking Azure login status..."
    $account = az account show 2>$null | ConvertFrom-Json
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Logged in as: $($account.user.name)"
        Write-Info "Subscription: $($account.name) ($($account.id))"
        return $true
    } else {
        Write-Error "Not logged in to Azure"
        Write-Info "Run: az login"
        return $false
    }
}

function Get-SecurePassword {
    param([string]$Prompt = "Enter password")
    
    Add-Type -AssemblyName System.Web
    $password = [System.Web.Security.Membership]::GeneratePassword(16, 4)
    
    # Ensure password meets PostgreSQL requirements
    $password = $password -replace '[<>%&]', 'A'  # Remove special chars that cause issues
    $password = "Aa1!" + $password  # Ensure complexity
    
    return $password
}

function Show-DeploymentSummary {
    Write-Section "Deployment Configuration Summary"
    
    Write-Host "Environment:          " -NoNewline -ForegroundColor Gray
    Write-Host $Environment -ForegroundColor White
    
    Write-Host "Location:             " -NoNewline -ForegroundColor Gray
    Write-Host $Location -ForegroundColor White
    
    Write-Host "`nResources to be created:" -ForegroundColor Yellow
    
    $resources = @(
        @{Name="Resource Group"; Value=$config.ResourceGroup},
        @{Name="PostgreSQL Server"; Value=$config.PostgresServer; Extra="(SKU: $($config.PostgresSku))"},
        @{Name="Key Vault"; Value=$config.KeyVault},
        @{Name="Container Registry"; Value=$config.ContainerRegistry; Extra="(SKU: $($config.AcrSku))"},
        @{Name="App Service Plan"; Value=$config.AppServicePlan; Extra="(SKU: $($config.AppServiceSku))"},
        @{Name="App Service"; Value=$config.AppService},
        @{Name="Log Analytics"; Value=$config.LogAnalytics},
        @{Name="Application Insights"; Value=$config.AppInsights}
    )
    
    foreach ($resource in $resources) {
        Write-Host "  • " -NoNewline -ForegroundColor Cyan
        Write-Host ("{0,-25}" -f $resource.Name) -NoNewline -ForegroundColor Gray
        Write-Host $resource.Value -NoNewline -ForegroundColor White
        if ($resource.Extra) {
            Write-Host " $($resource.Extra)" -ForegroundColor DarkGray
        } else {
            Write-Host ""
        }
    }
    
    # Cost estimate
    Write-Host "`nEstimated Monthly Cost:" -ForegroundColor Yellow
    if ($Environment -eq "prod") {
        Write-Host "  $280-320 USD (B2 tier, Standard DB)" -ForegroundColor White
    } else {
        Write-Host "  $35-40 USD (B1 tier, Basic DB)" -ForegroundColor White
    }
    
    Write-Host ""
}

function Confirm-Deployment {
    if ($SkipConfirmation -or $DryRun) {
        return $true
    }
    
    Write-Host "Do you want to proceed with this deployment? [Y/N]: " -NoNewline -ForegroundColor Yellow
    $response = Read-Host
    return $response -eq 'Y' -or $response -eq 'y'
}

# =============================================================================
# RESOURCE CREATION FUNCTIONS
# =============================================================================

function New-ResourceGroup {
    Write-Section "Creating Resource Group"
    
    Write-Step "Checking if resource group exists..."
    $exists = az group exists --name $config.ResourceGroup
    
    if ($exists -eq "true") {
        Write-Info "Resource group already exists: $($config.ResourceGroup)"
        return $true
    }
    
    if ($DryRun) {
        Write-Info "[DRY RUN] Would create resource group: $($config.ResourceGroup)"
        return $true
    }
    
    Write-Step "Creating resource group: $($config.ResourceGroup)"
    
    $tagString = ($config.Tags.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join " "
    
    az group create `
        --name $config.ResourceGroup `
        --location $Location `
        --tags $tagString
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Resource group created successfully"
        return $true
    } else {
        Write-Error "Failed to create resource group"
        return $false
    }
}

function New-PostgresServer {
    Write-Section "Creating PostgreSQL Flexible Server"
    
    Write-Step "Checking if PostgreSQL server exists..."
    $exists = az postgres flexible-server show `
        --resource-group $config.ResourceGroup `
        --name $config.PostgresServer `
        2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Info "PostgreSQL server already exists: $($config.PostgresServer)"
        return $true
    }
    
    # Generate secure admin password
    $adminPassword = Get-SecurePassword
    Write-Info "Generated admin password (save this securely!)"
    Write-Host "  Username: $($config.PostgresAdminUser)" -ForegroundColor Cyan
    Write-Host "  Password: $adminPassword" -ForegroundColor Cyan
    
    if ($DryRun) {
        Write-Info "[DRY RUN] Would create PostgreSQL server: $($config.PostgresServer)"
        return $true
    }
    
    Write-Step "Creating PostgreSQL Flexible Server (this may take 5-10 minutes)..."
    
    az postgres flexible-server create `
        --resource-group $config.ResourceGroup `
        --name $config.PostgresServer `
        --location $Location `
        --admin-user $config.PostgresAdminUser `
        --admin-password $adminPassword `
        --sku-name $config.PostgresSku `
        --tier Burstable `
        --storage-size $config.PostgresStorageGB `
        --version $config.PostgresVersion `
        --public-access 0.0.0.0-255.255.255.255 `
        --tags "Environment=$Environment" "Application=PriceScout"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "PostgreSQL server created successfully"
        
        # Save credentials to secure file
        $credFile = ".\deploy\postgres-credentials-$Environment.txt"
        @"
PostgreSQL Server: $($config.PostgresServer).postgres.database.azure.com
Admin Username: $($config.PostgresAdminUser)
Admin Password: $adminPassword
Connection String: postgresql://$($config.PostgresAdminUser):$adminPassword@$($config.PostgresServer).postgres.database.azure.com:5432/pricescout_db?sslmode=require

IMPORTANT: Store this password in Azure Key Vault immediately!
Command: az keyvault secret set --vault-name $($config.KeyVault) --name "postgresql-admin-password" --value "$adminPassword"
"@ | Out-File -FilePath $credFile -Encoding UTF8
        
        Write-Info "Credentials saved to: $credFile"
        
        # Create database
        Write-Step "Creating database: pricescout_db"
        az postgres flexible-server db create `
            --resource-group $config.ResourceGroup `
            --server-name $config.PostgresServer `
            --database-name pricescout_db
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Database created successfully"
        }
        
        return $true
    } else {
        Write-Error "Failed to create PostgreSQL server"
        return $false
    }
}

function New-KeyVault {
    Write-Section "Creating Azure Key Vault"
    
    Write-Step "Checking if Key Vault exists..."
    $exists = az keyvault show `
        --name $config.KeyVault `
        --resource-group $config.ResourceGroup `
        2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Info "Key Vault already exists: $($config.KeyVault)"
        return $true
    }
    
    if ($DryRun) {
        Write-Info "[DRY RUN] Would create Key Vault: $($config.KeyVault)"
        return $true
    }
    
    Write-Step "Creating Key Vault: $($config.KeyVault)"
    
    az keyvault create `
        --name $config.KeyVault `
        --resource-group $config.ResourceGroup `
        --location $Location `
        --enable-rbac-authorization false `
        --enabled-for-deployment true `
        --enabled-for-template-deployment true `
        --tags "Environment=$Environment" "Application=PriceScout"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Key Vault created successfully"
        
        # Set access policy for current user
        Write-Step "Configuring access policy for current user..."
        $currentUser = az account show --query user.name -o tsv
        
        az keyvault set-policy `
            --name $config.KeyVault `
            --upn $currentUser `
            --secret-permissions get list set delete
        
        Write-Success "Access policy configured"
        return $true
    } else {
        Write-Error "Failed to create Key Vault"
        return $false
    }
}

function New-ContainerRegistry {
    Write-Section "Creating Azure Container Registry"
    
    Write-Step "Checking if Container Registry exists..."
    $exists = az acr show `
        --name $config.ContainerRegistry `
        --resource-group $config.ResourceGroup `
        2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Info "Container Registry already exists: $($config.ContainerRegistry)"
        return $true
    }
    
    if ($DryRun) {
        Write-Info "[DRY RUN] Would create Container Registry: $($config.ContainerRegistry)"
        return $true
    }
    
    Write-Step "Creating Container Registry: $($config.ContainerRegistry)"
    
    az acr create `
        --resource-group $config.ResourceGroup `
        --name $config.ContainerRegistry `
        --sku $config.AcrSku `
        --location $Location `
        --admin-enabled true `
        --tags "Environment=$Environment" "Application=PriceScout"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Container Registry created successfully"
        
        # Get login credentials
        Write-Step "Retrieving registry credentials..."
        $acrUser = az acr credential show --name $config.ContainerRegistry --query username -o tsv
        $acrPass = az acr credential show --name $config.ContainerRegistry --query passwords[0].value -o tsv
        
        Write-Info "Registry: $($config.ContainerRegistry).azurecr.io"
        Write-Info "Username: $acrUser"
        
        # Save credentials
        $credFile = ".\deploy\acr-credentials-$Environment.txt"
        @"
Container Registry: $($config.ContainerRegistry).azurecr.io
Username: $acrUser
Password: $acrPass

Login Command:
az acr login --name $($config.ContainerRegistry)

Docker Login:
docker login $($config.ContainerRegistry).azurecr.io -u $acrUser -p $acrPass

Push Image:
docker tag pricescout:latest $($config.ContainerRegistry).azurecr.io/pricescout:latest
docker push $($config.ContainerRegistry).azurecr.io/pricescout:latest
"@ | Out-File -FilePath $credFile -Encoding UTF8
        
        Write-Info "Credentials saved to: $credFile"
        return $true
    } else {
        Write-Error "Failed to create Container Registry"
        return $false
    }
}

function New-LogAnalyticsWorkspace {
    Write-Section "Creating Log Analytics Workspace"
    
    Write-Step "Checking if Log Analytics workspace exists..."
    $exists = az monitor log-analytics workspace show `
        --resource-group $config.ResourceGroup `
        --workspace-name $config.LogAnalytics `
        2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Info "Log Analytics workspace already exists: $($config.LogAnalytics)"
        return $true
    }
    
    if ($DryRun) {
        Write-Info "[DRY RUN] Would create Log Analytics workspace: $($config.LogAnalytics)"
        return $true
    }
    
    Write-Step "Creating Log Analytics workspace: $($config.LogAnalytics)"
    
    az monitor log-analytics workspace create `
        --resource-group $config.ResourceGroup `
        --workspace-name $config.LogAnalytics `
        --location $Location `
        --tags "Environment=$Environment" "Application=PriceScout"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Log Analytics workspace created successfully"
        return $true
    } else {
        Write-Error "Failed to create Log Analytics workspace"
        return $false
    }
}

function New-ApplicationInsights {
    Write-Section "Creating Application Insights"
    
    Write-Step "Checking if Application Insights exists..."
    $exists = az monitor app-insights component show `
        --app $config.AppInsights `
        --resource-group $config.ResourceGroup `
        2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Info "Application Insights already exists: $($config.AppInsights)"
        return $true
    }
    
    if ($DryRun) {
        Write-Info "[DRY RUN] Would create Application Insights: $($config.AppInsights)"
        return $true
    }
    
    Write-Step "Creating Application Insights: $($config.AppInsights)"
    
    # Get Log Analytics workspace ID
    $workspaceId = az monitor log-analytics workspace show `
        --resource-group $config.ResourceGroup `
        --workspace-name $config.LogAnalytics `
        --query id -o tsv
    
    az monitor app-insights component create `
        --app $config.AppInsights `
        --location $Location `
        --resource-group $config.ResourceGroup `
        --workspace $workspaceId `
        --tags "Environment=$Environment" "Application=PriceScout"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Application Insights created successfully"
        
        # Get connection string
        $connString = az monitor app-insights component show `
            --app $config.AppInsights `
            --resource-group $config.ResourceGroup `
            --query connectionString -o tsv
        
        Write-Info "Connection String: $connString"
        
        # Store in Key Vault
        if (-not $DryRun) {
            Write-Step "Storing connection string in Key Vault..."
            az keyvault secret set `
                --vault-name $config.KeyVault `
                --name "appinsights-connection-string" `
                --value $connString
            Write-Success "Connection string stored in Key Vault"
        }
        
        return $true
    } else {
        Write-Error "Failed to create Application Insights"
        return $false
    }
}

function New-AppServicePlan {
    Write-Section "Creating App Service Plan"
    
    Write-Step "Checking if App Service Plan exists..."
    $exists = az appservice plan show `
        --name $config.AppServicePlan `
        --resource-group $config.ResourceGroup `
        2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Info "App Service Plan already exists: $($config.AppServicePlan)"
        return $true
    }
    
    if ($DryRun) {
        Write-Info "[DRY RUN] Would create App Service Plan: $($config.AppServicePlan)"
        return $true
    }
    
    Write-Step "Creating App Service Plan: $($config.AppServicePlan)"
    
    az appservice plan create `
        --name $config.AppServicePlan `
        --resource-group $config.ResourceGroup `
        --location $Location `
        --is-linux `
        --sku $config.AppServiceSku `
        --tags "Environment=$Environment" "Application=PriceScout"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "App Service Plan created successfully"
        return $true
    } else {
        Write-Error "Failed to create App Service Plan"
        return $false
    }
}

function New-AppService {
    Write-Section "Creating App Service for Containers"
    
    Write-Step "Checking if App Service exists..."
    $exists = az webapp show `
        --name $config.AppService `
        --resource-group $config.ResourceGroup `
        2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Info "App Service already exists: $($config.AppService)"
        return $true
    }
    
    if ($DryRun) {
        Write-Info "[DRY RUN] Would create App Service: $($config.AppService)"
        return $true
    }
    
    Write-Step "Creating App Service: $($config.AppService)"
    
    # Create placeholder deployment (will be updated with actual image later)
    az webapp create `
        --resource-group $config.ResourceGroup `
        --plan $config.AppServicePlan `
        --name $config.AppService `
        --deployment-container-image-name "mcr.microsoft.com/appsvc/staticsite:latest" `
        --tags "Environment=$Environment" "Application=PriceScout"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "App Service created successfully"
        
        # Enable system-assigned managed identity
        Write-Step "Enabling managed identity..."
        az webapp identity assign `
            --name $config.AppService `
            --resource-group $config.ResourceGroup
        
        Write-Success "Managed identity enabled"
        
        # Configure basic settings
        Write-Step "Configuring app settings..."
        az webapp config appsettings set `
            --name $config.AppService `
            --resource-group $config.ResourceGroup `
            --settings `
                "WEBSITES_PORT=8000" `
                "DEPLOYMENT_ENV=azure" `
                "ENVIRONMENT=$Environment" `
                "AZURE_KEY_VAULT_URL=https://$($config.KeyVault).vault.azure.net/"
        
        Write-Success "App settings configured"
        
        Write-Info "App Service URL: https://$($config.AppService).azurewebsites.net"
        return $true
    } else {
        Write-Error "Failed to create App Service"
        return $false
    }
}

function Grant-KeyVaultAccess {
    Write-Section "Configuring Key Vault Access for App Service"
    
    if ($DryRun) {
        Write-Info "[DRY RUN] Would grant Key Vault access to App Service"
        return $true
    }
    
    Write-Step "Getting App Service managed identity..."
    $principalId = az webapp identity show `
        --name $config.AppService `
        --resource-group $config.ResourceGroup `
        --query principalId -o tsv
    
    if (-not $principalId) {
        Write-Error "Failed to get managed identity"
        return $false
    }
    
    Write-Step "Granting Key Vault access to managed identity..."
    az keyvault set-policy `
        --name $config.KeyVault `
        --object-id $principalId `
        --secret-permissions get list
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Key Vault access granted"
        return $true
    } else {
        Write-Error "Failed to grant Key Vault access"
        return $false
    }
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

function Main {
    Write-Host @"
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║        PriceScout Azure Resource Provisioning Tool             ║
║                     Version 1.0.0                              ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan
    
    # Pre-flight checks
    if (-not (Test-AzureCLI)) { exit 1 }
    if (-not (Test-AzureLogin)) { exit 1 }
    
    # Show deployment summary
    Show-DeploymentSummary
    
    # Confirm deployment
    if (-not (Confirm-Deployment)) {
        Write-Info "Deployment cancelled by user"
        exit 0
    }
    
    if ($DryRun) {
        Write-Info "`n[DRY RUN MODE] No resources will be created`n"
    }
    
    # Create resources in order
    $steps = @(
        @{Name="Resource Group"; Function={New-ResourceGroup}},
        @{Name="PostgreSQL Server"; Function={New-PostgresServer}},
        @{Name="Key Vault"; Function={New-KeyVault}},
        @{Name="Container Registry"; Function={New-ContainerRegistry}},
        @{Name="Log Analytics"; Function={New-LogAnalyticsWorkspace}},
        @{Name="Application Insights"; Function={New-ApplicationInsights}},
        @{Name="App Service Plan"; Function={New-AppServicePlan}},
        @{Name="App Service"; Function={New-AppService}},
        @{Name="Key Vault Access"; Function={Grant-KeyVaultAccess}}
    )
    
    $failedSteps = @()
    
    foreach ($step in $steps) {
        $result = & $step.Function
        if (-not $result) {
            $failedSteps += $step.Name
        }
    }
    
    # Final summary
    Write-Section "Deployment Summary"
    
    if ($failedSteps.Count -eq 0) {
        Write-Success "All resources created successfully!"
        
        Write-Host "`nNext Steps:" -ForegroundColor Yellow
        Write-Host "  1. Review credentials saved in .\deploy\ folder" -ForegroundColor White
        Write-Host "  2. Store PostgreSQL password in Key Vault" -ForegroundColor White
        Write-Host "  3. Run migrations/schema.sql on PostgreSQL database" -ForegroundColor White
        Write-Host "  4. Build and push Docker image to ACR" -ForegroundColor White
        Write-Host "  5. Configure App Service to use your container image" -ForegroundColor White
        Write-Host "  6. Proceed to Task 6: Database Migration & Secrets" -ForegroundColor White
        
        Write-Host "`nResource URLs:" -ForegroundColor Yellow
        Write-Host "  App Service:     https://$($config.AppService).azurewebsites.net" -ForegroundColor Cyan
        Write-Host "  Key Vault:       https://$($config.KeyVault).vault.azure.net" -ForegroundColor Cyan
        Write-Host "  Container Reg:   $($config.ContainerRegistry).azurecr.io" -ForegroundColor Cyan
        Write-Host "  PostgreSQL:      $($config.PostgresServer).postgres.database.azure.com" -ForegroundColor Cyan
        
    } else {
        Write-Error "`nDeployment completed with errors:"
        foreach ($step in $failedSteps) {
            Write-Host "  ✗ $step" -ForegroundColor Red
        }
        exit 1
    }
}

# Run main function
Main
