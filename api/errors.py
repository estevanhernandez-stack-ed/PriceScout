"""
RFC 7807 Problem Details Implementation for PriceScout API

This module provides standardized error responses following RFC 7807
(Problem Details for HTTP APIs).

Usage:
    from api.errors import problem_response, ProblemType, validation_error

    # Generic problem response
    return problem_response(
        problem_type=ProblemType.VALIDATION_ERROR,
        title="Validation Error",
        status=400,
        detail="Invalid date format",
        instance=request.url.path,
        errors={"date": ["Must be YYYY-MM-DD format"]}
    )

    # Convenience functions
    return validation_error("Invalid input", {"field": ["Error message"]})
    return not_found_error("Theater not found")
    return unauthorized_error()

RFC 7807 Format:
{
    "type": "https://api.pricescout.io/errors/validation",
    "title": "Validation Error",
    "status": 400,
    "detail": "One or more validation errors occurred.",
    "instance": "/api/v1/theaters/123",
    "timestamp": "2025-11-28T12:00:00Z",
    "errors": {"field": ["error message"]}
}
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from fastapi import Request
from fastapi.responses import JSONResponse


class ProblemType(str, Enum):
    """
    Standard problem type URIs for PriceScout API.

    Each type corresponds to a specific error category with its own
    documentation page (to be implemented).
    """
    # Client Errors (4xx)
    VALIDATION_ERROR = "https://api.pricescout.io/errors/validation"
    NOT_FOUND = "https://api.pricescout.io/errors/not-found"
    UNAUTHORIZED = "https://api.pricescout.io/errors/unauthorized"
    FORBIDDEN = "https://api.pricescout.io/errors/forbidden"
    RATE_LIMITED = "https://api.pricescout.io/errors/rate-limited"
    CONFLICT = "https://api.pricescout.io/errors/conflict"
    BAD_REQUEST = "https://api.pricescout.io/errors/bad-request"

    # Server Errors (5xx)
    INTERNAL_ERROR = "https://api.pricescout.io/errors/internal"
    SERVICE_UNAVAILABLE = "https://api.pricescout.io/errors/service-unavailable"

    # Domain-Specific Errors
    PDF_GENERATION_FAILED = "https://api.pricescout.io/errors/pdf-generation-failed"
    SCRAPE_FAILED = "https://api.pricescout.io/errors/scrape-failed"
    DATABASE_ERROR = "https://api.pricescout.io/errors/database"
    AUTHENTICATION_FAILED = "https://api.pricescout.io/errors/authentication-failed"
    TOKEN_EXPIRED = "https://api.pricescout.io/errors/token-expired"
    API_KEY_INVALID = "https://api.pricescout.io/errors/api-key-invalid"
    API_KEY_EXPIRED = "https://api.pricescout.io/errors/api-key-expired"


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
        title: Short human-readable summary (should not change between occurrences)
        status: HTTP status code
        detail: Human-readable explanation specific to this occurrence
        instance: URI reference identifying the specific occurrence (usually request path)
        errors: Optional field-level errors (for validation)
        **extra_fields: Additional problem-specific fields

    Returns:
        JSONResponse with application/problem+json Content-Type

    Example:
        return problem_response(
            problem_type=ProblemType.VALIDATION_ERROR,
            title="Validation Error",
            status=400,
            detail="The 'date' field must be in YYYY-MM-DD format",
            instance="/api/v1/reports/selection-analysis",
            errors={"date": ["Invalid format. Expected YYYY-MM-DD."]}
        )
    """
    content = {
        "type": problem_type.value,
        "title": title,
        "status": status,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if instance:
        content["instance"] = instance

    if errors:
        content["errors"] = errors

    # Add any extra fields (e.g., retry_after, request_id)
    content.update(extra_fields)

    return JSONResponse(
        status_code=status,
        content=content,
        headers={"Content-Type": "application/problem+json"}
    )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def validation_error(
    detail: str,
    errors: Dict[str, list],
    instance: Optional[str] = None
) -> JSONResponse:
    """
    Create a validation error response (400 Bad Request).

    Args:
        detail: Description of what validation failed
        errors: Dict mapping field names to lists of error messages
        instance: Request path

    Example:
        return validation_error(
            "One or more fields failed validation",
            {"email": ["Invalid email format"], "date": ["Required field"]}
        )
    """
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
    instance: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None
) -> JSONResponse:
    """
    Create a not found error response (404 Not Found).

    Args:
        detail: Description of what was not found
        instance: Request path
        resource_type: Optional type of resource (e.g., "theater", "film")
        resource_id: Optional ID of resource that was not found
    """
    extra = {}
    if resource_type:
        extra["resource_type"] = resource_type
    if resource_id:
        extra["resource_id"] = resource_id

    return problem_response(
        problem_type=ProblemType.NOT_FOUND,
        title="Resource Not Found",
        status=404,
        detail=detail,
        instance=instance,
        **extra
    )


