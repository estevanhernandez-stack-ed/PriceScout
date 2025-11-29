"""
Unified Authentication Module for PriceScout API

Supports multiple authentication methods:
1. API Key authentication (X-API-Key header) - for external integrations
2. JWT Bearer token (Authorization header) - for UI/internal use
3. Entra ID SSO (via JWT after OAuth flow) - for enterprise users

Usage:
    from api.unified_auth import require_auth, optional_auth, AuthData

    @router.get("/endpoint")
    async def endpoint(auth: AuthData = Depends(require_auth)):
        print(f"User: {auth.username}, Method: {auth.auth_method}")

    @router.get("/optional-auth")
    async def optional_endpoint(auth: Optional[AuthData] = Depends(optional_auth)):
        if auth:
            return {"message": f"Hello, {auth.username}"}
        return {"message": "Hello, anonymous user"}

    @router.get("/admin-only")
    async def admin_endpoint(auth: AuthData = Depends(require_role("admin"))):
        return {"message": "Admin access granted"}
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Callable, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer

# Import auth method config flags
from app.config import DB_AUTH_ENABLED, API_KEY_AUTH_ENABLED, ENTRA_ENABLED

logger = logging.getLogger(__name__)

# ============================================================================
# AUTHENTICATION METHODS
# ============================================================================

class AuthMethod(str, Enum):
    """Authentication method used for the request."""
    API_KEY = "api_key"
    JWT = "jwt"
    ENTRA_ID = "entra_id"
    ANONYMOUS = "anonymous"


# ============================================================================
# AUTH DATA MODEL
# ============================================================================

@dataclass
class AuthData:
    """
    Unified authentication data returned by auth dependencies.

    Contains information about the authenticated user regardless of
    which authentication method was used.
    """
    username: str
    auth_method: AuthMethod
    company_id: Optional[int] = None
    role: str = "user"
    is_admin: bool = False

    # API Key specific fields
    api_key_tier: Optional[str] = None
    api_key_prefix: Optional[str] = None
    features: Optional[List[str]] = None

    # Entra ID specific fields
    entra_id: Optional[str] = None
    display_name: Optional[str] = None

    # Rate limiting info
    rate_limit_remaining: Optional[int] = None

    def has_feature(self, feature: str) -> bool:
        """
        Check if authenticated user has access to a feature.

        For API key auth, checks the tier's feature list.
        For JWT/Entra auth, returns True (all features).
        """
        if self.features is None:
            return True  # JWT/Entra users have all features
        return feature in self.features or "all" in self.features

    def has_role(self, *roles: str) -> bool:
        """Check if user has any of the specified roles."""
        return self.is_admin or self.role in roles

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            "username": self.username,
            "auth_method": self.auth_method.value,
            "company_id": self.company_id,
            "role": self.role,
            "is_admin": self.is_admin,
        }


# ============================================================================
# SECURITY SCHEMES
# ============================================================================

# API Key header
api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="API key for external integrations"
)

# OAuth2 Bearer token
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
    auto_error=False,
    description="JWT bearer token"
)


# ============================================================================
# AUTHENTICATION FUNCTIONS
# ============================================================================

async def _try_api_key_auth(api_key: str) -> Optional[AuthData]:
    """
    Attempt to authenticate using API key.

    Returns AuthData if successful, None if key is invalid or API key auth is disabled.
    """
    # Check if API key auth is enabled
    if not API_KEY_AUTH_ENABLED:
        logger.debug("API key auth is disabled via API_KEY_AUTH_ENABLED=false")
        return None

    try:
        from api.auth import verify_api_key
        key_data = await verify_api_key(api_key)

        return AuthData(
            username=key_data["client"],
            auth_method=AuthMethod.API_KEY,
            role="api_user",
            api_key_tier=key_data["tier"],
            api_key_prefix=key_data["key_prefix"],
            features=key_data.get("features", []),
        )
    except HTTPException:
        return None
    except Exception as e:
        logger.warning(f"API key auth error: {e}")
        return None


async def _try_jwt_auth(token: str) -> Optional[AuthData]:
    """
    Attempt to authenticate using JWT token.

    Returns AuthData if successful, None if token is invalid or auth method is disabled.

    Respects config flags:
    - DB_AUTH_ENABLED: Controls tokens with auth_method="password"
    - ENTRA_ENABLED: Controls tokens with auth_method="entra_id"
    """
    try:
        from api.routers.auth import get_current_user
        user = await get_current_user(token)

        # Determine auth method from token
        token_auth_method = user.get("auth_method", "password")

        # Check if the auth method used to create this token is still enabled
        if token_auth_method == "password" and not DB_AUTH_ENABLED:
            logger.debug("Rejecting password-based JWT: DB_AUTH_ENABLED=false")
            return None

        if token_auth_method == "entra_id" and not ENTRA_ENABLED:
            logger.debug("Rejecting Entra ID JWT: ENTRA_ENABLED=false")
            return None

        # Map to AuthMethod enum
        auth_method = AuthMethod.ENTRA_ID if token_auth_method == "entra_id" else AuthMethod.JWT

        return AuthData(
            username=user["username"],
            auth_method=auth_method,
            company_id=user.get("company_id"),
            role=user.get("role", "user"),
            is_admin=user.get("is_admin", False),
            entra_id=user.get("entra_id"),
            display_name=user.get("display_name"),
        )
    except HTTPException:
        return None
    except Exception as e:
        logger.warning(f"JWT auth error: {e}")
        return None


# ============================================================================
# DEPENDENCY FUNCTIONS
# ============================================================================

async def require_auth(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme)
) -> AuthData:
    """
    Require authentication via either API key or JWT token.

    Priority:
    1. API Key (if X-API-Key header present and API_KEY_AUTH_ENABLED)
    2. JWT Bearer token (if Authorization header present and method enabled)

    Raises:
        HTTPException 401 if neither is provided or valid

    Usage:
        @router.get("/protected")
        async def protected_endpoint(auth: AuthData = Depends(require_auth)):
            return {"user": auth.username}
    """
    # Try API Key first (if provided)
    if api_key:
        auth_data = await _try_api_key_auth(api_key)
        if auth_data:
            logger.debug(f"API key auth successful: {auth_data.api_key_prefix}")
            return auth_data

    # Try JWT token (if provided)
    if token:
        auth_data = await _try_jwt_auth(token)
        if auth_data:
            logger.debug(f"JWT auth successful: {auth_data.username}")
            return auth_data

    # Neither worked - build helpful error message
    enabled_methods = []
    if ENTRA_ENABLED:
        enabled_methods.append("Entra ID SSO (/api/v1/auth/entra/login)")
    if DB_AUTH_ENABLED:
        enabled_methods.append("Username/Password (/api/v1/auth/token)")
    if API_KEY_AUTH_ENABLED:
        enabled_methods.append("API Key (X-API-Key header)")

    if enabled_methods:
        detail = f"Authentication required. Enabled methods: {', '.join(enabled_methods)}"
    else:
        detail = "No authentication methods are enabled. Contact your administrator."

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer, ApiKey"} if API_KEY_AUTH_ENABLED else {"WWW-Authenticate": "Bearer"}
    )


async def optional_auth(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme)
) -> Optional[AuthData]:
    """
    Optional authentication - returns None if not authenticated.

    Useful for endpoints that provide enhanced features to authenticated users
    but still work for anonymous access.

    Usage:
        @router.get("/public-with-extras")
        async def public_endpoint(auth: Optional[AuthData] = Depends(optional_auth)):
            if auth:
                return {"message": f"Hello, {auth.username}", "premium_data": ...}
            return {"message": "Hello, guest"}
    """
    try:
        return await require_auth(request, api_key, token)
    except HTTPException:
        return None


def require_role(*roles: str) -> Callable:
    """
    Dependency factory that requires specific roles.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(auth: AuthData = Depends(require_role("admin"))):
            return {"message": "Admin access"}

        @router.get("/manager-or-admin")
        async def manager_endpoint(auth: AuthData = Depends(require_role("admin", "manager"))):
            return {"message": "Manager/Admin access"}
    """
    async def role_checker(
        request: Request,
        api_key: Optional[str] = Depends(api_key_header),
        token: Optional[str] = Depends(oauth2_scheme)
    ) -> AuthData:
        auth = await require_auth(request, api_key, token)

        if auth.is_admin:
            return auth  # Admins can access everything

        if auth.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {' or '.join(roles)}. Your role: {auth.role}"
            )

        return auth

    return role_checker


def require_feature(feature: str) -> Callable:
    """
    Dependency factory that requires specific API tier feature.

    Only applies to API key authentication. JWT users have all features.

    Usage:
        @router.get("/premium-endpoint")
        async def premium_endpoint(auth: AuthData = Depends(require_feature("pdf_exports"))):
            return {"message": "Premium feature access"}
    """
    async def feature_checker(
        request: Request,
        api_key: Optional[str] = Depends(api_key_header),
        token: Optional[str] = Depends(oauth2_scheme)
    ) -> AuthData:
        auth = await require_auth(request, api_key, token)

        if not auth.has_feature(feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires the '{feature}' feature. "
                       f"Your tier: {auth.api_key_tier or 'N/A'}. "
                       f"Upgrade your API tier for access."
            )

        return auth

    return feature_checker


def require_company(company_id: Optional[int] = None) -> Callable:
    """
    Dependency factory that requires user to belong to a specific company.

    If company_id is None, just requires user to have a company assigned.

    Usage:
        @router.get("/company-data")
        async def company_endpoint(auth: AuthData = Depends(require_company())):
            return {"company_id": auth.company_id}

        @router.get("/specific-company/{company_id}")
        async def specific_company(
            company_id: int,
            auth: AuthData = Depends(require_company())
        ):
            if auth.company_id != company_id and not auth.is_admin:
                raise HTTPException(403, "Access denied")
            return {"data": ...}
    """
    async def company_checker(
        request: Request,
        api_key: Optional[str] = Depends(api_key_header),
        token: Optional[str] = Depends(oauth2_scheme)
    ) -> AuthData:
        auth = await require_auth(request, api_key, token)

        # API key users may not have company association
        if auth.auth_method == AuthMethod.API_KEY:
            return auth

        # Check company requirement
        if auth.company_id is None and not auth.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No company assigned to your account. Contact administrator."
            )

        if company_id is not None and auth.company_id != company_id and not auth.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied for company {company_id}"
            )

        return auth

    return company_checker


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_auth_info_for_logging(auth: Optional[AuthData]) -> dict:
    """
    Get authentication info suitable for logging.

    Excludes sensitive data like tokens.
    """
    if auth is None:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "username": auth.username,
        "auth_method": auth.auth_method.value,
        "role": auth.role,
        "company_id": auth.company_id,
    }


def create_anonymous_auth() -> AuthData:
    """Create an anonymous AuthData for unauthenticated requests."""
    return AuthData(
        username="anonymous",
        auth_method=AuthMethod.ANONYMOUS,
        role="anonymous",
        is_admin=False,
    )
