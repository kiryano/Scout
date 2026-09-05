import logging
from typing import Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich import box

logger = logging.getLogger(__name__)

_BUSINESS_TYPE_KEYWORDS = {
    'e_commerce': [
        'shop', 'store', 'brand', 'product', 'buy', 'collection',
        'fashion', 'beauty', 'clothing', 'boutique', 'merch', 'swag',
    ],
    'agency': [
        'agency', 'studio', 'media', 'marketing', 'design', 'creative',
        'consulting', 'services', 'firm', 'agency', 'production',
    ],
    'saas': [
        'saas', 'software', 'platform', 'api', 'startup', 'tech',
        'app', 'tool', 'ai', 'automation', 'cloud', 'saas',
    ],
    'creator': [
        'creator', 'streamer', 'youtuber', 'content', 'influencer',
        'vlog', 'podcast', 'host', 'gamer', 'twitch',
    ],
    'personal_brand': [
        'coach', 'consultant', 'speaker', 'personal', 'freelance',
        'entrepreneur', 'mentor', 'strategist', 'advisor', 'expert',
    ],
}

_SOLO_PRONOUNS = [' i ', ' me ', ' myself ', 'my journey', 'my story', 'my passion']
_TEAM_PRONOUNS = ['we ', 'our team', ' our ', 'our mission', 'our company', 'our agency']

_TEAM_KEYWORDS = ['team', 'group', 'enterprise', 'corporation', 'holdings', 'firm', 'company']

_LARGE_KEYWORDS = ['enterprise', 'corporation', 'holdings', 'global', 'worldwide', 'multinational']


def _bio_matches(bio: str, keyword_list: list) -> list:
    if not bio:
        return []
    bio_lower = bio.lower()
    return [kw for kw in keyword_list if kw in bio_lower]


def _has_company_signals(lead: dict) -> bool:
    return bool(lead.get('company_domain') or lead.get('company'))


def detect_business_type(lead: dict) -> dict:
    bio = lead.get('bio', '') or ''
    platform = lead.get('platform', '')
    follower_count = int(lead.get('follower_count', 0) or 0)
    is_business = lead.get('is_business')
    is_partner = lead.get('is_partner')
    is_affiliate = lead.get('is_affiliate')
    is_hireable = lead.get('is_hireable')
    has_company = _has_company_signals(lead)

    candidates = []

    ecom_hits = _bio_matches(bio, _BUSINESS_TYPE_KEYWORDS['e_commerce'])
    if ecom_hits:
        score = 30
        if is_business:
            score += 30
        if follower_count > 10000:
            score += 10
        candidates.append(('e_commerce', score, ecom_hits + (['is_business'] if is_business else [])))

    agency_hits = _bio_matches(bio, _BUSINESS_TYPE_KEYWORDS['agency'])
    if agency_hits:
        score = 30
        if has_company:
            score += 25
        if is_business:
            score += 10
        if follower_count > 50000:
            score += 10
        candidates.append(('agency', score, agency_hits + (['company_domain'] if has_company else [])))

    saas_hits = _bio_matches(bio, _BUSINESS_TYPE_KEYWORDS['saas'])
    if saas_hits:
        score = 30
        if has_company:
            score += 25
        if is_hireable:
            score += 15
        if follower_count > 20000:
            score += 10
        candidates.append(('saas', score, saas_hits + (['company_domain'] if has_company else []) + (['is_hireable'] if is_hireable else [])))

    creator_score = 0
    creator_signals = []
    if platform in ('youtube', 'twitch'):
        if follower_count > 5000:
            creator_score += 30
            creator_signals.append(f'platform:{platform}')
    if is_partner or is_affiliate:
        creator_score += 25
        creator_signals.append('is_partner' if is_partner else 'is_affiliate')
    creator_hits = _bio_matches(bio, _BUSINESS_TYPE_KEYWORDS['creator'])
    if creator_hits:
        creator_score += 25
        creator_signals.extend(creator_hits)
    if creator_score >= 25:
        candidates.append(('creator', creator_score, creator_signals))

    personal_hits = _bio_matches(bio, _BUSINESS_TYPE_KEYWORDS['personal_brand'])
    if personal_hits:
        score = 25
        if is_hireable and not has_company:
            score += 20
        if not has_company and follower_count < 10000:
            score += 10
        candidates.append(('personal_brand', score, personal_hits + (['is_hireable'] if is_hireable else [])))

    if not candidates:
        candidates.append(('personal_brand', 15, ['default']))

    best = max(candidates, key=lambda c: c[1])
    btype, score, signals = best

    if score >= 40:
        confidence = 'high'
    elif score >= 25:
        confidence = 'medium'
    else:
        confidence = 'low'

    labels = {
        'e_commerce': 'E-commerce',
        'agency': 'Agency',
        'saas': 'SaaS',
        'creator': 'Creator',
        'personal_brand': 'Personal Brand',
    }

    return {
        'business_type': btype,
        'business_type_label': labels.get(btype, btype),
        'business_type_confidence': confidence,
        'business_type_signals': signals,
    }


