# Scout

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Discord](https://img.shields.io/discord/1467620600267931713?color=7289da&label=Discord&logo=discord&logoColor=white)](https://discord.gg/eneDNUbzcc)

> **Early access** — Scout is a CLI tool right now. A full web app with dashboard, CRM, and team features is in development. Looking for testers and feedback. Join the [Discord](https://discord.gg/eneDNUbzcc) or open an issue.

Lead generation tool for appointment setters. Scrapes profiles from 8 platforms, enriches them with verified emails using SMTP verification and company domain detection, and exports to CSV.

![Scout CLI](screenshot.png)

## Install

```bash
git clone https://github.com/kiryano/Scout.git
cd Scout
pip install -r requirements.txt
cp .env.example .env
```

## Usage

```bash
python scout.py
python scout.py --verbose   # enable debug logging
python scout.py --version
python scout.py --help
```

Interactive CLI for scraping profiles, enriching leads with contact info, and exporting to CSV.

## Supported Platforms

| Platform | Auth Required | What It Scrapes |
|----------|--------------|-----------------|
| Instagram | None | profile, bio, followers, email, phone, links |
| TikTok | None | profile, bio, followers, likes, email |
| LinkedIn | Session cookie | profile, headline, bio, email |
| GitHub | None | profile, bio, repos, email, website |
| YouTube | None | channel name, description, subscribers, email, links |
| Twitch | None | profile, bio, followers, partner/affiliate status, social links |
| Pinterest | None | profile, bio, followers, pins, website |
| Linktree | None | all link-in-bio platforms (Linktree, Stan, Linkr, Bio.link) |

## Features

- 8 platform scrapers with consistent output format
- Email enrichment with SMTP verification (no paid API needed)
- Company domain detection from headline/bio
- Email pattern detection (first.last@company.com patterns)
- Lead scoring (0-100)
- Website deep scraping for contact info
- Bio link scraping (Linktree, WhatsApp, tel: links)
- CSV export with enriched data
- Bulk scraping from username lists (CSV/TXT)
- Proxy rotation and user-agent rotation
- Configurable scrape delay and proxy settings
- Automatic update checker with version enforcement
- Debug logging with `--verbose` flag

## LinkedIn Setup

1. Log into LinkedIn in Chrome
2. Open DevTools (F12) > Application > Cookies > linkedin.com
3. Copy the value of `li_at`
4. Add to `.env`:

```
LINKEDIN_COOKIE=your_li_at_cookie_value
```

## Proxy Setup

```
# Single proxy
SCOUT_PROXY=http://user:pass@host:port

# Rotating proxies from file (one per line)
SCOUT_PROXY_FILE=proxies.txt

# Free anonymous proxies (no config needed)
SCOUT_FREE_PROXY=true
```

Proxies are optional. All scrapers work without them. Twitch automatically falls back to a direct connection if the proxy fails.

## How Enrichment Works

After scraping, Scout enriches leads with verified email addresses:

1. Extracts email/phone from bio text
2. Scrapes the lead's website, /contact, and /about pages
3. Detects the company from their headline (e.g. "CEO at CompanyX")
4. Finds the company domain via DNS MX lookup
5. Detects the email pattern from existing emails on the site
6. Generates email candidates (first.last@, first@, etc.)
7. Verifies each candidate against the mail server via SMTP
8. Scores confidence 0-100% based on source and verification

No paid API required. Optional Hunter.io support for additional coverage.

## Limitations

- Instagram may require retries depending on region/IP
- TikTok may serve CAPTCHAs depending on region or IP
- LinkedIn cookies expire periodically
- GitHub API is limited to 60 requests/hour without a token
- SMTP verification may be blocked by some mail servers
- Free proxies are unreliable

## Community

[Discord](https://discord.gg/eneDNUbzcc)

## License

MIT
