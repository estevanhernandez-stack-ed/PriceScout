# PriceScout Gap Analysis for Company Deployment

**Analysis Date:** November 28, 2025
**Evaluated Against:** `claude.md` TheatreOperations Platform Standards
**Current State:** FUNCTIONAL WITH ACKNOWLEDGED DEVIATIONS
**Target:** Company Azure Environment Deployment

---

## Executive Summary

PriceScout is functionally complete but has **two acknowledged deviations** from platform standards:

1. **Technology Stack**: Uses Python/FastAPI instead of .NET 8+ Minimal APIs
2. **Authentication**: Dual auth (Entra ID + Database) instead of Entra-only

These deviations are documented but represent real gaps from the standard.

**Compliance Score: 85/100** (up from 73/100)

| Category | Weight | Score | Status |
|----------|--------|-------|--------|
| API Design | 15% | 15/15 | Full - All endpoints implemented |
| Authentication | 10% | 5/10 | **PARTIAL** - Dual auth violates Entra-only requirement |
| Database | 15% | 15/15 | Full - competitive schema views added |
| Security | 15% | 15/15 | Full |
| DevOps | 15% | 15/15 | Full - CI/CD pipeline ready |
| Infrastructure | 10% | 10/10 | Full - Bicep IaC complete |
| Monitoring | 10% | 10/10 | Full - App Insights + OpenTelemetry |
| Documentation | 10% | 10/10 | Full - ADR + Runbook complete |
| **Technology Stack** | — | **-10** | **DEVIATION** - Python/FastAPI instead of .NET 8 |

---

## Acknowledged Deviations

### Deviation 1: Technology Stack (-.NET 8)

**Standard Requirement:**
> Runtime: .NET 8+ Minimal APIs

**Actual Implementation:** Python 3.11 + FastAPI

**Impact:** -10 points (significant platform deviation)

**Justification (see ADR-001):**
- Web scraping requires Playwright Python ecosystem
- Data science libraries (pandas, numpy) for analytics
- Existing team expertise
- Equivalent REST API capabilities

**Risk Assessment:**
- Different deployment model than other company apps
- Separate CI/CD pipeline patterns
- Different monitoring/debugging tooling

---

### Deviation 2: Dual Authentication

**Standard Requirement:**
> All users authenticate via corporate Entra ID

**Actual Implementation:**
- Entra ID SSO (optional, toggle via `ENTRA_ENABLED`)
- Database authentication (username/password + JWT)
- API keys for programmatic access

**Impact:** -5 points (partial compliance)

**Justification:**
- Allows operation before Entra ID integration is complete
- Supports external API consumers without Entra accounts
- Provides fallback during Entra ID outages

**Risk Assessment:**
- Password management overhead
- Multiple auth code paths to maintain
- Potential security inconsistencies

---

## Areas of Full Compliance

### 1. RFC 7807 Error Responses
- **Status:** Implemented in `api/errors.py`
- **Details:** Full problem details format with type URIs, proper HTTP headers, domain-specific error types

### 2. OpenAPI Documentation
- **Status:** Exposed at `/api/v1/docs`, `/api/v1/redoc`, `/api/v1/openapi.json`
- **Details:** Interactive Swagger UI, complete endpoint documentation

### 3. Authentication Architecture (PARTIAL COMPLIANCE)
- **Status:** Multi-method authentication implemented - **DEVIATES FROM STANDARD**
- **Standard Says:** "All users authenticate via corporate Entra ID"
- **What We Have:**
  - Entra ID SSO (optional, toggle via `ENTRA_ENABLED`)
  - Database auth with JWT tokens (non-standard)
  - API keys with SHA-256 hashing (non-standard for users)
  - 4-tier rate limiting (Free/Premium/Enterprise/Unlimited)
- **Gap:** Dual auth creates maintenance burden and security inconsistency

### 4. Azure Infrastructure (Bicep IaC)
- **Status:** Complete templates in `azure/iac/`
- **Components:**
  - App Service + App Service Plan
  - Azure SQL Database
  - Key Vault with Managed Identity
  - APIM with JWT validation policies
  - Service Bus for async messaging
  - Application Insights

