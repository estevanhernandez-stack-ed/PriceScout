# ADR-001: Python/FastAPI Technology Stack

**Status:** Accepted
**Date:** November 28, 2025
**Decision Makers:** Development Team, Architecture Review

---

## Context

The TheatreOperations platform standard specifies .NET 8+ Minimal APIs with Entity Framework Core as the backend technology stack. PriceScout requires a technology decision for its backend implementation.

## Decision

**We will use Python 3.11+ with FastAPI instead of .NET 8+ for PriceScout.**

## Rationale

### 1. Web Scraping Requirements

PriceScout's core functionality is automated web scraping of competitor pricing data from sources like Fandango. This requires:

- **Playwright automation** - The official Playwright library has first-class Python support with async capabilities. While Playwright .NET exists, the Python ecosystem has more mature tooling for web scraping patterns.
- **Dynamic page handling** - Python's async/await patterns integrate naturally with Playwright's async API.
- **HTML parsing** - BeautifulSoup and lxml provide robust HTML parsing that's well-documented for scraping use cases.

### 2. Data Science Ecosystem

Pricing analysis requires statistical operations that benefit from Python's data science stack:

- **Pandas** - DataFrame operations for pricing aggregation, time-series analysis
- **NumPy** - Numerical computations for trend analysis
- **Matplotlib/Plotly** - Visualization generation for reports

### 3. API Framework Parity

FastAPI provides equivalent capabilities to .NET Minimal APIs:

| Feature | .NET Minimal APIs | FastAPI |
|---------|------------------|---------|
| OpenAPI generation | Built-in | Built-in |
| Dependency injection | Built-in | Depends() |
| Async support | async/await | async/await |
| Validation | DataAnnotations | Pydantic |
| JWT authentication | Built-in | python-jose |
| Performance | Excellent | Excellent |

### 4. Team Expertise

The development team has stronger Python expertise, enabling:
- Faster initial development
- Lower maintenance overhead
- Easier onboarding for scraping-specific logic

## Compliance with Platform Standards

PriceScout maintains compliance with TheatreOperations standards through:

| Standard | Implementation |
|----------|---------------|
| API-First Architecture | FastAPI with OpenAPI spec at `/api/v1/openapi.json` |
| RFC 7807 Error Responses | Custom `api/errors.py` module |
| URL Structure | `/api/v{version}/{resource}` pattern |
| Authentication | Entra ID SSO + JWT + API Keys |
| Monitoring | OpenTelemetry → Application Insights |
| IaC | Bicep templates in `azure/iac/` |
| CI/CD | Azure Pipelines with standard stages |
| Secrets | Azure Key Vault via Managed Identity |

## Consequences

### Positive
- Optimal tooling for web scraping use case
- Rich data analysis capabilities
- Faster development velocity
- Strong async support for concurrent scraping

### Negative
- Technology divergence from platform standard
- Separate deployment configuration (no .NET runtime)
- Different debugging/profiling tools

### Mitigations
- Maintain strict API contract compliance
- Use same Azure services as .NET apps
- Document all deviations clearly
- Follow same CI/CD patterns

## Alternatives Considered

### Option A: .NET 8+ with Playwright .NET
- **Rejected:** Less mature scraping ecosystem, limited data science libraries

### Option B: Node.js with Puppeteer
- **Rejected:** Weaker typing, less suitable for data analysis

### Option C: Hybrid (.NET API + Python scraper)
- **Rejected:** Added complexity, deployment overhead, inter-service communication

---

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Playwright Python](https://playwright.dev/python/)
- [TheatreOperations Platform Standards](../claude.md)
