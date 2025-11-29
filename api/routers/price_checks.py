"""
Price Checks API Router

Endpoints for querying pricing data per claude.md TheatreOperations platform standards.

Endpoints:
    GET    /api/v1/price-checks                      - Query price checks with filters
    GET    /api/v1/price-checks/latest/{location_id} - Get latest prices for a location
    GET    /api/v1/price-history/{location_id}       - Get price history for a location
"""

from datetime import datetime, date, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Security, Query
from pydantic import BaseModel, Field
from api.routers.auth import get_current_user
from app.users import User
from app.db_session import get_session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class PriceCheck(BaseModel):
    """Model for a single price check record."""
    price_id: int
    theater_name: str
    film_title: str
    showtime: str
    play_date: date
    ticket_type: str
    format: Optional[str] = None
    price: float
    scraped_at: datetime


class PriceCheckLatest(BaseModel):
    """Model for latest price by theater/format."""
    theater_name: str
    ticket_type: str
    format: Optional[str] = None
    price: float
    last_checked: datetime
    sample_film: Optional[str] = None


class PriceHistory(BaseModel):
    """Model for price history entry."""
    date: date
    ticket_type: str
    format: Optional[str] = None
    avg_price: float
    min_price: float
    max_price: float
    price_count: int


class PriceComparison(BaseModel):
    """Model for price comparison between theaters."""
    theater_name: str
    ticket_type: str
    avg_price: float
    price_count: int
    vs_market_avg: Optional[float] = None  # Percentage difference from market average


class PriceCheckSummary(BaseModel):
    """Summary response for price checks query."""
    total_records: int
    date_range: dict
    price_checks: List[PriceCheck]


# ============================================================================
# PRICE CHECKS ENDPOINTS
# ============================================================================

@router.get("/price-checks", response_model=PriceCheckSummary, tags=["Price Data"])
async def query_price_checks(
    theater_name: Optional[str] = Query(None, description="Filter by theater name (partial match)"),
    film_title: Optional[str] = Query(None, description="Filter by film title (partial match)"),
    ticket_type: Optional[str] = Query(None, description="Filter by ticket type"),
    format: Optional[str] = Query(None, description="Filter by format (IMAX, Dolby, etc.)"),
    date_from: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Security(get_current_user, scopes=["read:prices"])
):
    """
    Query price check records with flexible filtering.

    Returns paginated results matching the specified criteria.
    """
    try:
        with get_session() as session:
            # Build dynamic query
            conditions = ["p.company_id = :company_id"]
            params = {"company_id": current_user.company_id or 1, "limit": limit, "offset": offset}

            if theater_name:
                conditions.append("s.theater_name LIKE :theater_name")
                params["theater_name"] = f"%{theater_name}%"
            if film_title:
                conditions.append("s.film_title LIKE :film_title")
                params["film_title"] = f"%{film_title}%"
            if ticket_type:
                conditions.append("p.ticket_type = :ticket_type")
                params["ticket_type"] = ticket_type
            if format:
                conditions.append("s.format = :format")
                params["format"] = format
            if date_from:
                conditions.append("s.play_date >= :date_from")
                params["date_from"] = date_from
            if date_to:
                conditions.append("s.play_date <= :date_to")
                params["date_to"] = date_to
            if min_price is not None:
                conditions.append("p.price >= :min_price")
                params["min_price"] = min_price
            if max_price is not None:
                conditions.append("p.price <= :max_price")
                params["max_price"] = max_price

            where_clause = " AND ".join(conditions)

            # Get total count
            count_query = f"""
                SELECT COUNT(*)
                FROM prices p
                JOIN showings s ON p.showing_id = s.showing_id
                WHERE {where_clause}
            """
            total = session.execute(text(count_query), params).scalar() or 0

            # Get date range
            range_query = f"""
                SELECT MIN(s.play_date), MAX(s.play_date)
                FROM prices p
                JOIN showings s ON p.showing_id = s.showing_id
                WHERE {where_clause}
            """
            date_range_result = session.execute(text(range_query), params).fetchone()

            # Get paginated results
            data_query = f"""
                SELECT p.price_id, s.theater_name, s.film_title, s.showtime,
                       s.play_date, p.ticket_type, s.format, p.price, p.scraped_at
                FROM prices p
                JOIN showings s ON p.showing_id = s.showing_id
                WHERE {where_clause}
                ORDER BY s.play_date DESC, s.theater_name, s.showtime
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """

            result = session.execute(text(data_query), params)

            price_checks = []
            for row in result.fetchall():
                price_checks.append(PriceCheck(
                    price_id=row[0],
                    theater_name=row[1],
                    film_title=row[2],
                    showtime=row[3],
                    play_date=row[4],
                    ticket_type=row[5],
                    format=row[6],
                    price=float(row[7]),
                    scraped_at=row[8]
                ))

            return PriceCheckSummary(
                total_records=total,
                date_range={
                    "from": str(date_range_result[0]) if date_range_result[0] else None,
                    "to": str(date_range_result[1]) if date_range_result[1] else None
                },
                price_checks=price_checks
            )
    except Exception as e:
        logger.exception(f"Error querying price checks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/price-checks/latest/{theater_name}", response_model=List[PriceCheckLatest], tags=["Price Data"])
