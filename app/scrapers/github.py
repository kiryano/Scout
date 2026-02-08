"""
GitHub Profile Scraper

Fetches public GitHub user profiles using the GitHub API.
Extracts username, name, bio, email, company, location, website, and social links.
No authentication required for basic profile data (60 requests/hour rate limit).
"""

import requests
from typing import Dict, Optional
import logging
import re

from app.scrapers.stealth import get_requests_proxies, random_user_agent

logger = logging.getLogger(__name__)


def scrape_profile(username: str) -> Optional[Dict]:
    """Fetch GitHub profile data for a username."""
    url = f'https://api.github.com/users/{username}'

    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': random_user_agent(),
    }

    try:
        r = requests.get(url, headers=headers, timeout=15, proxies=get_requests_proxies())

        if r.status_code == 404:
            logger.error(f"GitHub user @{username} not found")
            return None

        if r.status_code == 403:
            logger.error("GitHub API rate limit exceeded (60/hour without token)")
            return None

        if r.status_code != 200:
            logger.error(f"GitHub API error {r.status_code} for @{username}")
            return None

        data = r.json()
        bio = data.get('bio') or ''

        return {
            'username': data.get('login', username),
            'full_name': data.get('name') or '',
            'bio': bio,
            'email': data.get('email') or _extract_email(bio),
            'company': (data.get('company') or '').lstrip('@'),
            'location': data.get('location') or '',
            'website': data.get('blog') or '',
            'twitter': data.get('twitter_username') or '',
            'follower_count': data.get('followers', 0),
            'following_count': data.get('following', 0),
            'public_repos': data.get('public_repos', 0),
            'is_hireable': data.get('hireable') or False,
            'platform': 'github',
            'profile_url': data.get('html_url', f'https://github.com/{username}'),
        }

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching GitHub profile @{username}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching GitHub profile @{username}: {e}")
        return None


def _extract_email(text: str) -> str:
    if not text:
        return ''
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(pattern, text)
    return matches[0] if matches else ''
