"""
Instagram Profile Scraper

Scrapes public Instagram profiles by parsing the HTML page directly.
Uses mobile user agents and rotating residential proxies to avoid rate limits.

Features:
- Extracts follower/following counts, bio, verification status, etc.
- Multiple regex patterns to handle Instagram's varying HTML structures
- Automatic retry with proxy rotation on extraction failures
- No authentication required (public profiles only)
"""

import requests
from typing import Dict, Optional
import logging
import re

from app.scrapers.stealth import get_requests_proxies
from app.scrapers.utils import extract_email, extract_phone, parse_abbreviated_number

logger = logging.getLogger(__name__)

MOBILE_USER_AGENTS = [
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
]


def _is_page_not_found(html: str) -> bool:
    """Check if the HTML indicates the profile does not exist."""
    not_found_signals = [
        "Page Not Found",
        "Sorry, this page isn",
        "The link you followed may be broken",
        "Profile isn\\'t available",
        "profile may have been removed",
        '"HttpErrorPage"',
    ]
    snippet = html[:10000]
    return any(signal in snippet for signal in not_found_signals)


def scrape_profile_no_login(username: str, max_retries: int = 3) -> Optional[Dict]:
    """Scrape Instagram profile using mobile web HTML parsing (no API)."""
    import random
    import time

    url = f'https://www.instagram.com/{username}/'

    for attempt in range(max_retries):
        proxies = get_requests_proxies()

        headers = {
            'User-Agent': random.choice(MOBILE_USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        try:
            r = requests.get(url, headers=headers, proxies=proxies, timeout=20)

            if r.status_code == 404:
                return None

            if r.status_code == 429:
                raise RuntimeError("Rate limited by Instagram (429). Wait a few minutes before scraping again.")

            if r.status_code != 200:
                logger.debug(f"HTTP {r.status_code} for @{username}, attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None

            html = r.text

            if _is_page_not_found(html):
                return None

            if '/accounts/login' in r.url or ('login' in html[:5000].lower() and 'password' in html[:5000].lower()):
                return None

            data = _extract_profile_from_html(html, username)

            if data:
                return data

            if attempt < max_retries - 1:
                logger.debug(f"Extraction failed for @{username}, retrying ({attempt + 1}/{max_retries})")
                time.sleep(1.0)
                continue

            return None

        except requests.exceptions.Timeout:
            logger.debug(f"Timeout for @{username}, attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None
        except RuntimeError:
            raise
        except Exception as e:
            err = str(e)
            if '429' in err:
                raise RuntimeError("Rate limited by Instagram (429). Wait a few minutes before scraping again.")
            logger.debug(f"Error scraping @{username}: {e}, attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None

    return None


def _extract_profile_from_html(html: str, username: str) -> Optional[Dict]:
    """Extract profile data from Instagram HTML page."""

    results = {}

    username_patterns = [
        r'"username":"([^"]+)"',
        r'"owner":\{"username":"([^"]+)"',
        r'instagram\.com/([a-zA-Z0-9_.]+)/"\s*>',
    ]
    for pattern in username_patterns:
        match = re.search(pattern, html)
        if match and match.group(1).lower() == username.lower():
            results['username'] = match.group(1)
            break

    name_patterns = [
        r'"full_name":"([^"]*)"',
        r'"name":"([^"]*)"',
        r'<title>([^(<]+)\s*\(@' + re.escape(username) + r'\)',
    ]
    for pattern in name_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match and 'full_name' not in results:
            results['full_name'] = match.group(1).strip()
            break

    bio_patterns = [
        r'"biography":"([^"]*)"',
        r'"bio":"([^"]*)"',
        r'"description":"([^"]*)"',
    ]
    for pattern in bio_patterns:
        match = re.search(pattern, html)
        if match and 'biography' not in results:
            try:
                decoded = match.group(1).encode('utf-8').decode('unicode_escape')
                results['biography'] = decoded.encode('utf-16', 'surrogatepass').decode('utf-16')
            except (UnicodeDecodeError, UnicodeEncodeError):
                results['biography'] = match.group(1).replace('\\u', '')
            break

    follower_patterns = [
        r'"follower_count":(\d+)',
        r'"edge_followed_by":\{"count":(\d+)\}',
        r'"userInteractionCount":"?(\d+)"?.*?[Ff]ollow',
        r'followers["\s:]+(\d+)',
    ]
    for pattern in follower_patterns:
        match = re.search(pattern, html)
        if match and 'follower_count' not in results:
            results['follower_count'] = int(match.group(1))
            break

    following_patterns = [
        r'"following_count":(\d+)',
        r'"edge_follow":\{"count":(\d+)\}',
    ]
    for pattern in following_patterns:
        match = re.search(pattern, html)
        if match and 'following_count' not in results:
            results['following_count'] = int(match.group(1))
            break

    media_patterns = [
        r'"media_count":(\d+)',
        r'"edge_owner_to_timeline_media":\{"count":(\d+)\}',
    ]
    for pattern in media_patterns:
        match = re.search(pattern, html)
        if match and 'media_count' not in results:
            results['media_count'] = int(match.group(1))
            break

    meta_patterns = [
        r'content="([\d.,]+[KMB]?)\s*Followers?,\s*([\d.,]+[KMB]?)\s*Following,\s*([\d.,]+[KMB]?)\s*Posts?',
        r'([\d.,]+[KMB]?)\s*Followers?\s*[,·]\s*([\d.,]+[KMB]?)\s*Following\s*[,·]\s*([\d.,]+[KMB]?)\s*Posts?',
    ]
    for pattern in meta_patterns:
        meta_match = re.search(pattern, html, re.IGNORECASE)
        if meta_match:
            if 'follower_count' not in results:
                results['follower_count'] = _parse_abbreviated_number(meta_match.group(1))
            if 'following_count' not in results:
                results['following_count'] = _parse_abbreviated_number(meta_match.group(2))
            if 'media_count' not in results:
                results['media_count'] = _parse_abbreviated_number(meta_match.group(3))
            break

    verified_patterns = [
        r'"is_verified":(true|false)',
        r'"verified":(true|false)',
    ]
    for pattern in verified_patterns:
        match = re.search(pattern, html)
        if match:
            results['is_verified'] = match.group(1) == 'true'
            break

    match = re.search(r'"is_private":(true|false)', html)
    if match:
        results['is_private'] = match.group(1) == 'true'

    match = re.search(r'"is_business_account":(true|false)', html)
    if match:
        results['is_business'] = match.group(1) == 'true'

    url_patterns = [
        r'"external_url":"([^"]+)"',
        r'"website":"([^"]+)"',
        r'"url":"(https?://[^"]+)"',
    ]
    for pattern in url_patterns:
        match = re.search(pattern, html)
        if match and 'external_url' not in results:
            try:
                decoded = match.group(1).replace('\\/', '/').encode('utf-8').decode('unicode_escape')
                results['external_url'] = decoded.encode('utf-16', 'surrogatepass').decode('utf-16')
            except (UnicodeDecodeError, UnicodeEncodeError):
                results['external_url'] = match.group(1).replace('\\/', '/')
            break

    if 'follower_count' not in results or results.get('follower_count', 0) == 0:
        return None

    bio = results.get('biography', '')

    return {
        'username': results.get('username', username),
        'full_name': results.get('full_name', ''),
        'bio': bio,
        'follower_count': results.get('follower_count', 0),
        'following_count': results.get('following_count', 0),
        'post_count': results.get('media_count', 0),
        'is_verified': results.get('is_verified', False),
        'is_private': results.get('is_private', False),
        'is_business': results.get('is_business', False),
        'website': results.get('external_url', ''),
        'email': _extract_email(bio),
        'phone': _extract_phone(bio),
        'platform': 'instagram',
        'profile_url': f'https://www.instagram.com/{username}/',
    }


_parse_abbreviated_number = parse_abbreviated_number
_extract_email = extract_email
_extract_phone = extract_phone
