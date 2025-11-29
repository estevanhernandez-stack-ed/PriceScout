"""
Microsoft Entra ID Authentication Module for PriceScout

Provides enterprise SSO authentication via MSAL (Microsoft Authentication Library).
Designed to coexist with existing username/password authentication.

This module is READY FOR SYSTEM INTEGRATION TESTING.
Normal auth continues to work for regular testing.

Configuration (environment variables):
    ENTRA_CLIENT_ID     - Azure App Registration Client ID
    ENTRA_TENANT_ID     - Azure Tenant ID
    ENTRA_CLIENT_SECRET - Client secret (store in Key Vault for production)
    ENTRA_REDIRECT_URI  - OAuth callback URL
    ENTRA_ENABLED       - Set to 'true' to enable Entra authentication

Azure Setup Required:
    1. Create App Registration in Azure Portal
    2. Configure redirect URIs (web platform)
    3. Create client secret
    4. Add app roles: admin, manager, user
    5. Assign users to roles

Usage:
    # In API router
    from api.entra_auth import (
        is_entra_enabled,
        get_login_url,
        handle_callback,
        EntraUser,
        create_session_token
    )

    @router.get("/auth/entra/login")
    async def entra_login():
        if not is_entra_enabled():
            return {"error": "Entra ID not enabled"}
        return RedirectResponse(get_login_url())

    @router.get("/auth/entra/callback")
    async def entra_callback(code: str, state: str):
        user = await handle_callback(code, state)
        token = create_session_token(user)
        return {"access_token": token, "user": user.username}
"""

import os
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# Try to import MSAL - graceful fallback if not available
try:
    import msal
    MSAL_AVAILABLE = True
except ImportError:
    msal = None  # type: ignore
    MSAL_AVAILABLE = False
    logger.warning("MSAL not installed. Entra ID authentication will not be available.")


# ============================================================================
# CONFIGURATION
# ============================================================================

def _get_entra_config() -> Dict[str, Any]:
    """
    Load Entra ID configuration from environment variables.

    Returns dict with all configuration values.
    """
    tenant_id = os.getenv("ENTRA_TENANT_ID", "")
    return {
        "client_id": os.getenv("ENTRA_CLIENT_ID", ""),
        "tenant_id": tenant_id,
        "client_secret": os.getenv("ENTRA_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv(
            "ENTRA_REDIRECT_URI",
            "http://localhost:8000/api/v1/auth/entra/callback"
        ),
        "enabled": os.getenv("ENTRA_ENABLED", "false").lower() == "true",
        "authority": f"https://login.microsoftonline.com/{tenant_id}" if tenant_id else "",
        "scopes": ["User.Read", "openid", "profile", "email"],
    }


def is_entra_enabled() -> bool:
    """
    Check if Entra ID authentication is enabled and properly configured.

    Returns True only if:
    - ENTRA_ENABLED is 'true'
    - ENTRA_CLIENT_ID is set
    - ENTRA_TENANT_ID is set
    - MSAL library is available
    """
    if not MSAL_AVAILABLE:
        return False

    config = _get_entra_config()
    return (
        config["enabled"] and
        bool(config["client_id"]) and
        bool(config["tenant_id"])
    )


def get_entra_status() -> Dict[str, Any]:
    """
    Get detailed status of Entra ID configuration.

    Useful for debugging and health checks.
    """
    config = _get_entra_config()
    return {
        "enabled": config["enabled"],
        "msal_available": MSAL_AVAILABLE,
        "client_id_configured": bool(config["client_id"]),
        "tenant_id_configured": bool(config["tenant_id"]),
        "client_secret_configured": bool(config["client_secret"]),
        "redirect_uri": config["redirect_uri"],
        "fully_configured": is_entra_enabled(),
    }


