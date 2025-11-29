# PriceScout: Azure Deployment & Modernization Plan

**Version: 2.0**

**Date: November 12, 2025**

**Application Version:** v1.0.0 (Production-Ready, Grade A 94/100)

## 1. Executive Summary

This document outlines the strategic plan to evolve the `PriceScout` application from a local SQLite deployment to a scalable, secure, and robust enterprise SaaS platform hosted on Microsoft Azure. This transition addresses the current architecture limitations (local SQLite databases, single-user deployment) and positions the application for commercial launch with multi-tenancy support.

**Current Architecture:**
- **Database:** Dual SQLite (users.db for authentication, dynamic pricing DBs per company)
- **Framework:** Streamlit 1.49.1 with Python 3.11+
- **Authentication:** BCrypt password hashing with RBAC (5 role levels)
- **Scraping:** Playwright with Chromium (headless)
- **Status:** Production-ready, 97.4% test coverage (381/391 passing)

**Target Architecture:**
- **Containerization:** Docker with Playwright dependencies
- **Hosting:** Azure App Service for Containers (Linux)
- **Database:** Azure SQL Database (or Azure Database for PostgreSQL)
- **Secrets:** Azure Key Vault with Managed Identity
- **CI/CD:** GitHub Actions for automated deployments
- **Monitoring:** Azure Application Insights + Log Analytics

---

## 2. Current Application Architecture Analysis

### Database Structure
**Two Separate SQLite Databases:**

1. **`users.db`** (User Management & Authentication)
   - Location: Project root
   - Tables: `users`, `audit_log`, `password_reset_codes`, `rate_limit_log`
   - Purpose: Authentication, RBAC, security audit trail
   - Size: Small (<5MB typical)

2. **Dynamic Pricing Databases** (Per-Company Data)
   - Location: `data/[CompanyName]/[CompanyName].db`
   - Tables: `scrape_runs`, `showings`, `prices`, `films`, `theaters`, `markets`, etc.
   - Purpose: Theater pricing data, analysis, historical trends
   - Size: Variable (10MB - 500MB+ per company)

### Critical Application Dependencies
- **Playwright:** Requires Chromium browser + system dependencies
- **Streamlit:** Runs on port 8501 by default (needs reconfiguration for Azure)
- **SQLite:** File-based, not network-accessible (requires migration strategy)
- **RBAC System:** 5 role levels (Theater Manager, Theater Director, Market Director, Regional VP, Executive)
- **Multi-Company Support:** Users can access multiple theater chains

### Key Migration Challenges
1. **Dual Database Architecture:** Need strategy for users.db vs pricing data
2. **File-Based Storage:** SQLite files scattered across data/ directory structure
3. **Playwright in Container:** Complex browser dependency installation
4. **Multi-Tenancy:** Preserve company-specific data isolation in cloud DB
5. **Environment Variables:** Currently uses config.py with dynamic paths

---

## 3. Phased Implementation Roadmap

### Phase 1: Foundational Rework (Local Development - Week 1)

*Goal: Refactor the application to be cloud-ready and containerized before deploying to Azure.*

#### Task 1.1: Database Strategy & Schema Design

**Objective:** Design unified database schema that consolidates users.db and company pricing databases into a single cloud-ready structure.

**Decision Point:** Choose between:
- **Option A (Recommended):** Azure Database for PostgreSQL (better for large datasets, JSON support)
- **Option B:** Azure SQL Database (familiar T-SQL, enterprise features)

**Recommended Approach: PostgreSQL**
- Better performance for analytical queries
- Native JSON support for flexible schema
- Lower cost at scale
- Easier migration from SQLite (similar SQL dialect)

**Schema Design:**

1. **Unified Database Structure:**
   ```sql
   -- Core authentication (from users.db)
   users
   audit_log
   password_reset_codes
   rate_limit_log
   
   -- Pricing data (multi-tenant design)
   companies (NEW - tracks theater chains)
   scrape_runs (add company_id FK)
   showings (add company_id FK)
   prices (add company_id FK)
   films (shared across companies)
   theaters (add company_id FK)
   markets (add company_id FK)
   operating_hours (add company_id FK)
   ```

2. **Multi-Tenancy Implementation:**
   - Add `company_id` foreign key to all pricing tables
   - Create `companies` table: `(id, name, slug, created_at, is_active)`
   - Update all queries to filter by `company_id` based on user context
   - Row-Level Security (RLS) policies to enforce data isolation

**Action Items:**
1. [ ] Create unified schema design document (`docs/DATABASE_SCHEMA_V2.md`)
2. [ ] Write SQL migration script: `scripts/migrate_sqlite_to_postgres.py`
3. [ ] Set up local PostgreSQL instance via Docker for testing
   ```bash
   docker run --name pricescout-postgres -e POSTGRES_PASSWORD=devpass -p 5432:5432 -d postgres:16
   ```