### 5. CI/CD Pipeline
- **Status:** `azure-pipelines.yml` ready for import
- **Flow:** Build → DeployDev → DeployTest (approval) → DeployProd (approval)
- **Features:** Pip caching, Playwright browser install, pytest with coverage

### 6. Application Insights / Telemetry
- **Status:** OpenTelemetry instrumentation complete
- **Details:**
  - FastAPI auto-instrumentation
  - Custom spans on scraper operations
  - Business metrics (theater count, film count, price points)

### 7. Key Vault Integration
- **Status:** `app/azure_secrets.py` implemented
- **Details:** Managed Identity auth, fallback to environment variables

---

## Remediated Gaps

All previously identified gaps have been fixed:

### Gap 1: API Endpoints - FIXED

**New Endpoints Added (November 28, 2025):**

```
# Scrape Sources - api/routers/scrape_sources.py
GET    /api/v1/scrape-sources           ✅ Implemented
POST   /api/v1/scrape-sources           ✅ Implemented
GET    /api/v1/scrape-sources/{id}      ✅ Implemented
PUT    /api/v1/scrape-sources/{id}      ✅ Implemented
DELETE /api/v1/scrape-sources/{id}      ✅ Implemented
GET    /api/v1/scrape-jobs              ✅ Implemented
POST   /api/v1/scrape-jobs/trigger/{id} ✅ Implemented
GET    /api/v1/scrape-jobs/{id}/status  ✅ Implemented

# Price Checks - api/routers/price_checks.py
GET    /api/v1/price-checks             ✅ Implemented
GET    /api/v1/price-checks/latest/{id} ✅ Implemented
GET    /api/v1/price-history/{id}       ✅ Implemented
GET    /api/v1/price-comparison         ✅ Implemented

# Price Alerts - api/routers/price_alerts.py
GET    /api/v1/price-alerts             ✅ Implemented
GET    /api/v1/price-alerts/{id}        ✅ Implemented
GET    /api/v1/price-alerts/summary     ✅ Implemented
PUT    /api/v1/price-alerts/{id}/acknowledge    ✅ Implemented
PUT    /api/v1/price-alerts/acknowledge-bulk    ✅ Implemented
```

---

### Gap 2: Database Schema - FIXED

**New Migration Added:** `migrations/add_scrape_sources.sql`

```sql
-- ScrapeSources table added with:
- source_id, company_id, name, source_type
- base_url, scrape_frequency_minutes
- is_active, last_scrape_at, last_scrape_status
- configuration (JSON)
- created_at, updated_at, created_by

-- scrape_runs updated with source_id FK
-- Default sources seeded: Fandango, Box Office Mojo
```

---

### Gap 3: Technology Documentation - FIXED

**ADR Created:** `docs/architecture/ADR-001-PYTHON-FASTAPI.md`

Documents the rationale for using Python/FastAPI instead of .NET:
- Web scraping requirements (Playwright)
- Data science ecosystem (pandas, numpy)
- Team expertise
- Equivalent API capabilities

---

### Gap 4: Database Schema Naming - FIXED

**New Migration Added:** `migrations/add_competitive_schema_views.sql`

Creates `competitive` schema with standard-compliant views:
- `competitive.ScrapeSources` → maps to `scrape_sources`
- `competitive.ScrapeJobs` → maps to `scrape_runs`
- `competitive.PriceChecks` → joins `prices` + `showings`
- `competitive.PriceHistory` → computed price changes
- `competitive.PriceAlerts` → maps to `price_alerts`
- `competitive.MarketAnalysis` → computed positioning
- `competitive.PricingCategories` → derived from `prices`

This provides the expected naming convention without breaking existing code.

---

### Gap 5: Operations Documentation - FIXED

**New Document Created:** `docs/PriceScout-Runbook.md`

Comprehensive operations runbook including:
- Daily/weekly operational tasks
- Monitoring queries and thresholds
- Common procedures (restart, scale, maintenance)
- Troubleshooting guides
- Incident response procedures
- Security procedures (secret rotation, audit)
- Backup and recovery

