"""
Social media profile scrapers.

Supported platforms:
    - Instagram
    - TikTok
    - LinkedIn (requires cookie)
    - GitHub
    - YouTube
    - Twitch
"""

from .instagram import scrape_profile_no_login as scrape_instagram
from .tiktok import scrape_tiktok_profile as scrape_tiktok
from .linkedin import scrape_linkedin_profile as scrape_linkedin
from .github import scrape_profile as scrape_github
from .youtube import scrape_channel as scrape_youtube
from .twitch import scrape_profile as scrape_twitch

__all__ = [
    "scrape_instagram",
    "scrape_tiktok",
    "scrape_linkedin",
    "scrape_github",
    "scrape_youtube",
    "scrape_twitch",
]
