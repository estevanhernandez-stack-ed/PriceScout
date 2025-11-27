"""
API Authentication Module for PriceScout API

This module provides API key authentication for the PriceScout REST API.
Supports multiple tiers with different rate limits and features.

Usage:
    from api.auth import verify_api_key, get_rate_limit
    
    @router.get("/endpoint", dependencies=[Depends(verify_api_key)])
    async def protected_endpoint(api_key_data: dict = Depends(verify_api_key)):
        # Access authenticated user data
        client_name = api_key_data["client"]
        tier = api_key_data["tier"]
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Security, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text
from app.db_models import Base
from app.db_session import get_session as get_db_session, get_engine
import logging

logger = logging.getLogger(__name__)

# Security header configuration
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Get engine for table creation
engine = get_engine()

# Tier configuration
TIER_LIMITS = {
    "free": {
        "requests_per_hour": 100,
        "requests_per_day": 1000,
        "features": ["basic_reports", "theaters", "films"]
    },
    "premium": {
        "requests_per_hour": 1000,
        "requests_per_day": 50000,
        "features": ["basic_reports", "theaters", "films", "showtimes", "pricing", "pdf_exports"]
    },
    "enterprise": {
        "requests_per_hour": None,  # Unlimited
        "requests_per_day": None,
        "features": ["all"]
    },
    "internal": {
        "requests_per_hour": None,  # Unlimited
        "requests_per_day": None,
        "features": ["all"]
    }
}


class APIKey(Base):
    """
    Database model for API keys
    """
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256 hash
    key_prefix = Column(String(12), nullable=False)  # First 8 chars for identification (ps_xxx_abcd)
    client_name = Column(String(255), nullable=False)
    tier = Column(String(50), nullable=False, default="free")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # None = never expires
    last_used_at = Column(DateTime, nullable=True)
    total_requests = Column(Integer, default=0, nullable=False)
    notes = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<APIKey {self.key_prefix}... ({self.client_name}, {self.tier})>"


class APIKeyUsage(Base):
    """
    Track API key usage for rate limiting and analytics
    """
    __tablename__ = "api_key_usage"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key_prefix = Column(String(12), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    
    def __repr__(self):
        return f"<APIKeyUsage {self.key_prefix} {self.method} {self.endpoint}>"


def generate_api_key(tier: str = "free") -> str:
    """
    Generate a new API key with tier prefix
    
    Format: ps_{tier}_{random_32_chars}
    Examples:
        - ps_free_abc123def456...
        - ps_prem_xyz789uvw012...
        - ps_entp_qrs345mno678...
        - ps_test_internal123...
    
    Args:
        tier: API key tier (free, premium, enterprise, internal)
        
    Returns:
        String API key (42 characters total)
    """
    tier_prefix = {
        "free": "free",
        "premium": "prem",
        "enterprise": "entp",
        "internal": "test"
    }.get(tier, "free")
    
    # Generate secure random token
    random_part = secrets.token_urlsafe(24)  # 32 chars base64
    
    return f"ps_{tier_prefix}_{random_part}"


def hash_api_key(api_key: str) -> str:
    """
    Create SHA-256 hash of API key for secure storage
    
    Args:
        api_key: Plain text API key
        
    Returns:
        Hexadecimal hash string (64 chars)
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_key_prefix(api_key: str) -> str:
    """
    Extract prefix from API key for identification
    
    Args:
        api_key: Plain text API key (e.g., ps_free_abc123...)
        
    Returns:
        First 12 characters (e.g., ps_free_abcd)
    """
    return api_key[:12] if len(api_key) >= 12 else api_key


