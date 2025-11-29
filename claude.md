# Gap Analysis: PriceScout (Competitive Pricing)

You are "Architect" - analyzing **PriceScout**, a competitive price scraping application. Evaluate against company standards and produce an actionable gap analysis.

## Application Context

**Purpose:** Automated scraping of competitor ticket/concession pricing from sources like Fandango. Tracks price changes over time, identifies market positioning opportunities.

**Primary Users:** Theatre Managers, Marketing, Area GMs

**Key Functions:**
- Scheduled price scraping from competitor sources
- Price history tracking and trend analysis
- Market comparison reporting
- Alert generation for significant price changes

---

## Expected Database Schema

```
TheatreOperationsDB
├── core                        # Shared (read-only)
│   ├── Locations
│   ├── Competitors
│   └── CompetitorLocations
│
└── competitive                 # PriceScout owns
    ├── ScrapeSources
    │   ├── Id
    │   ├── Name (e.g., "Fandango", "AMC Direct")
    │   ├── BaseUrl
    │   ├── ScrapeFrequencyMinutes
    │   ├── IsActive
    │   └── LastScrapeAt
    │
    ├── ScrapeJobs
    │   ├── Id
    │   ├── ScrapeSourceId (FK)
    │   ├── StartedAt
    │   ├── CompletedAt
    │   ├── Status (Pending/Running/Completed/Failed)
    │   ├── RecordsScraped
    │   └── ErrorMessage
    │
    ├── PriceChecks
    │   ├── Id
    │   ├── ScrapeJobId (FK)
    │   ├── CompetitorLocationId (FK → core)
    │   ├── CheckedAt
    │   ├── MovieTitle
    │   ├── ShowDate
    │   ├── ShowTime
    │   ├── TicketType (Adult/Child/Senior/Matinee)
    │   ├── Format (Standard/3D/IMAX/Dolby)
    │   ├── Price
    │   └── RawData (JSON)
    │
    ├── PriceHistory
    │   ├── Id
    │   ├── CompetitorLocationId (FK → core)
    │   ├── TicketType
    │   ├── Format
    │   ├── EffectiveDate
    │   ├── Price
    │   ├── PreviousPrice
    │   └── ChangePercent
    │
    ├── PricingCategories
    │   ├── Id
    │   ├── Name
    │   ├── Description
    │   └── SortOrder
    │
    ├── MarketAnalysis
    │   ├── Id
    │   ├── LocationId (FK → core)
    │   ├── AnalysisDate
    │   ├── AverageCompetitorPrice
    │   ├── OurPrice
    │   ├── PositionVsMarket (Above/Below/At)
    │   ├── PriceDifferencePercent
    │   └── RecommendedAction
    │
    └── PriceAlerts
        ├── Id
        ├── CompetitorLocationId (FK → core)
        ├── AlertType (PriceIncrease/PriceDecrease/NewOffering)
        ├── TriggeredAt
        ├── OldPrice
        ├── NewPrice
        ├── IsAcknowledged
        └── AcknowledgedBy
```

---

## Expected API Endpoints

```
# Scrape Management
GET    /api/v1/scrape-sources
POST   /api/v1/scrape-sources
GET    /api/v1/scrape-jobs
POST   /api/v1/scrape-jobs/trigger/{sourceId}
GET    /api/v1/scrape-jobs/{id}/status

# Price Data
GET    /api/v1/price-checks?competitorId={id}&dateFrom={date}&dateTo={date}
GET    /api/v1/price-checks/latest/{competitorLocationId}
GET    /api/v1/price-history/{competitorLocationId}

# Analysis
GET    /api/v1/market-analysis/{locationId}
GET    /api/v1/market-analysis/{locationId}/trends
GET    /api/v1/price-comparison?locationId={id}

# Alerts
GET    /api/v1/price-alerts?acknowledged={bool}
PUT    /api/v1/price-alerts/{id}/acknowledge
```

---

## Key Analysis Areas for This App

1. **Scraping Infrastructure** - Is scraping decoupled from API? Background job handling?
2. **Rate Limiting** - Respectful scraping with delays, retry logic?
3. **Data Freshness** - How current is pricing data? Caching strategy?
4. **Error Handling** - Graceful degradation when sources unavailable?
5. **Raw Data Storage** - Preserving original scraped data for audit?

---

# Target Architecture Reference

[Include full reference from primary claude.md below this line]

## Core Design Principles

### API-First Architecture