4. [ ] Test migration with sample company data
5. [ ] Update connection logic in `app/database.py` to support both SQLite (dev) and PostgreSQL (prod)

#### Task 1.2: Database Abstraction Layer

**Objective:** Refactor database code to use SQLAlchemy ORM for database-agnostic operations.

**Why SQLAlchemy:**
- Abstracts away SQLite vs PostgreSQL differences
- Easier to write secure, parameterized queries
- Built-in connection pooling
- Migration support via Alembic

**Action Items:**
1. [ ] Add dependencies:
   ```bash
   pip install sqlalchemy psycopg2-binary alembic python-dotenv
   ```
2. [ ] Create `app/models.py` with SQLAlchemy models (User, Company, ScrapeRun, Showing, Price, etc.)
3. [ ] Update `requirements.txt`
4. [ ] Refactor `app/database.py`:
   ```python
   from sqlalchemy import create_engine
   from sqlalchemy.orm import sessionmaker
   import os
   
   def get_database_url():
       """Get DB URL from environment, fallback to SQLite for local dev"""
       if os.getenv('AZURE_DEPLOYMENT'):
           # Azure - use connection string from Key Vault
           return os.getenv('DATABASE_URL')
       else:
           # Local dev - use SQLite
           return f"sqlite:///{config.DB_FILE}"
   
   engine = create_engine(get_database_url())
   SessionLocal = sessionmaker(bind=engine)
   ```
5. [ ] Refactor `app/users.py` to use SQLAlchemy sessions instead of raw sqlite3
6. [ ] Update all database queries across codebase (data_management_v2.py, modes/, etc.)
7. [ ] Test locally with PostgreSQL to ensure compatibility

**Estimated Effort:** 2-3 days (critical path item)

#### Task 1.3: Application Containerization

**Objective:** Create production-ready Docker image with Playwright and all dependencies.

**Dockerfile Design:**
```dockerfile
# Stage 1: Base image with Python
FROM python:3.11-slim AS base

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Stage 2: Install Python dependencies
FROM base AS dependencies

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only for size optimization)
RUN playwright install --with-deps chromium

# Stage 3: Application code
FROM dependencies AS application

COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 pricescout && \
    chown -R pricescout:pricescout /app
USER pricescout

# Expose Streamlit port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
  CMD curl -f http://localhost:8000/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "app/price_scout_app.py", \
     "--server.port=8000", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.enableCORS=false", \
     "--server.enableXsrfProtection=true"]
```

**Action Items:**
1. [ ] Create `Dockerfile` in project root
2. [ ] Create `.dockerignore`:
   ```
   .git
   .vscode
   __pycache__
   *.pyc
   *.db
   *.sqlite
   data/
   debug_snapshots/
   test_reports/
   venv/
   .env
   .env.local
   deployment_pricescout_v2/
   archive/
   ```
3. [ ] Create `.env.example` for environment variable documentation
4. [ ] Update `app/config.py` to read from environment variables:
   ```python
   import os
   from dotenv import load_dotenv
   
   load_dotenv()
   
   # Azure deployment detection
   IS_AZURE = os.getenv('WEBSITE_INSTANCE_ID') is not None
   
   # Database config
   if IS_AZURE:
       DB_FILE = None  # Will use PostgreSQL
       DATABASE_URL = os.getenv('DATABASE_URL')
   else:
       DB_FILE = os.path.join(PROJECT_DIR, 'users.db')
   ```
5. [ ] Test Docker build locally:
   ```bash
   docker build -t pricescout:v1.0.0 .
   ```
6. [ ] Test Docker run with environment variables:
   ```bash
   docker run -p 8000:8000 --env-file .env pricescout:v1.0.0
   ```
7. [ ] Verify Playwright scraping works in container
8. [ ] Document Docker commands in `docs/DOCKER_GUIDE.md`

**Expected Image Size:** 1.5-2GB (mostly Playwright Chromium)

**Estimated Effort:** 1-2 days

---

### Phase 2: Azure Infrastructure Provisioning (Week 2)

*Goal: Create and configure all necessary Azure resources for production deployment.*

#### Task 2.1: Resource Group & Naming Convention

**Objective:** Establish Azure resource organization and naming standards.

**Naming Convention:**
```
Environment: prod, staging, dev
Region: eastus, westus2, etc.
Resource: rg (resource group), sql (database), kv (key vault), acr (container registry), app (app service)

Format: pricescout-[env]-[resource]-[region]
Example: pricescout-prod-rg-eastus
```

