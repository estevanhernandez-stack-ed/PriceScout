# Application Overview: PriceScout

> **Document Version:** 2.0
> **Last Updated:** November 28, 2025
> **Owner:** Estevan Hernandez / 626labs LLC
> **Status:** Production Ready (Azure Deployment)

---

## Summary

PriceScout automates the collection of competitor ticket and concession pricing from sources like Fandango. It replaces a tedious manual process that previously took hours of staff time, providing real-time market intelligence for pricing decisions.

| | |
|---|---|
| **Primary Users** | Theatre Managers, Marketing, Area GMs |
| **User Count** | Multi-tenant (company-based access) |
| **Launch Date** | November 2025 |
| **Production URL** | https://www.marketpricescout.com/ |
| **Repository** | Azure DevOps (pending import) |
| **Current Version** | 2.0.1 |

---

## Problem Statement

Competitive pricing data was gathered manually by visiting competitor websites one at a time, copying prices into spreadsheets. This process took 2-3 hours per market and was only done periodically, leaving gaps in market intelligence.

**Before this app:**
- Manual price checks taking 2-3+ hours
- Inconsistent data collection frequency
- No historical price tracking
- Delayed reaction to competitor price changes
- Staff time wasted on repetitive data entry

**After this app:**
- Automated scraping runs on schedule
- Complete price history with trends
- Alerts when competitors change prices
- Market positioning analysis at a glance
- Staff freed for higher-value work

---

## Key Features

### 1. Automated Price Scraping
Scheduled jobs scrape competitor pricing from Fandango and other sources without manual intervention. Configurable frequency per source via Azure Service Bus.

### 2. Price History & Trends
Every price check is stored historically, enabling trend analysis and identification of pricing patterns (seasonal, day-of-week, format-based, etc.).

### 3. Market Analysis Dashboard
Compare your pricing against local competitors. See where you're positioned (above/below/at market) with percentage differentials.

### 4. Price Change Alerts
Get notified when competitors make significant price changes so you can respond quickly to market movements.

### 5. Multi-Mode Interface
- **Market Mode** - Compare pricing across theaters in your market
- **CompSnipe Mode** - Competitive intelligence with ZIP code search
- **Daily Lineup** - Print-ready theater schedules with auto-enrichment
- **Operating Hours** - Track and analyze theater operating hours
- **Analysis Mode** - Film and theater performance analytics
- **Poster Board** - Film metadata and release calendar management
- **Admin Panel** - User management, RBAC, bulk operations

### 6. Film Metadata Enrichment
Automatic OMDb integration fetches runtime, ratings, and box office data. Per-film backfill for missing data.

---

## User Workflows

### Primary Workflow: Review Market Position

**Actor:** Theatre Manager
**Goal:** Understand how their pricing compares to nearby competitors

1. User logs into PriceScout via Entra ID SSO or database auth
2. User opens Market Mode dashboard
3. System displays market overview for their location
4. User sees their prices vs. competitor averages
5. User drills into specific competitors for detail
6. Result: Manager has data to inform pricing recommendations

### Secondary Workflow: Investigate Price Alert

**Actor:** Marketing Analyst
**Goal:** Respond to a competitor price change

1. User receives price alert notification
2. User opens alert detail in PriceScout
3. System shows old price, new price, change percentage
4. User reviews competitor's full pricing history
5. User acknowledges alert with notes
6. Result: Analyst can recommend whether to adjust pricing

### Tertiary Workflow: Generate Daily Lineup

**Actor:** Theatre Manager
**Goal:** Create print-ready schedule for box office

1. User selects theater and date
2. System scrapes current showings from Fandango
3. System auto-enriches with film metadata (runtime, rating)
4. User exports to PDF for printing
5. Result: Professional daily lineup ready for display

---

## Screenshots

### Market Mode Dashboard
*Compare pricing across competitors in your market with visual positioning indicators*

### Daily Lineup View
*Print-ready theater schedule with film metadata, showtimes, and formats*

### Analysis Mode
*Historical trends, film performance metrics, and pricing patterns*

---

## Technology Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| **Frontend** | Streamlit 1.40+ | Python-based interactive dashboard |
| **Backend API** | FastAPI 0.115+ | REST API with OpenAPI documentation |
| **Database** | Azure SQL / SQLite | Azure SQL for production, SQLite for local dev |
| **Hosting** | Azure App Service | Linux container with Python 3.11 |
| **Authentication** | Entra ID + Database | SSO via Microsoft + fallback to local auth |
| **Secrets** | Azure Key Vault | Managed Identity access |
| **Scraping** | Playwright | Headless Chromium for dynamic content |
| **Job Scheduling** | Azure Service Bus + Functions | Event-driven async scraping |
| **Monitoring** | Application Insights | OpenTelemetry instrumentation |
| **IaC** | Bicep | Infrastructure as Code templates |
| **CI/CD** | Azure Pipelines | Build → Dev → Test → Prod |

