# PriceScout

**Version:** 2.0.1
**Release Date:** November 28, 2025
**Status:** Production Ready (Azure Deployment)
**Python:** 3.11+

---

## Overview

PriceScout is a competitive intelligence and ticket pricing analysis platform for theatrical exhibitors. It provides real-time theater pricing data, competitive analysis, and operational insights.

### Key Features

- **Market Mode:** Compare pricing across theaters in your market
- **CompSnipe Mode:** Competitive intelligence with ZIP code search
- **Daily Lineup:** Print-ready theater schedules with auto-enrichment and per-film runtime backfill
- **Operating Hours:** Track and analyze theater operating hours
- **Analysis Mode:** Film and theater performance analytics
- **Poster Board:** Film metadata and release calendar management
- **Admin Panel:** User management, RBAC, bulk operations
### Recent Features (v2.0.0)

- **Auto-enrichment**: Film metadata automatically fetched from OMDb during scraping
- **Per-film backfill**: Click button next to any film missing runtime to fetch instantly
- **Unmatched logging**: Failed enrichments logged for manual review in Data Management
- **Improved OMDb config**: Secrets file + environment variable fallback
- **API Authentication**: SHA-256 API keys with 4-tier rate limiting

---

## Quick Start

### Prerequisites

- Python 3.11 or higher
- pip
- Playwright (for web scraping)

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/pricescout.git
cd pricescout

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

# Create environment configuration
cp .env.example .env
# Edit .env with your settings (OMDB_API_KEY, etc.)

# Run the application
streamlit run app/price_scout_app.py
```

The app will open at `http://localhost:8501`

### Default Login

- **Username:** `admin`
- **Password:** `admin`
- **IMPORTANT:** Change password immediately after first login!

---

## Azure Deployment

PriceScout is designed for Azure App Service deployment with PostgreSQL.

### Quick Deploy

```bash
# Build Docker image
docker build -t pricescout:latest .

# Test locally
docker run -p 8000:8000 pricescout:latest

# Deploy to Azure (see azure/docs/AZURE_DEPLOYMENT.md)
```

### Documentation

| Document | Description |
|----------|-------------|
| [azure/docs/AZURE_DEPLOYMENT.md](azure/docs/AZURE_DEPLOYMENT.md) | Complete Azure deployment guide |
| [azure/docs/DEPLOYMENT_GUIDE.md](azure/docs/DEPLOYMENT_GUIDE.md) | Step-by-step deployment guide |
| [.env.example](.env.example) | Environment configuration template |
| [Dockerfile](Dockerfile) | Multi-stage Docker build |

---

## Project Structure

```
pricescout/
├── api/                      # FastAPI backend
│   ├── routers/              # API route handlers
│   ├── entra_auth.py         # Entra ID authentication
│   └── main.py               # API entry point
├── app/                      # Streamlit application
│   ├── modes/                # Feature modules
│   │   ├── analysis_mode.py  # Film & theater analytics
│   │   ├── market_mode.py    # Market comparisons
│   │   ├── compsnipe_mode.py # Competitive analysis
│   │   ├── daily_lineup_mode.py # Print schedules
│   │   ├── operating_hours_mode.py
│   │   └── poster_mode.py    # Film metadata
│   ├── price_scout_app.py    # Main application
│   ├── scraper.py            # Playwright web scraper
│   ├── api_client.py         # API client for backend
│   ├── azure_secrets.py      # Key Vault integration
│   └── config.py             # Configuration
├── azure/                    # Azure infrastructure
│   ├── iac/                  # Bicep IaC templates
│   ├── functions/            # Azure Functions
│   ├── docs/                 # Deployment documentation
│   ├── deploy-infrastructure.ps1
│   └── verify-deployment.ps1
├── tests/                    # Test suite (441+ tests)
├── scripts/                  # Utility scripts
├── docs/                     # Documentation
│   ├── deployment/           # Deployment guides
│   ├── development/          # Development docs
│   └── archive/              # Historical docs
├── migrations/               # Database migrations
├── Dockerfile                # Production container
├── azure-pipelines.yml       # CI/CD pipeline
├── requirements.txt          # Python dependencies
└── VERSION                   # Current version
```

