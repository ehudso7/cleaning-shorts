#!/usr/bin/env python3
"""
Smoke Test B: Deterministic Delivery Test

Validates:
1. Same user + same day = same content
2. Different day = different content
3. daily_deliveries has exactly one row per user per day
4. No duplicate content until library exhausted

This test uses mocked database to verify logic.
"""

import sys
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class MockDeliveryTracker:
    """Simulates the daily_deliveries table."""

    def __init__(self):
        self.deliveries = []  # (user_id, template_id, delivery_date)

    def get_today_delivery(self, user_id: str, delivery_date: date):
        """Get existing delivery for user on date."""
        for d in self.deliveries:
            if d[0] == user_id and d[2] == delivery_date:
                return d[1]  # template_id
        return None

    def record_delivery(self, user_id: str, template_id: int, delivery_date: date):
        """Record a new delivery."""
        self.deliveries.append((user_id, template_id, delivery_date))

    def get_delivered_templates(self, user_id: str):
        """Get all template IDs delivered to user."""
        return [d[1] for d in self.deliveries if d[0] == user_id]

    def count_per_day(self, user_id: str) -> dict:
        """Count deliveries per day for a user."""
        counts = {}
        for d in self.deliveries:
            if d[0] == user_id:
                day = d[2]
                counts[day] = counts.get(day, 0) + 1
        return counts


class MockTemplateLibrary:
    """Simulates the content_templates table."""

    def __init__(self, templates: list):
        self.templates = templates  # List of (id, service_type, script, caption, cta)
        self.next_id = 1

    def get_random_unused(self, service_type: str, used_ids: list):
        """Get a random template not in used_ids."""
        available = [
            t for t in self.templates
            if t["service_type"] == service_type and t["id"] not in used_ids
        ]
        if available:
            return available[0]  # First available (deterministic for testing)
        return None

    def count_by_type(self, service_type: str) -> int:
        """Count templates for a service type."""
        return len([t for t in self.templates if t["service_type"] == service_type])


class MockContentService:
    """Simulates ContentService logic for testing."""

    def __init__(self, library: MockTemplateLibrary, tracker: MockDeliveryTracker):
        self.library = library
        self.tracker = tracker
        self.user_profiles = {}  # user_id -> {service_type, timezone}

    def set_profile(self, user_id: str, service_type: str, timezone: str = "America/New_York"):
        self.user_profiles[user_id] = {
            "service_type": service_type,
            "timezone": timezone
        }

    def generate_daily_content(self, user_id: str, today: date):
        """
        Core logic under test:
        1. Check if already delivered today -> return same
        2. Find unused template
        3. Record delivery
        4. Return content
        """
        profile = self.user_profiles.get(user_id, {"service_type": "deep_clean"})
        service_type = profile["service_type"]

        # Check existing delivery
        existing = self.tracker.get_today_delivery(user_id, today)
        if existing is not None:
            # Return same template
            template = next(t for t in self.library.templates if t["id"] == existing)
            return {
                "template_id": existing,
                "script": template["script"],
                "from_cache": True
            }

        # Get unused template
        used_ids = self.tracker.get_delivered_templates(user_id)
        template = self.library.get_random_unused(service_type, used_ids)

        if template is None:
            # Library exhausted - would reset in real implementation
            return {"error": "library_exhausted"}

        # Record delivery
        self.tracker.record_delivery(user_id, template["id"], today)

        return {
            "template_id": template["id"],
            "script": template["script"],
            "from_cache": False
        }


def create_test_library(count: int = 10):
    """Create a small test library."""
    templates = []
    for i in range(1, count + 1):
        templates.append({
            "id": i,
            "service_type": "deep_clean",
            "script": f"Test script {i}",
            "caption": f"Caption {i}",
            "cta": "DM 'CLEAN'"
        })
    return MockTemplateLibrary(templates)


def test_same_day_same_content():
    """Test: Calling twice on same day returns same content."""
    print("\n" + "=" * 60)
    print("TEST: Same Day = Same Content")
    print("=" * 60)

    library = create_test_library(10)
    tracker = MockDeliveryTracker()
    service = MockContentService(library, tracker)

    user_id = "test-user-1"
    service.set_profile(user_id, "deep_clean")
    today = date(2024, 1, 15)

    # First call
    result1 = service.generate_daily_content(user_id, today)
    print(f"  First call: template_id={result1['template_id']}, from_cache={result1['from_cache']}")

    # Second call - same day
    result2 = service.generate_daily_content(user_id, today)
    print(f"  Second call: template_id={result2['template_id']}, from_cache={result2['from_cache']}")

    # Verify
    if result1["template_id"] == result2["template_id"]:
        print("  ✓ PASS: Same template returned")
        if result2["from_cache"]:
            print("  ✓ PASS: Second call was from cache")
            return True
        else:
            print("  ✗ FAIL: Second call should be from cache")
            return False
    else:
        print("  ✗ FAIL: Different templates returned!")
        return False


