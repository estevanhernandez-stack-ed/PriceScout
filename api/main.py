"""
PriceScout API - FastAPI Application

Main entry point for the PriceScout REST API.
Provides endpoints for pricing data, reports, authentication, and management.

Run with:
    uvicorn api.main:app --reload --port 8000

API Documentation:
    - Swagger UI: http://localhost:8000/api/v1/docs
    - ReDoc: http://localhost:8000/api/v1/redoc
    - OpenAPI JSON: http://localhost:8000/api/v1/openapi.json
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# Add repo root to path so `app` package is importable when running `uvicorn api.main:app`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import routers
from api.routers import reports, resources, auth, markets, tasks, scrapes, users
from api.routers import scrape_sources, price_checks, price_alerts

# Import error handlers
from api.errors import (
    problem_response,
    ProblemType,
    validation_error,
    internal_error,
    not_found_error
)

# Import configuration
from app.config import (
    APPLICATIONINSIGHTS_CONNECTION_STRING,
    APP_NAME,
    APP_VERSION,
    DEBUG,
    is_production
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# APPLICATION SETUP
# ============================================================================

app = FastAPI(
    title="PriceScout API",
    version="2.0.0",
    description="""
## PriceScout API

REST API for the PriceScout competitive pricing intelligence application.

### Features
- **Reports**: Generate selection analysis, showtime views, daily lineups
- **Resources**: Access theaters, films, showtimes, and pricing data
- **Authentication**: JWT tokens, API keys, and Entra ID SSO
- **Management**: Scrape runs, scheduled tasks, user administration

### Authentication
Most endpoints require authentication via:
- **API Key**: Include `X-API-Key` header
- **JWT Token**: Include `Authorization: Bearer <token>` header

### Rate Limiting
API key tiers have different rate limits:
- Free: 100 requests/hour
- Premium: 1,000 requests/hour
- Enterprise: Unlimited

### Error Responses
All errors follow RFC 7807 Problem Details format.
    """,
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    contact={
        "name": "PriceScout Support",
        "email": "support@pricescout.io",
    },
    license_info={
        "name": "Proprietary",
    },
)


# ============================================================================
# OPENTELEMETRY / APPLICATION INSIGHTS
# ============================================================================

if APPLICATIONINSIGHTS_CONNECTION_STRING:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("Application Insights instrumentation enabled")
    except ImportError:
        logger.warning("OpenTelemetry not available - instrumentation disabled")
    except Exception as e:
        logger.warning(f"Failed to initialize Application Insights: {e}")


# ============================================================================
# CORS MIDDLEWARE
# ============================================================================

# Configure CORS for frontend access
origins = [
    "http://localhost:8501",      # Streamlit local
    "http://localhost:3000",      # React dev
    "http://localhost:8000",      # FastAPI local
    "https://*.azurewebsites.net",  # Azure App Service
]

if DEBUG:
    origins.append("*")  # Allow all in development

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if not DEBUG else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Rate-Limit-Remaining"],
)


# ============================================================================
# GLOBAL EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic validation errors with RFC 7807 format.
    """
    errors = {}
    for error in exc.errors():
        loc = ".".join(str(l) for l in error["loc"])
        if loc not in errors:
            errors[loc] = []
        errors[loc].append(error["msg"])

    return validation_error(
        detail="Request validation failed",
        errors=errors,
        instance=str(request.url.path)
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Convert HTTPException to RFC 7807 format.
    """
    # Map status codes to problem types
    problem_type_map = {
        400: ProblemType.BAD_REQUEST,
        401: ProblemType.UNAUTHORIZED,
        403: ProblemType.FORBIDDEN,
        404: ProblemType.NOT_FOUND,
        409: ProblemType.CONFLICT,
        429: ProblemType.RATE_LIMITED,
        500: ProblemType.INTERNAL_ERROR,
        503: ProblemType.SERVICE_UNAVAILABLE,
    }

    problem_type = problem_type_map.get(exc.status_code, ProblemType.INTERNAL_ERROR)

    return problem_response(
        problem_type=problem_type,
        title=exc.detail if isinstance(exc.detail, str) else "Error",
        status=exc.status_code,
        detail=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
        instance=str(request.url.path)
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all handler for unhandled exceptions.
    Logs the error and returns a safe RFC 7807 response.
    """
    logger.exception(f"Unhandled exception on {request.url.path}: {exc}")

    # Don't expose internal details in production
    detail = str(exc) if DEBUG else "An unexpected error occurred. Please try again."

    return internal_error(
        detail=detail,
        instance=str(request.url.path)
    )


# ============================================================================
# ROUTERS
# ============================================================================

# Authentication (must be first for token endpoint)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])

# Reports - selection analysis, showtime views, daily lineup
app.include_router(reports.router, tags=["Reports"])

# Resources - theaters, films, showtimes, pricing
app.include_router(resources.router, tags=["Resources"])

# Markets - market data and configuration
app.include_router(markets.router, prefix="/api/v1", tags=["Markets"])

# Tasks - scheduled task management
app.include_router(tasks.router, prefix="/api/v1", tags=["Tasks"])

# Scrapes - scrape run management
app.include_router(scrapes.router, prefix="/api/v1", tags=["Scrapes"])

# Users - user management (password changes, etc.)
app.include_router(users.router, prefix="/api/v1", tags=["Users"])

# Scrape Sources - configurable scrape source management (claude.md standard)
app.include_router(scrape_sources.router, prefix="/api/v1", tags=["Scrape Sources"])

# Price Checks - price data queries (claude.md standard)
app.include_router(price_checks.router, prefix="/api/v1", tags=["Price Data"])

# Price Alerts - price change alerts (claude.md standard)
app.include_router(price_alerts.router, prefix="/api/v1", tags=["Price Alerts"])


# ============================================================================
# ROOT ENDPOINTS
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    """
    API root - returns basic information and links.
    """
    return {
        "name": "PriceScout API",
        "version": "2.0.0",
        "status": "operational",
        "docs": "/api/v1/docs",
        "openapi": "/api/v1/openapi.json",
        "health": "/api/v1/health"
    }


@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.

    Returns:
        - status: 'healthy' or 'degraded'
        - timestamp: Current UTC time
        - version: API version
        - database: Database connection status
        - services: Status of dependent services
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "environment": "production" if is_production() else "development",
    }

    # Check database connection
    try:
        from app.db_session import get_session
        from sqlalchemy import text
        with get_session() as session:
            session.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = "disconnected"
        health_status["status"] = "degraded"
        logger.warning(f"Health check: database connection failed: {e}")

    # Check Entra ID status
    try:
        from api.entra_auth import is_entra_enabled
        health_status["entra_id"] = "enabled" if is_entra_enabled() else "disabled"
    except ImportError:
        health_status["entra_id"] = "not_configured"

    # Check Application Insights
    health_status["telemetry"] = "enabled" if APPLICATIONINSIGHTS_CONNECTION_STRING else "disabled"

    return health_status


