"""
Twitch Profile Scraper

Fetches public Twitch channel information using the Helix API.
Extracts username, display name, bio, and profile image.
No authentication required for basic channel info.
"""

import requests
from typing import Dict, Optional
import logging
import re

from app.scrapers.stealth import random_user_agent

logger = logging.getLogger(__name__)

CLIENT_ID = 'kimne78kx3ncx6brgo4mv6wki5h1ko'


def scrape_profile(username: str) -> Optional[Dict]:
    """
    Fetch Twitch channel data using GQL API.

    Args:
        username: Twitch username
    """
    username = username.lower().strip()

    headers = {
        'Client-ID': CLIENT_ID,
        'User-Agent': random_user_agent(),
        'Accept': 'application/json',
    }

    query = """
    query {
        user(login: "%s") {
            id
            login
            displayName
            description
            followers {
                totalCount
            }
            roles {
                isPartner
                isAffiliate
            }
            channel {
                socialMedias {
                    name
                    url
                }
            }
        }
    }
    """ % username

    try:
        r = requests.post(
            'https://gql.twitch.tv/gql',
            headers=headers,
            json={'query': query},
            timeout=20
        )

        if r.status_code != 200:
            logger.error(f"Twitch API error {r.status_code} for {username}")
            return None

        data = r.json()

        if 'errors' in data:
            logger.error(f"Twitch GQL error for {username}: {data['errors']}")
            return None

        user_data = data.get('data', {}).get('user')
        if not user_data:
            logger.error(f"Twitch user {username} not found")
            return None

        return _format_profile(user_data, username)

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching Twitch profile {username}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Twitch profile {username}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing Twitch response for {username}: {e}")
        return None


def _format_profile(data: dict, username: str) -> Dict:
    """Format Twitch API response into standard profile format."""

    bio = data.get('description', '') or ''

    followers = data.get('followers', {})
    follower_count = followers.get('totalCount', 0) if followers else 0

    roles = data.get('roles', {}) or {}
    is_partner = roles.get('isPartner', False)
    is_affiliate = roles.get('isAffiliate', False)

    links = []
    channel = data.get('channel', {}) or {}
    social_medias = channel.get('socialMedias', []) or []
    for social in social_medias:
        url = social.get('url', '')
        if url:
            links.append(url)

    return {
        'username': data.get('login', username),
        'full_name': data.get('displayName', ''),
        'bio': bio,
        'email': _extract_email(bio),
        'follower_count': follower_count,
        'is_partner': is_partner,
        'is_affiliate': is_affiliate,
        'links': links[:5],
        'website': links[0] if links else '',
        'platform': 'twitch',
        'profile_url': f'https://twitch.tv/{data.get("login", username)}',
    }


def _extract_email(text: str) -> str:
    if not text:
        return ''
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(pattern, text)
    return matches[0] if matches else ''