def _get_msal_app() -> "msal.ConfidentialClientApplication":
    """
    Create MSAL confidential client application.

    Raises HTTPException if not configured.
    """
    if not MSAL_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MSAL library not installed. Install with: pip install msal"
        )

    config = _get_entra_config()

    if not config["client_id"] or not config["tenant_id"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Entra ID authentication not configured. Set ENTRA_CLIENT_ID and ENTRA_TENANT_ID."
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
    """
    User data extracted from Entra ID token.

    Contains both Entra-specific data and mapped local system data.
    """
    # Entra ID data
    username: str  # UPN or email (e.g., user@company.com)
    display_name: str  # Full name
    email: str  # Email address
    entra_id: str  # Object ID in Entra (oid claim)
    tenant_id: str  # Tenant ID (tid claim)
    roles: List[str] = field(default_factory=list)  # App roles assigned
    groups: List[str] = field(default_factory=list)  # Group memberships

    # Mapped to local system
    local_role: str = "user"  # admin, manager, user
    company_id: Optional[int] = None  # Assigned after user sync

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role (either in Entra or mapped locally)."""
        return self.local_role == "admin" or "admin" in self.roles

    @property
    def is_manager(self) -> bool:
        """Check if user has manager role or higher."""
        return self.local_role in ("admin", "manager") or any(
            r in self.roles for r in ("admin", "manager")
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "username": self.username,
            "display_name": self.display_name,
            "email": self.email,
            "entra_id": self.entra_id,
            "tenant_id": self.tenant_id,
            "roles": self.roles,
            "local_role": self.local_role,
            "is_admin": self.is_admin,
            "auth_method": "entra_id"
        }


# ============================================================================
# AUTHENTICATION FLOW
# ============================================================================

# In-memory state storage for CSRF protection
# NOTE: In production with multiple instances, use Redis or database
_auth_states: Dict[str, Dict[str, Any]] = {}


def get_login_url(
    state: Optional[str] = None,
    redirect_after: Optional[str] = None
) -> str:
    """
    Generate Entra ID login URL for OAuth authorization code flow.

    Args:
        state: Optional state parameter for CSRF protection (generated if not provided)
        redirect_after: Optional URL to redirect to after successful login

    Returns:
        Authorization URL to redirect user to Microsoft login

    Raises:
        HTTPException: If Entra ID is not enabled/configured
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
        state = secrets.token_urlsafe(32)

    # Store state for validation in callback
    _auth_states[state] = {
        "redirect_after": redirect_after,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    # Clean old states (older than 10 minutes)
    _cleanup_old_states()

    # Build authorization URL
    auth_url = app.get_authorization_request_url(
        scopes=config["scopes"],
        state=state,
        redirect_uri=config["redirect_uri"],
    )

    logger.info(f"Generated Entra login URL for state: {state[:8]}...")
    return auth_url


def _cleanup_old_states() -> None:
    """Remove auth states older than 10 minutes."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    to_remove = []

    for state, data in _auth_states.items():
        try:
            created = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
            if created < cutoff:
                to_remove.append(state)
        except (KeyError, ValueError):
            to_remove.append(state)

    for state in to_remove:
        _auth_states.pop(state, None)


async def handle_callback(code: str, state: str) -> EntraUser:
    """
    Handle OAuth callback from Entra ID.

    Args:
        code: Authorization code from Entra
        state: State parameter for CSRF validation

    Returns:
        EntraUser with extracted user information

    Raises:
        HTTPException: If authentication fails or state is invalid
    """
    # Validate state (CSRF protection)
    if state not in _auth_states:
        logger.warning(f"Invalid state parameter received: {state[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter. Please try logging in again."
        )

    state_data = _auth_states.pop(state)
    config = _get_entra_config()
    app = _get_msal_app()

    try:
        # Exchange authorization code for tokens
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=config["scopes"],
            redirect_uri=config["redirect_uri"],
        )

        if "error" in result:
            error_desc = result.get("error_description", result["error"])
            logger.error(f"Entra token error: {error_desc}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {error_desc}"
            )

        # Extract user info from ID token claims
        id_token_claims = result.get("id_token_claims", {})

        user = EntraUser(
            username=id_token_claims.get(
                "preferred_username",
                id_token_claims.get("upn", "")
            ),
            display_name=id_token_claims.get("name", ""),
            email=id_token_claims.get(
                "email",
                id_token_claims.get("preferred_username", "")
            ),
            entra_id=id_token_claims.get("oid", ""),
            roles=id_token_claims.get("roles", []),
            groups=id_token_claims.get("groups", []),
            tenant_id=id_token_claims.get("tid", ""),
        )

        # Map Entra roles to local roles
        user.local_role = _map_entra_role_to_local(user.roles)

        # Optionally sync/create local user record
        await _sync_local_user(user)

        logger.info(
            f"Entra login successful: {user.username} "
            f"(role: {user.local_role}, entra_roles: {user.roles})"
        )
        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Entra callback error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication processing failed. Please try again."
        )


def _map_entra_role_to_local(entra_roles: List[str]) -> str:
    """
    Map Entra ID app roles to local application roles.

    Priority: admin > manager > user

    Args:
        entra_roles: List of role values from Entra token

    Returns:
        Local role string: 'admin', 'manager', or 'user'
    """
    # Normalize role names (Entra roles are case-sensitive)
    roles_lower = [r.lower() for r in entra_roles]

    if "admin" in roles_lower or "pricescout.admin" in roles_lower:
        return "admin"
    elif "manager" in roles_lower or "pricescout.manager" in roles_lower:
        return "manager"
    elif "user" in roles_lower or "pricescout.user" in roles_lower:
        return "user"
    else:
        # Default to user if no recognized role
        return "user"


async def _sync_local_user(entra_user: EntraUser) -> None:
    """
    Sync Entra user to local database (create or update).

    This enables:
    - Local user record for audit logging
    - Company association
    - Mode permissions
    - Consistent user management

    The user is created with a random password (never used for Entra users).
    """
    try:
        from app.users import get_user, create_user

        # Check if user exists by email/username
        local_user = get_user(entra_user.email) or get_user(entra_user.username)

        if local_user:
            # User exists - optionally update role if needed
            logger.debug(f"Existing local user found for Entra account: {entra_user.email}")
            # Could add role sync here if desired
        else:
            # Create local user record
            # Use random password - Entra users never use password auth
            temp_password = secrets.token_urlsafe(32)

            success, message = create_user(
                username=entra_user.email,
                password=temp_password,
                role=entra_user.local_role,
                company=None,  # Will be assigned by admin
            )

            if success:
                logger.info(f"Created local user for Entra account: {entra_user.email}")
            else:
                logger.warning(f"Could not create local user for {entra_user.email}: {message}")

    except ImportError:
        logger.warning("Could not import users module - skipping local user sync")
    except Exception as e:
        logger.warning(f"Error syncing local user: {e}")
        # Don't fail the login - user can still work via Entra


# ============================================================================
# JWT TOKEN GENERATION
# ============================================================================

def create_session_token(entra_user: EntraUser) -> str:
    """
    Create a local JWT session token after successful Entra authentication.

    This allows the app to use standard JWT validation for subsequent requests
    without needing to validate Entra tokens on every call.

    Args:
        entra_user: The authenticated Entra user

    Returns:
        JWT token string
    """
    try:
        from jose import jwt
        from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
    except ImportError as e:
        logger.error(f"Missing dependency for JWT: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error"
        )

    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": entra_user.username,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "role": entra_user.local_role,
        "auth_method": "entra_id",
        "entra_id": entra_user.entra_id,
        "display_name": entra_user.display_name,
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ============================================================================
# FASTAPI ROUTE HELPERS
# ============================================================================

def register_entra_routes(router) -> None:
    """
    Register Entra ID authentication routes on an existing router.

    Call this in api/routers/auth.py to add Entra endpoints:

        from api.entra_auth import register_entra_routes
        register_entra_routes(router)

    This adds:
        GET /entra/login   - Redirect to Microsoft login
        GET /entra/callback - Handle OAuth callback
        GET /entra/status  - Check Entra configuration
    """
    from fastapi import Query
    from fastapi.responses import RedirectResponse, JSONResponse

    @router.get("/entra/login", tags=["Authentication"])
    async def entra_login(
        redirect_after: Optional[str] = Query(
            None,
            description="URL to redirect after successful login"
        )
    ):
        """
        Initiate Entra ID SSO login.

        Redirects user to Microsoft login page. After authentication,
        user is redirected back to /entra/callback.
        """
        if not is_entra_enabled():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Entra ID authentication is not enabled",
                    "status": get_entra_status()
                }
            )

        login_url = get_login_url(redirect_after=redirect_after)
        return RedirectResponse(url=login_url)

    @router.get("/entra/callback", tags=["Authentication"])
    async def entra_callback(
        code: str = Query(..., description="Authorization code from Entra"),
        state: str = Query(..., description="State parameter for CSRF validation"),
        error: Optional[str] = Query(None, description="Error code if auth failed"),
        error_description: Optional[str] = Query(None, description="Error description"),
    ):
        """
        Handle OAuth callback from Entra ID.

        This endpoint is called by Microsoft after user authentication.
        Creates a local session and returns JWT token.
        """
        if error:
            logger.warning(f"Entra callback error: {error} - {error_description}")
            return JSONResponse(
                status_code=401,
                content={
                    "error": error,
                    "detail": error_description or "Authentication failed"
                }
            )

        # Handle the callback
        entra_user = await handle_callback(code, state)

        # Create local session token
        token = create_session_token(entra_user)

        # Check if we should redirect
        # Note: state_data was consumed in handle_callback, so we return JSON
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 1800,  # 30 minutes
            "user": entra_user.to_dict()
        }

    @router.get("/entra/status", tags=["Authentication"])
    async def entra_status():
        """
        Check Entra ID authentication status and configuration.

        Returns configuration status without exposing secrets.
        Useful for debugging and health checks.
        """
        return get_entra_status()


# ============================================================================
# TESTING UTILITIES
# ============================================================================

def create_test_entra_user(
    username: str = "test@company.com",
    role: str = "user"
) -> EntraUser:
    """
    Create a mock EntraUser for testing purposes.

    Args:
        username: Test username/email
        role: Role to assign (admin, manager, user)

    Returns:
        EntraUser instance for testing
    """
    return EntraUser(
        username=username,
        display_name="Test User",
        email=username,
        entra_id=f"test-oid-{secrets.token_hex(8)}",
        tenant_id="test-tenant-id",
        roles=[role],
        groups=[],
        local_role=role
    )


def mock_entra_callback(code: str = "test-code", role: str = "user") -> EntraUser:
    """
    Mock the Entra callback for testing without real Azure.

    Args:
        code: Mock authorization code
        role: Role for the test user

    Returns:
        EntraUser as if from real callback
    """
    return create_test_entra_user(
        username=f"testuser_{code[:8]}@company.com",
        role=role
    )
