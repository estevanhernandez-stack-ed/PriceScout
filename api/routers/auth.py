"""
Authentication Router for PriceScout API

Provides:
- OAuth2 Password flow (username/password → JWT token)
- Entra ID SSO endpoints (enterprise authentication)
- Token validation and user lookup

Usage:
    # Get token
    POST /api/v1/auth/token
    Content-Type: application/x-www-form-urlencoded
    username=user&password=pass

    # Use token
    GET /api/v1/some-endpoint
    Authorization: Bearer <token>

    # Entra ID login (if enabled)
    GET /api/v1/auth/entra/login
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel

from app import users
from app.config import OAUTH2_SCHEME, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

# Import RFC 7807 error helpers
from api.errors import (
    unauthorized_error,
    validation_error,
    internal_error,
    ProblemType
)

router = APIRouter()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    auth_method: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str


class User(BaseModel):
    username: str
    is_admin: bool
    company: Optional[str] = None
    default_company: Optional[str] = None
    role: str


# ============================================================================
# TOKEN FUNCTIONS
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data (must include 'sub' for username)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "auth_method": data.get("auth_method", "password")
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(OAUTH2_SCHEME)) -> dict:
    """
    Validate JWT token and return user data.

    This is a FastAPI dependency that extracts and validates the JWT token
    from the Authorization header.

    Args:
        token: JWT token from Authorization header

    Returns:
        User dict with username, role, company_id, etc.

    Raises:
        HTTPException 401 if token is invalid or user not found
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token_data = TokenData(
            username=username,
            role=payload.get("role"),
            auth_method=payload.get("auth_method")
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = users.get_user(username=token_data.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Add auth_method to user dict
    user["auth_method"] = token_data.auth_method
    return user


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post("/token", response_model=Token, tags=["Authentication"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 Password Grant - Exchange credentials for access token.

    This is the standard OAuth2 password flow. Send username and password
    as form data to receive a JWT access token.

    **Request:**
    ```
    POST /api/v1/auth/token
    Content-Type: application/x-www-form-urlencoded

    username=your_username&password=your_password
    ```

    **Response:**
    ```json
    {
        "access_token": "eyJ...",
        "token_type": "bearer"
    }
    ```
    """
    user = users.verify_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "role": user["role"],
            "auth_method": "password"
        },
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", tags=["Authentication"])
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Logout current user.

    Clears the user's session token on the server side.
    The client should also discard the access token.
    """
    try:
        users.clear_session_token(current_user['username'])
        return {"message": "Logout successful"}
    except Exception as e:
        # Don't fail logout even if session clear fails
        return {"message": "Logout successful", "note": "Session may persist"}


@router.get("/me", tags=["Authentication"])
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get information about the currently authenticated user.

    Returns user profile data including role, company, and permissions.
    """
    return {
        "username": current_user.get("username"),
        "role": current_user.get("role"),
        "is_admin": current_user.get("is_admin", False),
        "company": current_user.get("company"),
        "company_id": current_user.get("company_id"),
        "auth_method": current_user.get("auth_method", "password"),
        "allowed_modes": current_user.get("allowed_modes", [])
    }


@router.post("/refresh", response_model=Token, tags=["Authentication"])
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """
    Refresh access token.

    Exchange a valid (but possibly near-expiry) token for a fresh one.
    The old token remains valid until its original expiry.
    """
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": current_user["username"],
            "role": current_user.get("role", "user"),
            "auth_method": current_user.get("auth_method", "password")
        },
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


# ============================================================================
# ENTRA ID SSO ENDPOINTS
# ============================================================================

# Register Entra ID routes if available
try:
    from api.entra_auth import register_entra_routes, is_entra_enabled
    register_entra_routes(router)
except ImportError:
    # Entra auth module not available
    pass


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health", tags=["Authentication"])
async def auth_health():
    """
    Authentication service health check.

    Returns status of authentication services including Entra ID availability.
    """
    entra_status = {"enabled": False, "available": False}

    try:
        from api.entra_auth import is_entra_enabled, get_entra_status
        entra_status = get_entra_status()
    except ImportError:
        pass

    return {
        "status": "healthy",
        "jwt_configured": bool(SECRET_KEY),
        "token_expiry_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
        "entra_id": entra_status
    }
