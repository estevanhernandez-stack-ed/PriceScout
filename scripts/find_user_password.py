#!/usr/bin/env python3
"""
Script to find user information from the database
"""
import sqlite3
import sys

def find_user(user_id):
    """Find user by ID and display their information"""

    # Try both possible database locations
    db_paths = [
        'users.db',
        'app/users.db'
    ]

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

    # Get user information
    cursor.execute("""
        SELECT id, username, password_hash, role, company, default_company,
               is_admin, allowed_modes, home_location_type, home_location_value
        FROM users
        WHERE id = ?
    """, (user_id,))

    user = cursor.fetchone()

    if user:
        print("=" * 60)
        print(f"USER FOUND: ID {user_id}")
        print("=" * 60)
        print(f"ID:                {user[0]}")
        print(f"Username:          {user[1]}")
        print(f"Password Hash:     {user[2]}")
        print(f"Role:              {user[3]}")
        print(f"Company:           {user[4]}")
        print(f"Default Company:   {user[5]}")
        print(f"Is Admin:          {user[6]}")
        print(f"Allowed Modes:     {user[7]}")
        print(f"Home Location:     {user[8]} = {user[9]}")
        print("=" * 60)
        print("\nNOTE: Password is hashed with bcrypt for security.")
        print("To reset password, use the admin interface or database tools.")
        print("=" * 60)
    else:
        print(f"[X] No user found with ID: {user_id}")
        print("\nLet me show you all users in the database:")
        print("=" * 60)

        cursor.execute("""
            SELECT id, username, role, company
            FROM users
            ORDER BY id
        """)

        all_users = cursor.fetchall()
        if all_users:
            print(f"{'ID':<10} {'Username':<20} {'Role':<15} {'Company':<20}")
            print("-" * 60)
            for u in all_users:
                print(f"{u[0]:<10} {u[1]:<20} {u[2]:<15} {u[3] or 'N/A':<20}")
        else:
            print("No users found in database")

    conn.close()

if __name__ == "__main__":
    user_id = 102702
    if len(sys.argv) > 1:
        user_id = sys.argv[1]

    print("\n[*] Searching for user information...\n")
    find_user(user_id)
    print()