def estimate_team_size(lead: dict) -> dict:
    bio = lead.get('bio', '') or ''
    follower_count = int(lead.get('follower_count', 0) or 0)
    is_verified = lead.get('is_verified')
    is_business = lead.get('is_business')
    is_partner = lead.get('is_partner')
    is_affiliate = lead.get('is_affiliate')
    is_hireable = lead.get('is_hireable')
    company = lead.get('company', '') or ''
    has_company = _has_company_signals(lead)

    score = 0
    signals = []

    if has_company:
        score += 20
        signals.append('company_domain')

    bio_lower = bio.lower() if bio else ''
    team_kw_hits = [kw for kw in _TEAM_KEYWORDS if kw in bio_lower]
    large_kw_hits = [kw for kw in _LARGE_KEYWORDS if kw in bio_lower]

    if large_kw_hits:
        score += 30
        signals.extend([f'bio:{kw}' for kw in large_kw_hits])

    if team_kw_hits:
        score += 15
        signals.extend([f'bio:{kw}' for kw in team_kw_hits])

    if any(p in bio_lower for p in _SOLO_PRONOUNS):
        score -= 15
        signals.append('solo_pronouns')

    if any(p in bio_lower for p in _TEAM_PRONOUNS):
        score += 15
        signals.append('team_pronouns')

    if follower_count > 500000:
        score += 25
        signals.append(f'followers:{follower_count}')
    elif follower_count > 50000:
        score += 15
        signals.append(f'followers:{follower_count}')
    elif follower_count > 5000:
        score += 5
        signals.append(f'followers:{follower_count}')

    if is_verified:
        score += 15
        signals.append('is_verified')

    if is_partner or is_affiliate:
        score += 10
        signals.append('is_partner' if is_partner else 'is_affiliate')

    if is_hireable and not has_company:
        score -= 10
        signals.append('solo_hireable')

    if company and len(company.split()) > 3:
        score += 5
        signals.append('multi_word_company')

    if score >= 50:
        team_size = '50_plus'
        team_label = '50+'
        confidence = 'high' if score >= 65 else 'medium'
    elif score >= 30:
        team_size = '11_50'
        team_label = '11-50'
        confidence = 'high' if score >= 40 else 'medium'
    elif score >= 10:
        team_size = '2_10'
        team_label = '2-10'
        confidence = 'high' if score >= 20 else 'medium'
    else:
        team_size = 'solo'
        team_label = 'Solo'
        confidence = 'high' if score <= -10 else 'medium'

    if not has_company and not team_kw_hits and follower_count < 5000:
        team_size = 'solo'
        team_label = 'Solo'
        confidence = 'high'
        if 'solo_pronouns' not in signals:
            signals.append('no_company_small_following')

    return {
        'team_size': team_size,
        'team_size_label': team_label,
        'team_size_confidence': confidence,
        'team_size_signals': signals,
    }


def display_business_table(leads: List[dict], console: Console) -> None:
    if not leads:
        console.print("[dim]No leads to display.[/dim]")
        return

    table = Table(
        box=box.ROUNDED,
        border_style='dim',
        title='Business Profile',
        title_style='bold white',
        pad_edge=True,
        expand=True,
    )

    table.add_column('#', style='dim', width=4, justify='right')
    table.add_column('Name', style='bold white', min_width=14, max_width=22)
    table.add_column('Type', min_width=12, max_width=16)
    table.add_column('Size', min_width=8, max_width=12)
    table.add_column('Confidence', min_width=6, max_width=10)
    table.add_column('Signals', style='dim', min_width=14)

    TYPE_COLORS = {
        'e_commerce': 'red',
        'agency': 'magenta',
        'saas': 'blue',
        'creator': 'cyan',
        'personal_brand': 'green',
    }

    SIZE_COLORS = {
        '50_plus': 'red',
        '11_50': 'yellow',
        '2_10': 'green',
        'solo': 'cyan',
    }

    CONF_COLORS = {
        'high': 'bold green',
        'medium': 'bold yellow',
        'low': 'bold red',
    }

    for i, lead in enumerate(leads, 1):
        name = lead.get('name', lead.get('full_name', 'Unknown'))
        btype = lead.get('business_type', 'personal_brand')
        btype_label = lead.get('business_type_label', 'Personal Brand')
        bconf = lead.get('business_type_confidence', 'low')
        bsignals = lead.get('business_type_signals', [])

        tsize = lead.get('team_size', 'solo')
        tsize_label = lead.get('team_size_label', 'Solo')
        tconf = lead.get('team_size_confidence', 'low')
        tsignals = lead.get('team_size_signals', [])

        conf_combined = tconf if tconf == 'high' else (bconf if bconf != 'low' else tconf)
        conf_color = CONF_COLORS.get(conf_combined, 'dim')

        type_color = TYPE_COLORS.get(btype, 'dim')
        size_color = SIZE_COLORS.get(tsize, 'dim')

        all_signals = bsignals[:3] + tsignals[:3]
        signals_str = ', '.join(all_signals)

        table.add_row(
            str(i),
            name,
            f'[{type_color}]{btype_label}[/{type_color}]',
            f'[{size_color}]{tsize_label}[/{size_color}]',
            f'[{conf_color}]{conf_combined.upper()}[/{conf_color}]',
            signals_str,
        )

    console.print(table)
    console.print()
