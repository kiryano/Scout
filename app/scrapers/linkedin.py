import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional

import httpx

from app.scrapers.stealth import random_user_agent, get_httpx_proxy
from app.scrapers.utils import extract_email

logger = logging.getLogger(__name__)

_session_cache = {'client': None, 'csrf': None}


def _get_li_cookie() -> Optional[str]:
    cookie = os.environ.get('LINKEDIN_COOKIE', '').strip()
    if not cookie:
        return None
    if len(cookie) < 50:
        logger.warning("LinkedIn cookie seems too short - may be invalid")
    return cookie


def validate_cookie() -> dict:
    """Check if LinkedIn cookie is valid."""
    cookie = _get_li_cookie()
    if not cookie:
        return {'valid': False, 'message': 'No cookie set'}

    try:
        client = httpx.Client(follow_redirects=True, timeout=15)
        client.cookies.set('li_at', cookie, domain='.linkedin.com')
        resp = client.get('https://www.linkedin.com/feed/')

        if resp.status_code == 200 and 'feed' in str(resp.url):
            return {'valid': True, 'message': 'Cookie is valid'}
        elif 'login' in str(resp.url) or 'authwall' in str(resp.url):
            return {'valid': False, 'message': 'Cookie expired - please re-export'}
        else:
            return {'valid': False, 'message': f'Unexpected response: {resp.status_code}'}
    except Exception as e:
        return {'valid': False, 'message': f'Connection error: {str(e)}'}


def _get_session():
    if _session_cache['client'] and _session_cache['csrf']:
        return _session_cache['client'], _session_cache['csrf']

    cookie = _get_li_cookie()
    if not cookie:
        return None, None

    client = httpx.Client(follow_redirects=True, timeout=20)
    client.cookies.set('li_at', cookie, domain='.linkedin.com')

    resp = client.get('https://www.linkedin.com/feed/')

    csrf = None
    for c in client.cookies.jar:
        if c.name == 'JSESSIONID':
            csrf = c.value.strip('"')
            break

    if not csrf:
        logger.error("Could not extract CSRF token from LinkedIn")
        return None, None

    _session_cache['client'] = client
    _session_cache['csrf'] = csrf
    return client, csrf


def scrape_linkedin_profile(username: str) -> Optional[Dict]:
    """Scrape LinkedIn profile. Returns profile dict or None."""
    cookie = _get_li_cookie()
    if not cookie:
        logger.error("LINKEDIN_COOKIE not set in .env")
        return None

    client, csrf = _get_session()
    if not client or not csrf:
        logger.error("Failed to initialize LinkedIn session. Cookie may be expired.")
        return None

    logger.info(f"Scraping LinkedIn profile: {username}")

    headers = {
        'csrf-token': csrf,
        'Accept': 'application/vnd.linkedin.normalized+json+2.1',
        'x-li-lang': 'en_US',
        'x-restli-protocol-version': '2.0.0',
    }

    url = f'https://www.linkedin.com/voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity={username}'

    try:
        resp = client.get(url, headers=headers)
    except httpx.RequestError as e:
        logger.error(f"Request error for {username}: {e}")
        return None

    if resp.status_code == 403:
        logger.error(f"Profile {username} is restricted or not accessible")
        return None
    if resp.status_code == 401:
        _session_cache.update({'client': None, 'csrf': None})
        logger.error("LinkedIn cookie expired. Re-export your li_at cookie.")
        return None
    if resp.status_code != 200:
        logger.error(f"HTTP {resp.status_code} for {username}")
        return None

    try:
        data = resp.json()
    except json.JSONDecodeError:
        logger.error(f"Invalid response for {username}")
        return None

    profile_data = None
    for item in data.get('included', []):
        if 'firstName' in item and 'lastName' in item:
            profile_data = item
            break

    if not profile_data:
        logger.error(f"No profile data found for {username}")
        return None

    summary = profile_data.get('summary', '')
    if not summary:
        multi = profile_data.get('multiLocaleSummary', {})
        summary = multi.get('en_US', '') if isinstance(multi, dict) else ''

    websites = []
    for w in profile_data.get('websites', []):
        if isinstance(w, dict) and w.get('url'):
            websites.append(w['url'])

    profile = {
        'platform': 'linkedin',
        'username': profile_data.get('publicIdentifier', username),
        'full_name': f"{profile_data.get('firstName', '')} {profile_data.get('lastName', '')}".strip(),
        'headline': profile_data.get('headline', ''),
        'bio': summary,
        'profile_url': f"https://www.linkedin.com/in/{profile_data.get('publicIdentifier', username)}/",
        'is_verified': profile_data.get('showVerificationBadge', False),
        'is_premium': profile_data.get('premium', False),
        'is_influencer': profile_data.get('influencer', False),
        'website': websites[0] if websites else '',
        'email': extract_email(summary),
    }

    logger.info(f"Scraped {username}: {profile['full_name']} | {profile['headline'][:50]}")

    return profile
