#!/usr/bin/env python3
"""
Set up the database schema.
Run this once to create all tables and indexes.

Usage:
    python scripts/setup_database.py

Note: This creates tables in Supabase. For production, you may want
to run the SQL directly in the Supabase SQL editor for more control.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from supabase import create_client


def get_client():
    """Get Supabase client with service role key."""
    load_dotenv()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env"
        )

    return create_client(url, key)


def print_schema():
    """Print the schema SQL for manual execution."""
    from src.db.schema import SCHEMA_SQL, INDEXES_SQL

    print("=" * 60)
    print("DATABASE SCHEMA")
    print("=" * 60)
    print("\nCopy and paste this SQL into Supabase SQL Editor:\n")
    print("-" * 60)
    print(SCHEMA_SQL)
    print("-" * 60)
    print("\nINDEXES:")
    print("-" * 60)
    print(INDEXES_SQL)
    print("-" * 60)


def main():
    print("Cleaning Shorts App - Database Setup")
    print("=" * 40)
    print()
    print("This script outputs the SQL schema for your database.")
    print("For safety, please run the SQL manually in Supabase.")
    print()

    print_schema()

    print()
    print("Next steps:")
    print("1. Go to your Supabase project dashboard")
    print("2. Open the SQL Editor")
    print("3. Paste the schema SQL above and run it")
    print("4. Then run: python scripts/load_templates.py")


if __name__ == "__main__":
    main()