**Action Items:**
1. [ ] Create Resource Group via Azure Portal or CLI:
   ```bash
   az group create \
     --name pricescout-prod-rg-eastus \
     --location eastus \
     --tags project=pricescout environment=production owner=626labs
   ```

#### Task 2.2: Azure Database for PostgreSQL

**Objective:** Provision managed PostgreSQL instance for production data.

**Tier Recommendation:**
- **Start:** Flexible Server - Burstable (B1ms) - $12-15/month
- **Production:** General Purpose (GP_Standard_D2s_v3) - $140/month (2 vCore, 8GB RAM)

**Action Items:**
1. [ ] Provision PostgreSQL Flexible Server:
   ```bash
   az postgres flexible-server create \
     --resource-group pricescout-prod-rg-eastus \
     --name pricescout-prod-postgres \
     --location eastus \
     --admin-user psadmin \
     --admin-password [STRONG_PASSWORD] \
     --sku-name Standard_B1ms \
     --tier Burstable \
     --storage-size 32 \
     --version 16
   ```

2. [ ] Configure Firewall Rules:
   ```bash
   # Allow Azure services
   az postgres flexible-server firewall-rule create \
     --resource-group pricescout-prod-rg-eastus \
     --name pricescout-prod-postgres \
     --rule-name AllowAzureServices \
     --start-ip-address 0.0.0.0 \
     --end-ip-address 0.0.0.0
   
   # Allow your local IP for migration (temporary)
   az postgres flexible-server firewall-rule create \
     --resource-group pricescout-prod-rg-eastus \
     --name pricescout-prod-postgres \
     --rule-name AllowLocalDev \
     --start-ip-address [YOUR_IP] \
     --end-ip-address [YOUR_IP]
   ```

3. [ ] Create database:
   ```bash
   az postgres flexible-server db create \
     --resource-group pricescout-prod-rg-eastus \
     --server-name pricescout-prod-postgres \
     --database-name pricescout
   ```

4. [ ] Enable SSL enforcement (security requirement)
5. [ ] Configure automated backups (retention: 7-30 days)
6. [ ] Run migration script to populate database:
   ```bash
   python scripts/migrate_sqlite_to_postgres.py \
     --source users.db \
     --dest postgresql://psadmin@pricescout-prod-postgres:[PASSWORD]@pricescout-prod-postgres.postgres.database.azure.com/pricescout
   ```

#### Task 2.3: Azure Key Vault

**Objective:** Secure storage for secrets, connection strings, and API keys.

**Action Items:**
1. [ ] Provision Key Vault:
   ```bash
   az keyvault create \
     --name pricescout-prod-kv-626 \
     --resource-group pricescout-prod-rg-eastus \
     --location eastus \
     --enable-rbac-authorization true
   ```

2. [ ] Store secrets:
   ```bash
   # Database connection string
   az keyvault secret set \
     --vault-name pricescout-prod-kv-626 \
     --name DATABASE-URL \
     --value "postgresql://psadmin:[PASSWORD]@pricescout-prod-postgres.postgres.database.azure.com/pricescout?sslmode=require"
   
   # OMDb API Key
   az keyvault secret set \
     --vault-name pricescout-prod-kv-626 \
     --name OMDB-API-KEY \
     --value "[YOUR_OMDB_KEY]"
   
   # Streamlit Secret Key
   az keyvault secret set \
     --vault-name pricescout-prod-kv-626 \
     --name STREAMLIT-SECRET-KEY \
     --value "[GENERATE_RANDOM_STRING]"
   ```

3. [ ] Configure access policies (will be linked to App Service Managed Identity in Task 2.5)

#### Task 2.4: Azure Container Registry

**Objective:** Private Docker image repository for application containers.

**Action Items:**
1. [ ] Provision ACR:
   ```bash
   az acr create \
     --resource-group pricescout-prod-rg-eastus \
     --name pricescoutprodacr626 \
     --sku Basic \
     --location eastus \
     --admin-enabled true
   ```

2. [ ] Login to ACR:
   ```bash
   az acr login --name pricescoutprodacr626
   ```

3. [ ] Get admin credentials (for GitHub Actions later):
   ```bash
   az acr credential show --name pricescoutprodacr626
   ```

#### Task 2.5: Azure App Service (Containers)

**Objective:** Host the containerized Streamlit application with auto-scaling capabilities.

**Tier Recommendation:**
- **Start:** Basic B1 (1 core, 1.75GB RAM) - $13/month
- **Production:** Standard S1 (1 core, 1.75GB RAM) - $70/month (adds auto-scaling, custom domains)
- **Scale:** Premium P1v2 (1 core, 3.5GB RAM) - $85/month (better performance)

