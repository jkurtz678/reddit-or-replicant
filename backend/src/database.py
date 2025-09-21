#!/usr/bin/env python3
"""
Database service for storing Reddit posts and generated comments.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager

DB_FILE = "replicant.db"

def init_database():
    """Initialize the SQLite database with required tables"""
    with sqlite3.connect(DB_FILE) as conn:
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

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    try:
        yield conn
    finally:
        conn.close()

def save_post(reddit_url: str, title: str, subreddit: str, 
              mixed_comments_data: dict, ai_count: int, total_count: int) -> int:
    """
    Save a processed Reddit post with mixed comments to the database
    
    Returns:
        The ID of the saved post
    """
    mixed_comments_json = json.dumps(mixed_comments_data)
    
    with get_db_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO posts (reddit_url, title, subreddit, mixed_comments_json, ai_count, total_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (reddit_url, title, subreddit, mixed_comments_json, ai_count, total_count))
        conn.commit()
        return cursor.lastrowid

def get_post_by_id(post_id: int) -> Optional[Dict]:
    """Get a post by ID with parsed JSON comments"""
    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT id, reddit_url, title, subreddit, mixed_comments_json, 
                   ai_count, total_count, created_at
            FROM posts 
            WHERE id = ?
        """, (post_id,)).fetchone()
        
        if row:
            return {
                'id': row['id'],
                'reddit_url': row['reddit_url'],
                'title': row['title'],
                'subreddit': row['subreddit'],
                'mixed_comments': json.loads(row['mixed_comments_json']),
                'ai_count': row['ai_count'],
                'total_count': row['total_count'],
                'created_at': row['created_at']
            }
        return None

def get_all_posts(include_deleted: bool = False) -> List[Dict]:
    """Get all posts (without full comment data for listing)"""
    with get_db_connection() as conn:
        if include_deleted:
            # Admin view: show all posts including deleted ones
            rows = conn.execute("""
                SELECT id, reddit_url, title, subreddit, ai_count, total_count, 
                       created_at, deleted_at, is_deleted
                FROM posts 
                ORDER BY created_at DESC
            """).fetchall()
        else:
            # Public view: only show non-deleted posts
            rows = conn.execute("""
                SELECT id, reddit_url, title, subreddit, ai_count, total_count, created_at
                FROM posts 
                WHERE is_deleted = 0
                ORDER BY created_at DESC
            """).fetchall()
        
        return [dict(row) for row in rows]

def post_exists(reddit_url: str) -> bool:
    """Check if a Reddit URL has already been processed"""
    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT 1 FROM posts WHERE reddit_url = ?
        """, (reddit_url,)).fetchone()
        return row is not None

def soft_delete_post(post_id: int) -> bool:
    """Soft delete a post by ID"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            UPDATE posts 
            SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP 
            WHERE id = ? AND is_deleted = 0
        """, (post_id,))
        conn.commit()
        return cursor.rowcount > 0

def restore_post(post_id: int) -> bool:
    """Restore a soft-deleted post by ID"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            UPDATE posts 
            SET is_deleted = 0, deleted_at = NULL 
            WHERE id = ? AND is_deleted = 1
        """, (post_id,))
        conn.commit()
        return cursor.rowcount > 0

def delete_post(post_id: int) -> bool:
    """Hard delete a post by ID (kept for backwards compatibility)"""
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        conn.commit()
        return cursor.rowcount > 0

# User management functions

def create_user(anonymous_id: str) -> int:
    """Create a new anonymous user"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO users (anonymous_id)
            VALUES (?)
        """, (anonymous_id,))
        conn.commit()
        return cursor.lastrowid

def get_user_by_anonymous_id(anonymous_id: str) -> Optional[Dict]:
    """Get user by anonymous ID"""
    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT id, anonymous_id, created_at
            FROM users 
            WHERE anonymous_id = ?
        """, (anonymous_id,)).fetchone()
        
        if row:
            return {
                'id': row['id'],
                'anonymous_id': row['anonymous_id'],
                'created_at': row['created_at']
            }
        return None

def get_or_create_user(anonymous_id: str) -> int:
    """Get existing user ID or create new user, return user ID"""
    user = get_user_by_anonymous_id(anonymous_id)
    if user:
        return user['id']
    else:
        return create_user(anonymous_id)

# User guess tracking functions

def save_user_guess(user_id: int, post_id: int, comment_id: str, guess: str, is_correct: bool) -> bool:
    """Save or update a user's guess for a specific comment"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            INSERT OR REPLACE INTO user_guesses 
            (user_id, post_id, comment_id, guess, is_correct, guessed_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, post_id, comment_id, guess, int(is_correct)))
        conn.commit()
        return cursor.rowcount > 0

def get_user_progress(user_id: int, post_id: int) -> Dict:
    """Get user's progress on a specific post"""
    with get_db_connection() as conn:
        # Get all non-deleted guesses for this user/post
        guesses = conn.execute("""
            SELECT comment_id, guess, is_correct, guessed_at
            FROM user_guesses 
            WHERE user_id = ? AND post_id = ? AND is_deleted = 0
            ORDER BY guessed_at
        """, (user_id, post_id)).fetchall()
        
        guess_data = [dict(row) for row in guesses]
        
        # Calculate stats
        total_guesses = len(guess_data)
        correct_guesses = sum(1 for g in guess_data if g['is_correct'])
        
        return {
            'total_guesses': total_guesses,
            'correct_guesses': correct_guesses,
            'accuracy': correct_guesses / total_guesses if total_guesses > 0 else 0,
            'guesses': guess_data
        }

def get_user_all_progress(user_id: int) -> Dict[int, Dict]:
    """Get user's progress across all posts"""
    with get_db_connection() as conn:
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
            post_id = row['post_id']
            total = row['total_guesses']
            correct = row['correct_guesses']
            
            progress[post_id] = {
                'total_guesses': total,
                'correct_guesses': correct,
                'accuracy': correct / total if total > 0 else 0
            }
        
        return progress

def reset_user_progress(user_id: int, post_id: int) -> bool:
    """Reset user's progress on a specific post (soft delete their guesses)"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            UPDATE user_guesses 
            SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND post_id = ? AND is_deleted = 0
        """, (user_id, post_id))
        conn.commit()
        return cursor.rowcount > 0

# Initialize database on module import
init_database()