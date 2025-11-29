"""
Price Alerts API Router

Endpoints for managing price alerts per claude.md TheatreOperations platform standards.

Endpoints:
    GET    /api/v1/price-alerts              - List price alerts
    GET    /api/v1/price-alerts/{id}         - Get specific alert
    PUT    /api/v1/price-alerts/{id}/acknowledge - Acknowledge an alert
    GET    /api/v1/price-alerts/summary      - Get alert summary statistics
"""

from datetime import datetime, date, timezone
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

class PriceAlert(BaseModel):
    """Model for a price alert."""
    alert_id: int
    theater_name: str
    film_title: Optional[str] = None
    ticket_type: Optional[str] = None
    format: Optional[str] = None
    alert_type: str  # price_increase, price_decrease, new_offering, discontinued
    old_price: Optional[float] = None
    new_price: Optional[float] = None
    price_change_percent: Optional[float] = None
    triggered_at: datetime
    play_date: Optional[date] = None
    is_acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    acknowledgment_notes: Optional[str] = None


class AcknowledgeRequest(BaseModel):
    """Request model for acknowledging an alert."""
    notes: Optional[str] = Field(None, max_length=1000, description="Optional notes")


class AcknowledgeResponse(BaseModel):
    """Response model for acknowledgment."""
    alert_id: int
    acknowledged: bool = True
    acknowledged_at: datetime
    acknowledged_by: str


class AlertSummary(BaseModel):
    """Summary statistics for alerts."""
    total_pending: int
    total_acknowledged: int
    by_type: dict  # {alert_type: count}
    by_theater: dict  # {theater_name: count}
    oldest_pending: Optional[datetime] = None
    newest_pending: Optional[datetime] = None


class AlertListResponse(BaseModel):
    """Response model for alert list."""
    total: int
    pending: int
    alerts: List[PriceAlert]


# ============================================================================
# PRICE ALERTS ENDPOINTS
# ============================================================================

