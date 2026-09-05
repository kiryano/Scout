import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.scrapers.presence import (
    extract_platform_presence, display_social_presence, _get_platform_list
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


# --- _get_platform_list ---
print("\n[_get_platform_list]")
check("platforms list present", _get_platform_list({'platforms': ['instagram', 'youtube']}) == ['instagram', 'youtube'])
check("platforms empty list", _get_platform_list({'platforms': []}) == [])
check("fallback to singular", _get_platform_list({'platform': 'tiktok'}) == ['tiktok'])
check("no platform at all", _get_platform_list({}) == [])
check("platforms list takes precedence", _get_platform_list({'platforms': ['ig'], 'platform': 'tiktok'}) == ['ig'])
check("platforms non-list ignored", _get_platform_list({'platforms': 'instagram', 'platform': 'tiktok'}) == ['tiktok'])


# --- extract_platform_presence ---
print("\n[extract_platform_presence]")

r = extract_platform_presence({})
check("empty lead: no platforms", r['total_platforms'] == 0)
check("empty lead: all false", all(not v for k, v in r.items() if k.startswith('has_')))

r = extract_platform_presence({'platforms': ['instagram']})
check("single platform: ig present", r['has_instagram'] is True)
check("single platform: others absent", r['has_tiktok'] is False)
check("single platform: total=1", r['total_platforms'] == 1)

r = extract_platform_presence({'platforms': ['instagram', 'tiktok', 'linkedin']})
check("three platforms: ig present", r['has_instagram'] is True)
check("three platforms: tk present", r['has_tiktok'] is True)
check("three platforms: li present", r['has_linkedin'] is True)
check("three platforms: yt absent", r['has_youtube'] is False)
check("three platforms: total=3", r['total_platforms'] == 3)

r = extract_platform_presence({'platforms': ['linktree']})
check("linktree -> has_link_in_bio", r['has_link_in_bio'] is True)
check("linktree: ig absent", r['has_instagram'] is False)
check("linktree: total=1", r['total_platforms'] == 1)

r = extract_platform_presence({'platforms': ['stan', 'linkr', 'biolink']})
check("stan+linkr+biolink -> has_link_in_bio", r['has_link_in_bio'] is True)
check("all link-in-bio: total=3", r['total_platforms'] == 3)

r = extract_platform_presence({'platforms': ['linktree', 'instagram', 'youtube']})
check("mixed: link_in_bio + ig + yt", r['has_link_in_bio'] is True)
check("mixed: ig present", r['has_instagram'] is True)
check("mixed: yt present", r['has_youtube'] is True)
check("mixed: total=3", r['total_platforms'] == 3)

r = extract_platform_presence({'platforms': ['github', 'twitch', 'pinterest']})
check("gh+tw+pn present", r['has_github'] is True and r['has_twitch'] is True and r['has_pinterest'] is True)
check("gh+tw+pn: no ig", r['has_instagram'] is False)

r = extract_platform_presence({'platforms': ['instagram', 'tiktok', 'linkedin', 'youtube', 'github', 'twitch', 'pinterest', 'linktree']})
check("all 8 platforms: total=8", r['total_platforms'] == 8)
check("all 8: all has_ true", all(v for k, v in r.items() if k.startswith('has_')))


# --- singular platform fallback ---
print("\n[singular platform fallback]")
r = extract_platform_presence({'platform': 'instagram'})
check("singular instagram: ig present", r['has_instagram'] is True)
check("singular instagram: total=1", r['total_platforms'] == 1)

r = extract_platform_presence({'platform': 'linktree'})
check("singular linktree: has_link_in_bio", r['has_link_in_bio'] is True)


# --- display_social_presence ---
print("\n[display_social_presence]")
leads = [
    {
        'name': 'John Smith',
        'has_instagram': True, 'has_tiktok': False, 'has_linkedin': True,
        'has_youtube': False, 'has_github': False, 'has_twitch': False,
        'has_pinterest': False, 'has_link_in_bio': True, 'total_platforms': 3,
    },
    {
        'name': 'Sarah Lee',
        'has_instagram': False, 'has_tiktok': True, 'has_linkedin': True,
        'has_youtube': False, 'has_github': True, 'has_twitch': False,
        'has_pinterest': False, 'has_link_in_bio': False, 'total_platforms': 3,
    },
    {
        'name': 'Mike Chen',
        'has_instagram': False, 'has_tiktok': False, 'has_linkedin': False,
        'has_youtube': False, 'has_github': True, 'has_twitch': False,
        'has_pinterest': False, 'has_link_in_bio': False, 'total_platforms': 1,
    },
    {
        'name': 'Lisa Park',
        'has_instagram': True, 'has_tiktok': True, 'has_linkedin': True,
        'has_youtube': True, 'has_github': True, 'has_twitch': True,
        'has_pinterest': True, 'has_link_in_bio': True, 'total_platforms': 8,
    },
]
try:
    display_social_presence(leads, console)
    check("display_social_presence ran without error", True)
except Exception as e:
    check("display_social_presence ran without error", False, str(e))

try:
    display_social_presence([], console)
    check("display_social_presence with empty list", True)
except Exception as e:
    check("display_social_presence with empty list", False, str(e))


# --- JSON serialization ---
print("\n[JSON serialization]")
import json
test_leads = [
    {},
    {'platforms': ['instagram', 'youtube']},
    {'platforms': ['linktree', 'stan']},
    {'platform': 'tiktok'},
]
for lead in test_leads:
    result = extract_platform_presence(lead)
    try:
        json.dumps(result, default=str)
        check(f"JSON serializable: {lead.get('platforms', lead.get('platform', 'empty'))}", True)
    except Exception as e:
        check(f"JSON serializable: {lead.get('platforms', lead.get('platform', 'empty'))}", False, str(e))


# --- CSV key union test ---
print("\n[CSV compatibility]")
all_keys = set()
for lead in test_leads:
    merged = {**lead, **extract_platform_presence(lead)}
    all_keys.update(merged.keys())

csv_fields = sorted(all_keys)
expected = ['has_instagram', 'has_tiktok', 'has_linkedin', 'has_youtube',
            'has_github', 'has_twitch', 'has_pinterest', 'has_link_in_bio', 'total_platforms']
for exp in expected:
    check(f"CSV field '{exp}' present", exp in csv_fields, f"fields: {csv_fields}")


# --- Final ---
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
if failed > 0:
    sys.exit(1)
print("ALL TESTS PASSED")
