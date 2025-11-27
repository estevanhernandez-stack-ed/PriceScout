"""
Debug operating hours endpoint with detailed timing
"""
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from contextlib import contextmanager
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db_adapter import get_session, Showing
from sqlalchemy import func
from app import config

app = FastAPI()

@app.get("/debug-operating-hours")
def debug_operating_hours(theater: str = Query("Marcus Ridge Cinema")):
    """Debug version with timing at each step"""
    timings = {}
    start = time.time()
    
    try:
        timings['start'] = 0
        
        # Step 1: Enter session context
        session_start = time.time()
        session = get_session().__enter__()
        timings['session_open'] = time.time() - session_start
        
        # Step 2: Build query
        query_build_start = time.time()
        query = session.query(
            Showing.theater_name,
            Showing.play_date,
            func.min(Showing.showtime).label('opening_time'),
            func.max(Showing.showtime).label('closing_time'),
            func.count(Showing.showing_id).label('total_showtimes')
        )
        
        if config.company_id:
            query = query.filter(Showing.company_id == config.company_id)
        
        query = query.filter(Showing.theater_name == theater)
        query = query.group_by(Showing.theater_name, Showing.play_date)
        query = query.order_by(Showing.play_date.desc())
        query = query.limit(10)
        
        timings['query_build'] = time.time() - query_build_start
        
        # Step 3: Execute query
        exec_start = time.time()
        results = query.all()
        timings['query_execute'] = time.time() - exec_start
        
        # Step 4: Process results
        process_start = time.time()
        data = [{
            'theater_name': r.theater_name,
            'date': r.play_date.strftime('%Y-%m-%d'),
            'opening_time': r.opening_time,
            'closing_time': r.closing_time,
            'total_showtimes': r.total_showtimes
        } for r in results]
        timings['process_results'] = time.time() - process_start
        
        # Step 5: Close session
        close_start = time.time()
        session.close()
        timings['session_close'] = time.time() - close_start
        
        timings['total'] = time.time() - start
        
        return {
            "success": True,
            "result_count": len(data),
            "timings_seconds": timings,
            "sample_data": data[:2] if data else None
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "timings_seconds": timings,
                "elapsed": time.time() - start
            }
        )

if __name__ == "__main__":
    import uvicorn
    print("Starting debug server on port 8091...")
    print("Test with: curl http://localhost:8091/debug-operating-hours")
    uvicorn.run(app, host="127.0.0.1", port=8091, log_level="debug")
