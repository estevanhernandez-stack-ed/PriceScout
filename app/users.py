import sqlite3
import bcrypt

DB_FILE = "users.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT 0
            )
        """)
        
        # Add company column if it doesn't exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'company' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN company TEXT")
        # --- NEW: Add default_company column ---
        if 'default_company' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN default_company TEXT")

        # Add a default admin user if one doesn't exist
        cursor.execute("SELECT * FROM users WHERE username = ?", ("admin",))
        if not cursor.fetchone():
            password = b"admin"
            hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
            cursor.execute("INSERT INTO users (username, password_hash, is_admin, company) VALUES (?, ?, ?, ?)", ("admin", hashed_password.decode('utf-8'), 1, None))
        conn.commit()

def create_user(username, password, is_admin=False, company=None, default_company=None):
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    with get_db_connection() as conn:
        try:
            conn.execute("INSERT INTO users (username, password_hash, is_admin, company, default_company) VALUES (?, ?, ?, ?, ?)", (username, password_hash.decode('utf-8'), is_admin, company, default_company))
            conn.commit()
            return True, "User created successfully."
        except sqlite3.IntegrityError:
            return False, "Username already exists."

def get_user(username):
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return user

def verify_user(username, password):
    """Verifies a user's password."""
    user = get_user(username)
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        return user
    return None

def get_all_users():
    with get_db_connection() as conn:
        users = conn.execute("SELECT id, username, is_admin, company, default_company FROM users").fetchall()
        return users

def update_user(user_id, username, is_admin, company, default_company):
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET username = ?, is_admin = ?, company = ?, default_company = ? WHERE id = ?", (username, is_admin, company, default_company, user_id))
        conn.commit()

def delete_user(user_id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
