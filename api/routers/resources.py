"""
Resource endpoints for theaters, films, and scrape runs
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, date
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, distinct

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db_adapter import get_session, Showing, Film, ScrapeRun, Price
from app import config
from api.auth import verify_api_key, check_rate_limit

router = APIRouter(prefix="/api/v1", tags=["resources"])


@router.get("/theaters", response_model=None)
async def list_theaters(
    request: Request,
    active_only: bool = Query(True, description="Only show theaters with recent showtimes"),
    date_from: str = Query(None, description="Filter theaters with showtimes after this date (YYYY-MM-DD)"),
    format: str = Query("json", regex="^(json|csv)$"),
    api_key_data: dict = Depends(verify_api_key)
):
    """
    Get list of all theaters with metadata.
    Returns theater names, showtime counts, and date ranges.
    """
    await check_rate_limit(api_key_data, request)
    with get_session() as session:
        query = session.query(
            Showing.theater_name,
            func.count(distinct(Showing.play_date)).label('active_dates'),
            func.count(Showing.showing_id).label('total_showtimes'),
            func.min(Showing.play_date).label('first_date'),
            func.max(Showing.play_date).label('last_date'),
            func.count(distinct(Showing.film_title)).label('film_count')
        )
        
        if config.CURRENT_COMPANY_ID:
            query = query.filter(Showing.company_id == config.CURRENT_COMPANY_ID)
        
        if date_from:
            try:
                date_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                query = query.filter(Showing.play_date >= date_obj)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        query = query.group_by(Showing.theater_name)
        query = query.order_by(Showing.theater_name)
        
        results = query.all()
        
        if not results:
            raise HTTPException(status_code=404, detail="No theaters found")
        
        data = [{
            'theater_name': r.theater_name,
            'active_dates': r.active_dates,
            'total_showtimes': r.total_showtimes,
            'first_date': r.first_date.strftime('%Y-%m-%d'),
            'last_date': r.last_date.strftime('%Y-%m-%d'),
            'film_count': r.film_count
        } for r in results]
        
        if format == "json":
            return {
                "theater_count": len(data),
                "theaters": data
            }
        
        # CSV format
        import io
        csv_lines = ["theater_name,active_dates,total_showtimes,first_date,last_date,film_count"]
        for r in data:
            csv_lines.append(f"{r['theater_name']},{r['active_dates']},{r['total_showtimes']},{r['first_date']},{r['last_date']},{r['film_count']}")
        csv_content = "\n".join(csv_lines).encode('utf-8')
        
        from fastapi.responses import StreamingResponse
        filename = f"theaters_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return StreamingResponse(
            io.BytesIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


@router.get("/films", response_model=None)
async def list_films(
    request: Request,
    date: str = Query(None, description="Filter by specific date (YYYY-MM-DD)"),
    theater: str = Query(None, description="Filter by theater name"),
    limit: int = Query(100, description="Max results"),
    format: str = Query("json", regex="^(json|csv)$"),
    api_key_data: dict = Depends(verify_api_key)
):
    """
    Get list of films with showtime information.
    """
    await check_rate_limit(api_key_data, request)
    with get_session() as session:
        query = session.query(
            Showing.film_title,
            func.count(Showing.showing_id).label('showtime_count'),
            func.count(distinct(Showing.theater_name)).label('theater_count'),
            func.count(distinct(Showing.play_date)).label('date_count'),
            func.min(Showing.play_date).label('first_date'),
            func.max(Showing.play_date).label('last_date')
        )
        
        if config.CURRENT_COMPANY_ID:
            query = query.filter(Showing.company_id == config.CURRENT_COMPANY_ID)
        
        if date:
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d').date()
                query = query.filter(Showing.play_date == date_obj)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        if theater:
            query = query.filter(Showing.theater_name == theater)
        
        query = query.group_by(Showing.film_title)
        query = query.order_by(func.count(Showing.showing_id).desc())
        query = query.limit(limit)
        
        results = query.all()
        
        if not results:
            raise HTTPException(status_code=404, detail="No films found")
        
        data = [{
            'film_title': r.film_title,
            'showtime_count': r.showtime_count,
            'theater_count': r.theater_count,
            'date_count': r.date_count,
            'first_date': r.first_date.strftime('%Y-%m-%d'),
            'last_date': r.last_date.strftime('%Y-%m-%d')
        } for r in results]
        
        if format == "json":
            return {
                "film_count": len(data),
                "films": data
            }
        
        # CSV format
        import io
        csv_lines = ["film_title,showtime_count,theater_count,date_count,first_date,last_date"]
        for r in data:
            csv_lines.append(f"\"{r['film_title']}\",{r['showtime_count']},{r['theater_count']},{r['date_count']},{r['first_date']},{r['last_date']}")
        csv_content = "\n".join(csv_lines).encode('utf-8')
        
        from fastapi.responses import StreamingResponse
        filename = f"films_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return StreamingResponse(
            io.BytesIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


@router.get("/scrape-runs", response_model=None)
async def list_scrape_runs(
    request: Request,
    limit: int = Query(20, description="Max results"),
    format: str = Query("json", regex="^(json|csv)$"),
    api_key_data: dict = Depends(verify_api_key)
):
    """
    Get recent scrape run history with status and metrics.
    """
    await check_rate_limit(api_key_data, request)
    with get_session() as session:
        query = session.query(ScrapeRun)
        
        if config.CURRENT_COMPANY_ID:
            query = query.filter(ScrapeRun.company_id == config.CURRENT_COMPANY_ID)
        
        query = query.order_by(ScrapeRun.run_timestamp.desc())
        query = query.limit(limit)
        
        results = query.all()
        
        if not results:
            raise HTTPException(status_code=404, detail="No scrape runs found")
        
        data = [{
            'run_id': r.run_id,
            'status': r.status,
            'run_timestamp': r.run_timestamp.strftime('%Y-%m-%d %H:%M:%S') if r.run_timestamp else None,
            'mode': r.mode,
            'records_scraped': r.records_scraped,
            'error_message': r.error_message[:100] if r.error_message else None
        } for r in results]
        
        if format == "json":
            return {
                "scrape_run_count": len(data),
                "scrape_runs": data
            }
        
        # CSV format
        import io
        csv_lines = ["run_id,status,run_timestamp,mode,records_scraped,error_message"]
        for r in data:
            error = r['error_message'].replace(',', ';') if r['error_message'] else ''
            csv_lines.append(f"{r['run_id']},{r['status']},{r['run_timestamp']},{r['mode']},{r['records_scraped']},{error}")
        csv_content = "\n".join(csv_lines).encode('utf-8')
        
        from fastapi.responses import StreamingResponse
        filename = f"scrape_runs_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return StreamingResponse(
            io.BytesIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


@router.get("/showtimes/search", response_model=None)
async def search_showtimes(
    request: Request,
    film: str = Query(None, description="Film title (partial match)"),
    theater: str = Query(None, description="Theater name (partial match)"),
    date_from: str = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: str = Query(None, description="End date (YYYY-MM-DD)"),
    format_type: str = Query(None, description="Format filter (IMAX, Dolby, 3D, etc)"),
    limit: int = Query(100, description="Max results"),
    format: str = Query("json", regex="^(json|csv)$"),
    api_key_data: dict = Depends(verify_api_key)
):
    """
    Flexible showtime search with multiple filter options.
    """
    await check_rate_limit(api_key_data, request)
    with get_session() as session:
        query = session.query(Showing)
        
        if config.CURRENT_COMPANY_ID:
            query = query.filter(Showing.company_id == config.CURRENT_COMPANY_ID)
        
        if film:
            query = query.filter(Showing.film_title.ilike(f'%{film}%'))
        
        if theater:
            query = query.filter(Showing.theater_name.ilike(f'%{theater}%'))
        
        if date_from:
            try:
                date_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                query = query.filter(Showing.play_date >= date_obj)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_from format. Use YYYY-MM-DD")
        
        if date_to:
            try:
                date_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                query = query.filter(Showing.play_date <= date_obj)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_to format. Use YYYY-MM-DD")
        
        if format_type:
            query = query.filter(Showing.format.ilike(f'%{format_type}%'))
        
        query = query.order_by(Showing.play_date, Showing.theater_name, Showing.showtime)
        query = query.limit(limit)
        
        results = query.all()
        
        if not results:
            raise HTTPException(status_code=404, detail="No showtimes found matching criteria")
        
        data = [{
            'film_title': r.film_title,
            'theater_name': r.theater_name,
            'play_date': r.play_date.strftime('%Y-%m-%d'),
            'showtime': r.showtime,
            'format': r.format,
            'daypart': r.daypart,
            'is_plf': r.is_plf
        } for r in results]
        
        if format == "json":
            return {
                "showtime_count": len(data),
                "filters": {
                    "film": film,
                    "theater": theater,
                    "date_from": date_from,
                    "date_to": date_to,
                    "format_type": format_type
                },
                "showtimes": data
            }
        
        # CSV format
        import io
        csv_lines = ["film_title,theater_name,play_date,showtime,format,daypart,is_plf"]
        for r in data:
            csv_lines.append(f"\"{r['film_title']}\",{r['theater_name']},{r['play_date']},{r['showtime']},{r['format']},{r['daypart']},{r['is_plf']}")
        csv_content = "\n".join(csv_lines).encode('utf-8')
        
        from fastapi.responses import StreamingResponse
        filename = f"showtimes_search_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return StreamingResponse(
            io.BytesIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


@router.get("/pricing", response_model=None)
async def get_pricing(
    request: Request,
    theater: str = Query(None, description="Theater name filter"),
    film: str = Query(None, description="Film title filter"),
    date: str = Query(None, description="Date filter (YYYY-MM-DD)"),
    limit: int = Query(100, description="Max results"),
    format: str = Query("json", regex="^(json|csv)$"),
    api_key_data: dict = Depends(verify_api_key)
):
    """
    Get ticket pricing data with optional filters.
    """
    await check_rate_limit(api_key_data, request)
    with get_session() as session:
        query = session.query(
            Price,
            Showing.film_title,
            Showing.theater_name,
            Showing.play_date,
            Showing.showtime,
            Showing.format
        ).join(Showing, Price.showing_id == Showing.showing_id)
        
        if config.CURRENT_COMPANY_ID:
            query = query.filter(Showing.company_id == config.CURRENT_COMPANY_ID)
        
        if theater:
            query = query.filter(Showing.theater_name.ilike(f'%{theater}%'))
        
        if film:
            query = query.filter(Showing.film_title.ilike(f'%{film}%'))
        
        if date:
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d').date()
                query = query.filter(Showing.play_date == date_obj)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        query = query.order_by(Showing.play_date.desc(), Showing.theater_name)
        query = query.limit(limit)
        
        results = query.all()
        
        if not results:
            raise HTTPException(status_code=404, detail="No pricing data found")
        
        data = [{
            'film_title': r.film_title,
            'theater_name': r.theater_name,
            'play_date': r.play_date.strftime('%Y-%m-%d'),
            'showtime': r.showtime,
            'format': r.format,
            'ticket_type': r.Price.ticket_type,
            'price': float(r.Price.price) if r.Price.price else None,
            'scraped_at': r.Price.scraped_at.strftime('%Y-%m-%d %H:%M:%S') if r.Price.scraped_at else None
        } for r in results]
        
        if format == "json":
            return {
                "price_count": len(data),
                "pricing": data
            }
        
        # CSV format
        import io
        csv_lines = ["film_title,theater_name,play_date,showtime,format,ticket_type,price,scraped_at"]
        for r in data:
            csv_lines.append(f"\"{r['film_title']}\",{r['theater_name']},{r['play_date']},{r['showtime']},{r['format']},{r['ticket_type']},{r['price']},{r['scraped_at']}")
        csv_content = "\n".join(csv_lines).encode('utf-8')
        
        from fastapi.responses import StreamingResponse
        filename = f"pricing_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return StreamingResponse(
            io.BytesIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
