"""Quick script to get a sample ticket URL from the database."""
import sqlite3

db_path = r"C:\Users\estev\Desktop\Price Scout\pricescout.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get a recent ticket URL from showings table
cursor.execute("""
    SELECT ticket_url, theater_name, film_title, showtime, play_date
    FROM showings
    WHERE ticket_url IS NOT NULL
    ORDER BY created_at DESC
    LIMIT 5
""")

results = cursor.fetchall()

if results:
    print("\nRecent ticket URLs from database:\n")
    for i, (url, theater, film, showtime, date) in enumerate(results, 1):
        print(f"{i}. {theater} - {film} at {showtime} ({date})")
        print(f"   URL: {url}\n")
else:
    print("\nNo ticket URLs found in database.")

conn.close()