async def get_latest_prices(
    theater_name: str,
    current_user: User = Security(get_current_user, scopes=["read:prices"])
):
    """
    Get the latest prices for a specific theater.

    Returns the most recent price for each ticket type and format combination.
    """
    try:
        with get_session() as session:
            query = """
                WITH LatestPrices AS (
                    SELECT
                        s.theater_name,
                        p.ticket_type,
                        s.format,
                        p.price,
                        p.scraped_at,
                        s.film_title,
                        ROW_NUMBER() OVER (
                            PARTITION BY s.theater_name, p.ticket_type, ISNULL(s.format, 'Standard')
                            ORDER BY p.scraped_at DESC
                        ) as rn
                    FROM prices p
                    JOIN showings s ON p.showing_id = s.showing_id
                    WHERE p.company_id = :company_id
                      AND s.theater_name LIKE :theater_name
                )
                SELECT theater_name, ticket_type, format, price, scraped_at, film_title
                FROM LatestPrices
                WHERE rn = 1
                ORDER BY ticket_type, format
            """

            result = session.execute(
                text(query),
                {"company_id": current_user.company_id or 1, "theater_name": f"%{theater_name}%"}
            )

            latest = []
            for row in result.fetchall():
                latest.append(PriceCheckLatest(
                    theater_name=row[0],
                    ticket_type=row[1],
                    format=row[2],
                    price=float(row[3]),
                    last_checked=row[4],
                    sample_film=row[5]
                ))

            if not latest:
                raise HTTPException(status_code=404, detail=f"No prices found for theater: {theater_name}")

            return latest
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting latest prices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/price-history/{theater_name}", response_model=List[PriceHistory], tags=["Price Data"])
async def get_price_history(
    theater_name: str,
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    ticket_type: Optional[str] = Query(None, description="Filter by ticket type"),
    format: Optional[str] = Query(None, description="Filter by format"),
    current_user: User = Security(get_current_user, scopes=["read:prices"])
):
    """
    Get price history for a specific theater.

    Returns daily aggregated price statistics for the specified period.
    """
    try:
        with get_session() as session:
            conditions = [
                "p.company_id = :company_id",
                "s.theater_name LIKE :theater_name",
                "s.play_date >= :start_date"
            ]
            params = {
                "company_id": current_user.company_id or 1,
                "theater_name": f"%{theater_name}%",
                "start_date": date.today() - timedelta(days=days)
            }

            if ticket_type:
                conditions.append("p.ticket_type = :ticket_type")
                params["ticket_type"] = ticket_type
            if format:
                conditions.append("s.format = :format")
                params["format"] = format

            where_clause = " AND ".join(conditions)

            query = f"""
                SELECT
                    s.play_date,
                    p.ticket_type,
                    ISNULL(s.format, 'Standard') as format,
                    AVG(p.price) as avg_price,
                    MIN(p.price) as min_price,
                    MAX(p.price) as max_price,
                    COUNT(*) as price_count
                FROM prices p
                JOIN showings s ON p.showing_id = s.showing_id
                WHERE {where_clause}
                GROUP BY s.play_date, p.ticket_type, ISNULL(s.format, 'Standard')
                ORDER BY s.play_date DESC, p.ticket_type, format
            """

            result = session.execute(text(query), params)

            history = []
            for row in result.fetchall():
                history.append(PriceHistory(
                    date=row[0],
                    ticket_type=row[1],
                    format=row[2],
                    avg_price=round(float(row[3]), 2),
                    min_price=float(row[4]),
                    max_price=float(row[5]),
                    price_count=row[6]
                ))

            if not history:
                raise HTTPException(
                    status_code=404,
                    detail=f"No price history found for theater: {theater_name}"
                )

            return history
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting price history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/price-comparison", response_model=List[PriceComparison], tags=["Price Data"])
async def compare_prices(
    ticket_type: Optional[str] = Query(None, description="Filter by ticket type"),
    format: Optional[str] = Query(None, description="Filter by format"),
    days: int = Query(7, ge=1, le=30, description="Days to include in comparison"),
    current_user: User = Security(get_current_user, scopes=["read:prices"])
):
    """
    Compare prices across all theaters.

    Returns average prices per theater with market comparison.
    """
    try:
        with get_session() as session:
            conditions = [
                "p.company_id = :company_id",
                "s.play_date >= :start_date"
            ]
            params = {
                "company_id": current_user.company_id or 1,
                "start_date": date.today() - timedelta(days=days)
            }

            if ticket_type:
                conditions.append("p.ticket_type = :ticket_type")
                params["ticket_type"] = ticket_type
            if format:
                conditions.append("s.format = :format")
                params["format"] = format

            where_clause = " AND ".join(conditions)

            # Get per-theater averages and market average
            query = f"""
                WITH TheaterPrices AS (
                    SELECT
                        s.theater_name,
                        p.ticket_type,
                        AVG(p.price) as avg_price,
                        COUNT(*) as price_count
                    FROM prices p
                    JOIN showings s ON p.showing_id = s.showing_id
                    WHERE {where_clause}
                    GROUP BY s.theater_name, p.ticket_type
                ),
                MarketAvg AS (
                    SELECT
                        p.ticket_type,
                        AVG(p.price) as market_avg
                    FROM prices p
                    JOIN showings s ON p.showing_id = s.showing_id
                    WHERE {where_clause}
                    GROUP BY p.ticket_type
                )
                SELECT
                    tp.theater_name,
                    tp.ticket_type,
                    tp.avg_price,
                    tp.price_count,
                    ROUND(((tp.avg_price - ma.market_avg) / ma.market_avg) * 100, 2) as vs_market
                FROM TheaterPrices tp
                JOIN MarketAvg ma ON tp.ticket_type = ma.ticket_type
                ORDER BY tp.theater_name, tp.ticket_type
            """

            result = session.execute(text(query), params)

            comparisons = []
            for row in result.fetchall():
                comparisons.append(PriceComparison(
                    theater_name=row[0],
                    ticket_type=row[1],
                    avg_price=round(float(row[2]), 2),
                    price_count=row[3],
                    vs_market_avg=float(row[4]) if row[4] else None
                ))

            return comparisons
    except Exception as e:
        logger.exception(f"Error comparing prices: {e}")
        raise HTTPException(status_code=500, detail=str(e))
