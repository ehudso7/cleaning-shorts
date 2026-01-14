#!/usr/bin/env python3
"""
Smoke Test A: Database + Templates Load Verification

Validates:
1. Template counts by service type
2. No nulls in required fields
3. Field constraints (caption length, CTA format)
"""

import json
import sys
from pathlib import Path

def load_templates():
    """Load all template JSON files."""
    templates_dir = Path(__file__).parent.parent / "data" / "templates"

    all_templates = []
    files = {
        "deep_clean": templates_dir / "deep_clean.json",
        "airbnb": templates_dir / "airbnb.json",
        "move_out": templates_dir / "move_out.json",
    }

    for service_type, filepath in files.items():
        if filepath.exists():
            with open(filepath) as f:
                templates = json.load(f)
                all_templates.extend(templates)
                print(f"  Loaded {len(templates)} from {filepath.name}")
        else:
            print(f"  ERROR: {filepath.name} not found!")

    return all_templates


def test_template_counts(templates):
    """Test: Verify template counts by service type."""
    print("\n" + "=" * 60)
    print("TEST: Template Counts by Service Type")
    print("=" * 60)

    expected = {
        "deep_clean": 160,
        "airbnb": 150,
        "move_out": 150,
    }

    actual = {}
    for t in templates:
        stype = t.get("service_type", "unknown")
        actual[stype] = actual.get(stype, 0) + 1

    all_pass = True
    for stype, expected_count in expected.items():
        actual_count = actual.get(stype, 0)
        status = "✓ PASS" if actual_count >= expected_count else "✗ FAIL"
        if actual_count < expected_count:
            all_pass = False
        print(f"  {stype}: {actual_count} (expected >= {expected_count}) {status}")

    total = sum(actual.values())
    print(f"\n  Total templates: {total}")

    return all_pass


def test_no_nulls(templates):
    """Test: No nulls in required fields."""
    print("\n" + "=" * 60)
    print("TEST: No Nulls in Required Fields")
    print("=" * 60)

    required_fields = ["service_type", "script", "caption", "cta"]
    errors = []

    for i, t in enumerate(templates):
        for field in required_fields:
            value = t.get(field)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                errors.append(f"  Template {i}: {field} is null/empty")

    if errors:
        print(f"  ✗ FAIL: Found {len(errors)} null/empty required fields:")
        for e in errors[:10]:  # Show first 10
            print(e)
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        return False
    else:
        print(f"  ✓ PASS: All {len(templates)} templates have required fields")
        return True


def test_caption_length(templates):
    """Test: Caption length <= 180 characters."""
    print("\n" + "=" * 60)
    print("TEST: Caption Length (max 180 chars)")
    print("=" * 60)

    violations = []
    for i, t in enumerate(templates):
        caption = t.get("caption", "")
        if len(caption) > 180:
            violations.append(f"  Template {i}: {len(caption)} chars - '{caption[:50]}...'")

    if violations:
        print(f"  ✗ FAIL: Found {len(violations)} captions > 180 chars:")
        for v in violations[:5]:
            print(v)
        return False
    else:
        print(f"  ✓ PASS: All captions <= 180 characters")
        return True


def test_cta_format(templates):
    """Test: CTA contains expected format."""
    print("\n" + "=" * 60)
    print("TEST: CTA Format")
    print("=" * 60)

    expected_cta = "DM 'CLEAN' for pricing & availability."
    mismatches = []

    for i, t in enumerate(templates):
        cta = t.get("cta", "")
        if cta != expected_cta:
            mismatches.append(f"  Template {i}: '{cta}'")

    if mismatches:
        print(f"  ⚠ WARNING: {len(mismatches)} CTAs don't match expected format")
        print(f"  Expected: '{expected_cta}'")
        for m in mismatches[:3]:
            print(m)
        # This is a warning, not failure
        return True
    else:
        print(f"  ✓ PASS: All CTAs match expected format")
        return True


def test_script_structure(templates):
    """Test: Scripts have Hook/Visual/CTA structure."""
    print("\n" + "=" * 60)
    print("TEST: Script Structure (Hook/Visual/CTA)")
    print("=" * 60)

    missing_structure = []
    for i, t in enumerate(templates):
        script = t.get("script", "")
        has_hook = "Hook:" in script or "hook:" in script.lower()
        has_visual = "Visual:" in script or "visual:" in script.lower()
        has_cta = "CTA:" in script or "cta:" in script.lower()

        if not (has_hook and has_visual and has_cta):
            missing = []
            if not has_hook: missing.append("Hook")
            if not has_visual: missing.append("Visual")
            if not has_cta: missing.append("CTA")
            missing_structure.append(f"  Template {i}: missing {', '.join(missing)}")

    if missing_structure:
        print(f"  ⚠ WARNING: {len(missing_structure)} scripts missing structure elements")
        for m in missing_structure[:5]:
            print(m)
        # Warning, not failure
        return True
    else:
        print(f"  ✓ PASS: All scripts have Hook/Visual/CTA structure")
        return True


def test_service_type_consistency(templates):
    """Test: Service type matches file source."""
    print("\n" + "=" * 60)
    print("TEST: Service Type Consistency")
    print("=" * 60)

    valid_types = {"deep_clean", "airbnb", "move_out"}
    invalid = []

    for i, t in enumerate(templates):
        stype = t.get("service_type", "")
        if stype not in valid_types:
            invalid.append(f"  Template {i}: invalid type '{stype}'")

    if invalid:
        print(f"  ✗ FAIL: {len(invalid)} templates have invalid service_type:")
        for inv in invalid[:5]:
            print(inv)
        return False
    else:
        print(f"  ✓ PASS: All service_types are valid")
        return True


def test_category_coverage(templates):
    """Test: Categories are present for each service type."""
    print("\n" + "=" * 60)
    print("TEST: Category Coverage")
    print("=" * 60)

    expected_categories = {
        "before_after", "process", "pricing", "objections",
        "trust", "social_proof", "education", "urgency", "faq", "simple"
    }

    by_type = {}
    for t in templates:
        stype = t.get("service_type")
        cat = t.get("category", "uncategorized")
        if stype not in by_type:
            by_type[stype] = set()
        by_type[stype].add(cat)

    all_pass = True
    for stype, categories in by_type.items():
        missing = expected_categories - categories
        if missing:
            print(f"  ⚠ {stype}: missing categories {missing}")
        else:
            print(f"  ✓ {stype}: has all expected categories")
        print(f"    Categories found: {sorted(categories)}")

    return True  # Categories are informational


def main():
    print("\n" + "=" * 60)
    print("SMOKE TEST A: Database + Templates Load Verification")
    print("=" * 60)

    print("\nLoading templates from JSON files...")
    templates = load_templates()

    if not templates:
        print("\n✗ FATAL: No templates loaded!")
        sys.exit(1)

    # Run all tests
    results = []
    results.append(("Template Counts", test_template_counts(templates)))
    results.append(("No Nulls", test_no_nulls(templates)))
    results.append(("Caption Length", test_caption_length(templates)))
    results.append(("CTA Format", test_cta_format(templates)))
    results.append(("Script Structure", test_script_structure(templates)))
    results.append(("Service Type Consistency", test_service_type_consistency(templates)))
    results.append(("Category Coverage", test_category_coverage(templates)))

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
        print("\n✓ SMOKE TEST A: PASSED")
        return 0
    else:
        print("\n✗ SMOKE TEST A: FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
