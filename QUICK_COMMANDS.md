# Quick Command Reference Card

## Azure CLI Commands

### Login & Account
```powershell
az login                                    # Login to Azure
az account show                             # Show current account
az account list --output table              # List all subscriptions
az account set --subscription "Name"        # Switch subscription
```

### Task 5: Provision Resources
```powershell
# Development environment ($36/month)
.\deploy\provision-azure-resources.ps1 -Environment dev -Location eastus

# Production environment ($226/month)
.\deploy\provision-azure-resources.ps1 -Environment prod -Location eastus

# Dry run (preview only)
.\deploy\provision-azure-resources.ps1 -Environment dev -DryRun

# Verify resources
.\deploy\verify-azure-resources.ps1 -Environment dev -Location eastus
```

### Resource Management
```powershell
# List all resources in group
az resource list --resource-group pricescout-dev-rg-eastus --output table

# Check PostgreSQL status
az postgres flexible-server show --resource-group pricescout-dev-rg-eastus --name pricescout-db-dev-eastus

# List Key Vault secrets
az keyvault secret list --vault-name pricescout-kv-dev --output table

# Check App Service status
az webapp show --name pricescout-app-dev-eastus --resource-group pricescout-dev-rg-eastus --query "{Name:name, State:state, URL:defaultHostName}"
```

---

## Docker Commands

### Docker Basics
```powershell
docker --version                            # Check version
docker ps                                   # List running containers
docker ps -a                                # List all containers
docker images                               # List images
docker system prune -a                      # Clean up everything
```

### Docker Compose (PriceScout)
```powershell
# Start services
docker compose up -d                        # Start in background
docker compose up                           # Start with logs

# View logs
docker compose logs -f                      # All services
docker compose logs -f pricescout          # PriceScout only
docker compose logs -f postgres            # PostgreSQL only

# Stop services
docker compose down                         # Stop and remove containers
docker compose down -v                      # Stop and remove volumes (clean slate)

# Restart services
docker compose restart                      # Restart all
docker compose restart pricescout          # Restart PriceScout only

# Check status
docker compose ps                           # List services

# Access containers
docker compose exec pricescout /bin/bash   # Shell into PriceScout
docker compose exec postgres psql -U pricescout_app -d pricescout_db  # PostgreSQL
```

### Build & Push to Azure
```powershell
# Build image
docker build -t pricescout:latest .

# Tag for Azure
docker tag pricescout:latest pricescoutacrdev.azurecr.io/pricescout:latest

# Login to ACR
az acr login --name pricescoutacrdev

# Push image
docker push pricescoutacrdev.azurecr.io/pricescout:latest
```

---

## Database Commands

### Local PostgreSQL (via Docker Compose)
```powershell
# Connect to database
docker compose exec postgres psql -U pricescout_app -d pricescout_db

# Run SQL file
docker compose exec -T postgres psql -U pricescout_app -d pricescout_db < migrations/schema.sql

# Backup database
docker compose exec -T postgres pg_dump -U pricescout_app pricescout_db > backup.sql

# Restore database
docker compose exec -T postgres psql -U pricescout_app -d pricescout_db < backup.sql
```

### Azure PostgreSQL
```powershell
# Connect (requires psql client)
psql "host=pricescout-db-dev-eastus.postgres.database.azure.com port=5432 dbname=pricescout_db user=pricescout_admin sslmode=require"

# Apply schema
psql "host=pricescout-db-dev-eastus.postgres.database.azure.com port=5432 dbname=pricescout_db user=pricescout_admin sslmode=require" -f migrations/schema.sql

# Run migration script
python migrations/migrate_to_postgresql.py --migrate-all --pg-conn "postgresql://pricescout_admin:PASSWORD@pricescout-db-dev-eastus.postgres.database.azure.com:5432/pricescout_db?sslmode=require"
```

---

## Key Vault Commands

