"""
YouTube Channel Scraper

Scrapes public YouTube channel pages by parsing HTML and embedded JSON.
Extracts subscriber counts, video counts, channel description, and links.

Features:
- Parses ytInitialData JSON from page source
- Handles both @handle and /channel/ URL formats
- No API key required
"""

import requests
from typing import Dict, Optional
import logging
import re

from app.scrapers.stealth import random_user_agent, get_requests_proxies
from app.scrapers.utils import extract_email, parse_abbreviated_number

logger = logging.getLogger(__name__)


def scrape_channel(channel_identifier: str) -> Optional[Dict]:
    """
    Fetch YouTube channel data.

    Args:
        channel_identifier: Can be @handle, channel ID, or custom URL name
    """
    if channel_identifier.startswith('@'):
        url = f'https://www.youtube.com/{channel_identifier}/about'
    elif channel_identifier.startswith('UC') and len(channel_identifier) == 24:
        url = f'https://www.youtube.com/channel/{channel_identifier}/about'
    else:
        url = f'https://www.youtube.com/@{channel_identifier}/about'

    headers = {
        'User-Agent': random_user_agent(),
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        r = requests.get(url, headers=headers, timeout=20, proxies=get_requests_proxies())

        if r.status_code == 404:
            logger.error(f"YouTube channel {channel_identifier} not found")
            return None

        if r.status_code != 200:
            logger.error(f"YouTube error {r.status_code} for {channel_identifier}")
            return None

        html = r.text
        return _extract_channel_data(html, channel_identifier)

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching YouTube channel {channel_identifier}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching YouTube channel {channel_identifier}: {e}")
        return None


def _extract_channel_data(html: str, identifier: str) -> Optional[Dict]:
    """Extract channel data from YouTube page HTML."""

    results = {}

    name_match = re.search(r'"channelMetadataRenderer":\{"title":"([^"]+)"', html)
    if name_match:
        results['channel_name'] = name_match.group(1)

    desc_match = re.search(r'"description":"([^"]*)"', html)
    if desc_match:
        try:
            results['description'] = desc_match.group(1).encode('utf-8').decode('unicode_escape')
        except (UnicodeDecodeError, UnicodeEncodeError):
            results['description'] = desc_match.group(1)

    sub_patterns = [
        r'"subscriberCountText":\{"simpleText":"([\d.,]+[KMB]?) subscribers?"',
        r'"subscriberCountText":\{"accessibility":\{"accessibilityData":\{"label":"([\d.,]+[KMB]?) subscribers?"',
    ]
    for pattern in sub_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            results['subscriber_count'] = _parse_count(match.group(1))
            break

    handle_match = re.search(r'"canonicalChannelUrl":"https://www\.youtube\.com/@([^"]+)"', html)
    if handle_match:
        results['handle'] = handle_match.group(1)

    channel_id_match = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', html)
    if channel_id_match:
        results['channel_id'] = channel_id_match.group(1)

    email_match = re.search(r'"businessEmailLabel":\{"content":"([^"]+)"', html)
    if email_match:
        results['business_email'] = email_match.group(1)
    else:
        desc = results.get('description', '')
        results['business_email'] = _extract_email(desc)

    links = []
    link_pattern = r'"urlEndpoint":\{"url":"(https?://[^"]+)"'
    for match in re.finditer(link_pattern, html):
        link = match.group(1)
        if 'youtube.com' not in link and 'google.com' not in link:
            clean_link = _clean_redirect_url(link)
            if clean_link and clean_link not in links:
                links.append(clean_link)
    results['links'] = links[:5]

    if 'channel_name' not in results:
        return None

    handle = results.get('handle', identifier.lstrip('@'))

    return {
        'username': handle,
        'full_name': results.get('channel_name', ''),
        'bio': results.get('description', ''),
        'email': results.get('business_email', ''),
        'follower_count': results.get('subscriber_count', 0),
        'website': results['links'][0] if results.get('links') else '',
        'links': results.get('links', []),
        'channel_id': results.get('channel_id', ''),
        'platform': 'youtube',
        'profile_url': f'https://www.youtube.com/@{handle}',
    }


_parse_count = parse_abbreviated_number
_extract_email = extract_email


def _clean_redirect_url(url: str) -> str:
    """Extract actual URL from YouTube redirect wrapper."""
    if 'youtube.com/redirect' in url:
        q_match = re.search(r'[?&]q=([^&]+)', url)
        if q_match:
            from urllib.parse import unquote
            return unquote(q_match.group(1))
    return url
