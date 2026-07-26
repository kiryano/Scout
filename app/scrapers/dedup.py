import csv
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from rich.console import Console
from rich.table import Table
from rich import box

logger = logging.getLogger(__name__)

_EXPORT_PATTERN_RE = re.compile(r'.*_export_.*\.csv$')


def normalize_name(name: str) -> str:
    if not name:
        return ''
    name = name.lower().strip()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def normalize_email(email: str) -> str:
    if not email:
        return ''
    return email.lower().strip()


def normalize_domain(url_or_domain: str) -> str:
    if not url_or_domain:
        return ''
    url_or_domain = url_or_domain.strip()
    if not url_or_domain.startswith('http'):
        url_or_domain = 'https://' + url_or_domain
    try:
        domain = urlparse(url_or_domain).netloc
        if not domain:
            return ''
        domain = domain.lower().replace('www.', '', 1)
        return domain
    except Exception:
        return ''


def build_match_keys(lead: Dict) -> Dict:
    return {
        'email': normalize_email(lead.get('email', '')),
        'name': normalize_name(lead.get('full_name', '')),
        'website_domain': normalize_domain(lead.get('website', '')),
        'company_domain': normalize_domain(lead.get('company_domain', '')),
    }


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int):
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1


def load_all_exports(working_dir: str = '.') -> List[Dict]:
    csv_files = sorted(Path(working_dir).glob('*_export_*.csv'))
    leads = []
    for f in csv_files:
        if f.name.startswith('dedup_'):
            continue
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    row['_source_file'] = f.name
                    leads.append(row)
        except Exception as e:
            logger.debug(f"Could not read {f.name}: {e}")
    return leads


def find_duplicates(leads: List[Dict]) -> List[List[int]]:
    n = len(leads)
    if n == 0:
        return []

    uf = UnionFind(n)
    keys_list = [build_match_keys(lead) for lead in leads]

    email_index: Dict[str, List[int]] = {}
    for i, keys in enumerate(keys_list):
        e = keys['email']
        if e:
            email_index.setdefault(e, []).append(i)

    for indices in email_index.values():
        for i in range(1, len(indices)):
            uf.union(indices[0], indices[i])

    name_domain_index: Dict[Tuple[str, str], List[int]] = {}
    for i, keys in enumerate(keys_list):
        name = keys['name']
        domain = keys['website_domain'] or keys['company_domain']
        if name and domain:
            name_domain_index.setdefault((name, domain), []).append(i)

    for indices in name_domain_index.values():
        for i in range(1, len(indices)):
            uf.union(indices[0], indices[i])

    groups_map: Dict[int, List[int]] = {}
    for i in range(n):
        root = uf.find(i)
        groups_map.setdefault(root, []).append(i)

    return [indices for indices in groups_map.values() if len(indices) > 1]


def merge_lead_group(group: List[Dict]) -> Dict:
    merged = {}

    platforms = []
    source_files = []
    for lead in group:
        p = lead.get('platform', '')
        if p and p not in platforms:
            platforms.append(p)
        sf = lead.get('_source_file', '')
        if sf and sf not in source_files:
            source_files.append(sf)

    def best_value(key, prefer_longest=False):
        values = []
        for lead in group:
            v = lead.get(key, '')
            if isinstance(v, str):
                v = v.strip()
            if v:
                values.append(v)
        if not values:
            return ''
        if prefer_longest:
            return max(values, key=len)
        return values[0]

    def best_int(key):
        best = 0
        for lead in group:
            try:
                v = int(float(lead.get(key, 0) or 0))
                if v > best:
                    best = v
            except (ValueError, TypeError):
                pass
        return best

    def best_bool(key):
        for lead in group:
            v = lead.get(key, False)
            if v is True or v == 'True' or v == 'true' or v == '1':
                return True
        return False

    merged['full_name'] = best_value('full_name', prefer_longest=True)
    merged['username'] = best_value('username')
    merged['bio'] = best_value('bio', prefer_longest=True)
    merged['platform'] = ', '.join(platforms)
    merged['platforms'] = platforms
    merged['platform_count'] = len(platforms)

    emails = []
    for lead in group:
        e = lead.get('email', '').strip()
        if e:
            verified = lead.get('email_verified', False)
            if verified is True or verified == 'True' or verified == 'true':
                emails.insert(0, ('verified', e))
            else:
                emails.append(('unverified', e))

    if emails:
        merged['email'] = emails[0][1]
        merged['email_verified'] = emails[0][0] == 'verified'
    else:
        merged['email'] = best_value('email')
        merged['email_verified'] = False

    email_sources = []
    for lead in group:
        s = lead.get('email_source', '')
        if s:
            email_sources.append(s)
    merged['email_source'] = email_sources[0] if email_sources else ''

    email_scores = []
    for lead in group:
        try:
            score = int(float(lead.get('email_score', 0) or 0))
            if score > 0:
                email_scores.append(score)
        except (ValueError, TypeError):
            pass
    merged['email_score'] = max(email_scores) if email_scores else 0

    merged['phone'] = best_value('phone')
    merged['website'] = best_value('website')
    merged['company_domain'] = best_value('company_domain')
    merged['profile_url'] = best_value('profile_url')

    merged['follower_count'] = best_int('follower_count')
    merged['lead_score'] = best_int('lead_score')
    merged['priority_score'] = best_int('priority_score')

    merged['is_verified'] = best_bool('is_verified')

    for lead in group:
        for key in lead:
            if key.startswith('_'):
                continue
            if key not in merged or merged[key] == '':
                v = lead.get(key, '')
                if v and v != '0' and v != '[]' and v != '{}':
                    merged[key] = v

    merged['_source_files'] = source_files
    merged['is_merged'] = True
    merged['merge_count'] = len(group)

    return merged


