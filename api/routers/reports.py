from typing import Any, Dict
import io
import sys
import pandas as pd
from datetime import datetime
from sqlalchemy import func
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse, Response

# Ensure the app package is importable when running from repo root
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.schemas import SelectionAnalysisRequest, ShowtimeViewRequest
from api.unified_auth import require_auth, AuthData
from api.errors import (
    validation_error,
    not_found_error,
    pdf_generation_error
)

from app.utils import (
    generate_selection_analysis_report,
    to_csv,
    generate_showtime_html_report,
    generate_showtime_pdf_report,
)
from app.db_adapter import get_session, Showing, Film, config

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.post("/selection-analysis", response_model=None)
async def selection_analysis(
    req: SelectionAnalysisRequest,
    request: Request,
    format: str = Query("csv", regex="^(csv|json)$"),
    auth: AuthData = Depends(require_auth)
):
    df = generate_selection_analysis_report(req.selected_showtimes)
    if format == "json":
        return JSONResponse(content={"rows": df.to_dict(orient="records") if not df.empty else []})
    # CSV default
    csv_bytes = to_csv(df)
    return StreamingResponse(io.BytesIO(csv_bytes), media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=Showtime_Selection_Analysis.csv"
    })


@router.post("/showtime-view/html", response_model=None)
async def showtime_view_html(
    req: ShowtimeViewRequest,
    request: Request,
    auth: AuthData = Depends(require_auth)
):
    html_bytes = generate_showtime_html_report(
        req.all_showings,
        req.selected_films,
        req.theaters,
        (req.date_start, req.date_end),
        cache_data={},
        context_title=req.context_title,
    )
    return Response(content=html_bytes, media_type="text/html")


@router.post("/showtime-view/pdf", response_model=None)
async def showtime_view_pdf(
    req: ShowtimeViewRequest,
    request: Request,
    auth: AuthData = Depends(require_auth)
):
    try:
        pdf_bytes = await generate_showtime_pdf_report(
            req.all_showings,
            req.selected_films,
            req.theaters,
            (req.date_start, req.date_end),
            cache_data={},
            context_title=req.context_title,
        )
        return Response(content=pdf_bytes, media_type="application/pdf", headers={
            "Content-Disposition": "attachment; filename=Showtime_View.pdf"
        })
    except Exception as e:
        return pdf_generation_error(
            detail=f"PDF generation failed: {str(e)}",
            instance=str(request.url.path)
        )