@router.get("/price-alerts", response_model=AlertListResponse, tags=["Price Alerts"])
async def list_price_alerts(
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledgment status"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    theater_name: Optional[str] = Query(None, description="Filter by theater (partial match)"),
    days: int = Query(30, ge=1, le=365, description="Days of history to include"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Security(get_current_user, scopes=["read:alerts"])
):
    """
    List price alerts with optional filtering.

    Returns alerts ordered by triggered_at descending (most recent first).
    """
    try:
        with get_session() as session:
            conditions = [
                "pa.company_id = :company_id",
                "pa.triggered_at >= DATEADD(day, -:days, GETUTCDATE())"
            ]
            params = {
                "company_id": current_user.company_id or 1,
                "days": days,
                "limit": limit,
                "offset": offset
            }

            if acknowledged is not None:
                conditions.append("pa.is_acknowledged = :acknowledged")
                params["acknowledged"] = acknowledged
            if alert_type:
                conditions.append("pa.alert_type = :alert_type")
                params["alert_type"] = alert_type
            if theater_name:
                conditions.append("pa.theater_name LIKE :theater_name")
                params["theater_name"] = f"%{theater_name}%"

            where_clause = " AND ".join(conditions)

            # Get counts
            count_query = f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_acknowledged = 0 THEN 1 ELSE 0 END) as pending
                FROM price_alerts pa
                WHERE {where_clause}
            """
            counts = session.execute(text(count_query), params).fetchone()

            # Get alerts with user info
            data_query = f"""
                SELECT
                    pa.alert_id, pa.theater_name, pa.film_title, pa.ticket_type,
                    pa.format, pa.alert_type, pa.old_price, pa.new_price,
                    pa.price_change_percent, pa.triggered_at, pa.play_date,
                    pa.is_acknowledged, u.username as acknowledged_by,
                    pa.acknowledged_at, pa.acknowledgment_notes
                FROM price_alerts pa
                LEFT JOIN users u ON pa.acknowledged_by = u.user_id
                WHERE {where_clause}
                ORDER BY pa.triggered_at DESC
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """

            result = session.execute(text(data_query), params)

            alerts = []
            for row in result.fetchall():
                alerts.append(PriceAlert(
                    alert_id=row[0],
                    theater_name=row[1],
                    film_title=row[2],
                    ticket_type=row[3],
                    format=row[4],
                    alert_type=row[5],
                    old_price=float(row[6]) if row[6] else None,
                    new_price=float(row[7]) if row[7] else None,
                    price_change_percent=float(row[8]) if row[8] else None,
                    triggered_at=row[9],
                    play_date=row[10],
                    is_acknowledged=bool(row[11]),
                    acknowledged_by=row[12],
                    acknowledged_at=row[13],
                    acknowledgment_notes=row[14]
                ))

            return AlertListResponse(
                total=counts[0] or 0,
                pending=counts[1] or 0,
                alerts=alerts
            )
    except Exception as e:
        logger.exception(f"Error listing price alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/price-alerts/summary", response_model=AlertSummary, tags=["Price Alerts"])
async def get_alert_summary(
    days: int = Query(30, ge=1, le=365, description="Days to include"),
    current_user: User = Security(get_current_user, scopes=["read:alerts"])
):
    """
    Get summary statistics for price alerts.

    Returns counts by type, by theater, and date range info.
    """
    try:
        with get_session() as session:
            params = {"company_id": current_user.company_id or 1, "days": days}

            # Get totals
            totals_query = """
                SELECT
                    SUM(CASE WHEN is_acknowledged = 0 THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN is_acknowledged = 1 THEN 1 ELSE 0 END) as acknowledged,
                    MIN(CASE WHEN is_acknowledged = 0 THEN triggered_at END) as oldest,
                    MAX(CASE WHEN is_acknowledged = 0 THEN triggered_at END) as newest
                FROM price_alerts
                WHERE company_id = :company_id
                  AND triggered_at >= DATEADD(day, -:days, GETUTCDATE())
            """
            totals = session.execute(text(totals_query), params).fetchone()

            # Get by type
            type_query = """
                SELECT alert_type, COUNT(*) as cnt
                FROM price_alerts
                WHERE company_id = :company_id
                  AND triggered_at >= DATEADD(day, -:days, GETUTCDATE())
                  AND is_acknowledged = 0
                GROUP BY alert_type
            """
            by_type = {}
            for row in session.execute(text(type_query), params).fetchall():
                by_type[row[0]] = row[1]

            # Get by theater (top 10)
            theater_query = """
                SELECT TOP 10 theater_name, COUNT(*) as cnt
                FROM price_alerts
                WHERE company_id = :company_id
                  AND triggered_at >= DATEADD(day, -:days, GETUTCDATE())
                  AND is_acknowledged = 0
                GROUP BY theater_name
                ORDER BY cnt DESC
            """
            by_theater = {}
            for row in session.execute(text(theater_query), params).fetchall():
                by_theater[row[0]] = row[1]

            return AlertSummary(
                total_pending=totals[0] or 0,
                total_acknowledged=totals[1] or 0,
                by_type=by_type,
                by_theater=by_theater,
                oldest_pending=totals[2],
                newest_pending=totals[3]
            )
    except Exception as e:
        logger.exception(f"Error getting alert summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/price-alerts/{alert_id}", response_model=PriceAlert, tags=["Price Alerts"])
async def get_price_alert(
    alert_id: int,
    current_user: User = Security(get_current_user, scopes=["read:alerts"])
):
    """
    Get a specific price alert by ID.
    """
    try:
        with get_session() as session:
            result = session.execute(
                text("""
                    SELECT
                        pa.alert_id, pa.theater_name, pa.film_title, pa.ticket_type,
                        pa.format, pa.alert_type, pa.old_price, pa.new_price,
                        pa.price_change_percent, pa.triggered_at, pa.play_date,
                        pa.is_acknowledged, u.username as acknowledged_by,
                        pa.acknowledged_at, pa.acknowledgment_notes
                    FROM price_alerts pa
                    LEFT JOIN users u ON pa.acknowledged_by = u.user_id
                    WHERE pa.alert_id = :alert_id AND pa.company_id = :company_id
                """),
                {"alert_id": alert_id, "company_id": current_user.company_id or 1}
            )
            row = result.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

            return PriceAlert(
                alert_id=row[0],
                theater_name=row[1],
                film_title=row[2],
                ticket_type=row[3],
                format=row[4],
                alert_type=row[5],
                old_price=float(row[6]) if row[6] else None,
                new_price=float(row[7]) if row[7] else None,
                price_change_percent=float(row[8]) if row[8] else None,
                triggered_at=row[9],
                play_date=row[10],
                is_acknowledged=bool(row[11]),
                acknowledged_by=row[12],
                acknowledged_at=row[13],
                acknowledgment_notes=row[14]
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting price alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/price-alerts/{alert_id}/acknowledge", response_model=AcknowledgeResponse, tags=["Price Alerts"])
async def acknowledge_alert(
    alert_id: int,
    request: AcknowledgeRequest = None,
    current_user: User = Security(get_current_user, scopes=["write:alerts"])
):
    """
    Acknowledge a price alert.

    Marks the alert as acknowledged and records who acknowledged it.
    """
    try:
        with get_session() as session:
            # Check alert exists
            check = session.execute(
                text("""
                    SELECT is_acknowledged
                    FROM price_alerts
                    WHERE alert_id = :alert_id AND company_id = :company_id
                """),
                {"alert_id": alert_id, "company_id": current_user.company_id or 1}
            ).fetchone()

            if not check:
                raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

            if check[0]:
                raise HTTPException(status_code=400, detail="Alert already acknowledged")

            # Update alert
            now = datetime.now(timezone.utc)
            session.execute(
                text("""
                    UPDATE price_alerts
                    SET is_acknowledged = 1,
                        acknowledged_by = :user_id,
                        acknowledged_at = :now,
                        acknowledgment_notes = :notes
                    WHERE alert_id = :alert_id AND company_id = :company_id
                """),
                {
                    "alert_id": alert_id,
                    "company_id": current_user.company_id or 1,
                    "user_id": current_user.user_id,
                    "now": now,
                    "notes": request.notes if request else None
                }
            )
            session.commit()

            logger.info(f"Alert {alert_id} acknowledged by user {current_user.username}")

            return AcknowledgeResponse(
                alert_id=alert_id,
                acknowledged=True,
                acknowledged_at=now,
                acknowledged_by=current_user.username
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error acknowledging alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/price-alerts/acknowledge-bulk", tags=["Price Alerts"])
async def acknowledge_alerts_bulk(
    alert_ids: List[int],
    notes: Optional[str] = None,
    current_user: User = Security(get_current_user, scopes=["write:alerts"])
):
    """
    Acknowledge multiple alerts at once.

    Returns count of alerts acknowledged.
    """
    try:
        if not alert_ids:
            raise HTTPException(status_code=400, detail="No alert IDs provided")

        with get_session() as session:
            now = datetime.now(timezone.utc)

            # Build IN clause (safe since alert_ids are integers)
            id_list = ",".join(str(int(id)) for id in alert_ids)

            result = session.execute(
                text(f"""
                    UPDATE price_alerts
                    SET is_acknowledged = 1,
                        acknowledged_by = :user_id,
                        acknowledged_at = :now,
                        acknowledgment_notes = :notes
                    WHERE alert_id IN ({id_list})
                      AND company_id = :company_id
                      AND is_acknowledged = 0
                """),
                {
                    "company_id": current_user.company_id or 1,
                    "user_id": current_user.user_id,
                    "now": now,
                    "notes": notes
                }
            )

            count = result.rowcount
            session.commit()

            logger.info(f"{count} alerts acknowledged by user {current_user.username}")

            return {
                "acknowledged_count": count,
                "requested_count": len(alert_ids),
                "acknowledged_at": now.isoformat(),
                "acknowledged_by": current_user.username
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error bulk acknowledging alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