---

## Company Deployment Checklist

### Pre-Deployment (Do Now)

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| Import pipeline to Azure DevOps | Pending | DevOps | Copy `azure-pipelines.yml` |
| Create service connection | Pending | DevOps | Link to Azure subscription |
| Create variable group `pricescout-secrets` | Pending | DevOps | DATABASE_URL, SECRET_KEY, OMDB_API_KEY |
| Register Entra ID app in company tenant | Pending | IT Admin | Update CLIENT_ID, TENANT_ID |
| Configure environment approvals | Pending | DevOps | Test + Prod gates |

### Deployment Day

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| Run `azure/deploy-infrastructure.ps1 -Environment dev` | Pending | DevOps | Creates all resources |
| Populate Key Vault secrets | Pending | DevOps | DB connection, API keys |
| Run database migration | Pending | Dev | `migrations/schema_mssql.sql` |
| Deploy application via pipeline | Pending | DevOps | First build triggers |
| Run `azure/verify-deployment.ps1` | Pending | DevOps | Validate all components |
| Configure APIM policies | Pending | DevOps | Run `deploy-apim-policies.ps1` |

### Post-Deployment

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| Create Application Insights dashboards | Pending | Dev | Monitor scraper health |
| Configure alert rules | Pending | DevOps | Error rates, latency |
| Update DNS/custom domain | Pending | IT | If using custom domain |
| Enable Entra ID auth | Pending | Admin | Set ENTRA_ENABLED=true |

---

## Path to Full Compliance

### To Reach 90/100 (Remove Dual Auth)

| Task | Effort | Impact |
|------|--------|--------|
| Make Entra ID the only auth method | Medium | +5 points |
| Remove database auth fallback | Low | Cleaner codebase |
| Convert API keys to Entra service principals | Medium | Platform alignment |

**Note:** This may require all users to have Entra accounts before deployment.

### To Reach 100/100 (Rewrite in .NET 8)

| Task | Effort | Impact |
|------|--------|--------|
| Rewrite API in .NET 8 Minimal APIs | **HIGH** | +10 points |
| Migrate Playwright to .NET | High | Different scraping patterns |
| Replace pandas with .NET equivalents | High | Data processing changes |

**Recommendation:** The .NET rewrite is likely not justified given:
- Existing Python codebase works well
- Web scraping is more mature in Python
- Cost/benefit of rewrite is poor

**Accept the 85/100 score** with documented ADR justification.

---

## Recommendations

### Immediate (Before Company Deployment)

1. **Accept deviation score** - 85/100 is acceptable with ADR documentation
2. **Test Pipeline Import** - Dry run pipeline in Azure DevOps
3. **Prepare Entra ID Registration** - Coordinate with IT for app registration

### Short-Term (First Sprint Post-Deploy)

4. **Evaluate auth consolidation** - Could we remove DB auth and go Entra-only?
5. **Monitor deviation impact** - Track any issues from Python/FastAPI choice

### Medium-Term (If Compliance Critical)

6. **Auth consolidation** - Remove DB auth, require Entra for all users (+5 pts)
7. **API key migration** - Convert API keys to Entra service principals

---

## Appendix: Files Ready for Deployment

### Azure Infrastructure
- `azure/iac/main.bicep` - Main orchestrator
- `azure/iac/appservice.bicep` - App Service
- `azure/iac/sql.bicep` - Azure SQL
- `azure/iac/keyvault.bicep` - Key Vault
- `azure/iac/apim.bicep` - API Management
- `azure/iac/servicebus.bicep` - Service Bus

### Deployment Scripts
- `azure/deploy-infrastructure.ps1` - Automated deployment
- `azure/verify-deployment.ps1` - Deployment verification
- `azure/iac/deploy-apim-policies.ps1` - APIM policy deployment

### CI/CD
- `azure-pipelines.yml` - Ready for Azure DevOps import

### Database
- `migrations/schema_mssql.sql` - Azure SQL schema

---

**Prepared by:** Gap Analysis Agent
**Version:** 1.0.0
**Next Review:** Post-deployment validation
