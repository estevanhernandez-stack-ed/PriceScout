# PriceScout Azure Deployment Checklist

**Version:** 2.0.0
**Last Updated:** November 24, 2025

---

## Pre-Deployment Files Checklist

Ensure these files are present and configured before deployment:

### Required Files

| File | Description | Status |
|------|-------------|--------|
| `requirements.txt` | Python dependencies | Must have all packages |
| `Dockerfile` | Multi-stage Docker build | Production-ready |
| `.env.example` | Environment template | Reference for Azure config |
| `VERSION` | Current version (2.0.0) | Update before release |
| `app/` | Application code directory | All modules present |

### Key Configuration Files

| File | Purpose |
|------|---------|
| `app/config.py` | Application configuration |
| `app/db_models.py` | SQLAlchemy ORM models |
| `app/db_session.py` | Database session management |
| `app/security_config.py` | Security settings |

---

## Azure Resources Required

| Resource | SKU | Purpose |
|----------|-----|---------|
| Resource Group | - | Container for all resources |
| PostgreSQL Flexible Server | B1ms (min) | Database |
| Azure Key Vault | Standard | Secrets management |
| Azure Container Registry | Basic | Docker image storage |
| Azure App Service | B1 (min) | Container hosting |
| Application Insights | Free tier | Monitoring |

---

## Quick Deploy Commands

```bash
# 1. Build Docker image
docker build -t pricescout:2.0.0 .

# 2. Test locally
docker run -p 8000:8000 -e DEBUG=true pricescout:2.0.0

# 3. Tag for ACR
docker tag pricescout:2.0.0 <acr-name>.azurecr.io/pricescout:2.0.0

# 4. Push to ACR
az acr login --name <acr-name>
docker push <acr-name>.azurecr.io/pricescout:2.0.0

# 5. Deploy to App Service
az webapp config container set \
  --name <app-name> \
  --resource-group <rg-name> \
  --docker-custom-image-name <acr-name>.azurecr.io/pricescout:2.0.0

# 6. Restart
az webapp restart --name <app-name> --resource-group <rg-name>
```

---

## Environment Variables (Azure App Service)

Set these in Azure Portal > App Service > Configuration:

```
WEBSITES_PORT=8000
DEPLOYMENT_ENV=azure
KEY_VAULT_URL=https://<vault-name>.vault.azure.net/
ENVIRONMENT=production
```

---

## Key Vault Secrets

Store these in Azure Key Vault:

| Secret Name | Description |
|-------------|-------------|
| `DATABASE-URL` | PostgreSQL connection string |
| `SECRET-KEY` | Session encryption key (64-char hex) |
| `OMDB-API-KEY` | OMDb API key |

---

## Post-Deployment Verification

- [ ] Application loads at Azure URL
- [ ] Login works with admin credentials
- [ ] Database connection successful
- [ ] Scraping functions work (test with one theater)
- [ ] All modes accessible based on user role
- [ ] Session timeout working
- [ ] Security logging active

---

## Documentation

| Document | Location |
|----------|----------|
| Full Azure Guide | `deploy/AZURE_DEPLOYMENT.md` |
| Environment Template | `.env.example` |
| Security Docs | `docs/SECURITY_AUDIT_REPORT.md` |
| RBAC Guide | `docs/RBAC_GUIDE.md` |

---

**Ready for deployment!**
