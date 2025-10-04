#!/usr/bin/env python3
"""
Database service for storing Reddit posts and generated comments.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager
try:
    import libsql
    LIBSQL_AVAILABLE = True
except ImportError:
    LIBSQL_AVAILABLE = False

DB_FILE = "replicant.db"

# Turso configuration
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

def convert_rows_to_dicts(rows, columns):
    """Convert libsql rows (tuples) to dictionaries"""
    if not rows:
        return []

    # libsql always returns tuples, so we can simplify this
    return [dict(zip(columns, row)) for row in rows]

def use_turso() -> bool:
    """Check if we should use Turso based on environment variables and context"""
    # Only use Turso if:
    # 1. Environment variables are set AND
    # 2. libsql is available AND
    # 3. We're in a production environment (no local DB file or explicitly set)
    if not (TURSO_DATABASE_URL and TURSO_AUTH_TOKEN and LIBSQL_AVAILABLE):
        return False

    # Check if we're in a production environment
    # If FLY_APP_NAME is set, we're on Fly.io (production)
    if os.getenv("FLY_APP_NAME"):
        return True

    # If local database file doesn't exist, use Turso
    if not os.path.exists(DB_FILE):
        return True

    # If FORCE_TURSO is explicitly set, use Turso
    if os.getenv("FORCE_TURSO", "").lower() in ("true", "1", "yes"):
        return True

    # Default to local SQLite for development
    return False

def init_database():
    """Initialize the database with required tables"""
    if use_turso():
        conn = libsql.connect(database=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
    else:
        # Use libsql for local file too
        conn = libsql.connect(f"file:{DB_FILE}")

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reddit_url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                subreddit TEXT NOT NULL,
                mixed_comments_json TEXT NOT NULL,
                ai_count INTEGER NOT NULL,
                total_count INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP NULL,
                is_deleted INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anonymous_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_guesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                post_id INTEGER NOT NULL,
                comment_id TEXT NOT NULL,
                guess TEXT NOT NULL CHECK (guess IN ('reddit', 'replicant')),
                is_correct INTEGER NOT NULL,
                guessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0,
                deleted_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (post_id) REFERENCES posts (id),
                UNIQUE(user_id, post_id, comment_id)
            )
        """)

        conn.commit()
    finally:
        conn.close()

