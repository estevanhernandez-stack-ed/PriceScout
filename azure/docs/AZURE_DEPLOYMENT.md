# PriceScout Azure Deployment Guide

**Version:** 2.0.0
**Last Updated:** November 24, 2025
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Azure Resources](#azure-resources)
5. [Docker Deployment](#docker-deployment)
6. [Environment Configuration](#environment-configuration)
7. [Database Setup](#database-setup)
8. [CI/CD Pipeline](#cicd-pipeline)
9. [Monitoring](#monitoring)
10. [Troubleshooting](#troubleshooting)

---

## Overview

PriceScout is deployed as a containerized Streamlit application on Azure App Service. The architecture includes:

- **Compute:** Azure App Service for Containers (Linux)
- **Database:** Azure Database for PostgreSQL (Flexible Server)
- **Secrets:** Azure Key Vault with Managed Identity
- **Registry:** Azure Container Registry (ACR)
- **Monitoring:** Azure Application Insights

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Azure Resource Group                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   App        │  │  PostgreSQL  │  │  Key Vault   │       │
│  │   Service    │──│  Flexible    │──│  Secrets     │       │
│  │   Container  │  │  Server      │  │              │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                                    │               │
│         ▼                                    │               │
│  ┌──────────────┐                           │               │
│  │  Container   │◄──────────────────────────┘               │
│  │  Registry    │                                           │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### Local Development
- Docker Desktop
- Azure CLI (`az`)
- Python 3.11+
- Git

### Azure Account
- Active Azure subscription
- Contributor access to resource group
- Permissions to create App Service, PostgreSQL, Key Vault, ACR

### API Keys
- **OMDb API Key:** Get free at https://www.omdbapi.com/apikey.aspx

---

## Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/your-org/pricescout.git
cd pricescout
```

### 2. Build Docker Image
```bash
docker build -t pricescout:latest .
```

### 3. Test Locally
```bash
docker run -p 8000:8000 \
  -e ENVIRONMENT=development \
  -e DEBUG=true \
  pricescout:latest
```

Visit http://localhost:8000

### 4. Deploy to Azure
```bash
# Login to Azure
az login

# Create resource group
az group create --name pricescout-prod-rg --location eastus

# Run deployment script
./deploy/scripts/deploy-azure.sh
```

---

## Azure Resources

### Naming Convention
```
pricescout-{env}-{resource}-{region}

Examples:
- pricescout-prod-rg-eastus       (Resource Group)
- pricescout-prod-postgres        (PostgreSQL)
- pricescout-prod-kv              (Key Vault)
- pricescoutprodacr               (Container Registry)
- pricescout-prod-app             (App Service)
```

### 1. Resource Group
```bash
az group create \
  --name pricescout-prod-rg-eastus \
  --location eastus \
  --tags project=pricescout environment=production
```

### 2. PostgreSQL Flexible Server
```bash
# Create server
az postgres flexible-server create \
  --resource-group pricescout-prod-rg-eastus \
  --name pricescout-prod-postgres \
  --location eastus \
  --admin-user psadmin \
  --admin-password "$(openssl rand -base64 24)" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --version 16

# Create database
az postgres flexible-server db create \
  --resource-group pricescout-prod-rg-eastus \
  --server-name pricescout-prod-postgres \
  --database-name pricescout

# Allow Azure services
az postgres flexible-server firewall-rule create \
  --resource-group pricescout-prod-rg-eastus \
  --name pricescout-prod-postgres \
  --rule-name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

### 3. Key Vault
```bash
# Create Key Vault
az keyvault create \
  --name pricescout-prod-kv \
  --resource-group pricescout-prod-rg-eastus \
  --location eastus \
  --enable-rbac-authorization true

# Store secrets
az keyvault secret set --vault-name pricescout-prod-kv \
  --name DATABASE-URL \
  --value "postgresql://psadmin:PASSWORD@pricescout-prod-postgres.postgres.database.azure.com/pricescout?sslmode=require"

az keyvault secret set --vault-name pricescout-prod-kv \
  --name OMDB-API-KEY \
  --value "your-omdb-api-key"

az keyvault secret set --vault-name pricescout-prod-kv \
  --name SECRET-KEY \
  --value "$(openssl rand -hex 32)"
```

### 4. Container Registry
```bash
# Create ACR
az acr create \
  --resource-group pricescout-prod-rg-eastus \
  --name pricescoutprodacr \
  --sku Basic \
  --admin-enabled true

# Login to ACR
az acr login --name pricescoutprodacr

# Build and push image
az acr build \
  --registry pricescoutprodacr \
  --image pricescout:latest .
```

### 5. App Service
```bash
# Create App Service Plan
az appservice plan create \
  --name pricescout-prod-plan \
  --resource-group pricescout-prod-rg-eastus \
  --is-linux \
  --sku B1

# Create Web App
az webapp create \
  --resource-group pricescout-prod-rg-eastus \
  --plan pricescout-prod-plan \
  --name pricescout-prod-app \
  --deployment-container-image-name pricescoutprodacr.azurecr.io/pricescout:latest

# Enable Managed Identity
az webapp identity assign \
  --name pricescout-prod-app \
  --resource-group pricescout-prod-rg-eastus

# Configure container settings
az webapp config appsettings set \
  --name pricescout-prod-app \
  --resource-group pricescout-prod-rg-eastus \
  --settings \
    WEBSITES_PORT=8000 \
    DEPLOYMENT_ENV=azure \
    KEY_VAULT_URL=https://pricescout-prod-kv.vault.azure.net/
```

---

## Docker Deployment

### Dockerfile Overview

The multi-stage Dockerfile:

1. **Stage 1 (base):** Python 3.11 with system dependencies
2. **Stage 2 (builder):** Install Python packages + Playwright browsers
3. **Stage 3 (production):** Final optimized image

### Build Commands

```bash
# Development build
docker build -t pricescout:dev .

# Production build with version tag
docker build -t pricescout:v2.0.0 .

# Build for ACR
docker build -t pricescoutprodacr.azurecr.io/pricescout:v2.0.0 .

# Push to ACR
docker push pricescoutprodacr.azurecr.io/pricescout:v2.0.0
```

### Run Locally with PostgreSQL

```bash
# Start PostgreSQL container
docker run -d \
  --name pricescout-postgres \
  -e POSTGRES_PASSWORD=devpass \
  -e POSTGRES_DB=pricescout_dev \
  -p 5432:5432 \
  postgres:16

# Run PriceScout connected to PostgreSQL
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://postgres:devpass@host.docker.internal:5432/pricescout_dev \
  -e ENVIRONMENT=development \
  pricescout:latest
```

---

## Environment Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `SECRET_KEY` | Session encryption key | `64-char hex string` |
| `OMDB_API_KEY` | OMDb API key | `abc123xyz` |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | `development`, `staging`, `production` |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |
| `PORT` | `8000` | Web server port |
| `SESSION_TIMEOUT_MINUTES` | `60` | Session timeout |
| `PLAYWRIGHT_HEADLESS` | `true` | Headless browser mode |

### Azure Key Vault Integration

The app automatically retrieves secrets from Key Vault when running in Azure:

```python
# Automatic detection in app/config.py
if os.getenv('WEBSITE_INSTANCE_ID'):  # Azure App Service
    # Use Key Vault
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient
    # ... fetch secrets
else:
    # Use .env file
    from dotenv import load_dotenv
    load_dotenv()
```

---

## Database Setup

### Schema Migration

The application uses SQLAlchemy ORM with automatic schema detection:

```python
# Run migrations (if using Alembic)
alembic upgrade head

# Or initialize schema from models
python -c "from app.db_models import Base; from app.db_session import get_engine; Base.metadata.create_all(get_engine())"
```

### Initial Data

```bash
# Create admin user
python -c "
from app.users import create_user
create_user('admin', 'StrongPassword123!', is_admin=True, role='admin')
print('Admin user created')
"
```

### Backup and Restore

```bash
# Backup PostgreSQL
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Restore
psql $DATABASE_URL < backup_20251124.sql
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Azure

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  ACR_NAME: pricescoutprodacr
  IMAGE_NAME: pricescout
  APP_NAME: pricescout-prod-app
  RESOURCE_GROUP: pricescout-prod-rg-eastus

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Login to Azure
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Login to ACR
        run: az acr login --name ${{ env.ACR_NAME }}

      - name: Build and push
        run: |
          VERSION=$(cat VERSION)
          docker build -t ${{ env.ACR_NAME }}.azurecr.io/${{ env.IMAGE_NAME }}:$VERSION .
          docker push ${{ env.ACR_NAME }}.azurecr.io/${{ env.IMAGE_NAME }}:$VERSION

      - name: Deploy to App Service
        run: |
          VERSION=$(cat VERSION)
          az webapp config container set \
            --name ${{ env.APP_NAME }} \
            --resource-group ${{ env.RESOURCE_GROUP }} \
            --docker-custom-image-name ${{ env.ACR_NAME }}.azurecr.io/${{ env.IMAGE_NAME }}:$VERSION
          az webapp restart --name ${{ env.APP_NAME }} --resource-group ${{ env.RESOURCE_GROUP }}
```

### GitHub Secrets Required

- `AZURE_CREDENTIALS`: Service principal JSON
- Create with:
  ```bash
  az ad sp create-for-rbac --name pricescout-github \
    --role contributor \
    --scopes /subscriptions/{sub-id}/resourceGroups/pricescout-prod-rg-eastus \
    --sdk-auth
  ```

---

## Monitoring

### Application Insights

```bash
# Create Application Insights
az monitor app-insights component create \
  --app pricescout-prod-insights \
  --location eastus \
  --resource-group pricescout-prod-rg-eastus

# Get instrumentation key
az monitor app-insights component show \
  --app pricescout-prod-insights \
  --resource-group pricescout-prod-rg-eastus \
  --query instrumentationKey
```

### Key Metrics to Monitor

- **Response Time:** Target < 3 seconds
- **Error Rate:** Target < 1%
- **Container Health:** Check `/health` endpoint
- **Database Connections:** Monitor pool usage

### Alerts

```bash
# Create alert for HTTP 5xx errors
az monitor metrics alert create \
  --name "pricescout-5xx-alert" \
  --resource-group pricescout-prod-rg-eastus \
  --scopes "/subscriptions/{sub}/resourceGroups/pricescout-prod-rg-eastus/providers/Microsoft.Web/sites/pricescout-prod-app" \
  --condition "total Http5xx > 10" \
  --window-size 5m \
  --evaluation-frequency 1m
```

---

## Troubleshooting

### Common Issues

#### Container Won't Start

```bash
# Check logs
az webapp log tail --name pricescout-prod-app --resource-group pricescout-prod-rg-eastus

# SSH into container
az webapp ssh --name pricescout-prod-app --resource-group pricescout-prod-rg-eastus
```

#### Database Connection Failed

```bash
# Verify connection string
az keyvault secret show --vault-name pricescout-prod-kv --name DATABASE-URL

# Test from container
docker run -it pricescoutprodacr.azurecr.io/pricescout:latest \
  python -c "from app.db_session import get_engine; print(get_engine().connect())"
```

#### Playwright Browser Issues

```bash
# Verify Playwright installation in container
docker run -it pricescoutprodacr.azurecr.io/pricescout:latest \
  python -c "from playwright.sync_api import sync_playwright; print('OK')"

# Check browser path
echo $PLAYWRIGHT_BROWSERS_PATH
```

### Health Check

The app exposes a health endpoint at `/_stcore/health`:

```bash
curl https://pricescout-prod-app.azurewebsites.net/_stcore/health
```

---

## Cost Estimate

### Minimum (Development/Staging)
| Resource | SKU | Monthly Cost |
|----------|-----|--------------|
| PostgreSQL | B1ms | ~$15 |
| App Service | B1 | ~$13 |
| Container Registry | Basic | ~$5 |
| Key Vault | Standard | ~$1 |
| **Total** | | **~$35/month** |

### Production (100+ users)
| Resource | SKU | Monthly Cost |
|----------|-----|--------------|
| PostgreSQL | D2s_v3 | ~$140 |
| App Service | P1v2 | ~$85 |
| Container Registry | Standard | ~$20 |
| Key Vault | Standard | ~$1 |
| App Insights | 5GB | Free |
| **Total** | | **~$250/month** |

---

## Files Reference

```
deploy/
├── AZURE_DEPLOYMENT.md      # This guide
├── DEPLOYMENT_GUIDE.md      # Legacy Linux deployment
├── nginx.conf               # Nginx config (legacy)
├── scripts/
│   └── deploy-azure.sh      # Deployment automation
└── AZURE_PROVISIONING_GUIDE.md  # Detailed provisioning

Dockerfile                   # Multi-stage Docker build
.env.example                 # Environment template
requirements.txt             # Python dependencies
VERSION                      # Current version
```

---

**Support:** For issues, open a GitHub issue or contact the development team.