**Action Items:**
1. [ ] Create App Service Plan:
   ```bash
   az appservice plan create \
     --name pricescout-prod-plan \
     --resource-group pricescout-prod-rg-eastus \
     --location eastus \
     --is-linux \
     --sku B1
   ```

2. [ ] Create App Service for Containers:
   ```bash
   az webapp create \
     --resource-group pricescout-prod-rg-eastus \
     --plan pricescout-prod-plan \
     --name pricescout-prod-app-626 \
     --deployment-container-image-name pricescoutprodacr626.azurecr.io/pricescout:v1.0.0
   ```

3. [ ] Enable System-Assigned Managed Identity:
   ```bash
   az webapp identity assign \
     --name pricescout-prod-app-626 \
     --resource-group pricescout-prod-rg-eastus
   ```

4. [ ] Grant Key Vault access to Managed Identity:
   ```bash
   # Get the identity principal ID
   IDENTITY_ID=$(az webapp identity show \
     --name pricescout-prod-app-626 \
     --resource-group pricescout-prod-rg-eastus \
     --query principalId -o tsv)
   
   # Grant Key Vault Secrets User role
   az role assignment create \
     --assignee $IDENTITY_ID \
     --role "Key Vault Secrets User" \
     --scope /subscriptions/[SUBSCRIPTION_ID]/resourceGroups/pricescout-prod-rg-eastus/providers/Microsoft.KeyVault/vaults/pricescout-prod-kv-626
   ```

5. [ ] Configure App Settings:
   ```bash
   az webapp config appsettings set \
     --name pricescout-prod-app-626 \
     --resource-group pricescout-prod-rg-eastus \
     --settings \
       WEBSITES_PORT=8000 \
       AZURE_DEPLOYMENT=true \
       KEY_VAULT_URI=https://pricescout-prod-kv-626.vault.azure.net/ \
       ENVIRONMENT=production \
       STREAMLIT_SERVER_ENABLE_CORS=false \
       STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true
   ```

6. [ ] Configure ACR authentication:
   ```bash
   az webapp config container set \
     --name pricescout-prod-app-626 \
     --resource-group pricescout-prod-rg-eastus \
     --docker-custom-image-name pricescoutprodacr626.azurecr.io/pricescout:v1.0.0 \
     --docker-registry-server-url https://pricescoutprodacr626.azurecr.io \
     --docker-registry-server-user [ACR_USERNAME] \
     --docker-registry-server-password [ACR_PASSWORD]
   ```

7. [ ] Enable continuous deployment (webhook from ACR)
8. [ ] Configure custom domain (optional): `pricescout.626labs.com`
9. [ ] Enable HTTPS only

#### Task 2.6: Azure Application Insights

**Objective:** Monitor application performance, errors, and usage analytics.

**Action Items:**
1. [ ] Create Application Insights resource:
   ```bash
   az monitor app-insights component create \
     --app pricescout-prod-insights \
     --location eastus \
     --resource-group pricescout-prod-rg-eastus \
     --application-type web
   ```

2. [ ] Link to App Service:
   ```bash
   INSTRUMENTATION_KEY=$(az monitor app-insights component show \
     --app pricescout-prod-insights \
     --resource-group pricescout-prod-rg-eastus \
     --query instrumentationKey -o tsv)
   
   az webapp config appsettings set \
     --name pricescout-prod-app-626 \
     --resource-group pricescout-prod-rg-eastus \
     --settings \
       APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=$INSTRUMENTATION_KEY"
   ```

3. [ ] Configure alerts:
   - HTTP 5xx errors > 10 in 5 minutes
   - Response time > 5 seconds
   - Failed scraping jobs
   - Database connection failures

**Estimated Effort:** 1-2 days

---

### Phase 3: Application Refactoring & Deployment (Week 3)

*Goal: Update application code for cloud deployment and establish CI/CD pipeline.*

#### Task 3.1: Code Refactoring for Azure Key Vault

**Objective:** Securely retrieve secrets from Azure Key Vault at runtime using Managed Identity.

**Action Items:**
1. [ ] Add Azure SDK dependencies:
   ```bash
   pip install azure-keyvault-secrets azure-identity
   ```

2. [ ] Update `requirements.txt`

