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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

def get_all_posts() -> List[Dict]:
    """Get all posts (without full comment data for listing)"""
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT id, reddit_url, title, subreddit, ai_count, total_count, created_at
            FROM posts 
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

def delete_post(post_id: int) -> bool:
    """Delete a post by ID"""
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        conn.commit()
        return cursor.rowcount > 0

# Initialize database on module import
init_database()