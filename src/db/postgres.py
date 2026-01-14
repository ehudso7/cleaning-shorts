"""
Direct Postgres connection for testing and CI.

Supports multiple connection methods:
1. DATABASE_URL - Direct Postgres connection string (preferred for CI)
2. SUPABASE_DB_URL - Supabase direct connection string
3. Constructed from SUPABASE_URL + credentials

Usage:
    from src.db.postgres import get_postgres_connection

    with get_postgres_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM content_templates")
            count = cur.fetchone()[0]
"""

import os
import re
from typing import Optional
from urllib.parse import urlparse

import psycopg2
from psycopg2.extensions import connection


def get_database_url() -> str:
    """
    Get database connection URL from environment.

    Priority:
    1. DATABASE_URL (standard, used by most CI/CD platforms)
    2. SUPABASE_DB_URL (Supabase direct connection)
    3. Constructed from SUPABASE_URL (extract host) + SUPABASE_SERVICE_KEY

    Returns:
        PostgreSQL connection string

    Raises:
        ValueError: If no valid connection configuration found
    """
    # Option 1: Direct DATABASE_URL
    if database_url := os.environ.get("DATABASE_URL"):
        return database_url

    # Option 2: Supabase direct DB URL
    if supabase_db_url := os.environ.get("SUPABASE_DB_URL"):
        return supabase_db_url

    # Option 3: Construct from Supabase URL
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")

    if supabase_url and supabase_key:
        # Extract project ref from Supabase URL
        # Format: https://<project-ref>.supabase.co
        match = re.match(r'https://([^.]+)\.supabase\.co', supabase_url)
        if match:
            project_ref = match.group(1)
            # Supabase pooler connection format
            return f"postgresql://postgres.{project_ref}:{supabase_key}@aws-0-us-east-1.pooler.supabase.com:6543/postgres"

    raise ValueError(
        "No database connection configured. Set one of:\n"
        "  - DATABASE_URL: Direct PostgreSQL connection string\n"
        "  - SUPABASE_DB_URL: Supabase direct connection string\n"
        "  - SUPABASE_URL + SUPABASE_SERVICE_KEY: Supabase project credentials"
    )


def get_postgres_connection() -> connection:
    """
    Get a direct PostgreSQL connection.

    Returns:
        psycopg2 connection object

    Raises:
        psycopg2.Error: If connection fails
        ValueError: If no valid connection configuration
    """
    database_url = get_database_url()

    try:
        conn = psycopg2.connect(database_url)
        return conn
    except psycopg2.Error as e:
        raise psycopg2.Error(
            f"Failed to connect to database. Error: {e}\n"
            f"Check that DATABASE_URL is correct and the database is accessible."
        ) from e


def check_table_exists(conn: connection, table_name: str) -> bool:
    """
    Check if a table exists in the database.

    Args:
        conn: PostgreSQL connection
        table_name: Name of table to check

    Returns:
        True if table exists, False otherwise
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = %s
            )
        """, (table_name,))
        return cur.fetchone()[0]