3. [ ] Create `app/azure_secrets.py`:
   ```python
   import os
   from azure.identity import DefaultAzureCredential
   from azure.keyvault.secrets import SecretClient
   
   def is_azure_deployment():
       """Check if running in Azure App Service"""
       return os.getenv('WEBSITE_INSTANCE_ID') is not None
   
   def get_secret(secret_name):
       """Retrieve secret from Key Vault or environment variable"""
       if is_azure_deployment():
           # Azure - use Key Vault
           kv_uri = os.getenv('KEY_VAULT_URI')
           credential = DefaultAzureCredential()
           client = SecretClient(vault_url=kv_uri, credential=credential)
           secret = client.get_secret(secret_name)
           return secret.value
       else:
           # Local dev - use .env file
           from dotenv import load_dotenv
           load_dotenv()
           return os.getenv(secret_name)
   
   def get_database_url():
       """Get database connection string"""
       return get_secret('DATABASE-URL')
   
   def get_omdb_api_key():
       """Get OMDb API key"""
       return get_secret('OMDB-API-KEY')
   ```

4. [ ] Update `app/database.py` to use `get_database_url()`:
   ```python
   from app.azure_secrets import get_database_url, is_azure_deployment
   from sqlalchemy import create_engine
   
   if is_azure_deployment():
       engine = create_engine(get_database_url(), pool_pre_ping=True)
   else:
       # Local SQLite fallback
       engine = create_engine(f"sqlite:///{config.DB_FILE}")
   ```

5. [ ] Update `app/omdb_client.py` to use `get_omdb_api_key()`

6. [ ] Test locally with `.env` file before deploying

#### Task 3.2: Initial Manual Deployment

**Objective:** Deploy the first version of the application to Azure.

**Action Items:**
1. [ ] Build Docker image locally:
   ```bash
   docker build -t pricescout:v1.0.0 .
   ```

2. [ ] Tag for ACR:
   ```bash
   docker tag pricescout:v1.0.0 pricescoutprodacr626.azurecr.io/pricescout:v1.0.0
   docker tag pricescout:v1.0.0 pricescoutprodacr626.azurecr.io/pricescout:latest
   ```

3. [ ] Login to ACR:
   ```bash
   az acr login --name pricescoutprodacr626
   ```

4. [ ] Push images to ACR:
   ```bash
   docker push pricescoutprodacr626.azurecr.io/pricescout:v1.0.0
   docker push pricescoutprodacr626.azurecr.io/pricescout:latest
   ```

5. [ ] Trigger App Service deployment:
   ```bash
   az webapp restart \
     --name pricescout-prod-app-626 \
     --resource-group pricescout-prod-rg-eastus
   ```

6. [ ] Monitor deployment logs:
   ```bash
   az webapp log tail \
     --name pricescout-prod-app-626 \
     --resource-group pricescout-prod-rg-eastus
   ```

7. [ ] Verify deployment:
   - Visit `https://pricescout-prod-app-626.azurewebsites.net`
   - Test login functionality
   - Test scraping (ensure Playwright works in container)
   - Verify database connectivity
   - Check Application Insights for telemetry

8. [ ] Troubleshooting checklist if issues arise:
   - [ ] Check App Service logs
   - [ ] Verify Key Vault permissions
   - [ ] Test database connection from App Service console
   - [ ] Confirm Playwright dependencies installed
   - [ ] Validate environment variables set correctly

#### Task 3.3: CI/CD with GitHub Actions

**Objective:** Automate build and deployment process for future updates.

**Action Items:**
1. [ ] Create GitHub repository secrets:
   - `AZURE_CREDENTIALS` (service principal JSON)
   - `ACR_USERNAME` (from Task 2.4)
   - `ACR_PASSWORD` (from Task 2.4)
   - `ACR_LOGIN_SERVER` (`pricescoutprodacr626.azurecr.io`)

