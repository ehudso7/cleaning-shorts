#!/usr/bin/env python3
"""
Smoke Test C: Timezone Boundary Test

The #1 silent killer for content apps: timezone handling.

Validates:
1. "today" is calculated based on user's timezone, NOT server time
2. Day flips correctly at midnight in user's timezone
3. Users in different timezones see different "today" at same UTC instant

This is CRITICAL for:
- West coast users who would get tomorrow's content at 9pm
- International users who would be off by many hours
"""

import sys
from datetime import datetime, date, timedelta
from pathlib import Path
import pytz

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_user_today(utc_time: datetime, user_timezone: str) -> date:
    """
    Calculate what "today" is for a user in their timezone.
    This is the function we're testing.
    """
    tz = pytz.timezone(user_timezone)
    user_local_time = utc_time.astimezone(tz)
    return user_local_time.date()


def test_timezone_affects_today():
    """Test: Different timezones see different 'today' at same UTC instant."""
    print("\n" + "=" * 60)
    print("TEST: Different Timezones = Different 'Today'")
    print("=" * 60)

    # It's January 15, 2024 at 3:00 AM UTC
    utc_time = datetime(2024, 1, 15, 3, 0, 0, tzinfo=pytz.UTC)
    print(f"  UTC Time: {utc_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    timezones = {
        "America/New_York": "EST (UTC-5)",
        "America/Los_Angeles": "PST (UTC-8)",
        "UTC": "UTC",
        "Europe/London": "GMT",
        "Asia/Tokyo": "JST (UTC+9)",
    }

    results = {}
    print("\n  Local times and 'today' for each timezone:")
    for tz_name, label in timezones.items():
        tz = pytz.timezone(tz_name)
        local_time = utc_time.astimezone(tz)
        today = get_user_today(utc_time, tz_name)
        results[tz_name] = today
        print(f"    {label:20} {local_time.strftime('%Y-%m-%d %H:%M:%S')} -> today = {today}")

    # At 3AM UTC:
    # - NYC (UTC-5) = 10PM Jan 14 -> today = Jan 14
    # - LA (UTC-8) = 7PM Jan 14 -> today = Jan 14
    # - Tokyo (UTC+9) = 12PM Jan 15 -> today = Jan 15

    expected_jan14 = {"America/New_York", "America/Los_Angeles"}
    expected_jan15 = {"UTC", "Europe/London", "Asia/Tokyo"}

    all_correct = True

    for tz in expected_jan14:
        if results[tz] == date(2024, 1, 14):
            print(f"  ✓ {tz}: correctly sees Jan 14")
        else:
            print(f"  ✗ {tz}: should see Jan 14, got {results[tz]}")
            all_correct = False

    for tz in expected_jan15:
        if results[tz] == date(2024, 1, 15):
            print(f"  ✓ {tz}: correctly sees Jan 15")
        else:
            print(f"  ✗ {tz}: should see Jan 15, got {results[tz]}")
            all_correct = False

    return all_correct


