# PriceScout Remediation Plan

**Version:** 3.0.0
**Date:** November 28, 2025
**Status:** In Progress

---

## Executive Summary

This document details all identified gaps from the comprehensive code review and provides implementation plans to achieve 100% compliance with TheatreOperations platform standards.

**Current Score:** 92/100
**Target Score:** 100/100

---

## Table of Contents

1. [Gap Summary](#gap-summary)
2. [P1: RFC 7807 Error Responses](#p1-rfc-7807-error-responses)
3. [P1: PriceAlerts Table](#p1-pricealerts-table)
4. [P1: Unified API Authentication](#p1-unified-api-authentication)
5. [P2: Entra ID SSO Integration](#p2-entra-id-sso-integration)
6. [P2: Azure SQL Setup](#p2-azure-sql-setup)
7. [P3: Minor Improvements](#p3-minor-improvements)
8. [Implementation Timeline](#implementation-timeline)
9. [Testing Strategy](#testing-strategy)

---

## Gap Summary

| Priority | Gap | Impact | Effort | Status |
|----------|-----|--------|--------|--------|
| P1 | RFC 7807 Error Responses | Medium | 2-3 days | Pending |
| P1 | Missing `PriceAlerts` Table | Low | 1-2 days | Pending |
| P1 | Mixed Authentication Methods | Medium | 1-2 days | Pending |
| P2 | Entra ID SSO | Low | 3-5 days | Pending |
| P2 | Azure SQL Schema | Medium | 1 day | Pending |
| P3 | Streamlit Coupling in Scraper | Low | 0.5 day | Pending |
| P3 | Structured JSON Logging | Low | 0.5 day | Pending |

---

## P1: RFC 7807 Error Responses

### Current State

Error responses use inconsistent custom formats:

```python
# Current (reports.py:86-90)
return JSONResponse(status_code=503, content={
    "error": "PDF generation failed...",
    "detail": str(e)
})
```

### Target State

RFC 7807 Problem Details format:

```json
{
  "type": "https://api.pricescout.io/errors/pdf-generation-failed",
  "title": "PDF Generation Error",
  "status": 503,
  "detail": "PDF generation failed. Install Playwright browsers: 'playwright install chromium'",
  "instance": "/api/v1/reports/showtime-view/pdf",
  "timestamp": "2025-11-28T12:00:00Z"
}
```

### Implementation

#### File: `api/errors.py` (New)

```python
"""
RFC 7807 Problem Details Implementation for PriceScout API

Usage:
    from api.errors import problem_response, ProblemType

    return problem_response(
        problem_type=ProblemType.VALIDATION_ERROR,
        title="Validation Error",
        status=400,
        detail="Invalid date format",
        instance=request.url.path,
        errors={"date": ["Must be YYYY-MM-DD format"]}
    )
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from fastapi import Request
from fastapi.responses import JSONResponse


class ProblemType(str, Enum):
    """Standard problem type URIs for PriceScout API"""
    VALIDATION_ERROR = "https://api.pricescout.io/errors/validation"
    NOT_FOUND = "https://api.pricescout.io/errors/not-found"
    UNAUTHORIZED = "https://api.pricescout.io/errors/unauthorized"
    FORBIDDEN = "https://api.pricescout.io/errors/forbidden"
    RATE_LIMITED = "https://api.pricescout.io/errors/rate-limited"
    INTERNAL_ERROR = "https://api.pricescout.io/errors/internal"
    SERVICE_UNAVAILABLE = "https://api.pricescout.io/errors/service-unavailable"
    PDF_GENERATION_FAILED = "https://api.pricescout.io/errors/pdf-generation-failed"
    SCRAPE_FAILED = "https://api.pricescout.io/errors/scrape-failed"
    DATABASE_ERROR = "https://api.pricescout.io/errors/database"


def problem_response(
    problem_type: ProblemType,
    title: str,
    status: int,
    detail: str,
    instance: Optional[str] = None,
    errors: Optional[Dict[str, Any]] = None,
    **extra_fields
) -> JSONResponse:
    """
    Create an RFC 7807 Problem Details response.

    Args:
        problem_type: URI identifying the problem type
        title: Short human-readable summary
        status: HTTP status code
        detail: Human-readable explanation specific to this occurrence
        instance: URI reference identifying the specific occurrence
        errors: Optional field-level errors (for validation)
        **extra_fields: Additional problem-specific fields

    Returns:
        JSONResponse with proper Content-Type header
    """
    content = {
        "type": problem_type.value,
        "title": title,
        "status": status,
        "detail": detail,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    if instance:
        content["instance"] = instance

    if errors:
        content["errors"] = errors

    content.update(extra_fields)

    return JSONResponse(
        status_code=status,
        content=content,
        headers={"Content-Type": "application/problem+json"}
    )


def validation_error(
    detail: str,
    errors: Dict[str, list],
    instance: Optional[str] = None
) -> JSONResponse:
    """Convenience function for validation errors (400)"""
    return problem_response(
        problem_type=ProblemType.VALIDATION_ERROR,
        title="Validation Error",
        status=400,
        detail=detail,
        instance=instance,
        errors=errors
    )


def not_found_error(
    detail: str,
    instance: Optional[str] = None
) -> JSONResponse:
    """Convenience function for not found errors (404)"""
    return problem_response(
        problem_type=ProblemType.NOT_FOUND,
        title="Resource Not Found",
        status=404,
        detail=detail,
        instance=instance
    )


def unauthorized_error(
    detail: str = "Authentication required",
    instance: Optional[str] = None
) -> JSONResponse:
    """Convenience function for unauthorized errors (401)"""
    return problem_response(
        problem_type=ProblemType.UNAUTHORIZED,
        title="Unauthorized",
        status=401,
        detail=detail,
        instance=instance
    )


def rate_limit_error(
    detail: str,
    retry_after: int,
    instance: Optional[str] = None
) -> JSONResponse:
    """Convenience function for rate limit errors (429)"""
    return problem_response(
        problem_type=ProblemType.RATE_LIMITED,
        title="Rate Limit Exceeded",
        status=429,
        detail=detail,
        instance=instance,
        retry_after=retry_after
    )


def internal_error(
    detail: str = "An unexpected error occurred",
    instance: Optional[str] = None
) -> JSONResponse:
    """Convenience function for internal server errors (500)"""
    return problem_response(
        problem_type=ProblemType.INTERNAL_ERROR,
        title="Internal Server Error",
        status=500,
        detail=detail,
        instance=instance
    )


def service_unavailable_error(
    detail: str,
    instance: Optional[str] = None
) -> JSONResponse:
    """Convenience function for service unavailable errors (503)"""
    return problem_response(
        problem_type=ProblemType.SERVICE_UNAVAILABLE,
        title="Service Unavailable",
        status=503,
        detail=detail,
        instance=instance
    )
```

### Files to Update

| File | Changes Required |
|------|-----------------|
| `api/routers/reports.py` | Replace `JSONResponse` with `problem_response()` |
| `api/routers/resources.py` | Replace `HTTPException` with `problem_response()` |
| `api/routers/auth.py` | Replace `HTTPException` with `unauthorized_error()` |
| `api/routers/users.py` | Replace `HTTPException` with `validation_error()` |
| `api/routers/scrapes.py` | Replace `HTTPException` with `internal_error()` |
| `api/routers/markets.py` | Add error handling |
| `api/routers/tasks.py` | Add error handling |

---

## P1: PriceAlerts Table

### Expected Schema (from claude.md)

```sql
PriceAlerts
├── Id
├── CompetitorLocationId (FK → core)
├── AlertType (PriceIncrease/PriceDecrease/NewOffering)
├── TriggeredAt
├── OldPrice
├── NewPrice
├── IsAcknowledged
└── AcknowledgedBy
```

### Implementation

#### File: `migrations/add_price_alerts.sql` (New)

```sql
-- PriceAlerts Migration for PriceScout
-- Version: 1.0.0
-- Date: November 28, 2025

-- ============================================================================
-- PRICE ALERTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS price_alerts (
    alert_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,

    -- Reference to the price that triggered the alert
    price_id INTEGER,
    showing_id INTEGER,

    -- Alert details
    theater_name VARCHAR(255) NOT NULL,
    film_title VARCHAR(500),
    ticket_type VARCHAR(100),
    format VARCHAR(100),

    -- Price change information
    alert_type VARCHAR(50) NOT NULL,  -- 'price_increase', 'price_decrease', 'new_offering', 'discontinued'
    old_price NUMERIC(6, 2),
    new_price NUMERIC(6, 2),
    price_change_percent NUMERIC(5, 2),  -- Computed: ((new - old) / old) * 100

    -- Timestamps
    triggered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    play_date DATE,

    -- Acknowledgment
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by INTEGER,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledgment_notes TEXT,

    -- Notification tracking
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_sent_at TIMESTAMP WITH TIME ZONE,

    -- Foreign keys
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (price_id) REFERENCES prices(price_id) ON DELETE SET NULL,
    FOREIGN KEY (showing_id) REFERENCES showings(showing_id) ON DELETE SET NULL,
    FOREIGN KEY (acknowledged_by) REFERENCES users(user_id) ON DELETE SET NULL,

    -- Constraints
    CONSTRAINT valid_alert_type CHECK (
        alert_type IN ('price_increase', 'price_decrease', 'new_offering', 'discontinued', 'significant_change')
    ),
    CONSTRAINT price_change_logic CHECK (
        (alert_type = 'new_offering' AND old_price IS NULL) OR
        (alert_type = 'discontinued' AND new_price IS NULL) OR
        (old_price IS NOT NULL AND new_price IS NOT NULL)
    )
);

-- Indexes for common queries
CREATE INDEX idx_price_alerts_company ON price_alerts (company_id);
CREATE INDEX idx_price_alerts_theater ON price_alerts (company_id, theater_name);
CREATE INDEX idx_price_alerts_triggered ON price_alerts (triggered_at DESC);
CREATE INDEX idx_price_alerts_unacknowledged ON price_alerts (company_id, is_acknowledged)
    WHERE is_acknowledged = FALSE;
CREATE INDEX idx_price_alerts_type ON price_alerts (alert_type);

-- Comments
COMMENT ON TABLE price_alerts IS 'Price change alerts for competitor monitoring';
COMMENT ON COLUMN price_alerts.alert_type IS 'Type: price_increase, price_decrease, new_offering, discontinued, significant_change';
COMMENT ON COLUMN price_alerts.price_change_percent IS 'Percentage change: positive = increase, negative = decrease';

-- ============================================================================
-- ALERT CONFIGURATION TABLE (Optional - for threshold settings)
-- ============================================================================

CREATE TABLE IF NOT EXISTS alert_configurations (
    config_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,

    -- Alert thresholds
    min_price_change_percent NUMERIC(5, 2) DEFAULT 5.0,  -- Only alert if change >= 5%
    min_price_change_amount NUMERIC(6, 2) DEFAULT 1.00,  -- Or change >= $1.00

    -- Alert types enabled
    alert_on_increase BOOLEAN DEFAULT TRUE,
    alert_on_decrease BOOLEAN DEFAULT TRUE,
    alert_on_new_offering BOOLEAN DEFAULT TRUE,
    alert_on_discontinued BOOLEAN DEFAULT TRUE,

    -- Notification settings
    notification_email VARCHAR(255),
    notification_enabled BOOLEAN DEFAULT TRUE,

    -- Filters
    theaters_filter JSONB DEFAULT '[]',  -- Empty = all theaters
    ticket_types_filter JSONB DEFAULT '[]',  -- Empty = all types

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    CONSTRAINT unique_company_config UNIQUE (company_id)
);

CREATE INDEX idx_alert_config_company ON alert_configurations (company_id);

COMMENT ON TABLE alert_configurations IS 'Per-company configuration for price alert thresholds';

-- ============================================================================
-- VIEW: Unacknowledged Alerts Summary
-- ============================================================================

CREATE OR REPLACE VIEW v_pending_alerts AS
SELECT
    pa.company_id,
    c.company_name,
    pa.theater_name,
    pa.alert_type,
    COUNT(*) as alert_count,
    MIN(pa.triggered_at) as oldest_alert,
    MAX(pa.triggered_at) as newest_alert,
    AVG(ABS(pa.price_change_percent)) as avg_change_percent
FROM price_alerts pa
JOIN companies c ON pa.company_id = c.company_id
WHERE pa.is_acknowledged = FALSE
GROUP BY pa.company_id, c.company_name, pa.theater_name, pa.alert_type
ORDER BY COUNT(*) DESC;

-- ============================================================================
-- FUNCTION: Detect Price Changes and Create Alerts
-- ============================================================================

CREATE OR REPLACE FUNCTION detect_price_changes()
RETURNS TRIGGER AS $$
DECLARE
    prev_price NUMERIC(6, 2);
    change_percent NUMERIC(5, 2);
    alert_type_val VARCHAR(50);
    config_row alert_configurations%ROWTYPE;
BEGIN
    -- Get alert configuration for this company
    SELECT * INTO config_row
    FROM alert_configurations
    WHERE company_id = NEW.company_id;

    -- Default config if none exists
    IF NOT FOUND THEN
        config_row.min_price_change_percent := 5.0;
        config_row.min_price_change_amount := 1.00;
        config_row.alert_on_increase := TRUE;
        config_row.alert_on_decrease := TRUE;
    END IF;

    -- Find previous price for same showing + ticket type
    SELECT p.price INTO prev_price
    FROM prices p
    JOIN showings s ON p.showing_id = s.showing_id
    WHERE s.company_id = NEW.company_id
      AND s.theater_name = (SELECT theater_name FROM showings WHERE showing_id = NEW.showing_id)
      AND p.ticket_type = NEW.ticket_type
      AND p.price_id != NEW.price_id
    ORDER BY p.created_at DESC
    LIMIT 1;

    -- Calculate change if previous price exists
    IF prev_price IS NOT NULL AND prev_price > 0 THEN
        change_percent := ((NEW.price - prev_price) / prev_price) * 100;

        -- Determine alert type
        IF NEW.price > prev_price THEN
            alert_type_val := 'price_increase';
        ELSE
            alert_type_val := 'price_decrease';
        END IF;

        -- Check if change meets threshold
        IF ABS(change_percent) >= config_row.min_price_change_percent
           OR ABS(NEW.price - prev_price) >= config_row.min_price_change_amount THEN

            -- Check if this alert type is enabled
            IF (alert_type_val = 'price_increase' AND config_row.alert_on_increase)
               OR (alert_type_val = 'price_decrease' AND config_row.alert_on_decrease) THEN

                INSERT INTO price_alerts (
                    company_id, price_id, showing_id, theater_name,
                    film_title, ticket_type, format, alert_type,
                    old_price, new_price, price_change_percent, play_date
                )
                SELECT
                    NEW.company_id, NEW.price_id, NEW.showing_id, s.theater_name,
                    s.film_title, NEW.ticket_type, s.format, alert_type_val,
                    prev_price, NEW.price, change_percent, s.play_date
                FROM showings s
                WHERE s.showing_id = NEW.showing_id;
            END IF;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger (disabled by default - enable when ready)
-- DROP TRIGGER IF EXISTS trigger_price_change_detection ON prices;
-- CREATE TRIGGER trigger_price_change_detection
--     AFTER INSERT ON prices
--     FOR EACH ROW
--     EXECUTE FUNCTION detect_price_changes();

-- ============================================================================
-- API ENDPOINTS TO ADD
-- ============================================================================
-- GET    /api/v1/price-alerts                  - List alerts (with filters)
-- GET    /api/v1/price-alerts/{id}             - Get single alert
-- PUT    /api/v1/price-alerts/{id}/acknowledge - Acknowledge alert
-- GET    /api/v1/price-alerts/summary          - Aggregate summary
-- POST   /api/v1/alert-configurations          - Create/update config
-- GET    /api/v1/alert-configurations          - Get config
```

#### File: `app/db_models.py` (Add to existing)

```python
class PriceAlert(Base):
    """Price change alerts for competitor monitoring"""
    __tablename__ = 'price_alerts'

    alert_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.company_id', ondelete='CASCADE'), nullable=False)

    # References
    price_id = Column(Integer, ForeignKey('prices.price_id', ondelete='SET NULL'))
    showing_id = Column(Integer, ForeignKey('showings.showing_id', ondelete='SET NULL'))

    # Alert details
    theater_name = Column(String(255), nullable=False)
    film_title = Column(String(500))
    ticket_type = Column(String(100))
    format = Column(String(100))

    # Price change
    alert_type = Column(String(50), nullable=False)  # price_increase, price_decrease, new_offering, discontinued
    old_price = Column(Numeric(6, 2))
    new_price = Column(Numeric(6, 2))
    price_change_percent = Column(Numeric(5, 2))

    # Timestamps
    triggered_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    play_date = Column(Date)

    # Acknowledgment
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(Integer, ForeignKey('users.user_id', ondelete='SET NULL'))
    acknowledged_at = Column(DateTime(timezone=True))
    acknowledgment_notes = Column(Text)

    # Notification
    notification_sent = Column(Boolean, default=False)
    notification_sent_at = Column(DateTime(timezone=True))

    # Relationships
    company = relationship("Company", back_populates="price_alerts")
    price = relationship("Price")
    showing = relationship("Showing")
    acknowledger = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('price_increase', 'price_decrease', 'new_offering', 'discontinued', 'significant_change')",
            name='valid_alert_type'
        ),
        Index('idx_price_alerts_company', 'company_id'),
        Index('idx_price_alerts_theater', 'company_id', 'theater_name'),
        Index('idx_price_alerts_triggered', 'triggered_at'),
        Index('idx_price_alerts_unacknowledged', 'company_id', 'is_acknowledged'),
    )

    def __repr__(self):
        return f"<PriceAlert(id={self.alert_id}, type='{self.alert_type}', theater='{self.theater_name}')>"
```

---

## P1: Unified API Authentication

### Current State

Mixed authentication approaches across routers:

| Router | Current Method | Consistency Issue |
|--------|---------------|-------------------|
| `reports.py` | API Key (`verify_api_key`) | - |
| `resources.py` | API Key (`verify_api_key`) | - |
| `auth.py` | OAuth2 + JWT | Different flow |
| `markets.py` | JWT only (`get_current_user`) | No API key support |
| `tasks.py` | JWT only (`get_current_user`) | No API key support |
| `scrapes.py` | JWT only (`get_current_user`) | No API key support |
| `users.py` | JWT only (`get_current_user`) | No API key support |

### Target State

Unified authentication supporting both API keys (for external integrations) and JWT (for UI/internal):

```python
# Support both authentication methods
@router.get("/endpoint")
async def endpoint(
    request: Request,
    auth: AuthData = Depends(unified_auth)  # Accepts API key OR JWT
):
    pass
```

### Implementation

#### File: `api/unified_auth.py` (New)

```python
"""
Unified Authentication Module for PriceScout API

Supports both:
1. API Key authentication (X-API-Key header) - for external integrations
2. JWT Bearer token (Authorization header) - for UI/internal use

Usage:
    from api.unified_auth import require_auth, optional_auth, AuthData

    @router.get("/endpoint")
    async def endpoint(auth: AuthData = Depends(require_auth)):
        print(f"User: {auth.username}, Method: {auth.auth_method}")
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer

from api.auth import verify_api_key, TIER_LIMITS
from api.routers.auth import get_current_user


class AuthMethod(str, Enum):
    API_KEY = "api_key"
    JWT = "jwt"
    ENTRA_ID = "entra_id"  # Future


@dataclass
class AuthData:
    """Unified authentication data returned by auth dependencies"""
    username: str
    auth_method: AuthMethod
    company_id: Optional[int] = None
    role: str = "user"
    is_admin: bool = False

    # API Key specific
    api_key_tier: Optional[str] = None
    api_key_prefix: Optional[str] = None
    features: Optional[List[str]] = None

    # Rate limiting
    rate_limit_remaining: Optional[int] = None

    def has_feature(self, feature: str) -> bool:
        """Check if authenticated user has access to a feature"""
        if self.features is None:
            return True  # JWT users have all features
        return feature in self.features or "all" in self.features


# Security headers
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


async def require_auth(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme)
) -> AuthData:
    """
    Require authentication via either API key or JWT token.

    Priority:
    1. API Key (if X-API-Key header present)
    2. JWT Bearer token (if Authorization header present)

    Raises:
        HTTPException 401 if neither is provided or valid
    """
    # Try API Key first
    if api_key:
        try:
            key_data = await verify_api_key(api_key)
            return AuthData(
                username=key_data["client"],
                auth_method=AuthMethod.API_KEY,
                role="api_user",
                api_key_tier=key_data["tier"],
                api_key_prefix=key_data["key_prefix"],
                features=key_data["features"],
            )
        except HTTPException:
            pass  # Fall through to try JWT

    # Try JWT token
    if token:
        try:
            user = await get_current_user(token)
            return AuthData(
                username=user["username"],
                auth_method=AuthMethod.JWT,
                company_id=user.get("company_id"),
                role=user.get("role", "user"),
                is_admin=user.get("is_admin", False),
            )
        except HTTPException:
            pass  # Fall through to error

    # Neither worked
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide X-API-Key header or Bearer token.",
        headers={"WWW-Authenticate": "Bearer, ApiKey"}
    )


async def optional_auth(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme)
) -> Optional[AuthData]:
    """
    Optional authentication - returns None if not authenticated.
    Useful for endpoints that provide enhanced features to authenticated users.
    """
    try:
        return await require_auth(request, api_key, token)
    except HTTPException:
        return None


def require_role(*roles: str):
    """
    Dependency that requires specific roles.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(auth: AuthData = Depends(require_role("admin"))):
            pass
    """
    async def role_checker(auth: AuthData = Depends(require_auth)) -> AuthData:
        if auth.role not in roles and not auth.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(roles)}"
            )
        return auth
    return role_checker


def require_feature(feature: str):
    """
    Dependency that requires specific API tier feature.

    Usage:
        @router.get("/premium-endpoint")
        async def premium_endpoint(auth: AuthData = Depends(require_feature("pdf_exports"))):
            pass
    """
    async def feature_checker(auth: AuthData = Depends(require_auth)) -> AuthData:
        if not auth.has_feature(feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires the '{feature}' feature. Upgrade your API tier."
            )
        return auth
    return feature_checker
```

---

## P2: Entra ID SSO Integration

### Overview

Implement Microsoft Entra ID authentication to enable enterprise SSO. This will be **ready for system integration testing** while the application continues using normal auth for regular testing.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Authentication Flow                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User → Entra ID Login → ID Token → PriceScout API → User      │
│                                                                  │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│   │   Entra ID   │───▶│  MSAL Auth   │───▶│  JWT/Session │      │
│   │   (Azure)    │    │  (Backend)   │    │   (Local)    │      │
│   └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                  │
│   Fallback: Normal username/password auth (unchanged)           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Azure Setup Requirements

#### 1. Azure Entra ID App Registration

```powershell
# Create App Registration in Azure Portal or via CLI

# Variables
$appName = "PriceScout-API"
$redirectUri = "https://app-pricescout-prod.azurewebsites.net/api/v1/auth/callback"
$devRedirectUri = "http://localhost:8000/api/v1/auth/callback"

# App Registration Settings:
# - Supported account types: Single tenant (your org only)
# - Redirect URI: Web platform
# - Enable ID tokens (implicit grant)
# - Enable access tokens (implicit grant)
```

#### 2. App Roles (RBAC Mapping)

Configure these roles in the App Registration manifest:

```json
{
  "appRoles": [
    {
      "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      "allowedMemberTypes": ["User"],
      "displayName": "PriceScout Admin",
      "description": "Full administrative access",
      "value": "admin"
    },
    {
      "id": "ffffffff-1111-2222-3333-444444444444",
      "allowedMemberTypes": ["User"],
      "displayName": "PriceScout Manager",
      "description": "Manager-level access",
      "value": "manager"
    },
    {
      "id": "55555555-6666-7777-8888-999999999999",
      "allowedMemberTypes": ["User"],
      "displayName": "PriceScout User",
      "description": "Standard user access",
      "value": "user"
    }
  ]
}
```

#### 3. Environment Variables

```bash
# .env or Azure App Service Configuration
ENTRA_CLIENT_ID=<app-registration-client-id>
ENTRA_TENANT_ID=<your-tenant-id>
ENTRA_CLIENT_SECRET=<client-secret>  # Store in Key Vault
ENTRA_REDIRECT_URI=https://your-app.azurewebsites.net/api/v1/auth/callback
ENTRA_ENABLED=true  # Set to false to disable Entra auth
```

### Implementation

#### File: `api/entra_auth.py` (New)

```python
"""
Microsoft Entra ID Authentication Module for PriceScout

Provides enterprise SSO authentication via MSAL.
Designed to coexist with existing username/password authentication.

Usage:
    # In API router
    from api.entra_auth import entra_login_url, handle_entra_callback, EntraUser

    @router.get("/auth/entra/login")
    async def entra_login():
        return RedirectResponse(entra_login_url())

    @router.get("/auth/entra/callback")
    async def entra_callback(code: str, state: str):
        user = await handle_entra_callback(code, state)
        return {"user": user.username, "role": user.role}

Configuration (environment variables):
    ENTRA_CLIENT_ID - Azure App Registration Client ID
    ENTRA_TENANT_ID - Azure Tenant ID
    ENTRA_CLIENT_SECRET - Client secret (from Key Vault)
    ENTRA_REDIRECT_URI - OAuth callback URL
    ENTRA_ENABLED - Set to 'true' to enable (default: false)
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode

import msal
from fastapi import HTTPException, status
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

def _get_entra_config() -> Dict[str, Any]:
    """Load Entra ID configuration from environment"""
    return {
        "client_id": os.getenv("ENTRA_CLIENT_ID", ""),
        "tenant_id": os.getenv("ENTRA_TENANT_ID", ""),
        "client_secret": os.getenv("ENTRA_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv("ENTRA_REDIRECT_URI", "http://localhost:8000/api/v1/auth/entra/callback"),
        "enabled": os.getenv("ENTRA_ENABLED", "false").lower() == "true",
        "authority": f"https://login.microsoftonline.com/{os.getenv('ENTRA_TENANT_ID', '')}",
        "scopes": ["User.Read", "openid", "profile", "email"],
    }


def is_entra_enabled() -> bool:
    """Check if Entra ID authentication is enabled and configured"""
    config = _get_entra_config()
    return (
        config["enabled"] and
        bool(config["client_id"]) and
        bool(config["tenant_id"])
    )


def _get_msal_app() -> msal.ConfidentialClientApplication:
    """Create MSAL confidential client application"""
    config = _get_entra_config()

    if not config["client_id"] or not config["tenant_id"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Entra ID authentication not configured"
        )

    return msal.ConfidentialClientApplication(
        client_id=config["client_id"],
        client_credential=config["client_secret"] if config["client_secret"] else None,
        authority=config["authority"],
    )


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class EntraUser:
    """User data extracted from Entra ID token"""
    username: str  # UPN or email
    display_name: str
    email: str
    entra_id: str  # Object ID in Entra
    roles: List[str]  # App roles assigned
    groups: List[str]  # Group memberships
    tenant_id: str

    # Mapped to local system
    local_role: str = "user"  # admin, manager, user
    company_id: Optional[int] = None

    @property
    def is_admin(self) -> bool:
        return self.local_role == "admin" or "admin" in self.roles


# ============================================================================
# AUTHENTICATION FLOW
# ============================================================================

# In-memory state storage (use Redis in production for multi-instance)
_auth_states: Dict[str, Dict[str, Any]] = {}


def get_login_url(state: Optional[str] = None, redirect_after: Optional[str] = None) -> str:
    """
    Generate Entra ID login URL for OAuth authorization code flow.

    Args:
        state: Optional state parameter (generated if not provided)
        redirect_after: URL to redirect to after successful login

    Returns:
        Authorization URL to redirect user to
    """
    if not is_entra_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Entra ID authentication is not enabled"
        )

    config = _get_entra_config()
    app = _get_msal_app()

    # Generate state if not provided
    if not state:
        import secrets
        state = secrets.token_urlsafe(32)

    # Store state for validation
    _auth_states[state] = {
        "redirect_after": redirect_after,
        "created_at": __import__("datetime").datetime.utcnow().isoformat()
    }

    # Build authorization URL
    auth_url = app.get_authorization_request_url(
        scopes=config["scopes"],
        state=state,
        redirect_uri=config["redirect_uri"],
    )

    logger.info(f"Generated Entra login URL for state: {state[:8]}...")
    return auth_url


async def handle_callback(code: str, state: str) -> EntraUser:
    """
    Handle OAuth callback from Entra ID.

    Args:
        code: Authorization code from Entra
        state: State parameter for CSRF validation

    Returns:
        EntraUser with extracted user information

    Raises:
        HTTPException: If authentication fails
    """
    # Validate state
    if state not in _auth_states:
        logger.warning(f"Invalid state parameter: {state[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter. Please try logging in again."
        )

    state_data = _auth_states.pop(state)
    config = _get_entra_config()
    app = _get_msal_app()

    try:
        # Exchange code for tokens
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=config["scopes"],
            redirect_uri=config["redirect_uri"],
        )

        if "error" in result:
            logger.error(f"Entra token error: {result.get('error_description', result['error'])}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {result.get('error_description', 'Unknown error')}"
            )

        # Extract user info from ID token claims
        id_token_claims = result.get("id_token_claims", {})

        user = EntraUser(
            username=id_token_claims.get("preferred_username", id_token_claims.get("upn", "")),
            display_name=id_token_claims.get("name", ""),
            email=id_token_claims.get("email", id_token_claims.get("preferred_username", "")),
            entra_id=id_token_claims.get("oid", ""),
            roles=id_token_claims.get("roles", []),
            groups=id_token_claims.get("groups", []),
            tenant_id=id_token_claims.get("tid", ""),
        )

        # Map Entra roles to local roles
        user.local_role = _map_entra_role_to_local(user.roles)

        # Optionally sync/create local user
        await _sync_local_user(user)

        logger.info(f"Entra login successful: {user.username} (role: {user.local_role})")
        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Entra callback error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication processing failed"
        )


def _map_entra_role_to_local(entra_roles: List[str]) -> str:
    """Map Entra ID app roles to local application roles"""
    if "admin" in entra_roles:
        return "admin"
    elif "manager" in entra_roles:
        return "manager"
    elif "user" in entra_roles:
        return "user"
    else:
        return "user"  # Default role


async def _sync_local_user(entra_user: EntraUser) -> None:
    """
    Sync Entra user to local database (create or update).

    This enables:
    - Local user record for audit logging
    - Company association
    - Mode permissions
    """
    from app.users import get_user, create_user, update_user

    # Check if user exists
    local_user = get_user(entra_user.email)

    if local_user:
        # Update existing user's role if changed
        # (Optional: implement role sync)
        logger.debug(f"Existing local user found: {entra_user.email}")
    else:
        # Create local user record
        import secrets
        temp_password = secrets.token_urlsafe(32)  # Random password (never used)

        success, message = create_user(
            username=entra_user.email,
            password=temp_password,
            role=entra_user.local_role,
            company=None,  # Will be assigned separately
        )

        if success:
            logger.info(f"Created local user for Entra account: {entra_user.email}")
        else:
            logger.warning(f"Could not create local user: {message}")


# ============================================================================
# JWT TOKEN GENERATION (for local session after Entra login)
# ============================================================================

def create_session_token(entra_user: EntraUser) -> str:
    """
    Create a local JWT session token after successful Entra authentication.

    This allows the app to use standard JWT validation for subsequent requests.
    """
    from datetime import datetime, timedelta
    from jose import jwt
    from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": entra_user.username,
        "exp": expire,
        "role": entra_user.local_role,
        "auth_method": "entra_id",
        "entra_id": entra_user.entra_id,
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ============================================================================
# API ROUTER ADDITIONS
# ============================================================================

def register_entra_routes(router):
    """
    Register Entra ID authentication routes on the auth router.

    Call this in api/routers/auth.py:
        from api.entra_auth import register_entra_routes
        register_entra_routes(router)
    """
    from fastapi import Query
    from fastapi.responses import RedirectResponse, JSONResponse

    @router.get("/entra/login", tags=["Authentication"])
    async def entra_login(
        redirect_after: Optional[str] = Query(None, description="URL to redirect after login")
    ):
        """
        Initiate Entra ID SSO login.
        Redirects user to Microsoft login page.
        """
        if not is_entra_enabled():
            return JSONResponse(
                status_code=503,
                content={"error": "Entra ID authentication is not enabled"}
            )

        login_url = get_login_url(redirect_after=redirect_after)
        return RedirectResponse(url=login_url)

    @router.get("/entra/callback", tags=["Authentication"])
    async def entra_callback(
        code: str = Query(..., description="Authorization code from Entra"),
        state: str = Query(..., description="State parameter for CSRF validation"),
        error: Optional[str] = Query(None),
        error_description: Optional[str] = Query(None),
    ):
        """
        Handle OAuth callback from Entra ID.
        Creates local session and returns JWT token.
        """
        if error:
            return JSONResponse(
                status_code=401,
                content={"error": error, "detail": error_description}
            )

        # Handle callback
        entra_user = await handle_callback(code, state)

        # Create local session token
        token = create_session_token(entra_user)

        # Get redirect URL from state or default
        redirect_url = _auth_states.get(state, {}).get("redirect_after")

        if redirect_url:
            # Redirect with token in URL (for SPA)
            return RedirectResponse(url=f"{redirect_url}?token={token}")
        else:
            # Return token directly
            return {
                "access_token": token,
                "token_type": "bearer",
                "user": {
                    "username": entra_user.username,
                    "display_name": entra_user.display_name,
                    "email": entra_user.email,
                    "role": entra_user.local_role,
                    "auth_method": "entra_id"
                }
            }

    @router.get("/entra/status", tags=["Authentication"])
    async def entra_status():
        """Check if Entra ID authentication is enabled and configured"""
        return {
            "enabled": is_entra_enabled(),
            "configured": bool(os.getenv("ENTRA_CLIENT_ID")),
        }
```

### Testing Strategy for Entra ID

| Test Phase | Auth Method | Purpose |
|------------|-------------|---------|
| Unit Tests | Mock Entra | Test token parsing, role mapping |
| Integration Tests | Normal Auth | Full app functionality |
| System Integration | Entra ID | Enterprise SSO validation |
| UAT | Both | User acceptance |
| Production | Both | Gradual rollout |

---

## P2: Azure SQL Setup

### Current State

The application supports three database backends:
1. **SQLite** - Local development (current)
2. **PostgreSQL** - Configured, Bicep ready
3. **Azure SQL (MSSQL)** - Bicep template exists, needs schema adaptation

### Azure SQL Bicep Template

The existing `azure/iac/sql.bicep` is properly configured with:
- TLS 1.2 enforcement
- Azure services firewall rule
- Configurable SKU (default: S0 Standard)

### Azure SQL Schema Script

#### File: `migrations/schema_mssql.sql` (New)

```sql
-- PriceScout Azure SQL (MSSQL) Schema
-- Version: 1.0.0
-- Date: November 28, 2025
-- Target: Azure SQL Database
--
-- Key differences from PostgreSQL:
-- - IDENTITY instead of SERIAL
-- - NVARCHAR instead of VARCHAR for Unicode
-- - DATETIME2 instead of TIMESTAMP WITH TIME ZONE
-- - No JSONB (use NVARCHAR(MAX) with JSON functions)
-- - Different constraint syntax

-- ============================================================================
-- CORE TABLES: Multi-tenancy and User Management
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'companies')
CREATE TABLE companies (
    company_id INT IDENTITY(1,1) PRIMARY KEY,
    company_name NVARCHAR(255) NOT NULL UNIQUE,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    is_active BIT DEFAULT 1,
    settings NVARCHAR(MAX) DEFAULT '{}',  -- JSON string
    CONSTRAINT company_name_not_empty CHECK (LEN(company_name) > 0)
);

CREATE INDEX idx_companies_active ON companies (is_active);
CREATE INDEX idx_companies_name ON companies (company_name);

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'users')
CREATE TABLE users (
    user_id INT IDENTITY(1,1) PRIMARY KEY,
    username NVARCHAR(100) NOT NULL UNIQUE,
    password_hash NVARCHAR(255) NOT NULL,
    role NVARCHAR(50) NOT NULL DEFAULT 'user',
    company_id INT NULL,
    default_company_id INT NULL,
    home_location_type NVARCHAR(50) NULL,
    home_location_value NVARCHAR(255) NULL,
    allowed_modes NVARCHAR(MAX) DEFAULT '[]',  -- JSON array
    is_admin BIT DEFAULT 0,
    must_change_password BIT DEFAULT 0,
    reset_code NVARCHAR(10) NULL,
    reset_code_expiry BIGINT NULL,
    reset_attempts INT DEFAULT 0,
    session_token NVARCHAR(255) NULL,
    session_token_expiry BIGINT NULL,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    last_login DATETIME2 NULL,
    is_active BIT DEFAULT 1,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE SET NULL,
    FOREIGN KEY (default_company_id) REFERENCES companies(company_id),
    CONSTRAINT valid_role CHECK (role IN ('admin', 'manager', 'user')),
    CONSTRAINT valid_home_location CHECK (
        home_location_type IS NULL OR
        home_location_type IN ('director', 'market', 'theater')
    )
);

CREATE INDEX idx_users_username ON users (username);
CREATE INDEX idx_users_company ON users (company_id);
CREATE INDEX idx_users_role ON users (role);
CREATE INDEX idx_users_active ON users (is_active);

-- Audit log table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'audit_log')
CREATE TABLE audit_log (
    log_id INT IDENTITY(1,1) PRIMARY KEY,
    timestamp DATETIME2 DEFAULT GETUTCDATE(),
    user_id INT NULL,
    username NVARCHAR(100) NULL,
    company_id INT NULL,
    event_type NVARCHAR(100) NOT NULL,
    event_category NVARCHAR(50) NOT NULL,
    severity NVARCHAR(20) DEFAULT 'info',
    details NVARCHAR(MAX) NULL,  -- JSON
    ip_address NVARCHAR(45) NULL,
    user_agent NVARCHAR(MAX) NULL,
    session_id NVARCHAR(255) NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE SET NULL
);

CREATE INDEX idx_audit_timestamp ON audit_log (timestamp DESC);
CREATE INDEX idx_audit_user ON audit_log (user_id);
CREATE INDEX idx_audit_company ON audit_log (company_id);
CREATE INDEX idx_audit_event_type ON audit_log (event_type);

-- ============================================================================
-- PRICING DATA TABLES
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'scrape_runs')
CREATE TABLE scrape_runs (
    run_id INT IDENTITY(1,1) PRIMARY KEY,
    company_id INT NOT NULL,
    run_timestamp DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    mode NVARCHAR(100) NOT NULL,
    user_id INT NULL,
    status NVARCHAR(50) DEFAULT 'completed',
    records_scraped INT DEFAULT 0,
    error_message NVARCHAR(MAX) NULL,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_scrape_runs_company ON scrape_runs (company_id);
CREATE INDEX idx_scrape_runs_timestamp ON scrape_runs (run_timestamp DESC);

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'showings')
CREATE TABLE showings (
    showing_id INT IDENTITY(1,1) PRIMARY KEY,
    company_id INT NOT NULL,
    play_date DATE NOT NULL,
    theater_name NVARCHAR(255) NOT NULL,
    film_title NVARCHAR(500) NOT NULL,
    showtime NVARCHAR(20) NOT NULL,
    format NVARCHAR(100) NULL,
    daypart NVARCHAR(50) NULL,
    is_plf BIT DEFAULT 0,
    ticket_url NVARCHAR(MAX) NULL,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    CONSTRAINT unique_showing UNIQUE (company_id, play_date, theater_name, film_title, showtime, format)
);

CREATE INDEX idx_showings_company ON showings (company_id);
CREATE INDEX idx_showings_theater_date ON showings (company_id, theater_name, play_date);
CREATE INDEX idx_showings_film ON showings (company_id, film_title);
CREATE INDEX idx_showings_date ON showings (play_date);

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'prices')
CREATE TABLE prices (
    price_id INT IDENTITY(1,1) PRIMARY KEY,
    company_id INT NOT NULL,
    run_id INT NULL,
    showing_id INT NULL,
    ticket_type NVARCHAR(100) NOT NULL,
    price DECIMAL(6, 2) NOT NULL,
    capacity NVARCHAR(50) NULL,
    play_date DATE NULL,
    scraped_at DATETIME2 DEFAULT GETUTCDATE(),
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES scrape_runs(run_id) ON DELETE SET NULL,
    FOREIGN KEY (showing_id) REFERENCES showings(showing_id),
    CONSTRAINT price_positive CHECK (price >= 0)
);

CREATE INDEX idx_prices_company ON prices (company_id);
CREATE INDEX idx_prices_run ON prices (run_id);
CREATE INDEX idx_prices_showing ON prices (showing_id);
CREATE INDEX idx_prices_date ON prices (play_date);

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'films')
CREATE TABLE films (
    film_id INT IDENTITY(1,1) PRIMARY KEY,
    company_id INT NOT NULL,
    film_title NVARCHAR(500) NOT NULL,
    imdb_id NVARCHAR(20) NULL,
    genre NVARCHAR(255) NULL,
    mpaa_rating NVARCHAR(20) NULL,
    director NVARCHAR(500) NULL,
    actors NVARCHAR(MAX) NULL,
    plot NVARCHAR(MAX) NULL,
    poster_url NVARCHAR(MAX) NULL,
    metascore INT NULL,
    imdb_rating DECIMAL(3, 1) NULL,
    release_date NVARCHAR(50) NULL,
    domestic_gross BIGINT NULL,
    runtime NVARCHAR(50) NULL,
    opening_weekend_domestic BIGINT NULL,
    last_omdb_update DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    CONSTRAINT unique_film_per_company UNIQUE (company_id, film_title)
);

CREATE INDEX idx_films_company ON films (company_id);
CREATE INDEX idx_films_title ON films (company_id, film_title);
CREATE INDEX idx_films_imdb ON films (imdb_id);

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'operating_hours')
CREATE TABLE operating_hours (
    operating_hours_id INT IDENTITY(1,1) PRIMARY KEY,
    company_id INT NOT NULL,
    run_id INT NULL,
    market NVARCHAR(255) NULL,
    theater_name NVARCHAR(255) NOT NULL,
    scrape_date DATE NOT NULL,
    open_time NVARCHAR(20) NULL,
    close_time NVARCHAR(20) NULL,
    duration_hours DECIMAL(5, 2) NULL,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES scrape_runs(run_id) ON DELETE SET NULL
);

CREATE INDEX idx_operating_hours_company ON operating_hours (company_id);
CREATE INDEX idx_operating_hours_theater_date ON operating_hours (company_id, theater_name, scrape_date);

-- ============================================================================
-- PRICE ALERTS TABLE (New - from Gap Analysis)
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'price_alerts')
CREATE TABLE price_alerts (
    alert_id INT IDENTITY(1,1) PRIMARY KEY,
    company_id INT NOT NULL,
    price_id INT NULL,
    showing_id INT NULL,
    theater_name NVARCHAR(255) NOT NULL,
    film_title NVARCHAR(500) NULL,
    ticket_type NVARCHAR(100) NULL,
    format NVARCHAR(100) NULL,
    alert_type NVARCHAR(50) NOT NULL,
    old_price DECIMAL(6, 2) NULL,
    new_price DECIMAL(6, 2) NULL,
    price_change_percent DECIMAL(5, 2) NULL,
    triggered_at DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    play_date DATE NULL,
    is_acknowledged BIT DEFAULT 0,
    acknowledged_by INT NULL,
    acknowledged_at DATETIME2 NULL,
    acknowledgment_notes NVARCHAR(MAX) NULL,
    notification_sent BIT DEFAULT 0,
    notification_sent_at DATETIME2 NULL,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (price_id) REFERENCES prices(price_id) ON DELETE SET NULL,
    FOREIGN KEY (showing_id) REFERENCES showings(showing_id),
    FOREIGN KEY (acknowledged_by) REFERENCES users(user_id) ON DELETE SET NULL,
    CONSTRAINT valid_alert_type CHECK (
        alert_type IN ('price_increase', 'price_decrease', 'new_offering', 'discontinued', 'significant_change')
    )
);

CREATE INDEX idx_price_alerts_company ON price_alerts (company_id);
CREATE INDEX idx_price_alerts_theater ON price_alerts (company_id, theater_name);
CREATE INDEX idx_price_alerts_triggered ON price_alerts (triggered_at DESC);
CREATE INDEX idx_price_alerts_unack ON price_alerts (company_id, is_acknowledged) WHERE is_acknowledged = 0;

-- ============================================================================
-- API KEYS TABLE (for rate-limited API access)
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'api_keys')
CREATE TABLE api_keys (
    id INT IDENTITY(1,1) PRIMARY KEY,
    key_hash NVARCHAR(64) NOT NULL UNIQUE,
    key_prefix NVARCHAR(12) NOT NULL,
    client_name NVARCHAR(255) NOT NULL,
    tier NVARCHAR(50) NOT NULL DEFAULT 'free',
    is_active BIT DEFAULT 1,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    expires_at DATETIME2 NULL,
    last_used_at DATETIME2 NULL,
    total_requests INT DEFAULT 0,
    notes NVARCHAR(MAX) NULL
);

CREATE INDEX idx_api_keys_hash ON api_keys (key_hash);
CREATE INDEX idx_api_keys_active ON api_keys (is_active);

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'api_key_usage')
CREATE TABLE api_key_usage (
    id INT IDENTITY(1,1) PRIMARY KEY,
    key_prefix NVARCHAR(12) NOT NULL,
    timestamp DATETIME2 DEFAULT GETUTCDATE(),
    endpoint NVARCHAR(255) NOT NULL,
    method NVARCHAR(10) NOT NULL,
    status_code INT NULL,
    response_time_ms INT NULL
);

CREATE INDEX idx_api_usage_prefix ON api_key_usage (key_prefix);
CREATE INDEX idx_api_usage_timestamp ON api_key_usage (timestamp DESC);

-- ============================================================================
-- REFERENCE TABLES
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'unmatched_films')
CREATE TABLE unmatched_films (
    unmatched_film_id INT IDENTITY(1,1) PRIMARY KEY,
    company_id INT NOT NULL,
    film_title NVARCHAR(500) NOT NULL,
    first_seen DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    last_seen DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    occurrence_count INT DEFAULT 1,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    CONSTRAINT unique_unmatched_film UNIQUE (company_id, film_title)
);

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ignored_films')
CREATE TABLE ignored_films (
    ignored_film_id INT IDENTITY(1,1) PRIMARY KEY,
    company_id INT NOT NULL,
    film_title NVARCHAR(500) NOT NULL,
    reason NVARCHAR(MAX) NULL,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    created_by INT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL,
    CONSTRAINT unique_ignored_film UNIQUE (company_id, film_title)
);

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'unmatched_ticket_types')
CREATE TABLE unmatched_ticket_types (
    unmatched_ticket_id INT IDENTITY(1,1) PRIMARY KEY,
    company_id INT NOT NULL,
    original_description NVARCHAR(MAX) NULL,
    unmatched_part NVARCHAR(255) NULL,
    first_seen DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    last_seen DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    theater_name NVARCHAR(255) NULL,
    film_title NVARCHAR(500) NULL,
    showtime NVARCHAR(20) NULL,
    format NVARCHAR(100) NULL,
    play_date DATE NULL,
    occurrence_count INT DEFAULT 1,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert system company
IF NOT EXISTS (SELECT 1 FROM companies WHERE company_name = 'System')
INSERT INTO companies (company_name, is_active, settings)
VALUES ('System', 1, '{"type": "system", "description": "Internal system operations"}');

-- Insert default admin user (password: 'admin' - CHANGE IN PRODUCTION)
IF NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin')
INSERT INTO users (
    username, password_hash, role, company_id, is_admin,
    allowed_modes, must_change_password
)
VALUES (
    'admin',
    '$2b$12$rXjXOQ3MKDxPZ.qEgMZ9HuGVVz6V0z1JVD0pXKI1J6cHpV4iU9x7a',
    'admin',
    (SELECT company_id FROM companies WHERE company_name = 'System'),
    1,
    '["Market Mode", "Operating Hours Mode", "CompSnipe Mode", "Historical Data and Analysis", "Data Management", "Theater Matching", "Admin", "Poster Board"]',
    1
);

PRINT 'PriceScout Azure SQL schema created successfully';
GO
```

### Database Session Update

Update `app/db_session.py` to ensure MSSQL is fully supported (already has structure, verify connection string handling).

---

## P3: Minor Improvements

### 3.1 Remove Streamlit Coupling from Scraper

**File:** `app/scraper.py`

**Current (line 339):**
```python
if not movie_blocks and st.session_state.get('capture_html', False):
```

**Fix:**
```python
# Pass debug_mode as parameter instead
def __init__(self, headless=True, devtools=False, debug_mode=False):
    self.headless = headless
    self.devtools = devtools
    self.debug_mode = debug_mode

# In method
if not movie_blocks and self.debug_mode:
```

### 3.2 Structured JSON Logging

**File:** `app/config.py` (add logging configuration)

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def configure_logging():
    """Configure structured JSON logging for production"""
    if is_production():
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logging.basicConfig(level=LOG_LEVEL, handlers=[handler])
    else:
        logging.basicConfig(level=LOG_LEVEL)
```

---

## Implementation Timeline

| Phase | Tasks | Duration | Dependencies |
|-------|-------|----------|--------------|
| **Phase 1** | RFC 7807 errors, Unified auth | 2-3 days | None |
| **Phase 2** | PriceAlerts table, Azure SQL schema | 2-3 days | Phase 1 |
| **Phase 3** | Entra ID module (ready for integration) | 3-5 days | Phase 2 |
| **Phase 4** | Minor improvements, testing | 2 days | Phase 3 |

**Total Estimated Duration:** 9-13 days

---

## Testing Strategy

### Normal Auth Testing (Current)
- All existing tests continue to use username/password auth
- No changes required to test infrastructure
- API key testing via `pytest` fixtures

### Entra ID Testing (System Integration)
1. **Mock Testing:** Unit tests with mocked MSAL responses
2. **Sandbox Testing:** Azure B2C test tenant
3. **Integration Testing:** Real Entra ID with test users
4. **Dual-Mode Testing:** Both auth methods simultaneously

### Test Configuration

```python
# conftest.py additions for Entra testing
import pytest

@pytest.fixture
def mock_entra_user():
    from api.entra_auth import EntraUser
    return EntraUser(
        username="test@company.com",
        display_name="Test User",
        email="test@company.com",
        entra_id="test-oid",
        roles=["user"],
        groups=[],
        tenant_id="test-tenant",
        local_role="user"
    )

@pytest.fixture
def entra_enabled(monkeypatch):
    monkeypatch.setenv("ENTRA_ENABLED", "true")
    monkeypatch.setenv("ENTRA_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("ENTRA_TENANT_ID", "test-tenant-id")
```

---

## Verification Checklist

- [ ] RFC 7807 error responses implemented
- [ ] `PriceAlerts` table added to all schemas (PostgreSQL, MSSQL, SQLite model)
- [ ] Unified authentication working for all routers
- [ ] Entra ID module created and testable
- [ ] Azure SQL schema script validated
- [ ] All existing tests passing
- [ ] Documentation updated

---

*Document Version: 3.0.0*
*Last Updated: November 28, 2025*
