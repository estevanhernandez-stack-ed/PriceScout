#!/usr/bin/env python3
"""
Script to find user information by username
"""
import sqlite3
import sys

def find_user_by_username(username):
    """Find user by username and display their information"""

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

    # Get user information by username
    cursor.execute("""
        SELECT id, username, password_hash, role, company, default_company,
               is_admin, allowed_modes, home_location_type, home_location_value
        FROM users
        WHERE username = ?
    """, (username,))

    user = cursor.fetchone()

    if user:
        print("=" * 70)
        print(f"USER FOUND: {username}")
        print("=" * 70)
        print(f"ID:                {user[0]}")
        print(f"Username:          {user[1]}")
        print(f"Password Hash:     {user[2]}")
        print(f"Role:              {user[3]}")
        print(f"Company:           {user[4] or 'N/A'}")
        print(f"Default Company:   {user[5] or 'N/A'}")
        print(f"Is Admin:          {user[6]}")
        print(f"Allowed Modes:     {user[7] or 'All'}")
        print(f"Home Location:     {user[8] or 'N/A'} = {user[9] or 'N/A'}")
        print("=" * 70)
        print("\nNOTE: Password is hashed with bcrypt for security.")
        print("The hash cannot be reversed to get the plain text password.")
        print()
        print("To reset/change the password:")
        print("  1. Use the admin interface in the app")
        print("  2. Or create a new password hash and update the database")
        print("=" * 70)
    else:
        print(f"[X] No user found with username: {username}")
        print("\nAll users in database:")
        print("=" * 70)

        cursor.execute("""
            SELECT id, username, role, company
            FROM users
            ORDER BY id
        """)

        all_users = cursor.fetchall()
        if all_users:
            print(f"{'ID':<10} {'Username':<20} {'Role':<15} {'Company':<20}")
            print("-" * 70)
            for u in all_users:
                print(f"{u[0]:<10} {u[1]:<20} {u[2]:<15} {u[3] or 'N/A':<20}")
        else:
            print("No users found in database")
        print("=" * 70)

    conn.close()

if __name__ == "__main__":
    username = "102702"
    if len(sys.argv) > 1:
        username = sys.argv[1]

    print("\n[*] Searching for user by username...\n")
    find_user_by_username(username)
    print()
