#!/usr/bin/env python3
"""
Load content templates into the database.
Run this script to populate the content_templates table.

Usage:
    python scripts/load_templates.py

Or to load a specific service type:
    python scripts/load_templates.py --service deep_clean
"""

import argparse
import json
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


def load_templates_from_file(filepath: Path) -> list:
    """Load templates from a JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


def insert_templates(client, templates: list, batch_size: int = 50) -> int:
    """Insert templates in batches. Returns count of inserted."""
    inserted = 0

    for i in range(0, len(templates), batch_size):
        batch = templates[i:i + batch_size]

        # Prepare batch for insert
        records = []
        for t in batch:
            records.append({
                "service_type": t["service_type"],
                "script": t["script"],
                "caption": t["caption"],
                "cta": t["cta"],
                "category": t.get("category"),
                "is_active": True,
            })

        result = client.table("content_templates").insert(records).execute()
        inserted += len(result.data) if result.data else 0
        print(f"  Inserted batch {i // batch_size + 1}: {len(records)} templates")

    return inserted


def clear_templates(client, service_type: str = None):
    """Clear existing templates (optionally by service type)."""
    query = client.table("content_templates").delete()

    if service_type:
        query = query.eq("service_type", service_type)
    else:
        # Delete all - need a condition that matches all
        query = query.neq("id", -1)

    query.execute()


def main():
    parser = argparse.ArgumentParser(description="Load content templates into database")
    parser.add_argument(
        "--service",
        choices=["deep_clean", "airbnb", "move_out"],
        help="Only load templates for this service type"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing templates before loading"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be loaded without inserting"
    )

    args = parser.parse_args()

    # Find template files
    templates_dir = Path(__file__).parent.parent / "data" / "templates"

    files_to_load = []
    if args.service:
        files_to_load = [templates_dir / f"{args.service}.json"]
    else:
        files_to_load = list(templates_dir.glob("*.json"))

    # Load all templates
    all_templates = []
    for filepath in files_to_load:
        if filepath.exists():
            templates = load_templates_from_file(filepath)
            all_templates.extend(templates)
            print(f"Loaded {len(templates)} templates from {filepath.name}")
        else:
            print(f"Warning: {filepath} not found")

    print(f"\nTotal templates to load: {len(all_templates)}")

    # Count by service type
    by_type = {}
    for t in all_templates:
        stype = t["service_type"]
        by_type[stype] = by_type.get(stype, 0) + 1

    print("By service type:")
    for stype, count in by_type.items():
        print(f"  {stype}: {count}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made to database")
        return

    # Connect and load
    print("\nConnecting to database...")
    client = get_client()

    if args.clear:
        print("Clearing existing templates...")
        clear_templates(client, args.service)

    print("Inserting templates...")
    inserted = insert_templates(client, all_templates)

    print(f"\nDone! Inserted {inserted} templates.")


if __name__ == "__main__":
    main()
