#!/usr/bin/env python3
"""
Content Inventory Gate Test

Validates that the content_templates table meets minimum inventory requirements
and data integrity invariants before allowing deploys/merges.

This gate prevents:
- Deployments with insufficient content templates
- Data corruption (nulls in required fields)
- Invalid CTAs or service types

Configuration via environment variables:
- MIN_TEMPLATES_TOTAL: Minimum total templates (default: 450)
- MIN_TEMPLATES_DEEP_CLEAN: Minimum deep_clean templates (default: 150)
- MIN_TEMPLATES_AIRBNB: Minimum airbnb templates (default: 150)
- MIN_TEMPLATES_MOVE_OUT: Minimum move_out templates (default: 150)
- REQUIRED_CTA: Required CTA text (default: "DM 'CLEAN' for pricing & availability.")

Usage:
    # Run with pytest
    pytest tests/test_content_inventory_gate.py -v

    # Run standalone
    python tests/test_content_inventory_gate.py

    # With custom thresholds
    MIN_TEMPLATES_TOTAL=500 pytest tests/test_content_inventory_gate.py -v
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class InventoryConfig:
    """Configuration for inventory gate thresholds."""
    min_total: int
    min_deep_clean: int
    min_airbnb: int
    min_move_out: int
    required_cta: str
    valid_service_types: frozenset

    @classmethod
    def from_env(cls) -> "InventoryConfig":
        """Load configuration from environment variables with defaults."""
        return cls(
            min_total=int(os.environ.get("MIN_TEMPLATES_TOTAL", "450")),
            min_deep_clean=int(os.environ.get("MIN_TEMPLATES_DEEP_CLEAN", "150")),
            min_airbnb=int(os.environ.get("MIN_TEMPLATES_AIRBNB", "150")),
            min_move_out=int(os.environ.get("MIN_TEMPLATES_MOVE_OUT", "150")),
            required_cta=os.environ.get(
                "REQUIRED_CTA",
                "DM 'CLEAN' for pricing & availability."
            ),
            valid_service_types=frozenset({"deep_clean", "airbnb", "move_out"}),
        )


# =============================================================================
# Database Queries (COUNT-based, efficient)
# =============================================================================

def get_total_template_count(conn) -> int:
    """Get total count of active templates."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*)
            FROM content_templates
            WHERE is_active = TRUE
        """)
        return cur.fetchone()[0]


def get_template_counts_by_service(conn) -> dict:
    """Get template counts grouped by service_type."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT service_type, COUNT(*)
            FROM content_templates
            WHERE is_active = TRUE
            GROUP BY service_type
        """)
        return dict(cur.fetchall())


def get_null_field_counts(conn) -> dict:
    """Get counts of rows with NULL values in required fields."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                SUM(CASE WHEN script IS NULL THEN 1 ELSE 0 END) as null_script,
                SUM(CASE WHEN caption IS NULL THEN 1 ELSE 0 END) as null_caption,
                SUM(CASE WHEN cta IS NULL THEN 1 ELSE 0 END) as null_cta,
                SUM(CASE WHEN service_type IS NULL THEN 1 ELSE 0 END) as null_service_type
            FROM content_templates
            WHERE is_active = TRUE
        """)
        row = cur.fetchone()
        return {
            "script": row[0] or 0,
            "caption": row[1] or 0,
            "cta": row[2] or 0,
            "service_type": row[3] or 0,
        }


def get_invalid_cta_count(conn, required_cta: str) -> int:
    """Get count of templates with incorrect CTA."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*)
            FROM content_templates
            WHERE is_active = TRUE
            AND cta != %s
        """, (required_cta,))
        return cur.fetchone()[0]


def get_invalid_service_type_count(conn, valid_types: frozenset) -> int:
    """Get count of templates with invalid service_type."""
    with conn.cursor() as cur:
        # Use ANY for set membership check
        cur.execute("""
            SELECT COUNT(*)
            FROM content_templates
            WHERE is_active = TRUE
            AND service_type NOT IN %s
        """, (tuple(valid_types),))
        return cur.fetchone()[0]


# =============================================================================
# Connection Helper
# =============================================================================

def get_db_connection():
    """
    Get database connection for tests.

    Returns connection or raises with clear diagnostic message.
    """
    try:
        from src.db.postgres import get_postgres_connection, check_table_exists
        conn = get_postgres_connection()

        # Verify table exists
        if not check_table_exists(conn, "content_templates"):
            conn.close()
            raise RuntimeError(
                "Table 'content_templates' does not exist.\n"
                "Run 'python scripts/setup_database.py' to create schema, then\n"
                "Run 'python scripts/load_templates.py' to load templates."
            )

        return conn
    except ImportError as e:
        raise RuntimeError(
            f"Failed to import database module: {e}\n"
            "Ensure psycopg2-binary is installed: pip install psycopg2-binary"
        ) from e
    except Exception as e:
        if "No database connection configured" in str(e):
            raise RuntimeError(
                "DATABASE_URL not set.\n\n"
                "For local testing:\n"
                "  export DATABASE_URL='postgresql://user:pass@localhost:5432/dbname'\n\n"
                "For CI, ensure DATABASE_URL is set in the workflow environment."
            ) from e
        raise


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def db_connection():
    """Provide database connection for all tests in module."""
    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def config():
    """Provide inventory configuration."""
    return InventoryConfig.from_env()


# =============================================================================
# Test Cases
# =============================================================================

class TestContentInventoryGate:
    """Content inventory validation tests."""

    def test_total_template_count(self, db_connection, config):
        """Test that total templates meet minimum threshold."""
        total = get_total_template_count(db_connection)

        assert total >= config.min_total, (
            f"INVENTORY GATE FAILED: Total templates below minimum\n"
            f"  Actual: {total}\n"
            f"  Required: {config.min_total}\n"
            f"  Action: Add more templates or adjust MIN_TEMPLATES_TOTAL"
        )

    def test_deep_clean_count(self, db_connection, config):
        """Test that deep_clean templates meet minimum threshold."""
        counts = get_template_counts_by_service(db_connection)
        actual = counts.get("deep_clean", 0)

        assert actual >= config.min_deep_clean, (
            f"INVENTORY GATE FAILED: deep_clean templates below minimum\n"
            f"  Actual: {actual}\n"
            f"  Required: {config.min_deep_clean}\n"
            f"  Action: Add more deep_clean templates"
        )

    def test_airbnb_count(self, db_connection, config):
        """Test that airbnb templates meet minimum threshold."""
        counts = get_template_counts_by_service(db_connection)
        actual = counts.get("airbnb", 0)

        assert actual >= config.min_airbnb, (
            f"INVENTORY GATE FAILED: airbnb templates below minimum\n"
            f"  Actual: {actual}\n"
            f"  Required: {config.min_airbnb}\n"
            f"  Action: Add more airbnb templates"
        )

    def test_move_out_count(self, db_connection, config):
        """Test that move_out templates meet minimum threshold."""
        counts = get_template_counts_by_service(db_connection)
        actual = counts.get("move_out", 0)

        assert actual >= config.min_move_out, (
            f"INVENTORY GATE FAILED: move_out templates below minimum\n"
            f"  Actual: {actual}\n"
            f"  Required: {config.min_move_out}\n"
            f"  Action: Add more move_out templates"
        )

    def test_no_null_scripts(self, db_connection, config):
        """Test that no templates have NULL script."""
        nulls = get_null_field_counts(db_connection)

        assert nulls["script"] == 0, (
            f"INVENTORY GATE FAILED: Found {nulls['script']} templates with NULL script\n"
            f"  Action: Fix or remove templates with NULL script values"
        )

    def test_no_null_captions(self, db_connection, config):
        """Test that no templates have NULL caption."""
        nulls = get_null_field_counts(db_connection)

        assert nulls["caption"] == 0, (
            f"INVENTORY GATE FAILED: Found {nulls['caption']} templates with NULL caption\n"
            f"  Action: Fix or remove templates with NULL caption values"
        )

    def test_no_null_ctas(self, db_connection, config):
        """Test that no templates have NULL cta."""
        nulls = get_null_field_counts(db_connection)

        assert nulls["cta"] == 0, (
            f"INVENTORY GATE FAILED: Found {nulls['cta']} templates with NULL cta\n"
            f"  Action: Fix or remove templates with NULL cta values"
        )

    def test_no_null_service_types(self, db_connection, config):
        """Test that no templates have NULL service_type."""
        nulls = get_null_field_counts(db_connection)

        assert nulls["service_type"] == 0, (
            f"INVENTORY GATE FAILED: Found {nulls['service_type']} templates with NULL service_type\n"
            f"  Action: Fix or remove templates with NULL service_type values"
        )

    def test_all_ctas_match_required(self, db_connection, config):
        """Test that all templates have the required CTA."""
        invalid_count = get_invalid_cta_count(db_connection, config.required_cta)

        assert invalid_count == 0, (
            f"INVENTORY GATE FAILED: Found {invalid_count} templates with invalid CTA\n"
            f"  Required CTA: {config.required_cta!r}\n"
            f"  Action: Update templates to use the required CTA format"
        )

    def test_all_service_types_valid(self, db_connection, config):
        """Test that all templates have valid service_type."""
        invalid_count = get_invalid_service_type_count(
            db_connection, config.valid_service_types
        )

        assert invalid_count == 0, (
            f"INVENTORY GATE FAILED: Found {invalid_count} templates with invalid service_type\n"
            f"  Valid types: {sorted(config.valid_service_types)}\n"
            f"  Action: Fix templates with invalid service_type values"
        )


# =============================================================================
# Standalone Runner (for non-pytest execution)
# =============================================================================

def run_standalone() -> int:
    """
    Run inventory gate as standalone script.

    Returns:
        0 if all checks pass, 1 if any fail
    """
    print("\n" + "=" * 70)
    print("CONTENT INVENTORY GATE")
    print("=" * 70)

    # Load configuration
    config = InventoryConfig.from_env()
    print("\nConfiguration:")
    print(f"  MIN_TEMPLATES_TOTAL: {config.min_total}")
    print(f"  MIN_TEMPLATES_DEEP_CLEAN: {config.min_deep_clean}")
    print(f"  MIN_TEMPLATES_AIRBNB: {config.min_airbnb}")
    print(f"  MIN_TEMPLATES_MOVE_OUT: {config.min_move_out}")
    print(f"  REQUIRED_CTA: {config.required_cta!r}")

    # Connect to database
    print("\nConnecting to database...")
    try:
        conn = get_db_connection()
    except RuntimeError as e:
        print(f"\n✗ FAILED: {e}")
        return 1

    results = []

    # Test 1: Total count
    print("\n" + "-" * 50)
    print("TEST: Total Template Count")
    total = get_total_template_count(conn)
    passed = total >= config.min_total
    results.append(("Total Count", passed))
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {total} templates (min: {config.min_total})")

    # Test 2-4: Per-service counts
    counts = get_template_counts_by_service(conn)

    for service_type, min_count in [
        ("deep_clean", config.min_deep_clean),
        ("airbnb", config.min_airbnb),
        ("move_out", config.min_move_out),
    ]:
        print("\n" + "-" * 50)
        print(f"TEST: {service_type} Template Count")
        actual = counts.get(service_type, 0)
        passed = actual >= min_count
        results.append((f"{service_type} Count", passed))
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {actual} templates (min: {min_count})")

    # Test 5-8: Null checks
    print("\n" + "-" * 50)
    print("TEST: No NULL Values in Required Fields")
    nulls = get_null_field_counts(conn)

    for field, null_count in nulls.items():
        passed = null_count == 0
        results.append((f"No NULL {field}", passed))
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {field} has {null_count} NULL values")

    # Test 9: CTA validation
    print("\n" + "-" * 50)
    print("TEST: All CTAs Match Required Format")
    invalid_cta = get_invalid_cta_count(conn, config.required_cta)
    passed = invalid_cta == 0
    results.append(("Valid CTAs", passed))
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {invalid_cta} invalid CTAs found")

    # Test 10: Service type validation
    print("\n" + "-" * 50)
    print("TEST: All Service Types Valid")
    invalid_service = get_invalid_service_type_count(conn, config.valid_service_types)
    passed = invalid_service == 0
    results.append(("Valid Service Types", passed))
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {invalid_service} invalid service_types found")

    # Summary
    conn.close()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed_count = sum(1 for _, p in results if p)
    failed_count = sum(1 for _, p in results if not p)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")

    print(f"\n  Passed: {passed_count}")
    print(f"  Failed: {failed_count}")

    if failed_count == 0:
        print("\n" + "=" * 70)
        print("✓ CONTENT INVENTORY GATE: PASSED")
        print("=" * 70)
        return 0
    else:
        print("\n" + "=" * 70)
        print("✗ CONTENT INVENTORY GATE: FAILED")
        print("  Deployment blocked until issues are resolved.")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(run_standalone())