@contextmanager
def get_db_connection(force_turso: bool = None):
    """Context manager for database connections"""
    should_use_turso = use_turso()

    # Allow override via parameter
    if force_turso is not None:
        should_use_turso = force_turso and bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN and LIBSQL_AVAILABLE)

    # Debug logging (comment out for production)
    # print(f"get_db_connection: force_turso={force_turso}, should_use_turso={should_use_turso}")

    if should_use_turso:
        # Use Turso remote connection
        conn = libsql.connect(database=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
        try:
            yield conn
        finally:
            conn.close()
    else:
        # Use libsql for local file too - consistent format
        print("Using libsql local connection")
        conn = libsql.connect(f"file:{DB_FILE}")
        try:
            yield conn
        finally:
            conn.close()

def save_post(reddit_url: str, title: str, subreddit: str,
              mixed_comments_data: dict, ai_count: int, total_count: int, force_turso: bool = None) -> int:
    """
    Save a processed Reddit post with mixed comments to the database
    
    Returns:
        The ID of the saved post
    """
    mixed_comments_json = json.dumps(mixed_comments_data)
    
    with get_db_connection(force_turso) as conn:
        cursor = conn.execute("""
            INSERT INTO posts (reddit_url, title, subreddit, mixed_comments_json, ai_count, total_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (reddit_url, title, subreddit, mixed_comments_json, ai_count, total_count))
        conn.commit()
        return cursor.lastrowid

def get_post_by_id(post_id: int, force_turso: bool = None) -> Optional[Dict]:
    """Get a post by ID with parsed JSON comments"""
    with get_db_connection(force_turso) as conn:
        row = conn.execute("""
            SELECT id, reddit_url, title, subreddit, mixed_comments_json,
                   ai_count, total_count, created_at
            FROM posts
            WHERE id = ?
        """, (post_id,)).fetchone()

        if row:
            # libsql always returns tuples, so we can handle consistently
            return {
                'id': row[0],
                'reddit_url': row[1],
                'title': row[2],
                'subreddit': row[3],
                'mixed_comments': json.loads(row[4]),
                'ai_count': row[5],
                'total_count': row[6],
                'created_at': row[7]
            }
        return None

def get_all_posts(include_deleted: bool = False, force_turso: bool = None) -> List[Dict]:
    """Get all posts (without full comment data for listing)"""
    with get_db_connection(force_turso) as conn:
        if include_deleted:
            # Admin view: show all posts including deleted ones
            rows = conn.execute("""
                SELECT id, reddit_url, title, subreddit, ai_count, total_count,
                       created_at, deleted_at, is_deleted
                FROM posts
                ORDER BY created_at DESC
            """).fetchall()
            columns = ['id', 'reddit_url', 'title', 'subreddit', 'ai_count', 'total_count', 'created_at', 'deleted_at', 'is_deleted']
        else:
            # Public view: only show non-deleted posts
            rows = conn.execute("""
                SELECT id, reddit_url, title, subreddit, ai_count, total_count, created_at
                FROM posts
                WHERE is_deleted = 0
                ORDER BY created_at DESC
            """).fetchall()
            columns = ['id', 'reddit_url', 'title', 'subreddit', 'ai_count', 'total_count', 'created_at']

        return convert_rows_to_dicts(rows, columns)

def get_posts_by_subreddit(subreddit: str, include_deleted: bool = False, force_turso: bool = None) -> List[Dict]:
    """Get posts filtered by subreddit (without full comment data for listing)"""
    with get_db_connection(force_turso) as conn:
        if include_deleted:
            # Admin view: show all posts including deleted ones
            rows = conn.execute("""
                SELECT id, reddit_url, title, subreddit, ai_count, total_count,
                       created_at, deleted_at, is_deleted
                FROM posts
                WHERE subreddit = ?
                ORDER BY created_at DESC
            """, (subreddit,)).fetchall()
            columns = ['id', 'reddit_url', 'title', 'subreddit', 'ai_count', 'total_count', 'created_at', 'deleted_at', 'is_deleted']
        else:
            # Public view: only show non-deleted posts
            rows = conn.execute("""
                SELECT id, reddit_url, title, subreddit, ai_count, total_count, created_at
                FROM posts
                WHERE subreddit = ? AND is_deleted = 0
                ORDER BY created_at DESC
            """, (subreddit,)).fetchall()
            columns = ['id', 'reddit_url', 'title', 'subreddit', 'ai_count', 'total_count', 'created_at']

        return convert_rows_to_dicts(rows, columns)

def post_exists(reddit_url: str, force_turso: bool = None) -> bool:
    """Check if a Reddit URL has already been processed"""
    with get_db_connection(force_turso) as conn:
        row = conn.execute("""
            SELECT 1 FROM posts WHERE reddit_url = ?
        """, (reddit_url,)).fetchone()
        return row is not None

def soft_delete_post(post_id: int, force_turso: bool = None) -> bool:
    """Soft delete a post by ID"""
    with get_db_connection(force_turso) as conn:
        cursor = conn.execute("""
            UPDATE posts 
            SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP 
            WHERE id = ? AND is_deleted = 0
        """, (post_id,))
        conn.commit()
        return cursor.rowcount > 0

def restore_post(post_id: int, force_turso: bool = None) -> bool:
    """Restore a soft-deleted post by ID"""
    with get_db_connection(force_turso) as conn:
        cursor = conn.execute("""
            UPDATE posts 
            SET is_deleted = 0, deleted_at = NULL 
            WHERE id = ? AND is_deleted = 1
        """, (post_id,))
        conn.commit()
        return cursor.rowcount > 0

def delete_post(post_id: int) -> bool:
    """Hard delete a post by ID (kept for backwards compatibility)"""
    with get_db_connection(force_turso) as conn:
        cursor = conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        conn.commit()
        return cursor.rowcount > 0

# User management functions

def create_user(anonymous_id: str, force_turso: bool = None) -> int:
    """Create a new anonymous user"""
    with get_db_connection(force_turso) as conn:
        cursor = conn.execute("""
            INSERT INTO users (anonymous_id)
            VALUES (?)
        """, (anonymous_id,))
        conn.commit()
        return cursor.lastrowid

def get_user_by_anonymous_id(anonymous_id: str, force_turso: bool = None) -> Optional[Dict]:
    """Get user by anonymous ID"""
    with get_db_connection(force_turso) as conn:
        row = conn.execute("""
            SELECT id, anonymous_id, created_at
            FROM users
            WHERE anonymous_id = ?
        """, (anonymous_id,)).fetchone()

        if row:
            return {
                'id': row[0],
                'anonymous_id': row[1],
                'created_at': row[2]
            }
        return None

def get_or_create_user(anonymous_id: str, force_turso: bool = None) -> int:
    """Get existing user ID or create new user, return user ID"""
    user = get_user_by_anonymous_id(anonymous_id, force_turso)
    if user:
        return user['id']
    else:
        return create_user(anonymous_id, force_turso)

# User guess tracking functions

def save_user_guess(user_id: int, post_id: int, comment_id: str, guess: str, is_correct: bool, force_turso: bool = None) -> bool:
    """Save or update a user's guess for a specific comment"""
    with get_db_connection(force_turso) as conn:
        cursor = conn.execute("""
            INSERT OR REPLACE INTO user_guesses
            (user_id, post_id, comment_id, guess, is_correct, guessed_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, post_id, comment_id, guess, int(is_correct)))
        conn.commit()
        return cursor.rowcount > 0

def get_user_progress(user_id: int, post_id: int, force_turso: bool = None) -> Dict:
    """Get user's progress on a specific post"""
    with get_db_connection(force_turso) as conn:
        # Get all non-deleted guesses for this user/post
        guesses = conn.execute("""
            SELECT comment_id, guess, is_correct, guessed_at
            FROM user_guesses
            WHERE user_id = ? AND post_id = ? AND is_deleted = 0
            ORDER BY guessed_at
        """, (user_id, post_id)).fetchall()

        guess_data = [dict(zip(['comment_id', 'guess', 'is_correct', 'guessed_at'], row)) for row in guesses]

        # Calculate stats
        total_guesses = len(guess_data)
        correct_guesses = sum(1 for g in guess_data if g['is_correct'])

        return {
            'total_guesses': total_guesses,
            'correct_guesses': correct_guesses,
            'accuracy': correct_guesses / total_guesses if total_guesses > 0 else 0,
            'guesses': guess_data
        }

def get_user_all_progress(user_id: int, force_turso: bool = None) -> Dict[int, Dict]:
    """Get user's progress across all posts"""
    with get_db_connection(force_turso) as conn:
        # Get progress for each post this user has guessed on (non-deleted only)
        rows = conn.execute("""
            SELECT
                post_id,
                COUNT(*) as total_guesses,
                SUM(is_correct) as correct_guesses
            FROM user_guesses
            WHERE user_id = ? AND is_deleted = 0
            GROUP BY post_id
        """, (user_id,)).fetchall()

        progress = {}
        for row in rows:
            post_id = row[0]
            total = row[1]
            correct = row[2]

            progress[post_id] = {
                'total_guesses': total,
                'correct_guesses': correct,
                'accuracy': correct / total if total > 0 else 0
            }

        return progress

def reset_user_progress(user_id: int, post_id: int, force_turso: bool = None) -> bool:
    """Reset user's progress on a specific post (soft delete their guesses)"""
    with get_db_connection(force_turso) as conn:
        cursor = conn.execute("""
            UPDATE user_guesses
            SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND post_id = ? AND is_deleted = 0
        """, (user_id, post_id))
        conn.commit()
        return cursor.rowcount > 0

# Initialize database on module import
init_database()