def unauthorized_error(
    detail: str = "Authentication required",
    instance: Optional[str] = None,
    auth_scheme: str = "Bearer"
) -> JSONResponse:
    """
    Create an unauthorized error response (401 Unauthorized).

    Args:
        detail: Description of why authentication failed
        instance: Request path
        auth_scheme: Authentication scheme (Bearer, ApiKey, etc.)
    """
    response = problem_response(
        problem_type=ProblemType.UNAUTHORIZED,
        title="Unauthorized",
        status=401,
        detail=detail,
        instance=instance
    )
    # Add WWW-Authenticate header per HTTP spec
    response.headers["WWW-Authenticate"] = auth_scheme
    return response


def forbidden_error(
    detail: str = "Access denied",
    instance: Optional[str] = None,
    required_role: Optional[str] = None,
    required_permission: Optional[str] = None
) -> JSONResponse:
    """
    Create a forbidden error response (403 Forbidden).

    Args:
        detail: Description of why access is denied
        instance: Request path
        required_role: Role required for this action
        required_permission: Permission required for this action
    """
    extra = {}
    if required_role:
        extra["required_role"] = required_role
    if required_permission:
        extra["required_permission"] = required_permission

    return problem_response(
        problem_type=ProblemType.FORBIDDEN,
        title="Forbidden",
        status=403,
        detail=detail,
        instance=instance,
        **extra
    )


def rate_limit_error(
    detail: str,
    retry_after: int,
    instance: Optional[str] = None,
    limit: Optional[int] = None,
    remaining: int = 0
) -> JSONResponse:
    """
    Create a rate limit error response (429 Too Many Requests).

    Args:
        detail: Description of rate limit
        retry_after: Seconds until the rate limit resets
        instance: Request path
        limit: The rate limit value
        remaining: Remaining requests in the window
    """
    extra = {
        "retry_after": retry_after,
        "remaining": remaining
    }
    if limit:
        extra["limit"] = limit

    response = problem_response(
        problem_type=ProblemType.RATE_LIMITED,
        title="Rate Limit Exceeded",
        status=429,
        detail=detail,
        instance=instance,
        **extra
    )
    response.headers["Retry-After"] = str(retry_after)
    return response


def conflict_error(
    detail: str,
    instance: Optional[str] = None,
    conflicting_resource: Optional[str] = None
) -> JSONResponse:
    """
    Create a conflict error response (409 Conflict).

    Args:
        detail: Description of the conflict
        instance: Request path
        conflicting_resource: Identifier of the conflicting resource
    """
    extra = {}
    if conflicting_resource:
        extra["conflicting_resource"] = conflicting_resource

    return problem_response(
        problem_type=ProblemType.CONFLICT,
        title="Conflict",
        status=409,
        detail=detail,
        instance=instance,
        **extra
    )


def internal_error(
    detail: str = "An unexpected error occurred",
    instance: Optional[str] = None,
    request_id: Optional[str] = None
) -> JSONResponse:
    """
    Create an internal server error response (500 Internal Server Error).

    Args:
        detail: Description of the error (avoid exposing sensitive info)
        instance: Request path
        request_id: Optional request ID for support/debugging
    """
    extra = {}
    if request_id:
        extra["request_id"] = request_id

    return problem_response(
        problem_type=ProblemType.INTERNAL_ERROR,
        title="Internal Server Error",
        status=500,
        detail=detail,
        instance=instance,
        **extra
    )