2. [ ] Create `.github/workflows/deploy-to-azure.yml`:
   ```yaml
   name: Deploy to Azure App Service
   
   on:
     push:
       branches:
         - main
       paths-ignore:
         - 'docs/**'
         - 'tests/**'
         - '**.md'
     workflow_dispatch:
   
   env:
     ACR_NAME: pricescoutprodacr626
     IMAGE_NAME: pricescout
     APP_NAME: pricescout-prod-app-626
     RESOURCE_GROUP: pricescout-prod-rg-eastus
   
   jobs:
     build-and-deploy:
       runs-on: ubuntu-latest
       
       steps:
       - name: Checkout code
         uses: actions/checkout@v4
       
       - name: Login to Azure
         uses: azure/login@v1
         with:
           creds: ${{ secrets.AZURE_CREDENTIALS }}
       
       - name: Login to Azure Container Registry
         uses: docker/login-action@v3
         with:
           registry: ${{ secrets.ACR_LOGIN_SERVER }}
           username: ${{ secrets.ACR_USERNAME }}
           password: ${{ secrets.ACR_PASSWORD }}
       
       - name: Get version from VERSION file
         id: get_version
         run: echo "VERSION=$(cat VERSION)" >> $GITHUB_OUTPUT
       
       - name: Build and push Docker image
         uses: docker/build-push-action@v5
         with:
           context: .
           push: true
           tags: |
             ${{ secrets.ACR_LOGIN_SERVER }}/${{ env.IMAGE_NAME }}:${{ steps.get_version.outputs.VERSION }}
             ${{ secrets.ACR_LOGIN_SERVER }}/${{ env.IMAGE_NAME }}:latest
           cache-from: type=registry,ref=${{ secrets.ACR_LOGIN_SERVER }}/${{ env.IMAGE_NAME }}:buildcache
           cache-to: type=registry,ref=${{ secrets.ACR_LOGIN_SERVER }}/${{ env.IMAGE_NAME }}:buildcache,mode=max
       
       - name: Deploy to Azure App Service
         uses: azure/webapps-deploy@v2
         with:
           app-name: ${{ env.APP_NAME }}
           images: ${{ secrets.ACR_LOGIN_SERVER }}/${{ env.IMAGE_NAME }}:${{ steps.get_version.outputs.VERSION }}
       
       - name: Restart App Service
         run: |
           az webapp restart \
             --name ${{ env.APP_NAME }} \
             --resource-group ${{ env.RESOURCE_GROUP }}
       
       - name: Verify deployment
         run: |
           echo "Deployment complete!"
           echo "Application URL: https://${{ env.APP_NAME }}.azurewebsites.net"
   ```

3. [ ] Create service principal for GitHub Actions:
   ```bash
   az ad sp create-for-rbac \
     --name "pricescout-github-actions" \
     --role contributor \
     --scopes /subscriptions/[SUBSCRIPTION_ID]/resourceGroups/pricescout-prod-rg-eastus \
     --sdk-auth
   ```
   Copy output JSON to GitHub secret `AZURE_CREDENTIALS`

4. [ ] Test CI/CD pipeline:
   - Make minor change to README.md
   - Commit and push to `main` branch
   - Monitor GitHub Actions workflow
   - Verify deployment to Azure

5. [ ] Set up staging environment (optional but recommended):
   - Duplicate infrastructure with `-staging-` naming
   - Create separate branch `staging` that triggers staging deployment
   - Test changes in staging before merging to `main`

**Estimated Effort:** 2-3 days

---

## 4. Post-Deployment Tasks (Week 4)

### Task 4.1: Production Hardening

**Security:**
- [ ] Enable Azure Front Door or Application Gateway for DDoS protection
- [ ] Configure Web Application Firewall (WAF)
- [ ] Set up Azure Private Link for database (remove public endpoint)
- [ ] Enable Microsoft Defender for Cloud
- [ ] Configure audit logging for Key Vault access
- [ ] Implement rate limiting at app level

**Performance:**
- [ ] Configure App Service auto-scaling rules:
  - Scale out when CPU > 70% for 5 minutes
  - Scale in when CPU < 30% for 10 minutes
  - Min instances: 1, Max instances: 5
- [ ] Enable Azure CDN for static assets
- [ ] Configure database query performance insights
- [ ] Implement Redis cache for frequently accessed data (optional)

**Monitoring:**
- [ ] Set up Azure Dashboard with key metrics
- [ ] Configure alert action groups (email, SMS, Teams webhook)
- [ ] Create runbook for common issues
- [ ] Set up log retention policies (90 days for audit logs)

### Task 4.2: Disaster Recovery & Backup

**Database Backups:**
- [ ] Verify automated backups enabled (daily)
- [ ] Configure geo-redundant backup storage
- [ ] Test point-in-time restore procedure
- [ ] Document RTO (Recovery Time Objective): 1 hour
- [ ] Document RPO (Recovery Point Objective): 15 minutes

**Application Backup:**
- [ ] Configure App Service backup (app settings + logs)
- [ ] Store Docker images with version tags (never delete old versions)
- [ ] Maintain GitHub repository as source of truth

**Disaster Recovery Plan:**
- [ ] Deploy to secondary region (e.g., westus2) for DR
- [ ] Configure Azure Traffic Manager for failover
- [ ] Test failover procedure quarterly
- [ ] Document recovery steps in `docs/DISASTER_RECOVERY.md`

### Task 4.3: Documentation Updates

**Create/Update Documentation:**
- [ ] `docs/AZURE_DEPLOYMENT_GUIDE.md` - Step-by-step deployment instructions
- [ ] `docs/AZURE_TROUBLESHOOTING.md` - Common issues and solutions
- [ ] `docs/DATABASE_MIGRATION.md` - SQLite to PostgreSQL migration guide
- [ ] `docs/CI_CD_SETUP.md` - GitHub Actions configuration
- [ ] `docs/SCALING_GUIDE.md` - Performance tuning and scaling strategies
- [ ] `docs/COST_OPTIMIZATION.md` - Azure cost management tips
- [ ] Update `README.md` with Azure deployment section

