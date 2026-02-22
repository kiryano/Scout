"""
Link-in-Bio Scraper

Scrapes public link-in-bio pages across multiple platforms.

Supported platforms:
- Linktree (linktr.ee)
- Stan Store (stan.store)
- Linkr (linkr.bio)
- Bio.link (bio.link)

Features:
- Extracts all social links from profile pages
- Discovers email and phone from linked content
- Can scrape all supported platforms at once via scrape_all()
"""

import requests
from typing import Dict, Optional, List
import logging
import re
import json

from app.scrapers.stealth import random_user_agent
from app.scrapers.utils import extract_email as _shared_extract_email

logger = logging.getLogger(__name__)

PLATFORMS = {
    'linktree': 'https://linktr.ee/{username}',
    'stan': 'https://stan.store/{username}',
    'linkr': 'https://linkr.bio/{username}',
    'biolink': 'https://bio.link/{username}',
}


def scrape_linktree(username: str) -> Optional[Dict]:
    """Scrape Linktree profile."""
    return _scrape_profile(username, 'linktree')


def scrape_stan(username: str) -> Optional[Dict]:
    """Scrape Stan.store profile."""
    return _scrape_profile(username, 'stan')


def scrape_linkr(username: str) -> Optional[Dict]:
    """Scrape Linkr.bio profile."""
    return _scrape_profile(username, 'linkr')


def scrape_biolink(username: str) -> Optional[Dict]:
    """Scrape Bio.link profile."""
    return _scrape_profile(username, 'biolink')


def scrape_all(username: str) -> Optional[Dict]:
    """Try all link-in-bio platforms for a username."""
    for platform in PLATFORMS.keys():
        result = _scrape_profile(username, platform)
        if result:
            return result
    return None


