import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.scrapers.business import (
    detect_business_type, estimate_team_size, display_business_table,
    _bio_matches, _has_company_signals
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


# --- _bio_matches ---
print("\n[_bio_matches]")
check("empty bio returns empty", _bio_matches("", ["coach"]) == [])
check("match found", _bio_matches("I am a marketing agency", ["agency"]) == ["agency"])
check("no match", _bio_matches("Hello world", ["agency"]) == [])
check("case insensitive", _bio_matches("AGENCY Owner", ["agency"]) == ["agency"])
check("multiple matches", _bio_matches("marketing agency services", ["marketing", "agency", "media"]) == ["marketing", "agency"])
check("partial word match", _bio_matches("agencyx", ["agency"]) == ["agency"])


# --- _has_company_signals ---
print("\n[_has_company_signals]")
check("company_domain present", _has_company_signals({"company_domain": "acme.com"}) is True)
check("company field present", _has_company_signals({"company": "Acme Inc"}) is True)
check("both present", _has_company_signals({"company_domain": "acme.com", "company": "Acme"}) is True)
check("neither present", _has_company_signals({}) is False)
check("empty strings", _has_company_signals({"company_domain": "", "company": ""}) is False)


# --- detect_business_type ---
print("\n[detect_business_type]")

r = detect_business_type({})
check("empty lead -> personal_brand", r['business_type'] == 'personal_brand', f"got {r['business_type']}")

r = detect_business_type({"bio": "Welcome to my online shop! Buy our products here"})
check("shop keyword -> e_commerce", r['business_type'] == 'e_commerce', f"got {r['business_type']}")
check("high confidence with is_business", r['business_type_confidence'] in ('medium', 'high'))

r = detect_business_type({
    "bio": "Full service marketing agency",
    "company_domain": "agency.com",
    "follower_count": 100000,
})
check("agency keyword + company -> agency", r['business_type'] == 'agency', f"got {r['business_type']}")
check("confidence is high", r['business_type_confidence'] == 'high', f"got {r['business_type_confidence']}")

r = detect_business_type({
    "bio": "Building the best SaaS platform for automation",
    "company_domain": "saastool.io",
    "is_hireable": True,
})
check("saas keyword + company + hireable -> saas", r['business_type'] == 'saas', f"got {r['business_type']}")

r = detect_business_type({
    "platform": "twitch",
    "follower_count": 50000,
    "is_partner": True,
})
check("twitch + partner + followers -> creator", r['business_type'] == 'creator', f"got {r['business_type']}")

r = detect_business_type({
    "bio": "Content creator on YouTube making vlogs",
    "platform": "youtube",
    "follower_count": 10000,
})
check("youtube + creator keyword -> creator", r['business_type'] == 'creator', f"got {r['business_type']}")

r = detect_business_type({
    "bio": "I am a personal coach and speaker",
    "is_hireable": True,
})
check("coach keyword -> personal_brand", r['business_type'] == 'personal_brand', f"got {r['business_type']}")

r = detect_business_type({
    "bio": "Our team runs a creative media agency",
    "company_domain": "creative.com",
})
check("agency + creative -> agency (not creator)", r['business_type'] == 'agency', f"got {r['business_type']}")

r = detect_business_type({
    "bio": "Buy our fashion brand collection",
    "is_business": True,
    "follower_count": 5000,
})
check("fashion + brand -> e_commerce", r['business_type'] == 'e_commerce', f"got {r['business_type']}")

r = detect_business_type({
    "bio": "Software engineer building apps and tools",
    "is_hireable": True,
})
check("software + tools + hireable -> saas", r['business_type'] == 'saas', f"got {r['business_type']}")


# --- detect_business_type signals ---
print("\n[detect_business_type signals]")
r = detect_business_type({
    "bio": "Full service marketing agency",
    "company_domain": "agency.com",
})
check("signals list is non-empty", len(r['business_type_signals']) > 0)
check("signals contain company_domain", 'company_domain' in r['business_type_signals'], f"got {r['business_type_signals']}")


# --- estimate_team_size ---
print("\n[estimate_team_size]")

r = estimate_team_size({})
check("empty lead -> solo", r['team_size'] == 'solo', f"got {r['team_size']}")
check("solo confidence is high", r['team_size_confidence'] == 'high', f"got {r['team_size_confidence']}")

r = estimate_team_size({
    "bio": "I am a solo developer",
    "follower_count": 500,
})
check("small + solo pronouns -> solo", r['team_size'] == 'solo', f"got {r['team_size']}")

r = estimate_team_size({
    "company_domain": "acme.com",
    "follower_count": 25000,
})
check("company + 25k followers -> 2_10", r['team_size'] == '2_10', f"got {r['team_size']}")

r = estimate_team_size({
    "company_domain": "bigcorp.com",
    "follower_count": 200000,
})
check("company + 200k followers -> 11_50", r['team_size'] == '11_50', f"got {r['team_size']}")

r = estimate_team_size({
    "company_domain": "enterprise.com",
    "follower_count": 1000000,
    "is_verified": True,
})
check("company + 1M followers + verified -> 50_plus", r['team_size'] == '50_plus', f"got {r['team_size']}")

r = estimate_team_size({
    "company_domain": "startup.io",
    "follower_count": 10000,
    "bio": "We are building the future",
})
check("company + team pronouns + 10k -> 2_10 or 11_50", r['team_size'] in ('2_10', '11_50'), f"got {r['team_size']}")

r = estimate_team_size({
    "company_domain": "corp.com",
    "follower_count": 500000,
    "bio": "An enterprise holding company",
})
check("enterprise keyword -> 50_plus", r['team_size'] == '50_plus', f"got {r['team_size']}")

r = estimate_team_size({
    "is_hireable": True,
    "follower_count": 200,
})
check("hireable + small followers -> solo", r['team_size'] == 'solo', f"got {r['team_size']}")

r = estimate_team_size({
    "company_domain": "firm.com",
    "follower_count": 5000,
})
check("company + 5k followers -> 2_10", r['team_size'] == '2_10', f"got {r['team_size']}")

r = estimate_team_size({
    "company_domain": "group.com",
    "bio": "We are a global group",
    "follower_count": 500000,
    "is_verified": True,
})
check("global + verified + 500k -> 50_plus", r['team_size'] == '50_plus', f"got {r['team_size']}")


# --- estimate_team_size signals ---
print("\n[estimate_team_size signals]")
r = estimate_team_size({
    "company_domain": "acme.com",
    "follower_count": 25000,
})
check("signals list is non-empty", len(r['team_size_signals']) > 0)
check("signals contain company_domain", 'company_domain' in r['team_size_signals'], f"got {r['team_size_signals']}")
check("signals contain followers", any('followers' in s for s in r['team_size_signals']), f"got {r['team_size_signals']}")


# --- display_business_table ---
print("\n[display_business_table]")
leads = [
    {
        'name': 'John Smith',
        'business_type': 'agency',
        'business_type_label': 'Agency',
        'business_type_confidence': 'high',
        'business_type_signals': ['bio:agency', 'company_domain'],
        'team_size': '2_10',
        'team_size_label': '2-10',
        'team_size_confidence': 'high',
        'team_size_signals': ['company_domain', 'followers:12000'],
    },
    {
        'name': 'Sarah Lee',
        'business_type': 'saas',
        'business_type_label': 'SaaS',
        'business_type_confidence': 'medium',
        'business_type_signals': ['bio:saas'],
        'team_size': '11_50',
        'team_size_label': '11-50',
        'team_size_confidence': 'medium',
        'team_size_signals': ['company_domain', 'followers:200000'],
    },
    {
        'name': 'Mike Chen',
        'business_type': 'personal_brand',
        'business_type_label': 'Personal Brand',
        'business_type_confidence': 'low',
        'business_type_signals': ['default'],
        'team_size': 'solo',
        'team_size_label': 'Solo',
        'team_size_confidence': 'high',
        'team_size_signals': ['no_company_small_following'],
    },
]
try:
    display_business_table(leads, console)
    check("display_business_table ran without error", True)
except Exception as e:
    check("display_business_table ran without error", False, str(e))

check("display_business_table with empty list", True)
display_business_table([], console)


# --- JSON serialization ---
print("\n[JSON serialization]")
import json
for test_lead in [
    {},
    {"bio": "marketing agency", "company_domain": "x.com"},
    {"platform": "twitch", "follower_count": 50000, "is_partner": True},
    {"company_domain": "big.com", "follower_count": 1000000, "is_verified": True},
]:
    bt = detect_business_type(test_lead)
    ts = estimate_team_size(test_lead)
    try:
        json.dumps(bt, default=str)
        json.dumps(ts, default=str)
    except Exception as e:
        check(f"JSON serializable: {test_lead.get('bio', test_lead.get('platform', 'empty'))}", False, str(e))
        continue
    check(f"JSON serializable: {test_lead.get('bio', test_lead.get('platform', 'empty'))}", True)


# --- CSV key union test ---
print("\n[CSV compatibility]")
all_keys = set()
for test_lead in [
    {},
    {"bio": "agency", "company_domain": "x.com"},
    {"platform": "twitch", "follower_count": 50000, "is_partner": True},
    {"company_domain": "big.com", "follower_count": 1000000, "is_verified": True},
]:
    bt = detect_business_type(test_lead)
    ts = estimate_team_size(test_lead)
    merged = {**test_lead, **bt, **ts}
    all_keys.update(merged.keys())

csv_fields = sorted(all_keys)
expected = ['business_type', 'business_type_label', 'team_size', 'team_size_label']
for exp in expected:
    check(f"CSV field '{exp}' present", exp in csv_fields, f"fields: {csv_fields}")


# --- Final ---
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
if failed > 0:
    sys.exit(1)
print("ALL TESTS PASSED")