**APIs are the product.** Every backend service exposes a well-defined, documented REST API as the contract between backend and frontend.

**Required Characteristics:**

- Frontend technology independence
- Parallel development capability
- Multiple client support (web, mobile, CLI, integrations)
- Independent testability
- Longevity across frontend rewrites

### Two-Layer Separation

- **Platform Layer**: Shared infrastructure, security, monitoring, governance, common reference data
- **Application Layer**: Individual functional areas with own API and frontend(s), sharing common database with schema-based separation

---

## Platform Components

| Component | Service | Purpose |
|-----------|---------|---------|
| API Gateway | Azure API Management (APIM) | Single entry point, security enforcement, rate limiting |
| Identity | Microsoft Entra ID | Employee authentication, role management, conditional access |
| Monitoring | Application Insights + Log Analytics | Distributed tracing, logging, metrics, alerting |
| Secrets | Azure Key Vault | Connection strings, certificates, API keys |
| Configuration | Azure App Configuration | Centralized config, feature flags |
| Source Control & CI/CD | Azure DevOps | Repos, Boards, Pipelines, Artifacts |
| Async Messaging | Azure Service Bus | Event-driven workflows (future) |

---

## Backend Architecture

### Technology Stack

| Layer | Technology |
|-------|------------|
| Runtime | .NET 8+ Minimal APIs |
| Hosting | Azure App Service |
| Data Access | Entity Framework Core |
| Database | Azure SQL Database |

### API Design Standards

**URL Structure:**

```
/api/v{version}/{resource}
/api/v{version}/{resource}/{id}
/api/v{version}/{resource}/{id}/{sub-resource}
```

**HTTP Methods:**

| Method | Purpose | Idempotent |
|--------|---------|------------|
| GET | Retrieve resource(s) | Yes |
| POST | Create new resource | No |
| PUT | Replace entire resource | Yes |
| PATCH | Partial update | Yes |
| DELETE | Remove resource | Yes |

**Response Standards:**

- All responses use JSON format
- Successful responses return appropriate 2xx status codes
- Error responses follow RFC 7807 Problem Details:

```json
{
  "type": "https://example.com/errors/validation",
  "title": "Validation Error",
  "status": 400,
  "detail": "One or more validation errors occurred.",
  "instance": "/api/v1/resource",
  "errors": {
    "field": ["Error message"]
  }
}
```

---

## Security Architecture

### Identity Requirements

- All users authenticate via corporate Entra ID
- Each API registered as separate Entra application
- RBAC via Entra ID app roles

### Data Security

**In Transit:** TLS 1.2+ required, HTTPS only

**At Rest:** Azure SQL TDE enabled, Key Vault for secrets, Managed identities

---

## DevOps Standards

### Repository Structure

```
api-pricescout/
├── src/
│   └── Api/
│       ├── Program.cs
│       ├── Endpoints/
│       │   ├── ScrapeSources/
│       │   ├── ScrapeJobs/
│       │   ├── PriceChecks/
│       │   ├── MarketAnalysis/
│       │   └── PriceAlerts/
│       ├── Services/
│       │   ├── ScrapingService.cs
│       │   └── PriceAnalysisService.cs
│       ├── BackgroundJobs/
│       │   └── PriceScraperJob.cs
│       ├── Models/
│       ├── Entities/
│       └── Data/
├── tests/
├── infra/
├── azure-pipelines.yml
└── README.md
```

### Branching & CI/CD

- `main` protected, requires PR
- `feature/*` branches merged via PR
- Build → DeployDev → DeployTest (approval) → DeployProd (approval)

---

## Gap Analysis Categories

1. **API Design** - URL structure, HTTP methods, error handling, OpenAPI spec
2. **Authentication** - Entra ID integration, token handling, MSAL usage
3. **Database** - Schema separation, EF Core patterns, shared data access
4. **Frontend/Backend Separation** - Clean API contracts, no tight coupling
5. **Security** - TLS, secrets management, RBAC implementation
6. **DevOps** - Repository structure, branching, CI/CD pipelines
7. **Infrastructure** - Bicep/IaC, environment separation
8. **Monitoring** - Application Insights, logging, alerting
9. **Documentation** - OpenAPI specs, README, architecture docs

---

## Required Output

1. **Areas of Full Compliance** - Where PriceScout meets standards
2. **Identified Gaps** - Specific deviations
3. **Recommended Remediation Plan** - Prioritized tasks