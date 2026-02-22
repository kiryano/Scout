"""
Shared Scraper Utilities

Common functions used across all platform scrapers.

Provides:
- extract_email() — regex-based email extraction from text
- extract_phone() — phone number extraction from text
- parse_abbreviated_number() — converts "11.5K", "2.3M" to integers
"""

import re
from typing import List


def extract_email(text: str) -> str:
    """Extract first email address from text."""
    if not text:
        return ''
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(pattern, text)
    return matches[0] if matches else ''


def extract_phone(text: str) -> str:
    """Extract first phone number (10+ digits) from text."""
    if not text:
        return ''
    patterns = [
        r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            phone = re.sub(r'[^\d+]', '', matches[0])
            if len(phone) >= 10:
                return phone
    return ''


def parse_abbreviated_number(s: str) -> int:
    """Parse abbreviated numbers like 11M, 7.5K, 1.2B into integers."""
    s = s.strip().replace(',', '')
    multipliers = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000}

    for suffix, mult in multipliers.items():
        if s.upper().endswith(suffix):
            try:
                return int(float(s[:-1]) * mult)
            except (ValueError, IndexError):
                return 0

    try:
        return int(float(s))
    except ValueError:
        return 0