### Secrets Management
```powershell
# Store secret
az keyvault secret set --vault-name pricescout-kv-dev --name "secret-name" --value "secret-value"

# Get secret
az keyvault secret show --vault-name pricescout-kv-dev --name "secret-name" --query value -o tsv

# List secrets
az keyvault secret list --vault-name pricescout-kv-dev --output table

# Delete secret
az keyvault secret delete --vault-name pricescout-kv-dev --name "secret-name"
```

### Common Secrets to Store
```powershell
# PostgreSQL admin password
az keyvault secret set --vault-name pricescout-kv-dev --name "postgresql-admin-password" --value "YourPasswordHere"

# App secret key
az keyvault secret set --vault-name pricescout-kv-dev --name "secret-key" --value "$(openssl rand -base64 32)"

# OMDB API key
az keyvault secret set --vault-name pricescout-kv-dev --name "omdb-api-key" --value "YourApiKeyHere"

# ACR password
az keyvault secret set --vault-name pricescout-kv-dev --name "acr-password" --value "YourACRPassword"
```

---

## App Service Commands

### Configuration
```powershell
# List app settings
az webapp config appsettings list --name pricescout-app-dev-eastus --resource-group pricescout-dev-rg-eastus

# Set app setting
az webapp config appsettings set --name pricescout-app-dev-eastus --resource-group pricescout-dev-rg-eastus --settings KEY=VALUE

# Update container image
az webapp config container set --name pricescout-app-dev-eastus --resource-group pricescout-dev-rg-eastus --docker-custom-image-name pricescoutacrdev.azurecr.io/pricescout:latest

# Restart app
az webapp restart --name pricescout-app-dev-eastus --resource-group pricescout-dev-rg-eastus
```

### Logs
```powershell
# Stream logs
az webapp log tail --name pricescout-app-dev-eastus --resource-group pricescout-dev-rg-eastus

# Download logs
az webapp log download --name pricescout-app-dev-eastus --resource-group pricescout-dev-rg-eastus --log-file logs.zip
```

---

## Testing Commands

### Configuration Testing
```powershell
# Test configuration
python test_config.py

# Test with Azure simulation
python test_config.py --azure

# Skip database connection test
python test_config.py --skip-connection
```

### Run Tests
```powershell
# Run all tests
pytest

# Run specific test file
pytest tests/test_database.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run and show output
pytest -v -s
```

---

## Utility Commands

### Project Management
```powershell
# Check Python version
python --version

# Install requirements
pip install -r requirements.txt

# Run app locally
streamlit run app/price_scout_app.py

# Check for updates
pip list --outdated
```

### Clean Up
```powershell
# Remove Python cache
Get-ChildItem -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item -Force

# Remove test artifacts
Remove-Item -Recurse -Force .pytest_cache, htmlcov, .coverage

# Clean Docker
docker system prune -a --volumes
```

---

## Emergency Commands

### Stop Everything
```powershell
# Stop Docker services
docker compose down -v

# Stop Azure App Service
az webapp stop --name pricescout-app-dev-eastus --resource-group pricescout-dev-rg-eastus

# Stop PostgreSQL (saves cost)
az postgres flexible-server stop --name pricescout-db-dev-eastus --resource-group pricescout-dev-rg-eastus
```

### Delete Everything
```powershell
# WARNING: This deletes all data!

# Delete resource group (all Azure resources)
az group delete --name pricescout-dev-rg-eastus --yes --no-wait

# Remove Docker volumes
docker compose down -v
docker volume prune -f

# Clean project directory
Remove-Item -Recurse -Force data/*.db, logs/*.log, debug_snapshots/*
```

---

## Quick Access URLs

### Development Environment
- **App Service:** https://pricescout-app-dev-eastus.azurewebsites.net
- **Azure Portal:** https://portal.azure.com
- **Key Vault:** https://pricescout-kv-dev.vault.azure.net
- **Local App:** http://localhost:8000

### Useful Azure Links
- **Resource Groups:** https://portal.azure.com/#view/HubsExtension/BrowseResourceGroups
- **Cost Management:** https://portal.azure.com/#view/Microsoft_Azure_CostManagement/Menu/~/costanalysis
- **Service Health:** https://status.azure.com