---

## Security Features

### Authentication & Access Control

- **Rate Limiting:** 5 failed attempts = 15-minute lockout
- **Session Timeout:** 30-minute idle timeout
- **Password Requirements:** 8+ chars, uppercase, lowercase, number, special char
- **Password Reset:** Self-service with 6-digit codes (15-min expiry, 3 attempts max)
- **RBAC:** 3 roles (Admin, Manager, User) with mode-level permissions

### Data Protection

- BCrypt password hashing
- SQL injection protection (parameterized queries)
- File upload validation (50MB limit, type checking)
- Session tokens hashed in database

### Security Logging

All security events logged in structured JSON format:
- Login attempts (success/failure)
- Password changes
- Admin actions
- Session events

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes* | PostgreSQL connection string |
| `OMDB_API_KEY` | Yes | OMDb API key for film metadata |
| `SECRET_KEY` | Yes | Session encryption (64-char hex) |
| `ENVIRONMENT` | No | `development`, `staging`, `production` |
| `DEBUG` | No | Enable debug mode (`true`/`false`) |
| `LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

*Required for PostgreSQL; SQLite used automatically for local development.  
**Can also use `.streamlit/secrets.toml` (takes priority).

### OMDb API Configuration

Get free API key: https://www.omdbapi.com/apikey.aspx (1,000 requests/day)

**Method 1: Streamlit Secrets (Recommended)**
```toml
# Create .streamlit/secrets.toml at project root
omdb_api_key = "your_key_here"
omdb_poster_api_key = "your_key_here"
```

**Method 2: Environment Variable**
```bash
# Windows
$env:OMDB_API_KEY = "your_key_here"

# Linux/Mac or .env file
export OMDB_API_KEY="your_key_here"
```

**Note:** `.streamlit/secrets.toml` is git-ignored for security.

### Database Support

- **Development:** SQLite (automatic, no config needed)
- **Production:** PostgreSQL via `DATABASE_URL`

---

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_database.py -v

# Run specific test class
pytest tests/test_admin.py -v
```

### Test Coverage

- **441 tests** total
- **Key modules:** database, users, admin, modes
- See `htmlcov/index.html` for detailed coverage report

---

## Dependencies

### Core
- `streamlit` - Web application framework
- `pandas` - Data manipulation
- `playwright` - Web scraping automation
- `SQLAlchemy` - ORM and database abstraction

### Security
- `bcrypt` - Password hashing
- `azure-identity` - Azure authentication
- `azure-keyvault-secrets` - Key Vault integration

### Full list in [requirements.txt](requirements.txt)

---

## API Keys

### OMDb API

Required for film metadata enrichment.

1. Register at https://www.omdbapi.com/apikey.aspx
2. Free tier: 1,000 daily requests
3. Add to `.env`: `OMDB_API_KEY=your_key_here`

---

## Documentation

| Document | Description |
|----------|-------------|
| `docs/ADMIN_GUIDE.md` | Admin panel usage |
| `docs/RBAC_GUIDE.md` | Role-based access control |
| `docs/PASSWORD_RESET_GUIDE.md` | Password reset feature |
| `docs/SECURITY_AUDIT_REPORT.md` | Security audit results |
| `docs/SQLALCHEMY_MIGRATION.md` | Database migration guide |
| `docs/CHANGELOG.md` | Version history |

---

## Troubleshooting

### Playwright Browser Not Found

```bash
playwright install chromium
```

### Database Locked (SQLite)

Close all connections and restart the app.

### Module Import Errors

```bash
pip install -r requirements.txt --force-reinstall
```

### Web Scraping Failures

1. Check internet connection
2. Verify theater websites are accessible
3. Enable debug mode: `DEBUG=true`
4. Check `debug_snapshots/` for captured pages

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make changes and add tests
4. Run test suite: `pytest`
5. Submit pull request

---

## License

Proprietary - 626labs LLC

---

## Support

- **Documentation:** See `docs/` directory
- **Issues:** GitHub Issues
- **Security:** See `SECURITY.md`

---

**Version:** 2.0.1
**Last Updated:** November 28, 2025
**Maintainer:** 626labs LLC
