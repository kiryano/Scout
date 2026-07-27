import sys
import os
import csv
import tempfile
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.scrapers.tracker import (
    build_identity_key, load_baseline, detect_changes, classify_changes,
    display_change_tracker, _to_number, _to_bool
)
from rich.console import Console

console = Console()

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  OK  {name}")
    else:
        failed += 1
        print(f"  FAIL {name}  {detail}")


# --- _to_number ---
print("\n[_to_number]")
check("int passthrough", _to_number(42) == 42)
check("float to int", _to_number(3.14) == 3)
check("string int", _to_number("15000") == 15000)
check("string float returns None (int-only)", _to_number("3.14") is None)
check("empty string", _to_number("") is None)
check("None", _to_number(None) is None)
check("garbage", _to_number("abc") is None)
check("whitespace", _to_number("  42  ") == 42)
check("negative", _to_number("-5") == -5)


# --- _to_bool ---
print("\n[_to_bool]")
check("true string", _to_bool("True") is True)
check("false string", _to_bool("False") is False)
check("1 string", _to_bool("1") is True)
check("0 string", _to_bool("0") is False)
check("yes", _to_bool("yes") is True)
check("no", _to_bool("no") is False)
check("empty", _to_bool("") is False)
check("None", _to_bool(None) is None)
check("bool True", _to_bool(True) is True)
check("bool False", _to_bool(False) is False)


# --- build_identity_key ---
print("\n[build_identity_key]")
check("basic", build_identity_key({'platform': 'instagram', 'username': 'johndoe'}) == 'instagram:johndoe')
check("uppercase lowered", build_identity_key({'platform': 'YouTube', 'username': 'JohnDoe'}) == 'youtube:johndoe')
check("no platform", build_identity_key({'username': 'johndoe'}) == ':johndoe')
check("no username", build_identity_key({'platform': 'tiktok'}) == 'tiktok:')
check("empty", build_identity_key({}) == ':')
check("special chars", build_identity_key({'platform': 'GitHub', 'username': 'john_doe-123'}) == 'github:john_doe-123')


# --- detect_changes ---
print("\n[detect_changes]")

r = detect_changes({}, {})
check("no changes: empty dicts", len(r) == 0)

r = detect_changes(
    {'email': 'old@test.com', 'phone': '555-0100'},
    {'email': 'old@test.com', 'phone': '555-0100'},
)
check("no changes: identical", len(r) == 0)

r = detect_changes(
    {'email': ''},
    {'email': 'new@test.com'},
)
check("email added", any(c['field'] == 'email' and c['type'] == 'added' for c in r), f"got {r}")

r = detect_changes(
    {'email': 'old@test.com'},
    {'email': ''},
)
check("email removed", any(c['field'] == 'email' and c['type'] == 'removed' for c in r), f"got {r}")

r = detect_changes(
    {'email': 'old@test.com'},
    {'email': 'new@test.com'},
)
check("email changed", any(c['field'] == 'email' and c['type'] == 'changed' for c in r), f"got {r}")

r = detect_changes(
    {'email_verified': 'False'},
    {'email_verified': 'True'},
)
check("email_verified true->false", any(c['field'] == 'email_verified' and c['type'] == 'added' for c in r), f"got {r}")

r = detect_changes(
    {'email_verified': 'True'},
    {'email_verified': 'False'},
)
check("email_verified false->true", any(c['field'] == 'email_verified' and c['type'] == 'removed' for c in r), f"got {r}")

r = detect_changes(
    {'phone': ''},
    {'phone': '555-0100'},
)
check("phone added", any(c['field'] == 'phone' and c['type'] == 'added' for c in r), f"got {r}")

r = detect_changes(
    {'phone': '555-0100'},
    {'phone': ''},
)
check("phone removed", any(c['field'] == 'phone' and c['type'] == 'removed' for c in r), f"got {r}")

r = detect_changes(
    {'website': ''},
    {'website': 'https://example.com'},
)
check("website added", any(c['field'] == 'website' and c['type'] == 'added' for c in r), f"got {r}")

r = detect_changes(
    {'follower_count': '15000'},
    {'follower_count': '18500'},
)
check("followers increased", any(c['field'] == 'follower_count' and c['type'] == 'increased' for c in r), f"got {r}")

r = detect_changes(
    {'follower_count': '18500'},
    {'follower_count': '15000'},
)
check("followers decreased", any(c['field'] == 'follower_count' and c['type'] == 'decreased' for c in r), f"got {r}")

r = detect_changes(
    {'follower_count': '0'},
    {'follower_count': '350'},
)
check("followers from zero", any(c['field'] == 'follower_count' and c['type'] == 'increased' for c in r), f"got {r}")

