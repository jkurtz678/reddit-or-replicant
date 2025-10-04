#!/usr/bin/env python3
"""
Test script to verify Turso database connection and setup
"""

import os
import sys
sys.path.append('src')

from dotenv import load_dotenv
load_dotenv()

from database import use_turso, init_database, get_db_connection

def test_turso_connection():
    print("Testing Turso configuration...")
    print(f"TURSO_DATABASE_URL set: {bool(os.getenv('TURSO_DATABASE_URL'))}")
    print(f"TURSO_AUTH_TOKEN set: {bool(os.getenv('TURSO_AUTH_TOKEN'))}")
    print(f"Using Turso: {use_turso()}")

    if use_turso():
        print("\n✅ Turso configuration detected!")
        print("Initializing database tables...")
        try:
            init_database()
            print("✅ Database tables initialized successfully!")

            print("Testing database connection...")
            with get_db_connection() as conn:
                # Test a simple query
                result = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                print(f"✅ Connection successful! Found {len(result)} tables")
                for row in result:
                    print(f"  - {row[0] if hasattr(row, '__getitem__') else row}")

        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    else:
        print("\n⚠️  Turso not configured, using local SQLite")
        try:
            init_database()
            print("✅ Local SQLite initialized successfully!")
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    return True

if __name__ == "__main__":
    test_turso_connection()