#!/usr/bin/env python3
"""
Run all smoke tests in order.

Usage:
    python tests/run_all.py
"""

import subprocess
import sys
from pathlib import Path


def run_test(name: str, script: str) -> bool:
    """Run a test script and return success status."""
    print(f"\n{'='*70}")
    print(f"RUNNING: {name}")
    print(f"{'='*70}")

    result = subprocess.run(
        [sys.executable, script],
        capture_output=False,
    )

    return result.returncode == 0


def main():
    print("\n" + "=" * 70)
    print("CLEANING SHORTS BACKEND - SMOKE TEST SUITE")
    print("=" * 70)

    tests_dir = Path(__file__).parent
    tests = [
        ("A) Templates Load Verification", tests_dir / "test_a_templates.py"),
        ("B) Deterministic Delivery", tests_dir / "test_b_deterministic_delivery.py"),
        ("C) Timezone Boundary", tests_dir / "test_c_timezone_boundary.py"),
        ("D) Stripe Subscription Sync", tests_dir / "test_d_stripe_sync.py"),
    ]

    results = []
    for name, script in tests:
        if script.exists():
            passed = run_test(name, str(script))
            results.append((name, passed))
        else:
            print(f"⚠ Skipping {name}: {script} not found")
            results.append((name, None))

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    for name, passed in results:
        if passed is None:
            status = "⚠ SKIP"
        elif passed:
            status = "✓ PASS"
        else:
            status = "✗ FAIL"
        print(f"  {status}: {name}")

    passed_count = sum(1 for _, r in results if r is True)
    failed_count = sum(1 for _, r in results if r is False)
    skipped_count = sum(1 for _, r in results if r is None)

    print(f"\n  Passed: {passed_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Skipped: {skipped_count}")

    if failed_count == 0:
        print("\n" + "=" * 70)
        print("ALL SMOKE TESTS PASSED")
        print("=" * 70)
        return 0
    else:
        print("\n" + "=" * 70)
        print("SOME TESTS FAILED - SEE ABOVE FOR DETAILS")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