def display_duplicate_report(merged_groups: List[Dict], unique_count: int,
                             total_before: int, console: Optional[Console] = None):
    if console is None:
        console = Console()

    console.print()
    console.print('[bold white]Duplicate Detection[/bold white]')
    console.print()

    total_overlap = sum(g.get('merge_count', 1) for g in merged_groups)

    console.print(f'  [white]{total_before}[/white] [dim]total profiles across exports[/dim]')
    console.print(f'  [yellow]{len(merged_groups)}[/yellow] [dim]duplicate groups ({total_overlap} overlapping profiles)[/dim]')
    console.print(f'  [green]{unique_count}[/green] [dim]unique leads after merge[/dim]')
    console.print()

    if not merged_groups:
        return

    table = Table(
        show_header=True,
        box=box.SIMPLE_HEAVY,
        border_style='dim',
        padding=(0, 1),
    )
    table.add_column('#', style='dim', width=3, justify='right')
    table.add_column('Name', style='white', min_width=18)
    table.add_column('Platforms', min_width=16)
    table.add_column('Email', min_width=20)
    table.add_column('Merged', width=7, justify='center')

    for i, merged in enumerate(merged_groups, 1):
        name = merged.get('full_name') or merged.get('username', '?')
        name = name[:28]

        platforms = merged.get('platforms', [])
        plat_str = ', '.join(p[:3].upper() for p in platforms[:5])

        email = merged.get('email', '') or '-'
        email = email[:26]

        count = merged.get('merge_count', 1)
        table.add_row(
            str(i),
            name,
            plat_str,
            email,
            f'[{count}]',
        )

    console.print(table)
    console.print()


def deduplicate(leads: List[Dict]) -> Tuple[List[Dict], List[List[Dict]], Dict]:
    groups = find_duplicates(leads)

    merged_groups = []
    for group_indices in groups:
        group_leads = [leads[i] for i in group_indices]
        merged = merge_lead_group(group_leads)
        merged_groups.append(merged)

    merged_indices = set()
    for group_indices in groups:
        merged_indices.update(group_indices)

    unique = []
    for i, lead in enumerate(leads):
        if i not in merged_indices:
            unique.append(lead)

    all_deduplicated = unique + merged_groups
    all_deduplicated.sort(
        key=lambda x: int(float(x.get('priority_score', 0) or 0)),
        reverse=True
    )

    stats = {
        'total_before': len(leads),
        'groups': len(groups),
        'overlapping': sum(len(g) for g in groups),
        'unique_after': len(all_deduplicated),
    }

    return all_deduplicated, merged_groups, stats


def deduplicate_all(working_dir: str = '.') -> Tuple[List[Dict], List[List[Dict]], Dict, List[Dict]]:
    all_leads = load_all_exports(working_dir)
    deduplicated, merged_groups, stats = deduplicate(all_leads)
    return deduplicated, merged_groups, stats, all_leads
