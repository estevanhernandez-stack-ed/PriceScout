"""Direct database query test to isolate the issue"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd()))

from app.db_adapter import get_session, Showing
from sqlalchemy import func
import time

print("Testing operating hours query directly...")
start = time.time()

with get_session() as session:
    query = session.query(
        Showing.theater_name,
        Showing.play_date,
        func.min(Showing.showtime).label('opening_time'),
        func.max(Showing.showtime).label('closing_time'),
        func.count(Showing.showing_id).label('total_showtimes')
    )
    
    query = query.filter(Showing.theater_name == "Marcus Ridge Cinema")
    query = query.group_by(Showing.theater_name, Showing.play_date)
    query = query.order_by(Showing.play_date.desc())
    query = query.limit(100)
    
    print(f"Query built in {time.time() - start:.2f}s")
    
    exec_start = time.time()
    results = query.all()
    print(f"Query executed in {time.time() - exec_start:.2f}s")
    print(f"Results: {len(results)} rows")
    
    if results:
        print(f"Sample: {results[0]}")

print(f"\nTotal time: {time.time() - start:.2f}s")