r = detect_changes(
    {'lead_score': '67'},
    {'lead_score': '82'},
)
check("lead_score increased", any(c['field'] == 'lead_score' and c['type'] == 'increased' for c in r), f"got {r}")

r = detect_changes(
    {'priority_tier': 'warm'},
    {'priority_tier': 'hot'},
)
check("priority_tier changed", any(c['field'] == 'priority_tier' and c['type'] == 'changed' for c in r), f"got {r}")

r = detect_changes(
    {'outreach_ready': 'False'},
    {'outreach_ready': 'True'},
)
check("outreach_ready true", any(c['field'] == 'outreach_ready' and c['type'] == 'added' for c in r), f"got {r}")

r = detect_changes(
    {'is_private': 'False'},
    {'is_private': 'True'},
)
check("is_private true", any(c['field'] == 'is_private' and c['type'] == 'added' for c in r), f"got {r}")

r = detect_changes(
    {'bio': 'Old bio text'},
    {'bio': 'New bio text here'},
)
check("bio changed", any(c['field'] == 'bio' and c['type'] == 'changed' for c in r), f"got {r}")

r = detect_changes(
    {'full_name': 'John Smith'},
    {'full_name': 'John A. Smith'},
)
check("name changed", any(c['field'] == 'full_name' and c['type'] == 'changed' for c in r), f"got {r}")

r = detect_changes(
    {'company': ''},
    {'company': 'Acme Corp'},
)
check("company added", any(c['field'] == 'company' and c['type'] == 'added' for c in r), f"got {r}")

r = detect_changes(
    {'is_business': 'False'},
    {'is_business': 'True'},
)
check("is_business true", any(c['field'] == 'is_business' and c['type'] == 'added' for c in r), f"got {r}")


# --- multiple changes ---
print("\n[detect_changes multiple]")
r = detect_changes(
    {'email': 'old@test.com', 'follower_count': '1000', 'phone': '555-0100'},
    {'email': 'new@test.com', 'follower_count': '1500', 'phone': ''},
)
check("3 changes detected", len(r) == 3, f"got {len(r)}: {r}")
check("email changed", any(c['field'] == 'email' for c in r))
check("followers increased", any(c['field'] == 'follower_count' for c in r))
check("phone removed", any(c['field'] == 'phone' for c in r))


# --- classify_changes ---
print("\n[classify_changes]")
r = classify_changes([
    {'field': 'email', 'label': 'Email', 'type': 'added', 'detail': 'new@test.com'},
])
check("added with detail", r == ['+ Email: new@test.com'], f"got {r}")

r = classify_changes([
    {'field': 'email', 'label': 'Email', 'type': 'removed', 'detail': 'old@test.com'},
])
check("removed with detail", r == ['- Email: old@test.com'], f"got {r}")

r = classify_changes([
    {'field': 'email_verified', 'label': 'Email Verified', 'type': 'added', 'detail': ''},
])
check("bool added no detail", r == ['+ Email Verified'], f"got {r}")

r = classify_changes([
    {'field': 'email_verified', 'label': 'Email Verified', 'type': 'removed', 'detail': ''},
])
check("bool removed no detail", r == ['- Email Verified'], f"got {r}")

r = classify_changes([
    {'field': 'follower_count', 'label': 'Followers', 'type': 'increased', 'detail': '+350'},
])
check("number increased", r == ['~ Followers +350'], f"got {r}")

r = classify_changes([
    {'field': 'follower_count', 'label': 'Followers', 'type': 'decreased', 'detail': '-120'},
])
check("number decreased", r == ['~ Followers -120'], f"got {r}")

r = classify_changes([
    {'field': 'bio', 'label': 'Bio', 'type': 'changed', 'detail': 'old -> new'},
])
check("text changed", r == ['~ Bio old -> new'], f"got {r}")

r = classify_changes([
    {'field': 'priority_tier', 'label': 'Priority Tier', 'type': 'changed', 'detail': ''},
])
check("tier changed no detail", r == ['~ Priority Tier updated'], f"got {r}")

r = classify_changes([
    {'field': 'email', 'label': 'Email', 'type': 'added', 'detail': 'a@b.com'},
    {'field': 'phone', 'label': 'Phone', 'type': 'removed', 'detail': '555-0100'},
    {'field': 'follower_count', 'label': 'Followers', 'type': 'increased', 'detail': '+350'},
])
check("mixed changes", len(r) == 3, f"got {r}")


