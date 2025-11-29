from app import db_adapter as database

runs = database.get_scrape_runs()
print(f"Total scrape runs: {len(runs)}")
print("\nLast 5 runs:")
for r in runs[-5:]:
    print(f"  Run {r['run_id']}: {r['run_timestamp']} - {r['mode']}")

# Check if there are any showings
from app.db_session import get_session
from app.db_models import Showing

with get_session() as session:
    showing_count = session.query(Showing).count()
    print(f"\nTotal showings in database: {showing_count}")
    
    if showing_count > 0:
        recent_showings = session.query(Showing).limit(5).all()
        print("\nSample showings:")
        for s in recent_showings:
            print(f"  Theater: {s.theater_name}, Film: {s.film_title}, Time: {s.showtime}")