@app.get("/api/v1/info", tags=["Root"])
async def api_info():
    """
    Get detailed API information including available endpoints.
    """
    return {
        "name": "PriceScout API",
        "version": "2.0.0",
        "description": "Competitive pricing intelligence API",
        "authentication": {
            "methods": ["api_key", "jwt", "entra_id"],
            "api_key_header": "X-API-Key",
            "jwt_header": "Authorization: Bearer <token>",
            "token_endpoint": "/api/v1/auth/token",
            "entra_login": "/api/v1/auth/entra/login"
        },
        "rate_limits": {
            "free": {"requests_per_hour": 100, "requests_per_day": 1000},
            "premium": {"requests_per_hour": 1000, "requests_per_day": 50000},
            "enterprise": {"requests_per_hour": "unlimited", "requests_per_day": "unlimited"}
        },
        "endpoints": {
            "authentication": "/api/v1/auth/*",
            "reports": "/api/v1/reports/*",
            "theaters": "/api/v1/theaters",
            "films": "/api/v1/films",
            "showtimes": "/api/v1/showtimes/*",
            "pricing": "/api/v1/pricing",
            "markets": "/api/v1/markets",
            "tasks": "/api/v1/tasks",
            "scrapes": "/api/v1/scrapes/*"
        },
        "documentation": {
            "swagger": "/api/v1/docs",
            "redoc": "/api/v1/redoc",
            "openapi": "/api/v1/openapi.json"
        }
    }


# ============================================================================
# STARTUP / SHUTDOWN EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Initialize resources on application startup.
    """
    logger.info(f"Starting PriceScout API v2.0.0")
    logger.info(f"Environment: {'production' if is_production() else 'development'}")
    logger.info(f"Debug mode: {DEBUG}")

    # Initialize database connection pool
    try:
        from app.db_session import get_engine
        engine = get_engine()
        logger.info(f"Database connection initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup resources on application shutdown.
    """
    logger.info("Shutting down PriceScout API")

    # Close database connections
    try:
        from app.db_session import close_engine
        close_engine()
        logger.info("Database connections closed")
    except Exception as e:
        logger.warning(f"Error closing database: {e}")