**Technology Choice:** See [ADR-001-PYTHON-FASTAPI](docs/architecture/ADR-001-PYTHON-FASTAPI.md) for rationale on Python/FastAPI vs .NET standard.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           AZURE CLOUD                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │                 │     │                 │     │                 │   │
│  │  Streamlit UI   │────▶│  FastAPI        │────▶│   Azure SQL     │   │
│  │  (App Service)  │     │  (App Service)  │     │   Database      │   │
│  │                 │     │                 │     │                 │   │
│  └─────────────────┘     └────────┬────────┘     └─────────────────┘   │
│          │                        │                      ▲              │
│          │                        │                      │              │
│          ▼                        ▼                      │              │
│  ┌─────────────────┐     ┌─────────────────┐            │              │
│  │                 │     │                 │            │              │
│  │   Entra ID      │     │  Service Bus    │            │              │
│  │   (Auth)        │     │  (Queue)        │            │              │
│  │                 │     │                 │            │              │
│  └─────────────────┘     └────────┬────────┘            │              │
│                                   │                      │              │
│          ┌─────────────────┐      │                      │              │
│          │                 │      │                      │              │
│          │   Key Vault     │      │                      │              │
│          │   (Secrets)     │      │                      │              │
│          │                 │      │                      │              │
│          └─────────────────┘      │                      │              │
│                                   ▼                      │              │
│                          ┌─────────────────┐            │              │
│                          │                 │            │              │
│                          │  Azure Function │────────────┘              │
│                          │  (Scraper)      │                           │
│                          │                 │                           │
│                          └────────┬────────┘                           │
│                                   │                                     │
│  ┌─────────────────┐              │     ┌─────────────────┐            │
│  │                 │              │     │                 │            │
│  │  App Insights   │◀─────────────┘     │  API Management │            │
│  │  (Telemetry)    │                    │  (Gateway)      │            │
│  │                 │                    │                 │            │
│  └─────────────────┘                    └─────────────────┘            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │                 │
                          │    Fandango     │
                          │  Box Office Mojo│
                          │    OMDb API     │
                          │                 │
                          └─────────────────┘
```

---

## Database Overview

### Tables Owned by This Application

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `companies` | Multi-tenant company management | company_id, company_name, settings |
| `users` | User accounts and authentication | user_id, username, role, company_id |
| `scrape_sources` | Configured scraping targets | source_id, name, base_url, frequency |
| `scrape_runs` | Execution history of scrape jobs | run_id, source_id, status, records_scraped |
| `showings` | Individual showtime records | showing_id, theater_name, film_title, showtime |
| `prices` | Price data points per showing | price_id, showing_id, ticket_type, price |
| `films` | Film metadata from OMDb | film_id, film_title, imdb_id, runtime, rating |
| `price_alerts` | Generated alerts for price changes | alert_id, alert_type, old_price, new_price |
| `alert_configurations` | Per-company alert settings | config_id, thresholds, notification_email |
| `operating_hours` | Theater operating hours data | theater_name, open_time, close_time |
| `api_keys` | API key management | key_hash, tier, rate_limits |
| `audit_log` | Security and action logging | event_type, user_id, timestamp |

### Views

| View | Purpose |
|------|---------|
| `v_recent_scrapes` | Recent scrape runs with company/user info |
| `v_pending_alerts` | Summary of unacknowledged alerts by theater |

---

## API Summary

Full OpenAPI documentation available at `/api/v1/docs`

### Authentication
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/auth/token` | Get JWT access token |
| GET | `/api/v1/auth/entra/login` | Initiate Entra ID SSO |
| GET | `/api/v1/auth/entra/callback` | Handle SSO callback |

### Scrape Management
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/scrape-sources` | List configured scrape sources |
| POST | `/api/v1/scrape-sources` | Add new scrape source |
| GET | `/api/v1/scrape-sources/{id}` | Get specific source |
| PUT | `/api/v1/scrape-sources/{id}` | Update source configuration |
| DELETE | `/api/v1/scrape-sources/{id}` | Remove source |
| POST | `/api/v1/scrape-jobs/trigger/{id}` | Manually trigger a scrape |
| GET | `/api/v1/scrape-jobs/{id}/status` | Check scrape job status |
| GET | `/api/v1/scrape-jobs` | List recent scrape jobs |

### Price Data
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/price-checks` | Query price check data with filters |
| GET | `/api/v1/price-checks/latest/{theater}` | Get most recent prices |
| GET | `/api/v1/price-history/{theater}` | Get price history |
| GET | `/api/v1/price-comparison` | Compare prices across theaters |

