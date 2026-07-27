import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich import box

logger = logging.getLogger(__name__)

_TRACKED_STRINGS = [
    ('email', 'Email'),
    ('phone', 'Phone'),
    ('website', 'Website'),
    ('full_name', 'Name'),
    ('bio', 'Bio'),
    ('company', 'Company'),
    ('company_domain', 'Company Domain'),
    ('email_source', 'Email Source'),
    ('priority_tier', 'Priority Tier'),
    ('business_type', 'Business Type'),
    ('team_size', 'Team Size'),
]

_TRACKED_NUMBERS = [
    ('follower_count', 'Followers'),
    ('following_count', 'Following'),
    ('email_score', 'Email Score'),
    ('lead_score', 'Lead Score'),
    ('priority_score', 'Priority Score'),
    ('readiness_score', 'Readiness Score'),
    ('post_count', 'Posts'),
    ('video_count', 'Videos'),
    ('likes_count', 'Likes'),
    ('public_repos', 'Repos'),
    ('pin_count', 'Pins'),
]

_TRACKED_BOOLS = [
    ('email_verified', 'Email Verified'),
    ('outreach_ready', 'Outreach Ready'),
    ('is_private', 'Private Account'),
    ('is_verified', 'Verified'),
    ('is_business', 'Business Account'),
    ('is_hireable', 'Hireable'),
    ('is_partner', 'Partner'),
    ('is_affiliate', 'Affiliate'),
    ('is_premium', 'Premium'),
    ('is_influencer', 'Influencer'),
]


def build_identity_key(lead: dict) -> str:
    return f"{lead.get('platform', '')}:{lead.get('username', '')}".lower()


def load_baseline(working_dir: str = '.') -> dict:
    baseline = {}
    export_files = list(Path(working_dir).glob('*_export_*.csv'))
    for filepath in export_files:
        if filepath.name.startswith('dedup_'):
            continue
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = build_identity_key(row)
                    if key and key != ':':
                        if key not in baseline:
                            baseline[key] = row
        except Exception as e:
            logger.debug("Skipping %s: %s", filepath.name, e)
            continue
    return baseline


def _to_number(val) -> Optional[int]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip()
    if not s:
        return None
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _to_bool(val) -> Optional[bool]:
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ('true', '1', 'yes'):
        return True
    if s in ('false', '0', 'no', ''):
        return False
    return None


def _changed_str(old_val, new_val) -> bool:
    old = str(old_val or '').strip()
    new = str(new_val or '').strip()
    return old != new


def _changed_num(old_val, new_val) -> bool:
    old = _to_number(old_val)
    new = _to_number(new_val)
    if old is None and new is None:
        return False
    if old is None or new is None:
        return True
    return old != new


def _changed_bool(old_val, new_val) -> bool:
    old = _to_bool(old_val)
    new = _to_bool(new_val)
    if old is None and new is None:
        return False
    if old is None or new is None:
        return True
    return old != new