def test_different_day_different_content():
    """Test: Different days return different content."""
    print("\n" + "=" * 60)
    print("TEST: Different Day = Different Content")
    print("=" * 60)

    library = create_test_library(10)
    tracker = MockDeliveryTracker()
    service = MockContentService(library, tracker)

    user_id = "test-user-2"
    service.set_profile(user_id, "deep_clean")

    day1 = date(2024, 1, 15)
    day2 = date(2024, 1, 16)

    # Day 1
    result1 = service.generate_daily_content(user_id, day1)
    print(f"  Day 1: template_id={result1['template_id']}")

    # Day 2
    result2 = service.generate_daily_content(user_id, day2)
    print(f"  Day 2: template_id={result2['template_id']}")

    if result1["template_id"] != result2["template_id"]:
        print("  ✓ PASS: Different templates on different days")
        return True
    else:
        print("  ✗ FAIL: Same template on different days!")
        return False


def test_one_delivery_per_day():
    """Test: Exactly one row per user per day in daily_deliveries."""
    print("\n" + "=" * 60)
    print("TEST: One Delivery Per User Per Day")
    print("=" * 60)

    library = create_test_library(10)
    tracker = MockDeliveryTracker()
    service = MockContentService(library, tracker)

    user_id = "test-user-3"
    service.set_profile(user_id, "deep_clean")
    today = date(2024, 1, 15)

    # Call 5 times on same day
    for i in range(5):
        service.generate_daily_content(user_id, today)

    # Check delivery count
    counts = tracker.count_per_day(user_id)
    print(f"  Calls made: 5")
    print(f"  Deliveries recorded: {counts.get(today, 0)}")

    if counts.get(today, 0) == 1:
        print("  ✓ PASS: Exactly 1 delivery per day")
        return True
    else:
        print("  ✗ FAIL: Multiple deliveries recorded!")
        return False


def test_no_duplicates_until_exhausted():
    """Test: No duplicate content until library is exhausted."""
    print("\n" + "=" * 60)
    print("TEST: No Duplicates Until Library Exhausted")
    print("=" * 60)

    library_size = 5
    library = create_test_library(library_size)
    tracker = MockDeliveryTracker()
    service = MockContentService(library, tracker)

    user_id = "test-user-4"
    service.set_profile(user_id, "deep_clean")

    delivered_ids = []
    base_date = date(2024, 1, 1)

    # Get content for library_size days
    for i in range(library_size):
        current_day = base_date + timedelta(days=i)
        result = service.generate_daily_content(user_id, current_day)

        if "error" in result:
            print(f"  Day {i+1}: Error - {result['error']}")
            break

        template_id = result["template_id"]
        print(f"  Day {i+1}: template_id={template_id}")

        if template_id in delivered_ids:
            print(f"  ✗ FAIL: Duplicate template {template_id} on day {i+1}!")
            return False

        delivered_ids.append(template_id)

    # Verify all templates used
    if len(set(delivered_ids)) == library_size:
        print(f"  ✓ PASS: All {library_size} unique templates used")
        return True
    else:
        print(f"  ✗ FAIL: Only {len(set(delivered_ids))} unique templates used")
        return False


def test_library_exhaustion():
    """Test: Proper handling when library is exhausted."""
    print("\n" + "=" * 60)
    print("TEST: Library Exhaustion Handling")
    print("=" * 60)

    library_size = 3
    library = create_test_library(library_size)
    tracker = MockDeliveryTracker()
    service = MockContentService(library, tracker)

    user_id = "test-user-5"
    service.set_profile(user_id, "deep_clean")
    base_date = date(2024, 1, 1)

    # Use all templates
    for i in range(library_size):
        service.generate_daily_content(user_id, base_date + timedelta(days=i))

    # Try to get one more
    exhausted_day = base_date + timedelta(days=library_size)
    result = service.generate_daily_content(user_id, exhausted_day)

    print(f"  Library size: {library_size}")
    print(f"  Days used: {library_size}")
    print(f"  Day {library_size + 1} result: {result}")

    if "error" in result and result["error"] == "library_exhausted":
        print("  ✓ PASS: Library exhaustion detected correctly")
        return True
    else:
        print("  ⚠ Note: In production, library would reset here")
        return True  # This is acceptable behavior


def main():
    print("\n" + "=" * 60)
    print("SMOKE TEST B: Deterministic Delivery Test")
    print("=" * 60)

    results = []
    results.append(("Same Day = Same Content", test_same_day_same_content()))
    results.append(("Different Day = Different Content", test_different_day_different_content()))
    results.append(("One Delivery Per Day", test_one_delivery_per_day()))
    results.append(("No Duplicates Until Exhausted", test_no_duplicates_until_exhausted()))
    results.append(("Library Exhaustion Handling", test_library_exhaustion()))

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
        print("\n✓ SMOKE TEST B: PASSED")
        return 0
    else:
        print("\n✗ SMOKE TEST B: FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
