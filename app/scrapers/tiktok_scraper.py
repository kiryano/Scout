import json
import logging
import re
from datetime import datetime
from typing import Dict, Any

import httpx

from app.scrapers.stealth import random_user_agent, get_httpx_proxy

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        proxy = get_httpx_proxy()
        _client = httpx.Client(follow_redirects=True, timeout=20, proxy=proxy)
    return _client


def _build_headers() -> dict:
    return {
        'User-Agent': random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-Dest': 'document',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
    }


def scrape_tiktok_profile(username: str) -> Dict[str, Any]:
    url = f'https://www.tiktok.com/@{username}'
    logger.info(f"Scraping TikTok profile: {url}")

    try:
        client = _get_client()
        resp = client.get(url, headers=_build_headers())
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error for @{username}: {e.response.status_code}")
        return {'status': 'error', 'message': f'HTTP {e.response.status_code} for @{username}'}
    except httpx.RequestError as e:
        logger.error(f"Request error for @{username}: {e}")
        return {'status': 'error', 'message': str(e)}

    html = resp.text

    match = re.search(
        r'<script\s+id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        logger.warning(f"Could not find rehydration data for @{username}")
        return {
            'status': 'error',
            'message': f'Could not extract profile data for @{username}. Page may require CAPTCHA or profile does not exist.',
        }

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error for @{username}: {e}")
        return {'status': 'error', 'message': f'Failed to parse profile data for @{username}'}

    try:
        user_detail = data['__DEFAULT_SCOPE__']['webapp.user-detail']
        user_info = user_detail['userInfo']
        user = user_info.get('user', {})
        stats = user_info.get('stats', {})
    except (KeyError, TypeError) as e:
        logger.error(f"Unexpected JSON structure for @{username}: {e}")
        return {'status': 'error', 'message': f'Unexpected data structure for @{username}'}

    profile = {
        'platform': 'tiktok',
        'username': user.get('uniqueId', username),
        'full_name': user.get('nickname', ''),
        'bio': user.get('signature', ''),
        'profile_url': url,
        'is_verified': user.get('verified', False),
        'profile_pic_url': user.get('avatarLarger', ''),
        'follower_count': stats.get('followerCount', 0),
        'following_count': stats.get('followingCount', 0),
        'likes_count': stats.get('heartCount', 0),
        'video_count': stats.get('videoCount', 0),
        'scraped_from': f'@{username}',
        'scraped_at': datetime.utcnow().isoformat(),
    }

    logger.info(
        f"Scraped @{username}: {profile['full_name']} | "
        f"{profile['follower_count']} followers | {profile['likes_count']} likes"
    )

    return {
        'status': 'success',
        'message': f'Scraped @{username} successfully',
        'profile': profile,
    }