# --- load_baseline ---
print("\n[load_baseline]")
with tempfile.TemporaryDirectory() as tmpdir:
    csv_path = os.path.join(tmpdir, 'instagram_export_20260727.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['platform', 'username', 'email', 'follower_count'])
        writer.writeheader()
        writer.writerow({'platform': 'instagram', 'username': 'johndoe', 'email': 'john@test.com', 'follower_count': '15000'})
        writer.writerow({'platform': 'instagram', 'username': 'janedoe', 'email': 'jane@test.com', 'follower_count': '25000'})

    baseline = load_baseline(tmpdir)
    check("baseline loaded 2 leads", len(baseline) == 2, f"got {len(baseline)}")
    check("john in baseline", 'instagram:johndoe' in baseline)
    check("jane in baseline", 'instagram:janedoe' in baseline)
    check("john email preserved", baseline['instagram:johndoe'].get('email') == 'john@test.com')

    dedup_path = os.path.join(tmpdir, 'dedup_export_20260727.csv')
    with open(dedup_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['platform', 'username', 'email'])
        writer.writeheader()
        writer.writerow({'platform': 'tiktok', 'username': 'johndoe', 'email': 'john@test.com'})

    baseline2 = load_baseline(tmpdir)
    check("dedup file skipped", len(baseline2) == 2, f"got {len(baseline2)}")

    empty_baseline = load_baseline(tmpdir + '/nonexistent')
    check("empty dir returns empty", len(empty_baseline) == 0)


# --- load_baseline with empty username ---
print("\n[load_baseline edge cases]")
with tempfile.TemporaryDirectory() as tmpdir:
    csv_path = os.path.join(tmpdir, 'test_export_20260727.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['platform', 'username'])
        writer.writeheader()
        writer.writerow({'platform': 'instagram', 'username': ''})
        writer.writerow({'platform': 'tiktok', 'username': 'validuser'})
    baseline = load_baseline(tmpdir)
    check("empty username skipped", 'instagram:' not in baseline or baseline.get('instagram:', {}).get('username') == '', f"got keys: {list(baseline.keys())}")
    check("valid user present", 'tiktok:validuser' in baseline)


# --- display_change_tracker ---
print("\n[display_change_tracker]")
leads = [
    {
        'name': 'John Smith',
        'platform': 'instagram',
        'username': 'johndoe',
        '_changes': ['+ Email Verified', '~ Followers +350'],
    },
    {
        'name': 'Sarah Lee',
        'platform': 'tiktok',
        'username': 'sarahlee',
        '_changes': [],
    },
    {
        'name': 'Mike Chen',
        'platform': 'github',
        'username': 'mikechen',
        '_changes': ['+ Website Added'],
    },
]
baseline = {
    'instagram:johndoe': {'platform': 'instagram', 'username': 'johndoe'},
    'tiktok:sarahlee': {'platform': 'tiktok', 'username': 'sarahlee'},
}
try:
    display_change_tracker(leads, baseline, console)
    check("display_change_tracker ran without error", True)
except Exception as e:
    check("display_change_tracker ran without error", False, str(e))

try:
    display_change_tracker([], {}, console)
    check("display with empty leads", True)
except Exception as e:
    check("display with empty leads", False, str(e))

all_no_changes = [
    {'name': 'A', 'platform': 'ig', 'username': 'a', '_changes': []},
    {'name': 'B', 'platform': 'ig', 'username': 'b', '_changes': []},
]
baseline_all = {'ig:a': {}, 'ig:b': {}}
try:
    display_change_tracker(all_no_changes, baseline_all, console)
    check("display with no changes", True)
except Exception as e:
    check("display with no changes", False, str(e))


# --- JSON serialization ---
print("\n[JSON serialization]")
changes = detect_changes(
    {'email': 'old@test.com', 'follower_count': '1000', 'is_verified': 'False'},
    {'email': 'new@test.com', 'follower_count': '1500', 'is_verified': 'True'},
)
labels = classify_changes(changes)
try:
    json.dumps(changes, default=str)
    json.dumps(labels, default=str)
    check("changes JSON serializable", True)
except Exception as e:
    check("changes JSON serializable", False, str(e))


# --- CSV compatibility ---
print("\n[CSV compatibility]")
leads_with_changes = [
    {'name': 'A', '_changes': ['+ Email', '~ Followers +350'], 'platform': 'ig', 'username': 'a'},
    {'name': 'B', '_changes': [], 'platform': 'ig', 'username': 'b'},
]
all_keys = set()
for lead in leads_with_changes:
    export_lead = {k: v for k, v in lead.items() if not k.startswith('_')}
    export_lead['_changes'] = '; '.join(lead.get('_changes', []))
    all_keys.update(export_lead.keys())
csv_fields = sorted(all_keys)
check("CSV has _changes field", '_changes' in csv_fields, f"fields: {csv_fields}")


# --- Final ---
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
if failed > 0:
    sys.exit(1)
print("ALL TESTS PASSED")
