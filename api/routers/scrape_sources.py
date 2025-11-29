"""
Scrape Sources API Router

Endpoints for managing configurable scrape sources (Fandango, AMC, etc.)
per claude.md TheatreOperations platform standards.

Endpoints:
    GET    /api/v1/scrape-sources           - List all scrape sources
    POST   /api/v1/scrape-sources           - Create new scrape source
    GET    /api/v1/scrape-sources/{id}      - Get specific source
    PUT    /api/v1/scrape-sources/{id}      - Update source
    DELETE /api/v1/scrape-sources/{id}      - Delete source
    POST   /api/v1/scrape-jobs/trigger/{id} - Trigger scrape for source
    GET    /api/v1/scrape-jobs/{id}/status  - Get job status
"""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Security, Query
from pydantic import BaseModel, Field
from api.routers.auth import get_current_user
from api.errors import not_found_error, validation_error
from app.users import User
from app.db_session import get_session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ScrapeSourceBase(BaseModel):
    """Base model for scrape source data."""
    name: str = Field(..., min_length=1, max_length=100, description="Source name")
    source_type: str = Field(default="web", description="Type: web, api, file")
    base_url: Optional[str] = Field(None, max_length=500, description="Base URL for scraping")
    scrape_frequency_minutes: int = Field(default=60, ge=5, le=10080, description="Frequency in minutes")
    is_active: bool = Field(default=True, description="Whether source is active")
    configuration: Optional[dict] = Field(default={}, description="JSON configuration")


class ScrapeSourceCreate(ScrapeSourceBase):
    """Model for creating a new scrape source."""
    pass