@router.get("/daily-lineup", response_model=None)
async def daily_lineup(
    request: Request,
    theater: str = Query(..., description="Theater name (exact match)"),
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    format: str = Query("json", regex="^(json|csv)$", description="Response format"),
    auth: AuthData = Depends(require_auth)
):
    """
    Get daily lineup for a specific theater and date.
    Returns chronologically sorted showtimes with film titles and formats.
    """
    # Parse date
    try:
        play_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        return validation_error(
            detail="Invalid date format",
            errors={"date": ["Must be in YYYY-MM-DD format"]},
            instance=str(request.url.path)
        )

    # Query showings
    with get_session() as session:
        company_id = getattr(config, 'CURRENT_COMPANY_ID', None)

        query = session.query(
            Showing.film_title,
            Showing.showtime,
            Showing.format,
            Showing.daypart,
            Film.runtime
        ).outerjoin(
            Film,
            (Showing.film_title == Film.film_title) & (Showing.company_id == Film.company_id)
        )

        if config.CURRENT_COMPANY_ID:
            query = query.filter(Showing.company_id == config.CURRENT_COMPANY_ID)

        query = query.filter(
            Showing.theater_name == theater,
            Showing.play_date == play_date
        ).order_by(Showing.showtime, Showing.film_title)

        results = query.all()

        if not results:
            return not_found_error(
                detail=f"No showtimes found for {theater} on {date}",
                instance=str(request.url.path),
                resource_type="showtimes"
            )

        # Convert to DataFrame for consistent processing
        df = pd.DataFrame(
            results,
            columns=['film_title', 'showtime', 'format', 'daypart', 'runtime']
        )

    # Format response
    if format == "json":
        rows = df.to_dict(orient="records")
        return JSONResponse(content={
            "theater": theater,
            "date": date,
            "showtime_count": len(rows),
            "showtimes": rows
        })
    
    # CSV format
    csv_data = df.to_csv(index=False).encode('utf-8')
    filename = f"daily_lineup_{theater.replace(' ', '_')}_{date}.csv"
    return StreamingResponse(
        io.BytesIO(csv_data),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/operating-hours", response_model=None)
async def operating_hours(
    request: Request,
    theater: str = Query(None, description="Theater name filter (optional)"),
    date: str = Query(None, description="Date in YYYY-MM-DD format (optional)"),
    limit: int = Query(100, description="Maximum records to return (default 100)"),
    format: str = Query("json", regex="^(json|csv)$", description="Response format"),
    auth: AuthData = Depends(require_auth)
):
    """
    Get derived operating hours (first/last showtime) per theater per date.
    Based on actual showing data in the database.
    """
    from sqlalchemy import func
    
    with get_session() as session:
        # Build query for first/last showtime per theater/date
        query = session.query(
            Showing.theater_name,
            Showing.play_date,
            func.min(Showing.showtime).label('opening_time'),
            func.max(Showing.showtime).label('closing_time'),
            func.count(Showing.showing_id).label('total_showtimes')
        )
        
        # Apply company filter if set
        if config.CURRENT_COMPANY_ID:
            query = query.filter(Showing.company_id == config.CURRENT_COMPANY_ID)
        
        # Optional filters
        if theater:
            query = query.filter(Showing.theater_name == theater)
        if date:
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d').date()
                query = query.filter(Showing.play_date == date_obj)
            except ValueError:
                return validation_error(
                    detail="Invalid date format",
                    errors={"date": ["Must be in YYYY-MM-DD format"]},
                    instance=str(request.url.path)
                )

        # Group and order
        query = query.group_by(Showing.theater_name, Showing.play_date)
        query = query.order_by(Showing.play_date.desc(), Showing.theater_name)

        # Apply limit to avoid long queries
        query = query.limit(limit)

        results = query.all()

        if not results:
            return not_found_error(
                detail="No operating hours data found",
                instance=str(request.url.path),
                resource_type="operating_hours"
            )
        
        # Convert to simple dict list (no pandas)
        data = [{
            'theater_name': r.theater_name,
            'date': r.play_date.strftime('%Y-%m-%d'),
            'opening_time': r.opening_time,
            'closing_time': r.closing_time,
            'total_showtimes': r.total_showtimes
        } for r in results]
        
        if format == "json":
            dates = [r['date'] for r in data]
            return {
                "record_count": len(data),
                "date_range": {
                    "earliest": min(dates) if dates else None,
                    "latest": max(dates) if dates else None
                },
                "operating_hours": data
            }
        
        # CSV format - simple string building
        csv_lines = ["theater_name,date,opening_time,closing_time,total_showtimes"]
        for r in data:
            csv_lines.append(f"{r['theater_name']},{r['date']},{r['opening_time']},{r['closing_time']},{r['total_showtimes']}")
        csv_content = "\n".join(csv_lines).encode('utf-8')
        
        filename = f"operating_hours_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return StreamingResponse(
            io.BytesIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


@router.get("/plf-formats", response_model=None)
async def plf_formats(
    request: Request,
    date: str = Query(None, description="Date filter in YYYY-MM-DD format (optional)"),
    limit: int = Query(100, description="Maximum records to return (default 100)"),
    format: str = Query("json", regex="^(json|csv)$", description="Response format"),
    api_key_data: dict = Depends(verify_api_key)
):
    """
    Get premium large format (PLF) distribution across theaters.
    Shows which premium formats (IMAX, Dolby, ScreenX, etc.) are available.
    """
    await check_rate_limit(api_key_data, request)
    with get_session() as session:
        # Query distinct formats per theater
        query = session.query(
            Showing.theater_name,
            Showing.format,
            func.count(Showing.showing_id).label('showtime_count')
        )
        
        # Apply company filter
        if config.CURRENT_COMPANY_ID:
            query = query.filter(Showing.company_id == config.CURRENT_COMPANY_ID)
        
        # Filter for premium formats only (not Standard/2D)
        plf_formats = ['IMAX', 'Dolby', 'ScreenX', 'UltraScreen', 'SuperScreen', 
                       'IMAX 3D', 'Dolby 3D', '3D', 'DBox', 'RPX']
        query = query.filter(Showing.format.in_(plf_formats))
        
        # Optional date filter
        if date:
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d').date()
                query = query.filter(Showing.play_date == date_obj)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Group and order
        query = query.group_by(Showing.theater_name, Showing.format)
        query = query.order_by(Showing.theater_name, Showing.format)
        
        # Apply limit
        query = query.limit(limit)
        
        results = query.all()
        
        if not results:
            raise HTTPException(status_code=404, detail="No PLF format data found")
        
        # Convert to simple dict list (no pandas)
        data = [{
            'theater_name': r.theater_name,
            'format': r.format,
            'showtime_count': r.showtime_count
        } for r in results]
        
        if format == "json":
            # Group by theater manually
            theaters_plf = {}
            for item in data:
                theater = item['theater_name']
                if theater not in theaters_plf:
                    theaters_plf[theater] = []
                theaters_plf[theater].append({
                    'format': item['format'],
                    'showtime_count': item['showtime_count']
                })
            
            total_showtimes = sum(item['showtime_count'] for item in data)
            
            return {
                "theater_count": len(theaters_plf),
                "total_plf_showtimes": total_showtimes,
                "theaters": theaters_plf
            }
        
        # CSV format - simple string building
        csv_lines = ["theater_name,format,showtime_count"]
        for r in data:
            csv_lines.append(f"{r['theater_name']},{r['format']},{r['showtime_count']}")
        csv_content = "\n".join(csv_lines).encode('utf-8')
        
        date_suffix = f"_{date}" if date else ""
        filename = f"plf_formats{date_suffix}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return StreamingResponse(
            io.BytesIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