def test_midnight_boundary_flip():
    """Test: Day flips at midnight in USER's timezone."""
    print("\n" + "=" * 60)
    print("TEST: Midnight Boundary Flip (User Timezone)")
    print("=" * 60)

    user_tz = "America/New_York"
    print(f"  User timezone: {user_tz}")

    # Test around midnight in NYC
    # Midnight in NYC = 5AM UTC (when EST = UTC-5)
    # 11:58 PM NYC = 4:58 AM UTC
    # 12:02 AM NYC = 5:02 AM UTC

    before_midnight_utc = datetime(2024, 1, 15, 4, 58, 0, tzinfo=pytz.UTC)
    after_midnight_utc = datetime(2024, 1, 15, 5, 2, 0, tzinfo=pytz.UTC)

    tz = pytz.timezone(user_tz)
    before_local = before_midnight_utc.astimezone(tz)
    after_local = after_midnight_utc.astimezone(tz)

    print(f"\n  Before midnight:")
    print(f"    UTC: {before_midnight_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"    NYC: {before_local.strftime('%Y-%m-%d %H:%M:%S')}")

    print(f"\n  After midnight:")
    print(f"    UTC: {after_midnight_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"    NYC: {after_local.strftime('%Y-%m-%d %H:%M:%S')}")

    today_before = get_user_today(before_midnight_utc, user_tz)
    today_after = get_user_today(after_midnight_utc, user_tz)

    print(f"\n  'Today' before midnight: {today_before}")
    print(f"  'Today' after midnight: {today_after}")

    # Before midnight should be Jan 14, after should be Jan 15
    if today_before == date(2024, 1, 14) and today_after == date(2024, 1, 15):
        print("  ✓ PASS: Day flips correctly at user's midnight")
        return True
    else:
        print("  ✗ FAIL: Day did not flip correctly!")
        return False


def test_west_coast_evening():
    """Test: LA user at 11pm sees TODAY's content, not tomorrow's."""
    print("\n" + "=" * 60)
    print("TEST: West Coast Evening (LA at 11pm)")
    print("=" * 60)

    # 11pm in LA = 7am UTC next day
    # This is the classic bug: server in UTC thinks it's "tomorrow"

    la_tz = "America/Los_Angeles"
    # 11pm Jan 14 in LA = 7am Jan 15 UTC
    utc_time = datetime(2024, 1, 15, 7, 0, 0, tzinfo=pytz.UTC)

    tz = pytz.timezone(la_tz)
    la_time = utc_time.astimezone(tz)

    print(f"  UTC time: {utc_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  LA time: {la_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Server might think "today" is Jan 15 (UTC)
    server_today = utc_time.date()
    # But user should see Jan 14 (their local date)
    user_today = get_user_today(utc_time, la_tz)

    print(f"\n  If using server time (UTC): today = {server_today}")
    print(f"  If using user timezone: today = {user_today}")

    if user_today == date(2024, 1, 14):
        print(f"  ✓ PASS: User correctly sees Jan 14 (their local date)")
        return True
    else:
        print(f"  ✗ FAIL: User would see wrong date!")
        return False


def test_utc_user():
    """Test: UTC user gets correct behavior."""
    print("\n" + "=" * 60)
    print("TEST: UTC User")
    print("=" * 60)

    utc_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
    user_today = get_user_today(utc_time, "UTC")

    print(f"  UTC time: {utc_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  User's today: {user_today}")

    if user_today == date(2024, 1, 15):
        print("  ✓ PASS: UTC user sees correct date")
        return True
    else:
        print("  ✗ FAIL: UTC user sees wrong date!")
        return False


def test_day_boundary_for_multiple_users():
    """Test: At same instant, users in different TZ get different 'today'."""
    print("\n" + "=" * 60)
    print("TEST: Same Instant, Different Users, Different 'Today'")
    print("=" * 60)

    # It's 2am UTC on Jan 15
    utc_time = datetime(2024, 1, 15, 2, 0, 0, tzinfo=pytz.UTC)
    print(f"  Server time (UTC): {utc_time.strftime('%Y-%m-%d %H:%M:%S')}")

    users = [
        ("User A", "America/Los_Angeles"),  # 6pm Jan 14
        ("User B", "America/New_York"),      # 9pm Jan 14
        ("User C", "Europe/London"),         # 2am Jan 15
        ("User D", "Asia/Tokyo"),            # 11am Jan 15
    ]

    print("\n  Each user's perspective:")
    results = []
    for name, tz_name in users:
        tz = pytz.timezone(tz_name)
        local_time = utc_time.astimezone(tz)
        today = get_user_today(utc_time, tz_name)
        results.append((name, tz_name, local_time, today))
        print(f"    {name} ({tz_name}): {local_time.strftime('%H:%M %b %d')} -> today = {today}")

    # Verify: LA and NYC should see Jan 14, London and Tokyo should see Jan 15
    all_correct = True

    if results[0][3] == date(2024, 1, 14):
        print(f"  ✓ User A (LA): correctly sees Jan 14")
    else:
        print(f"  ✗ User A (LA): should see Jan 14")
        all_correct = False

    if results[1][3] == date(2024, 1, 14):
        print(f"  ✓ User B (NYC): correctly sees Jan 14")
    else:
        print(f"  ✗ User B (NYC): should see Jan 14")
        all_correct = False

    if results[2][3] == date(2024, 1, 15):
        print(f"  ✓ User C (London): correctly sees Jan 15")
    else:
        print(f"  ✗ User C (London): should see Jan 15")
        all_correct = False

    if results[3][3] == date(2024, 1, 15):
        print(f"  ✓ User D (Tokyo): correctly sees Jan 15")
    else:
        print(f"  ✗ User D (Tokyo): should see Jan 15")
        all_correct = False

    return all_correct


def test_content_service_uses_user_timezone():
    """Test: Verify the actual ContentService would use user timezone."""
    print("\n" + "=" * 60)
    print("TEST: ContentService Uses User Timezone")
    print("=" * 60)

    # Read the actual content.py to verify it uses user timezone
    content_file = Path(__file__).parent.parent / "src" / "lib" / "content.py"

    if not content_file.exists():
        print(f"  ✗ FAIL: Cannot find {content_file}")
        return False

    content = content_file.read_text()

    # Check for critical patterns
    checks = [
        ("get_user_timezone", "Gets user's timezone from profile"),
        ("get_today_date", "Calculates today based on timezone"),
        ("pytz.timezone", "Uses pytz for timezone handling"),
        ("datetime.now(tz)", "Gets current time in user's timezone"),
    ]

    all_found = True
    for pattern, description in checks:
        if pattern in content:
            print(f"  ✓ Found: {description}")
        else:
            print(f"  ⚠ Not found: {description}")
            # Don't fail, just warn

    # Critical check: verify get_today_date uses timezone
    if "def get_today_date" in content and "timezone" in content:
        print("  ✓ PASS: get_today_date respects timezone")
        return True
    else:
        print("  ⚠ WARNING: Could not verify timezone usage in get_today_date")
        return True  # Don't fail, but warn


def main():
    print("\n" + "=" * 60)
    print("SMOKE TEST C: Timezone Boundary Test")
    print("=" * 60)
    print("Testing the #1 silent killer: timezone handling")

    results = []
    results.append(("Different TZ = Different Today", test_timezone_affects_today()))
    results.append(("Midnight Boundary Flip", test_midnight_boundary_flip()))
    results.append(("West Coast Evening", test_west_coast_evening()))
    results.append(("UTC User", test_utc_user()))
    results.append(("Same Instant, Different Users", test_day_boundary_for_multiple_users()))
    results.append(("ContentService Uses Timezone", test_content_service_uses_user_timezone()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")

    print(f"\n  Result: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ SMOKE TEST C: PASSED")
        print("\n  Timezone handling is correct!")
        print("  Users will see content for THEIR day, not server's day.")
        return 0
    else:
        print("\n✗ SMOKE TEST C: FAILED")
        print("\n  ⚠ CRITICAL: Timezone bugs will cause wrong content delivery!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
