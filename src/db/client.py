"""
Supabase client configuration.
Two clients: one for user operations (RLS), one for admin operations.
"""

import os
from functools import lru_cache
from supabase import create_client, Client


@lru_cache()
def get_supabase_client() -> Client:
    """
    Get Supabase client with anon key (respects RLS).
    Use this for all user-facing operations.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

    return create_client(url, key)


@lru_cache()
def get_admin_client() -> Client:
    """
    Get Supabase client with service role key (bypasses RLS).
    Use this ONLY for:
    - Webhook handlers
    - Admin operations
    - Background jobs
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

    return create_client(url, key)