def detect_changes(old_lead: dict, new_lead: dict) -> list:
    changes = []

    for field, label in _TRACKED_STRINGS:
        old_val = old_lead.get(field, '')
        new_val = new_lead.get(field, '')
        if not _changed_str(old_val, new_val):
            continue
        old_s = str(old_val or '').strip()
        new_s = str(new_val or '').strip()
        if not old_s and new_s:
            changes.append({'field': field, 'label': label, 'type': 'added', 'detail': new_s})
        elif old_s and not new_s:
            changes.append({'field': field, 'label': label, 'type': 'removed', 'detail': old_s})
        elif old_s != new_s:
            changes.append({'field': field, 'label': label, 'type': 'changed', 'detail': f'{old_s[:30]} -> {new_s[:30]}'})

    for field, label in _TRACKED_NUMBERS:
        old_val = old_lead.get(field)
        new_val = new_lead.get(field)
        if not _changed_num(old_val, new_val):
            continue
        old_n = _to_number(old_val)
        new_n = _to_number(new_val)
        if old_n is None and new_n is not None:
            changes.append({'field': field, 'label': label, 'type': 'added', 'detail': str(new_n)})
        elif old_n is not None and new_n is None:
            changes.append({'field': field, 'label': label, 'type': 'removed', 'detail': str(old_n)})
        elif old_n is not None and new_n is not None:
            delta = new_n - old_n
            sign = '+' if delta > 0 else ''
            changes.append({'field': field, 'label': label, 'type': 'increased' if delta > 0 else 'decreased', 'detail': f'{sign}{delta}'})

    for field, label in _TRACKED_BOOLS:
        old_val = old_lead.get(field)
        new_val = new_lead.get(field)
        if not _changed_bool(old_val, new_val):
            continue
        old_b = _to_bool(old_val)
        new_b = _to_bool(new_val)
        if old_b is False and new_b is True:
            changes.append({'field': field, 'label': label, 'type': 'added', 'detail': ''})
        elif old_b is True and new_b is False:
            changes.append({'field': field, 'label': label, 'type': 'removed', 'detail': ''})
        elif old_b != new_b:
            changes.append({'field': field, 'label': label, 'type': 'changed', 'detail': ''})

    return changes


def classify_changes(raw_changes: list) -> list:
    labels = []
    for c in raw_changes:
        ctype = c['type']
        label = c['label']
        detail = c.get('detail', '')

        if ctype == 'added':
            if detail:
                labels.append(f'+ {label}: {detail}')
            else:
                labels.append(f'+ {label}')
        elif ctype == 'removed':
            if detail:
                labels.append(f'- {label}: {detail}')
            else:
                labels.append(f'- {label}')
        elif ctype in ('increased', 'decreased'):
            labels.append(f'~ {label} {detail}')
        elif ctype == 'changed':
            if detail:
                labels.append(f'~ {label} {detail}')
            else:
                labels.append(f'~ {label} updated')

    return labels


def display_change_tracker(leads: list, baseline: dict, console: Console) -> None:
    if not leads:
        console.print("[dim]No leads to display.[/dim]")
        return

    changed_leads = []
    new_leads = []
    unchanged_leads = []

    for lead in leads:
        changes = lead.get('_changes', [])
        key = build_identity_key(lead)
        if key in baseline:
            if changes:
                changed_leads.append(lead)
            else:
                unchanged_leads.append(lead)
        else:
            new_leads.append(lead)

    if not changed_leads and not new_leads:
        console.print("  [green]All leads match previous data — no changes detected[/green]")
        console.print()
        return

    table = Table(
        box=box.ROUNDED,
        border_style='dim',
        title='Changes Since Last Scrape',
        title_style='bold white',
        pad_edge=True,
        expand=True,
    )

    table.add_column('#', style='dim', width=4, justify='right')
    table.add_column('Name', style='bold white', min_width=14, max_width=22)
    table.add_column('Changes', min_width=30)

    row_num = 0
    for lead in changed_leads:
        row_num += 1
        name = lead.get('name', lead.get('full_name', 'Unknown'))
        changes = lead.get('_changes', [])
        changes_str = ', '.join(changes[:5])
        if len(changes) > 5:
            changes_str += f', +{len(changes) - 5} more'
        table.add_row(str(row_num), name, changes_str)

    for lead in new_leads:
        row_num += 1
        name = lead.get('name', lead.get('full_name', 'Unknown'))
        table.add_row(str(row_num), name, '[dim](new lead)[/dim]')

    console.print(table)

    total = len(changed_leads) + len(new_leads)
    parts = []
    if changed_leads:
        parts.append(f'{len(changed_leads)} changed')
    if new_leads:
        parts.append(f'{len(new_leads)} new')
    console.print(f"  [dim]{', '.join(parts)} out of {len(leads)} leads[/dim]")
    console.print()