async def verify_api_key(
    api_key: str = Security(API_KEY_HEADER)
) -> Dict[str, Any]:
    """
    Verify API key and return client information
    
    This dependency can be added to any endpoint to require authentication:
    
        @router.get("/endpoint", dependencies=[Depends(verify_api_key)])
        async def my_endpoint():
            ...
    
    Or to access the client data:
    
        @router.get("/endpoint")
        async def my_endpoint(api_key_data: dict = Depends(verify_api_key)):
            client_name = api_key_data["client"]
            tier = api_key_data["tier"]
    
    Args:
        api_key: API key from X-API-Key header
        
    Returns:
        Dictionary with client information:
        {
            "client": "Client Name",
            "tier": "premium",
            "key_prefix": "ps_prem_abcd",
            "features": ["all"],
            "rate_limits": {...}
        }
        
    Raises:
        HTTPException: 401 if key is missing, invalid, expired, or inactive
    """
    # Check if API key was provided
    if not api_key:
        logger.warning(f"API key missing from request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Include 'X-API-Key' header in your request.",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    # Validate key format
    if not api_key.startswith("ps_"):
        logger.warning(f"Invalid API key format: {api_key[:12]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format. Keys must start with 'ps_'."
        )
    
    # Hash the key for database lookup
    key_hash = hash_api_key(api_key)
    key_prefix = get_key_prefix(api_key)
    
    # Query database
    with get_db_session() as db:
        api_key_record = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()
        
        if not api_key_record:
            logger.warning(f"API key not found: {key_prefix}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key. Key not found in database."
            )
        
        # Check if key is active
        if not api_key_record.is_active:
            logger.warning(f"Inactive API key used: {key_prefix} ({api_key_record.client_name})")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has been deactivated. Contact support."
            )
        
        # Check if key has expired
        if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
            logger.warning(f"Expired API key used: {key_prefix} ({api_key_record.client_name})")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"API key expired on {api_key_record.expires_at.strftime('%Y-%m-%d')}. Contact support."
            )
        
        # Update last used timestamp and total requests
        api_key_record.last_used_at = datetime.utcnow()
        api_key_record.total_requests += 1
        db.commit()
        
        # Get tier configuration
        tier_config = TIER_LIMITS.get(api_key_record.tier, TIER_LIMITS["free"])
        
        logger.info(f"API key verified: {key_prefix} ({api_key_record.client_name}, {api_key_record.tier})")
        
        return {
            "client": api_key_record.client_name,
            "tier": api_key_record.tier,
            "key_prefix": key_prefix,
            "features": tier_config["features"],
            "rate_limits": {
                "requests_per_hour": tier_config["requests_per_hour"],
                "requests_per_day": tier_config["requests_per_day"]
            },
            "total_requests": api_key_record.total_requests,
            "created_at": api_key_record.created_at.isoformat(),
            "expires_at": api_key_record.expires_at.isoformat() if api_key_record.expires_at else None
        }


async def check_rate_limit(api_key_data: Dict[str, Any], request: Request) -> None:
    """
    Check if API key has exceeded rate limits
    
    This should be called after verify_api_key in endpoints that need rate limiting.
    
    Args:
        api_key_data: Client data from verify_api_key
        request: FastAPI request object
        
    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    tier = api_key_data["tier"]
    key_prefix = api_key_data["key_prefix"]
    
    # Get limits for this tier
    hourly_limit = TIER_LIMITS[tier]["requests_per_hour"]
    daily_limit = TIER_LIMITS[tier]["requests_per_day"]
    
    # Unlimited tiers skip rate limiting
    if hourly_limit is None:
        return
    
    # Query recent usage
    with get_db_session() as db:
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        # Count requests in last hour
        hourly_count = db.query(APIKeyUsage).filter(
            APIKeyUsage.key_prefix == key_prefix,
            APIKeyUsage.timestamp >= hour_ago
        ).count()
        
        # Count requests in last day
        daily_count = db.query(APIKeyUsage).filter(
            APIKeyUsage.key_prefix == key_prefix,
            APIKeyUsage.timestamp >= day_ago
        ).count()
        
        # Check hourly limit
        if hourly_limit and hourly_count >= hourly_limit:
            logger.warning(f"Hourly rate limit exceeded: {key_prefix} ({hourly_count}/{hourly_limit})")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Hourly rate limit exceeded ({hourly_count}/{hourly_limit}). Upgrade to premium for higher limits.",
                headers={
                    "X-RateLimit-Limit": str(hourly_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int((now + timedelta(hours=1)).timestamp()))
                }
            )
        
        # Check daily limit
        if daily_limit and daily_count >= daily_limit:
            logger.warning(f"Daily rate limit exceeded: {key_prefix} ({daily_count}/{daily_limit})")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Daily rate limit exceeded ({daily_count}/{daily_limit}). Upgrade to premium for higher limits.",
                headers={
                    "X-RateLimit-Limit": str(daily_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int((now + timedelta(days=1)).timestamp()))
                }
            )
        
        # Log this request for analytics
        usage = APIKeyUsage(
            key_prefix=key_prefix,
            endpoint=str(request.url.path),
            method=request.method
        )
        db.add(usage)
        db.commit()
        
        # Add rate limit headers to response (will be handled by middleware)
        request.state.rate_limit_headers = {
            "X-RateLimit-Limit": str(hourly_limit),
            "X-RateLimit-Remaining": str(hourly_limit - hourly_count),
            "X-RateLimit-Reset": str(int((now + timedelta(hours=1)).timestamp()))
        }


def optional_api_key(api_key: str = Security(API_KEY_HEADER)) -> Optional[Dict[str, Any]]:
    """
    Optional API key validation for endpoints that work with or without auth
    
    Returns None if no key provided, otherwise validates and returns client data.
    Useful for public endpoints that provide enhanced features to authenticated users.
    
    Args:
        api_key: API key from X-API-Key header (optional)
        
    Returns:
        Client data dict if authenticated, None if not
    """
    if not api_key:
        return None
    
    try:
        return verify_api_key(api_key)
    except HTTPException:
        return None