### Alerts
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/price-alerts` | List price alerts |
| GET | `/api/v1/price-alerts/summary` | Get alert statistics |
| GET | `/api/v1/price-alerts/{id}` | Get specific alert |
| PUT | `/api/v1/price-alerts/{id}/acknowledge` | Acknowledge an alert |
| PUT | `/api/v1/price-alerts/acknowledge-bulk` | Bulk acknowledge |

### Reports
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/reports/selection-analysis` | Generate selection analysis |
| GET | `/api/v1/reports/showtime-view` | Generate showtime view |
| GET | `/api/v1/reports/daily-lineup` | Generate daily lineup PDF |

---

## Integrations

| System | Integration Type | Purpose |
|--------|-----------------|---------|
| Fandango | Web Scraping (Playwright) | Primary source for competitor ticket prices |
| Box Office Mojo | Web Scraping (Playwright) | Film financial data (gross, opening weekend) |
| OMDb API | REST API | Film metadata (runtime, rating, cast, plot) |
| Microsoft Entra ID | OAuth 2.0 SSO | Enterprise authentication |
| Azure Key Vault | SDK (Managed Identity) | Secrets management |
| Azure Service Bus | SDK | Async job queue for scraping |
| Application Insights | OpenTelemetry | Distributed tracing and monitoring |

---

## Security Features

| Feature | Implementation |
|---------|---------------|
| Authentication | Entra ID SSO + Database auth with BCrypt |
| Authorization | RBAC with 3 roles (Admin, Manager, User) |
| Rate Limiting | 4-tier API key system (Free/Premium/Enterprise/Unlimited) |
| Session Management | JWT tokens with 30-minute idle timeout |
| Account Lockout | 5 failed attempts = 15-minute lockout |
| Password Policy | 8+ chars, uppercase, lowercase, number, special char |
| Secrets | Azure Key Vault with Managed Identity |
| Data in Transit | TLS 1.2+ (HTTPS only) |
| Data at Rest | Azure SQL TDE encryption |
| Audit Logging | Structured JSON logs for all security events |

---

## Known Limitations

- **Scraping fragility:** Depends on external site structure; Fandango changes may break scrapers
- **Rate limiting required:** Respectful delays (2+ seconds) to avoid IP blocking
- **Dynamic content:** Some competitor sites use heavy JavaScript requiring full browser rendering
- **Login-gated content:** Some price data behind authentication not accessible
- **OMDb API limits:** Free tier limited to 1,000 requests/day
- **PLF format detection:** Premium Large Format identification relies on naming patterns

---

## Future Enhancements

| Enhancement | Priority | Effort | Notes |
|-------------|----------|--------|-------|
| Additional scrape sources | Medium | M | AMC, Regal, Cinemark direct sites |
| Concession price tracking | Medium | M | Extend beyond tickets to food/drinks |
| Automated pricing recommendations | Low | L | ML-based optimal pricing suggestions |
| Mobile app notifications | Low | M | Push alerts for price changes |
| Market heat maps | Low | M | Geographic visualization of pricing |
| API webhooks | Low | S | Real-time alerts to external systems |
| Multi-region Azure deployment | Low | L | DR and latency optimization |

---

## Deployment Information

### Environments

| Environment | URL | Resource Group |
|-------------|-----|----------------|
| Development | `app-pricescout-dev.azurewebsites.net` | `rg-pricescout-dev` |
| Test | `app-pricescout-test.azurewebsites.net` | `rg-pricescout-test` |
| Production | `www.marketpricescout.com` | `rg-pricescout-prod` |

### Cost Estimates

| Environment | Monthly Cost |
|-------------|--------------|
| Development | ~$40-50 |
| Production | ~$250-300 |

### Key Resources

- App Service Plan (B1/P1v2)
- Azure SQL Database (Basic/S1)
- Key Vault (Standard)
- Application Insights
- API Management (Developer/Standard)
- Service Bus (Basic)

---

## Related Documents

| Document | Purpose |
|----------|---------|
| [GAP_ANALYSIS_COMPANY_DEPLOYMENT.md](./GAP_ANALYSIS_COMPANY_DEPLOYMENT.md) | Compliance assessment and remediation |
| [GAP_REMEDIATION_PLAN.md](./GAP_REMEDIATION_PLAN.md) | Detailed task tracking |
| [ADR-001-PYTHON-FASTAPI](./docs/architecture/ADR-001-PYTHON-FASTAPI.md) | Technology decision record |
| [AZURE_DEPLOYMENT_GUIDE](./azure/docs/AZURE_DEPLOYMENT.md) | Deployment instructions |
| [README.md](./README.md) | Quick start and installation |
| [docs/USER_GUIDE.md](./docs/USER_GUIDE.md) | End-user documentation |
| [docs/ADMIN_GUIDE.md](./docs/ADMIN_GUIDE.md) | Administrator guide |

---

## Contact

| Role | Name | Contact |
|------|------|---------|
| **Developer** | Estevan Hernandez | 626labs LLC |
| **Business Owner** | Estevan Hernandez | 626labs LLC |

---

*Last updated: November 28, 2025*
