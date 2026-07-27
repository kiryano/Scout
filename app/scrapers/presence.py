import logging
from typing import Dict, List

from rich.console import Console
from rich.table import Table
from rich import box

logger = logging.getLogger(__name__)

_PLATFORMS = [
    ('instagram', 'IG'),
    ('tiktok', 'TK'),
    ('linkedin', 'LI'),
    ('youtube', 'YT'),
    ('github', 'GH'),
    ('twitch', 'TW'),
    ('pinterest', 'PN'),
]

_LINK_IN_BIO = {'linktree', 'stan', 'linkr', 'biolink'}


def _get_platform_list(lead: dict) -> list:
    if 'platforms' in lead and isinstance(lead['platforms'], list):
        return lead['platforms']
    p = lead.get('platform', '')
    return [p] if p else []


def extract_platform_presence(lead: dict) -> dict:
    platforms = _get_platform_list(lead)
    platforms_set = set(p.lower() for p in platforms if p)

    result = {}
    for key, _ in _PLATFORMS:
        result[f'has_{key}'] = key in platforms_set

    result['has_link_in_bio'] = bool(platforms_set & _LINK_IN_BIO)
    result['total_platforms'] = len(platforms_set)
    return result


def display_social_presence(leads: List[dict], console: Console) -> None:
    if not leads:
        console.print("[dim]No leads to display.[/dim]")
        return

    sorted_leads = sorted(leads, key=lambda l: l.get('total_platforms', 0), reverse=True)

    table = Table(
        box=box.ROUNDED,
        border_style='dim',
        title='Social Presence',
        title_style='bold white',
        pad_edge=True,
        expand=True,
    )

    table.add_column('#', style='dim', width=4, justify='right')
    table.add_column('Name', style='bold white', min_width=14, max_width=22)

    for _, abbr in _PLATFORMS:
        table.add_column(abbr, width=5, justify='center')
    table.add_column('LiB', width=5, justify='center')
    table.add_column('Total', width=6, justify='center', style='bold white')

    for i, lead in enumerate(sorted_leads, 1):
        name = lead.get('name', lead.get('full_name', 'Unknown'))
        total = lead.get('total_platforms', 0)

        row = [str(i), name]
        for key, _ in _PLATFORMS:
            if lead.get(f'has_{key}'):
                row.append('[green]+[/green]')
            else:
                row.append('[dim]-[/dim]')

        if lead.get('has_link_in_bio'):
            row.append('[green]+[/green]')
        else:
            row.append('[dim]-[/dim]')

        row.append(str(total))
        table.add_row(*row)

    console.print(table)
    console.print()
