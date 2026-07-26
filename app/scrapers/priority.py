import logging
from typing import Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich import box

logger = logging.getLogger(__name__)

_EMAIL_SOURCE_WEIGHTS = {
    'bio': 20,
    'website': 15,
    'contact_page': 15,
    'hunter.io': 12,
    'smtp_guess': 8,
    'pattern': 5,
    'bio_link': 10,
}

_SOCIAL_DOMAINS = {
    'youtube.com', 'youtu.be', 'instagram.com', 'tiktok.com',
    'twitter.com', 'x.com', 'facebook.com', 'linktr.ee',
    'stan.store', 'beacons.ai', 'bit.ly', 'spotify.com',
    'discord.gg', 'twitch.tv',
}


def calculate_priority(lead: Dict) -> Dict:
    enriched = lead.copy()
    score = 0

    email = enriched.get('email', '')
    email_verified = enriched.get('email_verified', False)
    email_source = enriched.get('email_source', '')
    email_score = enriched.get('email_score', 0)

    if email:
        if email_verified:
            score += 30
        else:
            score += 5

        source_pts = _EMAIL_SOURCE_WEIGHTS.get(email_source, 0)
        score += source_pts

        if email_score >= 70:
            score += 5
        elif email_score >= 50:
            score += 2

    if enriched.get('company_domain'):
        score += 10

    website = enriched.get('website', '')
    if website and not any(d in website.lower() for d in _SOCIAL_DOMAINS):
        score += 5

    if enriched.get('phone'):
        score += 5

    if not email and enriched.get('possible_emails'):
        score += 2

    bio = (enriched.get('bio') or '').lower()
    biz_keywords = ['coach', 'consultant', 'ceo', 'founder', 'entrepreneur',
                    'agency', 'business', 'owner', 'director', 'manager']
    if any(k in bio for k in biz_keywords):
        score += 3

    enriched['priority_score'] = min(score, 100)

    if score >= 40:
        enriched['priority_tier'] = 'hot'
    elif score >= 10:
        enriched['priority_tier'] = 'warm'
    else:
        enriched['priority_tier'] = 'cool'

    return enriched


def rank_leads(enriched_profiles: List[Dict]) -> List[Dict]:
    ranked = [calculate_priority(p) for p in enriched_profiles]
    ranked.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
    for i, lead in enumerate(ranked, 1):
        lead['priority_rank'] = i
    return ranked


def _email_display(lead: Dict) -> tuple:
    email = lead.get('email', '')
    if not email:
        if lead.get('possible_emails'):
            return '~ Candidates only', 'yellow'
        return 'X No email', 'dim'

    verified = lead.get('email_verified', False)
    source = lead.get('email_source', '')
    source_labels = {
        'bio': 'bio',
        'website': 'website',
        'contact_page': 'contact',
        'hunter.io': 'hunter',
        'smtp_guess': 'smtp guess',
        'pattern': 'pattern',
        'bio_link': 'bio link',
    }
    label = source_labels.get(source, source)

    if verified:
        return f'[VERIFIED] ({label})', 'green'
    return f'[UNVERIFIED] ({label})', 'yellow'


def display_priority_queue(ranked_profiles: List[Dict], console: Optional[Console] = None):
    if not ranked_profiles:
        return

    if console is None:
        console = Console()

    console.print()
    console.print('[bold white]Priority Queue[/bold white]')
    console.print()

    table = Table(
        show_header=True,
        box=box.SIMPLE_HEAVY,
        border_style='dim',
        padding=(0, 1),
        title=None,
    )
    table.add_column('#', style='dim', width=3, justify='right')
    table.add_column('Name', style='white', min_width=18)
    table.add_column('Tier', width=6, justify='center')
    table.add_column('Contact', min_width=22)
    table.add_column('Score', width=5, justify='right')

    tier_styles = {
        'hot': ('bold green', 'HOT'),
        'warm': ('bold yellow', 'WARM'),
        'cool': ('dim', 'COOL'),
    }

    for lead in ranked_profiles:
        rank = lead.get('priority_rank', '?')
        name = lead.get('full_name') or lead.get('username', '?')
        name = name[:28]

        tier = lead.get('priority_tier', 'cool')
        tier_style, tier_label = tier_styles.get(tier, ('dim', '❄ COOL'))

        contact_text, contact_style = _email_display(lead)
        if lead.get('phone') and lead.get('email'):
            contact_text += ' +phone'

        pts = lead.get('priority_score', 0)
        if pts >= 40:
            score_style = 'green'
        elif pts >= 10:
            score_style = 'yellow'
        else:
            score_style = 'dim'

        table.add_row(
            str(rank),
            name,
            f'[{tier_style}]{tier_label}[/{tier_style}]',
            f'[{contact_style}]{contact_text}[/{contact_style}]',
            f'[{score_style}]{pts}[/{score_style}]',
        )

    console.print(table)
    console.print()
