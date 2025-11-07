#!/usr/bin/env python3
"""
Script to check database structure
"""
import sqlite3

def check_structure():
    """Check database structure"""

    db_paths = ['users.db', 'app/users.db']

    db_path = None
    for path in db_paths:
        try:
            conn = sqlite3.connect(path)
            db_path = path
            break
        except:
            continue

    if db_path is None:
        print("[X] Could not find users.db database")
        return

    print(f"[OK] Connected to database: {db_path}\n")

    cursor = conn.cursor()

    # Get table structure
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()

    print("=" * 60)
    print("USERS TABLE STRUCTURE")
    print("=" * 60)
    print(f"{'#':<5} {'Column Name':<20} {'Type':<15} {'Not Null':<10}")
    print("-" * 60)

    for col in columns:
        print(f"{col[0]:<5} {col[1]:<20} {col[2]:<15} {col[3]:<10}")

    print("=" * 60)
    print()

    conn.close()

if __name__ == "__main__":
    check_structure()
