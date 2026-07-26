import logging
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.table import Table
from rich import box

logger = logging.getLogger(__name__)

_SOCIAL_DOMAINS = {
    'youtube.com', 'youtu.be', 'instagram.com', 'tiktok.com',
    'twitter.com', 'x.com', 'facebook.com', 'linktr.ee',
    'stan.store', 'beacons.ai', 'bit.ly', 'spotify.com',
    'discord.gg', 'twitch.tv',
}

_HIGH_QUALITY_SOURCES = {'bio', 'website', 'contact_page', 'hunter.io'}


def evaluate_readiness(lead: Dict) -> Dict:
    email = lead.get('email', '').strip()
    email_verified = lead.get('email_verified', False)
    email_source = lead.get('email_source', '')
    website = lead.get('website', '').strip()
    company_domain = lead.get('company_domain', '').strip()
    phone = lead.get('phone', '').strip()
    is_private = lead.get('is_private', False)

    if is_private is True or is_private == 'True' or is_private == 'true':
        is_private = True
    else:
        is_private = False

    checklist = []

    has_verified_email = bool(email) and (email_verified is True or email_verified == 'True' or email_verified == 'true')
    checklist.append(('Verified Email', has_verified_email))

    has_quality_email = bool(email) and email_source in _HIGH_QUALITY_SOURCES
    checklist.append(('Email Quality', has_quality_email))

    has_website = bool(website) and not any(d in website.lower() for d in _SOCIAL_DOMAINS)
    checklist.append(('Website Found', has_website))

    has_company = bool(company_domain)
    checklist.append(('Company Domain', has_company))

    has_phone = bool(phone)
    checklist.append(('Phone Number', has_phone))

    not_private = not is_private
    checklist.append(('Public Account', not_private))

    passed = sum(1 for _, ok in checklist if ok)
    total = len(checklist)
    readiness_score = int((passed / total) * 100) if total > 0 else 0

    if has_verified_email:
        ready = True
    elif email and (has_website or has_company):
        ready = True
    else:
        ready = False

    if is_private:
        ready = False

    missing = [name for name, ok in checklist if not ok]

    return {
        'outreach_ready': ready,
        'readiness_score': readiness_score,
        'checklist': checklist,
        'missing': missing,
    }


def display_readiness_table(leads: List[Dict], console: Optional[Console] = None):
    if not leads:
        return

    if console is None:
        console = Console()

    console.print()
    console.print('[bold white]Outreach Readiness[/bold white]')
    console.print()

    table = Table(
        show_header=True,
        box=box.SIMPLE_HEAVY,
        border_style='dim',
        padding=(0, 1),
    )
    table.add_column('#', style='dim', width=3, justify='right')
    table.add_column('Name', style='white', min_width=18)
    table.add_column('Score', width=5, justify='right')
    table.add_column('Ready', width=5, justify='center')
    table.add_column('Checklist', min_width=30)

    ready_count = 0

    for i, lead in enumerate(leads, 1):
        name = lead.get('full_name') or lead.get('username', '?')
        name = name[:22]

        is_ready = lead.get('outreach_ready', False)
        score = lead.get('readiness_score', 0)
        checklist = lead.get('checklist', [])

        if is_ready:
            ready_count += 1

        if score >= 80:
            score_style = 'green'
        elif score >= 50:
            score_style = 'yellow'
        else:
            score_style = 'dim'

        ready_label = '[bold green]YES[/bold green]' if is_ready else '[red]NO[/red]'

        checks = []
        for _, ok in checklist:
            if ok:
                checks.append('[green]+[/green]')
            else:
                checks.append('[red]-[/red]')
        check_str = ' '.join(checks)

        table.add_row(
            str(i),
            name,
            f'[{score_style}]{score}[/{score_style}]',
            ready_label,
            check_str,
        )

    console.print(table)
    console.print()

    console.print(f'  [dim]Ready:[/dim] [white]{ready_count}/{len(leads)}[/white] [dim]leads[/dim]')
    console.print()
    console.print('  [dim]Checklist:[/dim] [green]+[/green] Verified Email  [green]+[/green] Email Quality  [green]+[/green] Website')
    console.print('  ' + ' ' * 13 + '[red]-[/red] Company Domain  [red]-[/red] Phone  [red]-[/red] Public Account')
    console.print()