### Task 4.4: Cost Optimization

**Initial Monthly Cost Estimate:**
```
Azure Database for PostgreSQL (B1ms):        $12-15
Azure App Service (Basic B1):                $13
Azure Container Registry (Basic):            $5
Azure Key Vault (Standard):                  $0.03 per 10K transactions (~$1)
Azure Application Insights (5GB/month):      Free tier
Azure Storage (logs, backups):              $2-5
------------------------------------------------------
TOTAL:                                       ~$35-40/month
```

**Production Scaling (100+ active users):**
```
Azure Database (General Purpose D2s_v3):     $140
Azure App Service (Standard S1):             $70
Azure Container Registry (Standard):         $20
Azure Front Door + WAF:                      $35
Azure Application Insights (20GB/month):     $5
Azure Storage (backups):                     $10
------------------------------------------------------
TOTAL:                                       ~$280/month
```

**Cost Optimization Actions:**
- [ ] Enable Azure Reserved Instances (1-year commitment = 30% savings)
- [ ] Use Azure Cost Management alerts (budget: $500/month)
- [ ] Review and delete unused resources monthly
- [ ] Use serverless PostgreSQL for non-peak hours
- [ ] Implement auto-shutdown for non-production environments

---

## 5. Success Criteria & Validation

### Deployment Success Checklist

**Functionality:**
- [ ] Application loads at Azure URL
- [ ] User login works (authentication via PostgreSQL)
- [ ] RBAC permissions enforced correctly
- [ ] Scraping functionality operational (Playwright in container)
- [ ] Data persists across container restarts
- [ ] All 6 analysis modes functional
- [ ] CSV export works
- [ ] OMDb metadata enrichment works

**Performance:**
- [ ] Page load time <3 seconds
- [ ] Scraping performance matches local (50 theaters in 5-10 minutes)
- [ ] Database queries <500ms (95th percentile)
- [ ] Zero memory leaks after 24-hour uptime test

**Security:**
- [ ] All secrets retrieved from Key Vault (not hardcoded)
- [ ] HTTPS enforced
- [ ] CORS properly configured
- [ ] SQL injection tests pass (automated via pytest)
- [ ] Rate limiting active
- [ ] Audit logs capturing all access

**Reliability:**
- [ ] Application survives container restart
- [ ] Database connection pooling works
- [ ] Error handling graceful (no 500 errors exposed to users)
- [ ] Logs captured in Application Insights
- [ ] Uptime > 99.5% after first week

**Scalability:**
- [ ] Auto-scaling triggers at 70% CPU
- [ ] Handles 100 concurrent users (load test)
- [ ] Database connection pool doesn't exhaust
- [ ] Container startup time <60 seconds

---

## 6. Rollback Plan

**If deployment fails or critical issues arise:**

### Immediate Actions (Incident Response)
1. **Enable Maintenance Mode:**
   - Display user-friendly message: "System undergoing maintenance"
   - Disable new scraping jobs
   - Prevent new user logins

2. **Assess Impact:**
   - Check Application Insights for error rate
   - Review recent deployments in GitHub Actions
   - Identify affected functionality

### Rollback Procedure

**Option A: Rollback to Previous Image (Fast - 5 minutes)**
```bash
# Find previous working image tag
az acr repository show-tags \
  --name pricescoutprodacr626 \
  --repository pricescout \
  --orderby time_desc

# Update App Service to previous tag
az webapp config container set \
  --name pricescout-prod-app-626 \
  --resource-group pricescout-prod-rg-eastus \
  --docker-custom-image-name pricescoutprodacr626.azurecr.io/pricescout:v1.0.0

# Restart
az webapp restart \
  --name pricescout-prod-app-626 \
  --resource-group pricescout-prod-rg-eastus
```

**Option B: Database Rollback (If schema changed - 15-30 minutes)**
```bash
# Restore from point-in-time
az postgres flexible-server restore \
  --resource-group pricescout-prod-rg-eastus \
  --name pricescout-prod-postgres-restore \
  --source-server pricescout-prod-postgres \
  --restore-time "2025-11-12T10:00:00Z"

# Update connection string in Key Vault
# Restart App Service
```

**Option C: Full Rollback to Local Deployment (Nuclear option - 1-2 hours)**
- Restore local SQLite databases from backup
- Deploy to on-premises server
- Update DNS to point to local server
- Notify customers of temporary degradation

### Post-Incident Review
- Document what went wrong
- Update runbook with new scenario
- Implement automated tests to prevent recurrence
- Schedule post-mortem meeting