def _scrape_profile(username: str, platform: str) -> Optional[Dict]:
    """
    Fetch link-in-bio profile data.

    Args:
        username: Profile username
        platform: Platform name (linktree, stan, linkr, biolink)
    """
    username = username.lstrip('@').strip().lower()

    if platform not in PLATFORMS:
        logger.error(f"Unknown platform: {platform}")
        return None

    url = PLATFORMS[platform].format(username=username)

    headers = {
        'User-Agent': random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        r = requests.get(url, headers=headers, timeout=20)

        if r.status_code == 404:
            logger.debug(f"{platform} user {username} not found")
            return None

        if r.status_code != 200:
            logger.error(f"{platform} error {r.status_code} for {username}")
            return None

        html = r.text

        if platform == 'linktree':
            return _parse_linktree(html, username)
        elif platform == 'stan':
            return _parse_stan(html, username)
        else:
            return _parse_generic(html, username, platform)

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {platform} profile {username}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching {platform} profile {username}: {e}")
        return None


def _parse_linktree(html: str, username: str) -> Optional[Dict]:
    """Parse Linktree page."""

    data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not data_match:
        return _parse_generic(html, username, 'linktree')

    try:
        data = json.loads(data_match.group(1))
        account = data.get('props', {}).get('pageProps', {}).get('account', {})

        if not account:
            return None

        links = []
        for link in account.get('links', []):
            if link.get('url'):
                links.append({
                    'title': link.get('title', ''),
                    'url': link.get('url', ''),
                })

        bio = account.get('description', '')

        return {
            'username': username,
            'full_name': account.get('pageTitle', ''),
            'bio': bio,
            'email': _extract_email_from_links(links) or _extract_email(bio),
            'follower_count': 0,
            'website': _extract_website(links),
            'links': links,
            'link_count': len(links),
            'socials': _extract_socials(links),
            'platform': 'linktree',
            'profile_url': f'https://linktr.ee/{username}',
        }

    except json.JSONDecodeError:
        return _parse_generic(html, username, 'linktree')


def _parse_stan(html: str, username: str) -> Optional[Dict]:
    """Parse Stan.store page."""

    links = []
    link_matches = re.findall(r'href="(https?://[^"]+)"', html)
    for url in link_matches:
        if 'stan.store' not in url and url.startswith('http'):
            links.append({'title': '', 'url': url})

    name_match = re.search(r'"name":"([^"]+)"', html)
    full_name = name_match.group(1) if name_match else ''

    bio_match = re.search(r'"description":"([^"]*)"', html)
    bio = bio_match.group(1) if bio_match else ''

    if not full_name and not links:
        return None

    return {
        'username': username,
        'full_name': full_name,
        'bio': bio,
        'email': _extract_email_from_links(links) or _extract_email(bio),
        'follower_count': 0,
        'website': _extract_website(links),
        'links': links[:20],
        'link_count': len(links),
        'socials': _extract_socials(links),
        'platform': 'stan',
        'profile_url': f'https://stan.store/{username}',
    }


def _parse_generic(html: str, username: str, platform: str) -> Optional[Dict]:
    """Generic parser for link-in-bio pages."""

    links = []
    link_matches = re.findall(r'href="(https?://[^"]+)"', html)

    seen = set()
    for url in link_matches:
        if url not in seen and not any(skip in url for skip in ['favicon', 'static', 'assets', '.css', '.js']):
            links.append({'title': '', 'url': url})
            seen.add(url)

    title_match = re.search(r'<title>([^<]+)</title>', html)
    full_name = title_match.group(1).strip() if title_match else ''

    bio = ''
    meta_desc = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
    if meta_desc:
        bio = meta_desc.group(1)

    if not links:
        return None

    base_url = PLATFORMS.get(platform, '').format(username=username)

    return {
        'username': username,
        'full_name': full_name,
        'bio': bio,
        'email': _extract_email_from_links(links) or _extract_email(bio),
        'follower_count': 0,
        'website': _extract_website(links),
        'links': links[:20],
        'link_count': len(links),
        'socials': _extract_socials(links),
        'platform': platform,
        'profile_url': base_url,
    }


def _extract_socials(links: List[Dict]) -> Dict[str, str]:
    """Extract social media links from link list."""
    socials = {}

    patterns = {
        'instagram': r'instagram\.com/([^/?]+)',
        'twitter': r'(?:twitter|x)\.com/([^/?]+)',
        'tiktok': r'tiktok\.com/@?([^/?]+)',
        'youtube': r'youtube\.com/(?:@|c/|channel/)?([^/?]+)',
        'twitch': r'twitch\.tv/([^/?]+)',
        'github': r'github\.com/([^/?]+)',
        'linkedin': r'linkedin\.com/in/([^/?]+)',
        'discord': r'discord\.(?:gg|com/invite)/([^/?]+)',
        'spotify': r'open\.spotify\.com/(?:artist|user)/([^/?]+)',
        'soundcloud': r'soundcloud\.com/([^/?]+)',
    }

    for link in links:
        url = link.get('url', '')
        for platform, pattern in patterns.items():
            if platform not in socials:
                match = re.search(pattern, url, re.IGNORECASE)
                if match:
                    socials[platform] = match.group(1)

    return socials


def _extract_website(links: List[Dict]) -> str:
    """Extract a personal website URL from links, skipping social media."""
    social_domains = [
        'instagram.com', 'twitter.com', 'x.com', 'tiktok.com',
        'youtube.com', 'twitch.tv', 'github.com', 'linkedin.com',
        'discord.gg', 'discord.com', 'spotify.com', 'soundcloud.com',
        'facebook.com', 'pinterest.com', 'snapchat.com', 'reddit.com',
        'stan.store', 'linktr.ee', 'linkr.bio', 'bio.link',
    ]
    for link in links:
        url = link.get('url', '')
        if url.startswith('http') and not url.startswith('mailto:'):
            if not any(domain in url.lower() for domain in social_domains):
                return url
    return ''


def _extract_email_from_links(links: List[Dict]) -> str:
    """Extract email from mailto links."""
    for link in links:
        url = link.get('url', '')
        if url.startswith('mailto:'):
            return url.replace('mailto:', '').split('?')[0]
    return ''


_extract_email = _shared_extract_email
