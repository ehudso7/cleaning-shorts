#!/usr/bin/env python3
"""
Admin utilities for managing the Cleaning Shorts app.

Commands:
    python scripts/admin.py stats           - Show database stats
    python scripts/admin.py users           - List recent users
    python scripts/admin.py templates       - List template counts
    python scripts/admin.py deactivate ID   - Deactivate a template
    python scripts/admin.py activate ID     - Activate a template
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

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


def cmd_stats(client, args):
    """Show database statistics."""
    print("\n📊 Database Statistics")
    print("=" * 40)

    # Users
    users = client.table("users").select("id", count="exact").execute()
    print(f"Users: {users.count or 0}")

    # Active subscriptions
    active = (
        client.table("users")
        .select("id", count="exact")
        .eq("subscription_status", "active")
        .execute()
    )
    print(f"Active subscriptions: {active.count or 0}")

    # Templates
    templates = client.table("content_templates").select("id", count="exact").execute()
    active_templates = (
        client.table("content_templates")
        .select("id", count="exact")
        .eq("is_active", True)
        .execute()
    )
    print(f"Templates: {templates.count or 0} ({active_templates.count or 0} active)")

    # Deliveries
    deliveries = client.table("daily_deliveries").select("id", count="exact").execute()
    print(f"Total deliveries: {deliveries.count or 0}")

    # Refunds
    refunds = client.table("refund_log").select("id", count="exact").execute()
    print(f"Refunds processed: {refunds.count or 0}")


def cmd_users(client, args):
    """List recent users."""
    print("\n👤 Recent Users")
    print("=" * 60)

    result = (
        client.table("users")
        .select("id, email, subscription_status, created_at")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )

    for user in result.data or []:
        status = user.get("subscription_status", "unknown")
        email = user.get("email", "")[:30]
        created = user.get("created_at", "")[:10]
        print(f"  [{status:10}] {email:30} ({created})")


def cmd_templates(client, args):
    """Show template statistics by service type."""
    print("\n📝 Template Statistics")
    print("=" * 40)

    service_types = ["deep_clean", "airbnb", "move_out"]

    for stype in service_types:
        total = (
            client.table("content_templates")
            .select("id", count="exact")
            .eq("service_type", stype)
            .execute()
        )
        active = (
            client.table("content_templates")
            .select("id", count="exact")
            .eq("service_type", stype)
            .eq("is_active", True)
            .execute()
        )
        print(f"  {stype:15} {active.count or 0:3} active / {total.count or 0:3} total")


def cmd_deactivate(client, args):
    """Deactivate a template by ID."""
    template_id = args.id

    result = (
        client.table("content_templates")
        .update({"is_active": False})
        .eq("id", template_id)
        .execute()
    )

    if result.data:
        print(f"✓ Template {template_id} deactivated")
    else:
        print(f"✗ Template {template_id} not found")


def cmd_activate(client, args):
    """Activate a template by ID."""
    template_id = args.id

    result = (
        client.table("content_templates")
        .update({"is_active": True})
        .eq("id", template_id)
        .execute()
    )

    if result.data:
        print(f"✓ Template {template_id} activated")
    else:
        print(f"✗ Template {template_id} not found")


def main():
    parser = argparse.ArgumentParser(description="Admin utilities")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Stats command
    subparsers.add_parser("stats", help="Show database statistics")

    # Users command
    subparsers.add_parser("users", help="List recent users")

    # Templates command
    subparsers.add_parser("templates", help="Show template counts")

    # Deactivate command
    deactivate_parser = subparsers.add_parser("deactivate", help="Deactivate a template")
    deactivate_parser.add_argument("id", type=int, help="Template ID")

    # Activate command
    activate_parser = subparsers.add_parser("activate", help="Activate a template")
    activate_parser.add_argument("id", type=int, help="Template ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    client = get_client()

    commands = {
        "stats": cmd_stats,
        "users": cmd_users,
        "templates": cmd_templates,
        "deactivate": cmd_deactivate,
        "activate": cmd_activate,
    }

    commands[args.command](client, args)


if __name__ == "__main__":
    main()