class ScrapeSourceUpdate(BaseModel):
    """Model for updating a scrape source."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    source_type: Optional[str] = None
    base_url: Optional[str] = None
    scrape_frequency_minutes: Optional[int] = Field(None, ge=5, le=10080)
    is_active: Optional[bool] = None
    configuration: Optional[dict] = None


class ScrapeSourceResponse(ScrapeSourceBase):
    """Response model for scrape source."""
    source_id: int
    company_id: int
    last_scrape_at: Optional[datetime] = None
    last_scrape_status: Optional[str] = None
    last_scrape_records: int = 0
    created_at: datetime
    updated_at: datetime


class ScrapeJobStatus(BaseModel):
    """Response model for scrape job status."""
    run_id: int
    source_id: Optional[int] = None
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    records_scraped: int = 0
    error_message: Optional[str] = None


class TriggerResponse(BaseModel):
    """Response model for trigger request."""
    message: str
    run_id: int
    source_id: int
    source_name: str


# ============================================================================
# SCRAPE SOURCES ENDPOINTS
# ============================================================================

@router.get("/scrape-sources", response_model=List[ScrapeSourceResponse], tags=["Scrape Sources"])
async def list_scrape_sources(
    active_only: bool = Query(False, description="Filter to active sources only"),
    current_user: User = Security(get_current_user, scopes=["read:scrapes"])
):
    """
    List all configured scrape sources.

    Returns a list of all scrape sources for the user's company,
    optionally filtered to only active sources.
    """
    try:
        with get_session() as session:
            query = """
                SELECT source_id, company_id, name, source_type, base_url,
                       scrape_frequency_minutes, is_active, last_scrape_at,
                       last_scrape_status, last_scrape_records, configuration,
                       created_at, updated_at
                FROM scrape_sources
                WHERE company_id = :company_id
            """
            if active_only:
                query += " AND is_active = 1"
            query += " ORDER BY name"

            result = session.execute(
                text(query),
                {"company_id": current_user.company_id or 1}
            )

            sources = []
            for row in result.fetchall():
                sources.append(ScrapeSourceResponse(
                    source_id=row[0],
                    company_id=row[1],
                    name=row[2],
                    source_type=row[3],
                    base_url=row[4],
                    scrape_frequency_minutes=row[5],
                    is_active=bool(row[6]),
                    last_scrape_at=row[7],
                    last_scrape_status=row[8],
                    last_scrape_records=row[9] or 0,
                    configuration=row[10] if isinstance(row[10], dict) else {},
                    created_at=row[11],
                    updated_at=row[12]
                ))

            return sources
    except Exception as e:
        logger.exception(f"Error listing scrape sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scrape-sources", response_model=ScrapeSourceResponse, status_code=201, tags=["Scrape Sources"])
async def create_scrape_source(
    source: ScrapeSourceCreate,
    current_user: User = Security(get_current_user, scopes=["write:scrapes"])
):
    """
    Create a new scrape source configuration.

    Requires write:scrapes permission (admin/manager role).
    """
    try:
        with get_session() as session:
            # Check for duplicate name
            check = session.execute(
                text("SELECT 1 FROM scrape_sources WHERE company_id = :company_id AND name = :name"),
                {"company_id": current_user.company_id or 1, "name": source.name}
            ).fetchone()

            if check:
                raise HTTPException(status_code=409, detail=f"Source '{source.name}' already exists")

            # Insert new source
            import json
            result = session.execute(
                text("""
                    INSERT INTO scrape_sources
                    (company_id, name, source_type, base_url, scrape_frequency_minutes,
                     is_active, configuration, created_by)
                    OUTPUT INSERTED.source_id, INSERTED.created_at, INSERTED.updated_at
                    VALUES (:company_id, :name, :source_type, :base_url, :frequency,
                            :is_active, :config, :user_id)
                """),
                {
                    "company_id": current_user.company_id or 1,
                    "name": source.name,
                    "source_type": source.source_type,
                    "base_url": source.base_url,
                    "frequency": source.scrape_frequency_minutes,
                    "is_active": source.is_active,
                    "config": json.dumps(source.configuration or {}),
                    "user_id": current_user.user_id
                }
            )
            row = result.fetchone()
            session.commit()

            return ScrapeSourceResponse(
                source_id=row[0],
                company_id=current_user.company_id or 1,
                name=source.name,
                source_type=source.source_type,
                base_url=source.base_url,
                scrape_frequency_minutes=source.scrape_frequency_minutes,
                is_active=source.is_active,
                configuration=source.configuration or {},
                created_at=row[1],
                updated_at=row[2]
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating scrape source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scrape-sources/{source_id}", response_model=ScrapeSourceResponse, tags=["Scrape Sources"])
async def get_scrape_source(
    source_id: int,
    current_user: User = Security(get_current_user, scopes=["read:scrapes"])
):
    """
    Get a specific scrape source by ID.
    """
    try:
        with get_session() as session:
            result = session.execute(
                text("""
                    SELECT source_id, company_id, name, source_type, base_url,
                           scrape_frequency_minutes, is_active, last_scrape_at,
                           last_scrape_status, last_scrape_records, configuration,
                           created_at, updated_at
                    FROM scrape_sources
                    WHERE source_id = :source_id AND company_id = :company_id
                """),
                {"source_id": source_id, "company_id": current_user.company_id or 1}
            )
            row = result.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"Scrape source {source_id} not found")

            return ScrapeSourceResponse(
                source_id=row[0],
                company_id=row[1],
                name=row[2],
                source_type=row[3],
                base_url=row[4],
                scrape_frequency_minutes=row[5],
                is_active=bool(row[6]),
                last_scrape_at=row[7],
                last_scrape_status=row[8],
                last_scrape_records=row[9] or 0,
                configuration=row[10] if isinstance(row[10], dict) else {},
                created_at=row[11],
                updated_at=row[12]
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting scrape source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/scrape-sources/{source_id}", response_model=ScrapeSourceResponse, tags=["Scrape Sources"])
async def update_scrape_source(
    source_id: int,
    update: ScrapeSourceUpdate,
    current_user: User = Security(get_current_user, scopes=["write:scrapes"])
):
    """
    Update a scrape source configuration.
    """
    try:
        with get_session() as session:
            # Build dynamic update query
            updates = []
            params = {"source_id": source_id, "company_id": current_user.company_id or 1}

            if update.name is not None:
                updates.append("name = :name")
                params["name"] = update.name
            if update.source_type is not None:
                updates.append("source_type = :source_type")
                params["source_type"] = update.source_type
            if update.base_url is not None:
                updates.append("base_url = :base_url")
                params["base_url"] = update.base_url
            if update.scrape_frequency_minutes is not None:
                updates.append("scrape_frequency_minutes = :frequency")
                params["frequency"] = update.scrape_frequency_minutes
            if update.is_active is not None:
                updates.append("is_active = :is_active")
                params["is_active"] = update.is_active
            if update.configuration is not None:
                import json
                updates.append("configuration = :config")
                params["config"] = json.dumps(update.configuration)

            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")

            updates.append("updated_at = GETUTCDATE()")

            session.execute(
                text(f"""
                    UPDATE scrape_sources
                    SET {', '.join(updates)}
                    WHERE source_id = :source_id AND company_id = :company_id
                """),
                params
            )
            session.commit()

            # Fetch updated record
            return await get_scrape_source(source_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating scrape source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scrape-sources/{source_id}", status_code=204, tags=["Scrape Sources"])
async def delete_scrape_source(
    source_id: int,
    current_user: User = Security(get_current_user, scopes=["admin:scrapes"])
):
    """
    Delete a scrape source.

    Requires admin permission.
    """
    try:
        with get_session() as session:
            result = session.execute(
                text("""
                    DELETE FROM scrape_sources
                    WHERE source_id = :source_id AND company_id = :company_id
                """),
                {"source_id": source_id, "company_id": current_user.company_id or 1}
            )

            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Scrape source {source_id} not found")

            session.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting scrape source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SCRAPE JOBS ENDPOINTS
# ============================================================================

@router.post("/scrape-jobs/trigger/{source_id}", response_model=TriggerResponse, tags=["Scrape Jobs"])
async def trigger_scrape_job(
    source_id: int,
    current_user: User = Security(get_current_user, scopes=["write:scrapes"])
):
    """
    Trigger a scrape job for a specific source.

    Creates a new scrape run and queues it for execution.
    In production, this would send a message to Azure Service Bus.
    """
    try:
        with get_session() as session:
            # Get source info
            source = session.execute(
                text("""
                    SELECT name, is_active FROM scrape_sources
                    WHERE source_id = :source_id AND company_id = :company_id
                """),
                {"source_id": source_id, "company_id": current_user.company_id or 1}
            ).fetchone()

            if not source:
                raise HTTPException(status_code=404, detail=f"Scrape source {source_id} not found")

            if not source[1]:
                raise HTTPException(status_code=400, detail=f"Source '{source[0]}' is not active")

            # Create scrape run
            result = session.execute(
                text("""
                    INSERT INTO scrape_runs (company_id, source_id, mode, user_id, status)
                    OUTPUT INSERTED.run_id
                    VALUES (:company_id, :source_id, :mode, :user_id, 'pending')
                """),
                {
                    "company_id": current_user.company_id or 1,
                    "source_id": source_id,
                    "mode": f"triggered:{source[0]}",
                    "user_id": current_user.user_id
                }
            )
            run_id = result.fetchone()[0]
            session.commit()

            # TODO: In production, send message to Service Bus
            # from azure.servicebus import ServiceBusClient
            # client.send_message({"run_id": run_id, "source_id": source_id})

            logger.info(f"Triggered scrape job {run_id} for source {source_id} ({source[0]})")

            return TriggerResponse(
                message=f"Scrape job triggered for {source[0]}",
                run_id=run_id,
                source_id=source_id,
                source_name=source[0]
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error triggering scrape job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scrape-jobs/{run_id}/status", response_model=ScrapeJobStatus, tags=["Scrape Jobs"])
async def get_scrape_job_status(
    run_id: int,
    current_user: User = Security(get_current_user, scopes=["read:scrapes"])
):
    """
    Get the status of a specific scrape job.
    """
    try:
        with get_session() as session:
            result = session.execute(
                text("""
                    SELECT run_id, source_id, status, run_timestamp,
                           NULL as completed_at, records_scraped, error_message
                    FROM scrape_runs
                    WHERE run_id = :run_id AND company_id = :company_id
                """),
                {"run_id": run_id, "company_id": current_user.company_id or 1}
            )
            row = result.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"Scrape job {run_id} not found")

            return ScrapeJobStatus(
                run_id=row[0],
                source_id=row[1],
                status=row[2] or "unknown",
                started_at=row[3],
                completed_at=row[4],
                records_scraped=row[5] or 0,
                error_message=row[6]
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting scrape job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scrape-jobs", response_model=List[ScrapeJobStatus], tags=["Scrape Jobs"])
async def list_scrape_jobs(
    source_id: Optional[int] = Query(None, description="Filter by source ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    current_user: User = Security(get_current_user, scopes=["read:scrapes"])
):
    """
    List recent scrape jobs with optional filtering.
    """
    try:
        with get_session() as session:
            query = """
                SELECT TOP(:limit) run_id, source_id, status, run_timestamp,
                       NULL as completed_at, records_scraped, error_message
                FROM scrape_runs
                WHERE company_id = :company_id
            """
            params = {"company_id": current_user.company_id or 1, "limit": limit}

            if source_id:
                query += " AND source_id = :source_id"
                params["source_id"] = source_id
            if status:
                query += " AND status = :status"
                params["status"] = status

            query += " ORDER BY run_timestamp DESC"

            result = session.execute(text(query), params)

            jobs = []
            for row in result.fetchall():
                jobs.append(ScrapeJobStatus(
                    run_id=row[0],
                    source_id=row[1],
                    status=row[2] or "unknown",
                    started_at=row[3],
                    completed_at=row[4],
                    records_scraped=row[5] or 0,
                    error_message=row[6]
                ))

            return jobs
    except Exception as e:
        logger.exception(f"Error listing scrape jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