---

## 7. Obsolete Artifacts (To Archive/Remove)

The following files and processes are **deprecated** after Azure migration:

### Files to Archive:
- [ ] `prepare_deployment.bat` → Move to `archive/legacy_deployment/`
- [ ] `MIGRATION_QUICK_REFERENCE.txt` → Move to `archive/legacy_deployment/`
- [ ] `deployment_pricescout_v2/` → Move to `archive/legacy_deployment/`
- [ ] `migrate_to_subdomain.sh` → Move to `archive/legacy_deployment/`
- [ ] Any `systemd` service files
- [ ] Any `nginx` configuration files

### Files to Update:
- [ ] `README.md` - Remove local deployment instructions, add Azure deployment link
- [ ] `docs/DEPLOYMENT_GUIDE.md` - Replace with Azure-specific guide
- [ ] `.gitignore` - Add Azure-specific exclusions (`.azure/`, `*.publish`)

### Database Files (DO NOT DELETE - Archive Only):
- [ ] `users.db` - Archive with date stamp `users_backup_2025-11-12.db`
- [ ] `data/*/` SQLite files - Archive entire directory as `data_backup_2025-11-12.tar.gz`
- [ ] Store archives in Azure Blob Storage (cold tier, 7-year retention)

---

## 8. Timeline Summary

**Week 1: Foundation (Local Development)**
- Days 1-2: Database migration (SQLite → PostgreSQL with SQLAlchemy)
- Days 3-4: Application containerization (Dockerfile, Docker testing)
- Day 5: Local validation & troubleshooting

**Week 2: Infrastructure (Azure Setup)**
- Days 1-2: Provision Azure resources (PostgreSQL, Key Vault, ACR, App Service)
- Day 3: Configure networking, security, monitoring
- Days 4-5: Data migration to Azure, testing

**Week 3: Deployment (Go-Live)**
- Days 1-2: Code refactoring (Key Vault integration, connection pooling)
- Day 3: Initial manual deployment & validation
- Days 4-5: CI/CD setup (GitHub Actions), testing

**Week 4: Hardening (Production-Ready)**
- Days 1-2: Security hardening, performance tuning
- Day 3: Disaster recovery setup, backup validation
- Days 4-5: Documentation, cost optimization, training

**Total Estimated Effort:** 15-20 business days (3-4 weeks)

---

## 9. Risk Assessment & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Playwright fails in container** | Medium | High | Test early, use official Playwright Docker base image, document workarounds |
| **Database migration data loss** | Low | Critical | Dry-run migration multiple times, keep SQLite backups, validate data integrity |
| **Cost overrun** | Medium | Medium | Start with lowest tiers, set budget alerts, monitor daily |
| **Performance degradation** | Medium | High | Load test before go-live, implement caching, profile slow queries |
| **Key Vault access issues** | Low | High | Test Managed Identity locally with Azure CLI, document troubleshooting |
| **Container startup timeout** | Medium | Medium | Optimize image size, use multi-stage builds, implement health checks |
| **Scraping blocked by Azure IP** | Low | High | Rotate user agents, implement delays, consider proxy service if needed |
| **Concurrent user database locks** | Low | Medium | Use PostgreSQL (better concurrency than SQLite), implement connection pooling |

---

## 10. Next Steps (Immediate Actions)

**Priority 1 (This Week):**
1. [ ] Review and approve this deployment plan
2. [ ] Set up Azure subscription (if not already done)
3. [ ] Create `dev` branch in GitHub for deployment work
4. [ ] Set up local PostgreSQL Docker container for testing
5. [ ] Begin Task 1.1 (Database abstraction layer with SQLAlchemy)

**Priority 2 (Next Week):**
1. [ ] Complete Phase 1 (local development & containerization)
2. [ ] Test Docker image thoroughly on local machine
3. [ ] Start Phase 2 (provision Azure resources)
4. [ ] Set up Azure Cost Management alerts

**Priority 3 (Week 3):**
1. [ ] Execute deployment to Azure
2. [ ] Set up CI/CD pipeline
3. [ ] Conduct load testing

**Priority 4 (Week 4):**
1. [ ] Production hardening
2. [ ] Documentation finalization
3. [ ] Team training on Azure operations

---

**Document Version:** 2.0  
**Last Updated:** November 12, 2025  
**Next Review:** After Phase 1 completion  
**Owner:** 626labs LLC - Price Scout Team  

---

*This deployment plan represents a significant evolution in the maturity and scalability of the Price Scout application. By completing this Azure migration, the service will be positioned for commercial launch, enterprise customer acquisition, and long-term growth as a SaaS platform.*