def service_unavailable_error(
    detail: str,
    instance: Optional[str] = None,
    retry_after: Optional[int] = None
) -> JSONResponse:
    """
    Create a service unavailable error response (503 Service Unavailable).

    Args:
        detail: Description of why service is unavailable
        instance: Request path
        retry_after: Optional seconds until service is expected to be available
    """
    extra = {}
    if retry_after:
        extra["retry_after"] = retry_after

    response = problem_response(
        problem_type=ProblemType.SERVICE_UNAVAILABLE,
        title="Service Unavailable",
        status=503,
        detail=detail,
        instance=instance,
        **extra
    )

    if retry_after:
        response.headers["Retry-After"] = str(retry_after)

    return response


# ============================================================================
# DOMAIN-SPECIFIC ERROR HELPERS
# ============================================================================

def pdf_generation_error(
    detail: str = "PDF generation failed",
    instance: Optional[str] = None
) -> JSONResponse:
    """Create error response for PDF generation failures."""
    return problem_response(
        problem_type=ProblemType.PDF_GENERATION_FAILED,
        title="PDF Generation Failed",
        status=503,
        detail=detail,
        instance=instance,
        suggestion="Ensure Playwright browsers are installed: 'playwright install chromium'"
    )


def scrape_error(
    detail: str,
    instance: Optional[str] = None,
    theater: Optional[str] = None,
    source: Optional[str] = None
) -> JSONResponse:
    """Create error response for scraping failures."""
    extra = {}
    if theater:
        extra["theater"] = theater
    if source:
        extra["source"] = source

    return problem_response(
        problem_type=ProblemType.SCRAPE_FAILED,
        title="Scrape Failed",
        status=503,
        detail=detail,
        instance=instance,
        **extra
    )


def database_error(
    detail: str = "Database operation failed",
    instance: Optional[str] = None
) -> JSONResponse:
    """Create error response for database failures."""
    return problem_response(
        problem_type=ProblemType.DATABASE_ERROR,
        title="Database Error",
        status=503,
        detail=detail,
        instance=instance
    )


def api_key_error(
    detail: str,
    instance: Optional[str] = None,
    expired: bool = False
) -> JSONResponse:
    """Create error response for API key issues."""
    problem_type = ProblemType.API_KEY_EXPIRED if expired else ProblemType.API_KEY_INVALID
    title = "API Key Expired" if expired else "Invalid API Key"

    return problem_response(
        problem_type=problem_type,
        title=title,
        status=401,
        detail=detail,
        instance=instance
    )


def token_expired_error(
    detail: str = "Authentication token has expired",
    instance: Optional[str] = None
) -> JSONResponse:
    """Create error response for expired JWT tokens."""
    return problem_response(
        problem_type=ProblemType.TOKEN_EXPIRED,
        title="Token Expired",
        status=401,
        detail=detail,
        instance=instance
    )


# ============================================================================
# EXCEPTION HANDLER UTILITIES
# ============================================================================

def handle_exception(
    request: Request,
    exc: Exception,
    include_traceback: bool = False
) -> JSONResponse:
    """
    Convert an exception to an RFC 7807 problem response.

    Args:
        request: FastAPI request object
        exc: The exception that was raised
        include_traceback: Whether to include traceback (only for development)

    Returns:
        JSONResponse with problem details
    """
    import traceback
    import logging

    logger = logging.getLogger(__name__)
    logger.exception(f"Unhandled exception: {exc}")

    extra = {}
    if include_traceback:
        extra["traceback"] = traceback.format_exc()

    return problem_response(
        problem_type=ProblemType.INTERNAL_ERROR,
        title="Internal Server Error",
        status=500,
        detail="An unexpected error occurred. Please try again or contact support.",
        instance=str(request.url.path),
        **extra
    )
