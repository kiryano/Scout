#!/usr/bin/env python3

import sys
import csv
import time
import os
import logging
from pathlib import Path

if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent))

from app import __version__

_verbose = '--verbose' in sys.argv or '-V' in sys.argv
logging.basicConfig(
    level=logging.DEBUG if _verbose else logging.WARNING,
    format='%(name)s: %(message)s',
)

_args = [a for a in sys.argv[1:] if a not in ('--verbose', '-V')]
if _args:
    arg = _args[0].lower()
    if arg in ('--version', '-v', 'version'):
        print(f"Scout v{__version__}")
        sys.exit(0)
    elif arg in ('--help', '-h', 'help'):
        print(f"Scout v{__version__} - Social media lead generation tool")
        print()
        print("Usage: python scout.py [options]")
        print()
        print("Options:")
        print("  --version, -v    Show version")
        print("  --help, -h       Show this help")
        print("  --verbose, -V    Enable debug logging")
        print()
        print("Run without arguments to start the interactive menu.")
        sys.exit(0)

env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _key, _, _val = _line.partition('=')
                os.environ.setdefault(_key.strip(), _val.strip())

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from rich.layout import Layout
from rich.text import Text
from rich.theme import Theme

from app.scrapers.instagram import scrape_profile_no_login
from app.scrapers.stealth import random_delay, proxy_status

ACCENT = "#a70947"
ACCENT_DIM = "#6b0530"
ACCENT_LIGHT = "#d64d7a"

custom_theme = Theme({
    "prompt.choices": ACCENT,
    "prompt.default": "dim",
})
console = Console(theme=custom_theme)
Prompt.prompt_suffix = " "
Confirm.prompt_suffix = " "


def _update_env(key, value):
    env_path = Path(__file__).parent / '.env'
    lines = []
    found = False
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith(key + '='):
                    lines.append(f'{key}={value}\n')
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f'{key}={value}\n')
    with open(env_path, 'w') as f:
        f.writelines(lines)
    os.environ[key] = value


def enrich_profiles(profiles):
    if not profiles:
        return profiles

    if not Confirm.ask("\n[white][+] Enrich leads with contact info?[/white]", default=True):
        return profiles

    from app.scrapers.enrichment import LeadEnricher
    hunter_key = os.environ.get('HUNTER_API_KEY', '').strip() or None
    enricher = LeadEnricher(hunter_api_key=hunter_key)

    console.print()
    emails_found = 0
    phones_found = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("[white]Enriching leads...", total=len(profiles))

        enriched = []
        for p in profiles:
            had_email = bool(p.get('email'))
            had_phone = bool(p.get('phone'))

            result = enricher.enrich_lead(p)
            enriched.append(result)

            if result.get('email') and not had_email:
                emails_found += 1
            if result.get('phone') and not had_phone:
                phones_found += 1

            progress.advance(task)

    console.print()

    summary_parts = []
    if emails_found:
        summary_parts.append(f"[green]{emails_found} emails found[/green]")
    if phones_found:
        summary_parts.append(f"[green]{phones_found} phones found[/green]")
    if not summary_parts:
        summary_parts.append("[yellow]No new contact info found[/yellow]")

    scores = [e.get('lead_score', 0) for e in enriched]
    avg_score = sum(scores) // len(scores) if scores else 0
    summary_parts.append(f"[white]Avg lead score: {avg_score}/100[/white]")

    console.print(Panel(
        "\n".join(summary_parts),
        title="[bold]Enrichment Results[/bold]",
        border_style=ACCENT_DIM
    ))

    email_leads = [e for e in enriched if e.get('email')]
    if email_leads:
        console.print()
        t = Table(show_header=True, box=box.SIMPLE)
        t.add_column("Lead", style="white")
        t.add_column("Email", style="white")
        t.add_column("Confidence", style="green")
        t.add_column("Source", style="dim")
        t.add_column("Verified", style="yellow")

        for e in email_leads:
            name = e.get('full_name') or e.get('username', '?')
            email_score = e.get('email_score', 0)
            score_color = 'green' if email_score >= 70 else 'yellow' if email_score >= 40 else 'red'
            verified = 'Yes' if e.get('email_verified') else 'No'
            t.add_row(
                name[:25],
                e['email'],
                f"[{score_color}]{email_score}%[/{score_color}]",
                e.get('email_source', '?'),
                verified
            )

        console.print(t)

    return enriched


def show_header():
    logo = """
███████╗ ██████╗ ██████╗ ██╗   ██╗████████╗
██╔════╝██╔════╝██╔═══██╗██║   ██║╚══██╔══╝
███████╗██║     ██║   ██║██║   ██║   ██║
╚════██║██║     ██║   ██║██║   ██║   ██║
███████║╚██████╗╚██████╔╝╚██████╔╝   ██║
╚══════╝ ╚═════╝ ╚═════╝  ╚═════╝    ╚═╝
    """

    console.print(logo, style=f"bold {ACCENT}", justify="center")
    console.print("[bold white]Free Lead Generation Tool[/bold white]", justify="center")
    console.print()

    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column(justify="right", style="dim")
    info_table.add_column(style=f"{ACCENT}")

    info_table.add_row("Discord", "discord.gg/eneDNUbzcc")
    info_table.add_row("GitHub", "github.com/kiryano/Scout")

    ps = proxy_status()
    if ps == 'custom':
        info_table.add_row("Proxy", "[green]● custom[/green]")
    elif ps == 'file':
        info_table.add_row("Proxy", "[green]● rotating[/green]")
    elif ps == 'free':
        info_table.add_row("Proxy", "[yellow]● free[/yellow]")
    else:
        info_table.add_row("Proxy", "[dim]○ off[/dim]")

    console.print(info_table, justify="center")
    console.print()


def show_menu():
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 3),
        expand=False
    )

    table.add_column("", style=f"bold {ACCENT}", width=3)
    table.add_column("", style="white")
    table.add_column("", style="dim", width=20)

    table.add_row("1", "Instagram", "profiles")
    table.add_row("2", "TikTok", "profiles")
    table.add_row("3", "LinkedIn", "requires cookie")
    table.add_row("4", "GitHub", "profiles")
    table.add_row("5", "YouTube", "channels")
    table.add_row("6", "Twitch", "streamers")
    table.add_row("7", "Linktree", "link-in-bio")
    table.add_row("8", "Pinterest", "profiles")
    table.add_row("", "", "")
    table.add_row("9", "Bulk Scrape", "from file")
    table.add_row("10", "Exports", "view files")
    table.add_row("11", "Proxy", "settings")
    table.add_row("0", "Exit", "")

    console.print(Panel(
        table,
        title=f"[bold {ACCENT}]─── SELECT PLATFORM ───[/bold {ACCENT}]",
        border_style=ACCENT_DIM,
        box=box.HEAVY,
        padding=(1, 4)
    ))
    console.print()


def scrape_instagram_interactive():
    console.print()
    console.print(Panel(
        f"[bold {ACCENT}]INSTAGRAM[/bold {ACCENT}]\n[dim]No login required[/dim]",
        border_style=ACCENT_DIM,
        box=box.HEAVY
    ))
    console.print()

    console.print("[white]Enter Instagram usernames (one per line)[/white]")
    console.print("[dim]Press Enter on empty line when done[/dim]")
    console.print()

    usernames = []
    while True:
        username = Prompt.ask("Username", default="")
        if not username:
            break
        username = username.replace('@', '').strip()
        if username:
            usernames.append(username)
            console.print(f"[green]✓[/green] Added @{username}")

    if not usernames:
        console.print("[yellow]⚠ No usernames entered![/yellow]")
        return

    console.print()
    console.print(f"[bold white]Scraping {len(usernames)} profiles...[/bold white]")
    console.print()

    profiles = []
    successful = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        for i, username in enumerate(usernames, 1):
            task = progress.add_task(
                f"[white]Scraping @{username}...",
                total=None
            )

            try:
                profile = scrape_profile_no_login(username)

                if profile:
                    profiles.append(profile)
                    successful += 1

                    progress.update(task, description=f"[green]✓ @{username}")

                    info_table = Table(show_header=False, box=None, padding=(0, 2))
                    info_table.add_column(style="dim")
                    info_table.add_column(style="white")

                    info_table.add_row("Followers:", f"{profile['follower_count']:,}")

                    if profile.get('full_name'):
                        info_table.add_row("Name:", profile['full_name'][:50])

                    if profile.get('bio'):
                        bio = profile['bio'][:80] + '...' if len(profile['bio']) > 80 else profile['bio']
                        info_table.add_row("Bio:", bio)

                    if profile.get('email'):
                        info_table.add_row("Email:", profile['email'])

                    if profile.get('website'):
                        info_table.add_row("Website:", profile['website'])

                    console.print(info_table)
                    console.print()

                else:
                    progress.update(task, description=f"[red]✗ @{username} - Failed")

            except RuntimeError as e:
                progress.update(task, description=f"[red]✗ @{username} - Rate Limited")
                console.print(f"\n[bold red]⚠ {e}[/bold red]")
                break
            except Exception as e:
                progress.update(task, description=f"[red]✗ @{username} - Error")
                console.print(f"[dim red]Error: {str(e)[:100]}[/dim red]")

            if i < len(usernames):
                random_delay(1.5, 4.0)

    console.print()

    if profiles:
        result_panel = Panel(
            f"[bold green]Successfully scraped {successful}/{len(usernames)} profiles[/bold green]",
            style="green",
            box=box.DOUBLE
        )
        console.print(result_panel)
        console.print()

        profiles = enrich_profiles(profiles)

        if Confirm.ask("[+] Export to CSV?", default=True):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"instagram_export_{timestamp}.csv"

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if profiles:
                    writer = csv.DictWriter(f, fieldnames=profiles[0].keys())
                    writer.writeheader()
                    writer.writerows(profiles)

            console.print()
            console.print(Panel(
                f"[bold]Exported to:[/bold] [white]{filename}[/white]\n"
                f"[bold]Total profiles:[/bold] {len(profiles)}",
                title="[green]✓ Export Complete[/green]",
                border_style="green"
            ))
    else:
        console.print(Panel(
            "[yellow]No profiles were scraped successfully[/yellow]",
            style="yellow"
        ))


def scrape_tiktok_interactive():
    from app.scrapers.tiktok import scrape_tiktok_profile

    console.print()
    console.print(Panel(
        f"[bold {ACCENT}]TIKTOK[/bold {ACCENT}]\n[dim]No login required[/dim]",
        border_style=ACCENT_DIM,
        box=box.HEAVY
    ))
    console.print()

    console.print("[white]Enter TikTok usernames (one per line, without @)[/white]")
    console.print("[dim]Press Enter on empty line when done[/dim]")
    console.print()

    usernames = []
    while True:
        username = Prompt.ask("Username", default="")
        if not username:
            break
        username = username.replace('@', '').strip()
        if username:
            usernames.append(username)
            console.print(f"[green]✓[/green] Added @{username}")

    if not usernames:
        console.print("[yellow]⚠ No usernames entered![/yellow]")
        return

    console.print()
    console.print(f"[bold white]Scraping {len(usernames)} TikTok profiles...[/bold white]")
    console.print()

    profiles = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        for i, username in enumerate(usernames, 1):
            task = progress.add_task(
                f"[white]Scraping @{username}...",
                total=None
            )

            try:
                profile = scrape_tiktok_profile(username)

                if profile:
                    profiles.append(profile)

                    progress.update(task, description=f"[green]✓ @{username}")

                    info_table = Table(show_header=False, box=None, padding=(0, 2))
                    info_table.add_column(style="dim")
                    info_table.add_column(style="white")

                    if profile.get('follower_count'):
                        info_table.add_row("Followers:", str(profile['follower_count']))
                    if profile.get('full_name'):
                        info_table.add_row("Name:", profile['full_name'][:50])
                    if profile.get('bio'):
                        bio = profile['bio'][:80] + '...' if len(profile['bio']) > 80 else profile['bio']
                        info_table.add_row("Bio:", bio)
                    if profile.get('email'):
                        info_table.add_row("Email:", profile['email'])

                    console.print(info_table)
                    console.print()
                else:
                    progress.update(task, description=f"[red]✗ @{username} - Failed")

            except Exception as e:
                progress.update(task, description=f"[red]✗ @{username} - Error")
                console.print(f"[dim red]Error: {str(e)[:100]}[/dim red]")

            if i < len(usernames):
                random_delay(2.0, 5.0)

    console.print()

    if profiles:
        result_panel = Panel(
            f"[bold green]Successfully scraped {len(profiles)}/{len(usernames)} profiles[/bold green]",
            style="green",
            box=box.DOUBLE
        )
        console.print(result_panel)
        console.print()

        profiles = enrich_profiles(profiles)

        if Confirm.ask("[+] Export to CSV?", default=True):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"tiktok_export_{timestamp}.csv"

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if profiles:
                    writer = csv.DictWriter(f, fieldnames=profiles[0].keys())
                    writer.writeheader()
                    writer.writerows(profiles)

            console.print()
            console.print(Panel(
                f"[bold]Exported to:[/bold] [white]{filename}[/white]\n"
                f"[bold]Total profiles:[/bold] {len(profiles)}",
                title="[green]✓ Export Complete[/green]",
                border_style="green"
            ))
    else:
        console.print(Panel(
            "[yellow]No profiles were scraped successfully[/yellow]",
            style="yellow"
        ))


def scrape_linkedin_interactive():
    from app.scrapers.linkedin import scrape_linkedin_profile

    console.print()

    cookie = os.environ.get('LINKEDIN_COOKIE', '').strip()
    if not cookie:
        console.print(Panel(
            "[bold yellow]LinkedIn Cookie Required[/bold yellow]\n\n"
            "[white]To scrape LinkedIn profiles:[/white]\n"
            "1. Open Chrome and go to linkedin.com (logged in)\n"
            "2. Press F12 > Application > Cookies > linkedin.com\n"
            "3. Copy the value of [white]li_at[/white]\n"
            "4. Add to your .env file: [white]LINKEDIN_COOKIE=your_value_here[/white]\n"
            "5. Restart Scout",
            style="yellow",
            box=box.DOUBLE
        ))
        console.print()
        return

    console.print(Panel(
        f"[bold {ACCENT}]LINKEDIN[/bold {ACCENT}]\n[dim]Using session cookie[/dim]",
        border_style=ACCENT_DIM,
        box=box.HEAVY
    ))
    console.print()

    console.print("[white]Enter LinkedIn usernames or profile URLs (one per line)[/white]")
    console.print("[dim]Press Enter on empty line when done[/dim]")
    console.print()

    usernames = []
    while True:
        entry = Prompt.ask("Username/URL", default="")
        if not entry:
            break
        entry = entry.strip().rstrip('/')
        if '/in/' in entry:
            entry = entry.split('/in/')[-1]
        entry = entry.lstrip('@').strip()
        if entry:
            usernames.append(entry)
            console.print(f"[green]✓[/green] Added {entry}")

    if not usernames:
        console.print("[yellow]No usernames entered![/yellow]")
        return

    console.print()
    console.print(f"[bold white]Scraping {len(usernames)} LinkedIn profiles...[/bold white]")
    console.print()

    profiles = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        for i, username in enumerate(usernames, 1):
            task = progress.add_task(
                f"[white]Scraping {username}...",
                total=None
            )

            try:
                profile = scrape_linkedin_profile(username)

                if profile:
                    profiles.append(profile)

                    progress.update(task, description=f"[green]✓ {username}")

                    info_table = Table(show_header=False, box=None, padding=(0, 2))
                    info_table.add_column(style="dim")
                    info_table.add_column(style="white")

                    if profile.get('full_name'):
                        info_table.add_row("Name:", profile['full_name'][:50])
                    if profile.get('headline'):
                        info_table.add_row("Title:", profile['headline'][:80])
                    if profile.get('company'):
                        info_table.add_row("Company:", profile['company'][:50])
                    if profile.get('location'):
                        info_table.add_row("Location:", profile['location'][:50])
                    if profile.get('email'):
                        info_table.add_row("Email:", profile['email'])

                    console.print(info_table)
                    console.print()
                else:
                    progress.update(task, description=f"[red]✗ {username} - Failed")

            except Exception as e:
                progress.update(task, description=f"[red]✗ {username} - Error")
                console.print(f"[dim red]Error: {str(e)[:100]}[/dim red]")

            if i < len(usernames):
                random_delay(3.0, 6.0)

    console.print()

    if profiles:
        result_panel = Panel(
            f"[bold green]Successfully scraped {len(profiles)}/{len(usernames)} profiles[/bold green]",
            style="green",
            box=box.DOUBLE
        )
        console.print(result_panel)
        console.print()

        profiles = enrich_profiles(profiles)

        if Confirm.ask("[+] Export to CSV?", default=True):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"linkedin_export_{timestamp}.csv"

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if profiles:
                    writer = csv.DictWriter(f, fieldnames=profiles[0].keys())
                    writer.writeheader()
                    writer.writerows(profiles)

            console.print()
            console.print(Panel(
                f"[bold]Exported to:[/bold] [white]{filename}[/white]\n"
                f"[bold]Total profiles:[/bold] {len(profiles)}",
                title="[green]✓ Export Complete[/green]",
                border_style="green"
            ))
    else:
        console.print(Panel(
            "[yellow]No profiles were scraped successfully[/yellow]",
            style="yellow"
        ))


def scrape_github_interactive():
    from app.scrapers.github import scrape_profile

    console.print()
    console.print(Panel(
        f"[bold {ACCENT}]GITHUB[/bold {ACCENT}]\n[dim]No login required[/dim]",
        border_style=ACCENT_DIM,
        box=box.HEAVY
    ))
    console.print()

    console.print("[white]Enter GitHub usernames (one per line)[/white]")
    console.print("[dim]Press Enter on empty line when done[/dim]")
    console.print()

    usernames = []
    while True:
        username = Prompt.ask("Username", default="")
        if not username:
            break
        username = username.strip()
        if username:
            usernames.append(username)
            console.print(f"[green]✓[/green] Added {username}")

    if not usernames:
        console.print("[yellow]No usernames entered![/yellow]")
        return

    console.print()
    console.print(f"[bold white]Scraping {len(usernames)} GitHub profiles...[/bold white]")
    console.print()

    profiles = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        for i, username in enumerate(usernames, 1):
            task = progress.add_task(
                f"[white]Scraping {username}...",
                total=None
            )

            try:
                profile = scrape_profile(username)

                if profile:
                    profiles.append(profile)
                    progress.update(task, description=f"[green]✓ {username}")

                    info_table = Table(show_header=False, box=None, padding=(0, 2))
                    info_table.add_column(style="dim")
                    info_table.add_column(style="white")

                    if profile.get('full_name'):
                        info_table.add_row("Name:", profile['full_name'][:50])
                    if profile.get('follower_count'):
                        info_table.add_row("Followers:", str(profile['follower_count']))
                    if profile.get('bio'):
                        bio = profile['bio'][:80] + '...' if len(profile['bio']) > 80 else profile['bio']
                        info_table.add_row("Bio:", bio)
                    if profile.get('email'):
                        info_table.add_row("Email:", profile['email'])
                    if profile.get('company'):
                        info_table.add_row("Company:", profile['company'])
                    if profile.get('website'):
                        info_table.add_row("Website:", profile['website'])

                    console.print(info_table)
                    console.print()
                else:
                    progress.update(task, description=f"[red]✗ {username} - Not found")

            except Exception as e:
                progress.update(task, description=f"[red]✗ {username} - Error")
                console.print(f"[dim red]Error: {str(e)[:100]}[/dim red]")

            if i < len(usernames):
                random_delay(0.5, 1.5)

    console.print()

    if profiles:
        result_panel = Panel(
            f"[bold green]Successfully scraped {len(profiles)}/{len(usernames)} profiles[/bold green]",
            style="green",
            box=box.DOUBLE
        )
        console.print(result_panel)
        console.print()

        profiles = enrich_profiles(profiles)

        if Confirm.ask("[+] Export to CSV?", default=True):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"github_export_{timestamp}.csv"

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if profiles:
                    writer = csv.DictWriter(f, fieldnames=profiles[0].keys())
                    writer.writeheader()
                    writer.writerows(profiles)

            console.print()
            console.print(Panel(
                f"[bold]Exported to:[/bold] [white]{filename}[/white]\n"
                f"[bold]Total profiles:[/bold] {len(profiles)}",
                title="[green]✓ Export Complete[/green]",
                border_style="green"
            ))
    else:
        console.print(Panel(
            "[yellow]No profiles were scraped successfully[/yellow]",
            style="yellow"
        ))


def scrape_youtube_interactive():
    from app.scrapers.youtube import scrape_channel

    console.print()
    console.print(Panel(
        f"[bold {ACCENT}]YOUTUBE[/bold {ACCENT}]\n[dim]No login required[/dim]",
        border_style=ACCENT_DIM,
        box=box.HEAVY
    ))
    console.print()

    console.print("[white]Enter YouTube channel handles (e.g. @MrBeast) or channel IDs[/white]")
    console.print("[dim]Press Enter on empty line when done[/dim]")
    console.print()

    channels = []
    while True:
        channel = Prompt.ask("Channel", default="")
        if not channel:
            break
        channel = channel.strip()
        if channel:
            channels.append(channel)
            console.print(f"[green]✓[/green] Added {channel}")

    if not channels:
        console.print("[yellow]No channels entered![/yellow]")
        return

    console.print()
    console.print(f"[bold white]Scraping {len(channels)} YouTube channels...[/bold white]")
    console.print()

    profiles = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        for i, channel in enumerate(channels, 1):
            task = progress.add_task(
                f"[white]Scraping {channel}...",
                total=None
            )

            try:
                profile = scrape_channel(channel)

                if profile:
                    profiles.append(profile)
                    progress.update(task, description=f"[green]✓ {channel}")

                    info_table = Table(show_header=False, box=None, padding=(0, 2))
                    info_table.add_column(style="dim")
                    info_table.add_column(style="white")

                    if profile.get('full_name'):
                        info_table.add_row("Name:", profile['full_name'][:50])
                    if profile.get('follower_count'):
                        info_table.add_row("Subscribers:", f"{profile['follower_count']:,}")
                    if profile.get('bio'):
                        bio = profile['bio'][:80] + '...' if len(profile['bio']) > 80 else profile['bio']
                        info_table.add_row("Description:", bio)
                    if profile.get('email'):
                        info_table.add_row("Email:", profile['email'])
                    if profile.get('website'):
                        info_table.add_row("Website:", profile['website'])

                    console.print(info_table)
                    console.print()
                else:
                    progress.update(task, description=f"[red]✗ {channel} - Not found")

            except Exception as e:
                progress.update(task, description=f"[red]✗ {channel} - Error")
                console.print(f"[dim red]Error: {str(e)[:100]}[/dim red]")

            if i < len(channels):
                random_delay(1.0, 2.5)

    console.print()

    if profiles:
        result_panel = Panel(
            f"[bold green]Successfully scraped {len(profiles)}/{len(channels)} channels[/bold green]",
            style="green",
            box=box.DOUBLE
        )
        console.print(result_panel)
        console.print()

        profiles = enrich_profiles(profiles)

        if Confirm.ask("[+] Export to CSV?", default=True):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"youtube_export_{timestamp}.csv"

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if profiles:
                    writer = csv.DictWriter(f, fieldnames=profiles[0].keys())
                    writer.writeheader()
                    writer.writerows(profiles)

            console.print()
            console.print(Panel(
                f"[bold]Exported to:[/bold] [white]{filename}[/white]\n"
                f"[bold]Total channels:[/bold] {len(profiles)}",
                title="[green]✓ Export Complete[/green]",
                border_style="green"
            ))
    else:
        console.print(Panel(
            "[yellow]No channels were scraped successfully[/yellow]",
            style="yellow"
        ))


def scrape_twitch_interactive():
    from app.scrapers.twitch import scrape_profile

    console.print()
    console.print(Panel(
        f"[bold {ACCENT}]TWITCH[/bold {ACCENT}]\n[dim]No login required[/dim]",
        border_style=ACCENT_DIM,
        box=box.HEAVY
    ))
    console.print()

    console.print("[white]Enter Twitch usernames (one per line)[/white]")
    console.print("[dim]Press Enter on empty line when done[/dim]")
    console.print()

    usernames = []
    while True:
        username = Prompt.ask("Username", default="")
        if not username:
            break
        username = username.strip()
        if username:
            usernames.append(username)
            console.print(f"[green]✓[/green] Added {username}")

    if not usernames:
        console.print("[yellow]No usernames entered![/yellow]")
        return

    console.print()
    console.print(f"[bold white]Scraping {len(usernames)} Twitch profiles...[/bold white]")
    console.print()

    profiles = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        for i, username in enumerate(usernames, 1):
            task = progress.add_task(
                f"[white]Scraping {username}...",
                total=None
            )

            try:
                profile = scrape_profile(username)

                if profile:
                    profiles.append(profile)
                    progress.update(task, description=f"[green]✓ {username}")

                    info_table = Table(show_header=False, box=None, padding=(0, 2))
                    info_table.add_column(style="dim")
                    info_table.add_column(style="white")

                    if profile.get('full_name'):
                        info_table.add_row("Name:", profile['full_name'][:50])
                    if profile.get('follower_count'):
                        info_table.add_row("Followers:", f"{profile['follower_count']:,}")
                    if profile.get('bio'):
                        bio = profile['bio'][:80] + '...' if len(profile['bio']) > 80 else profile['bio']
                        info_table.add_row("Bio:", bio)
                    if profile.get('is_partner'):
                        info_table.add_row("Status:", "[purple]Partner[/purple]")
                    elif profile.get('is_affiliate'):
                        info_table.add_row("Status:", "[blue]Affiliate[/blue]")
                    if profile.get('email'):
                        info_table.add_row("Email:", profile['email'])

                    console.print(info_table)
                    console.print()
                else:
                    progress.update(task, description=f"[red]✗ {username} - Not found")

            except Exception as e:
                progress.update(task, description=f"[red]✗ {username} - Error")
                console.print(f"[dim red]Error: {str(e)[:100]}[/dim red]")

            if i < len(usernames):
                random_delay(0.5, 1.5)

    console.print()

    if profiles:
        result_panel = Panel(
            f"[bold green]Successfully scraped {len(profiles)}/{len(usernames)} profiles[/bold green]",
            style="green",
            box=box.DOUBLE
        )
        console.print(result_panel)
        console.print()

        profiles = enrich_profiles(profiles)

        if Confirm.ask("[+] Export to CSV?", default=True):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"twitch_export_{timestamp}.csv"

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if profiles:
                    writer = csv.DictWriter(f, fieldnames=profiles[0].keys())
                    writer.writeheader()
                    writer.writerows(profiles)

            console.print()
            console.print(Panel(
                f"[bold]Exported to:[/bold] [white]{filename}[/white]\n"
                f"[bold]Total profiles:[/bold] {len(profiles)}",
                title="[green]✓ Export Complete[/green]",
                border_style="green"
            ))
    else:
        console.print(Panel(
            "[yellow]No profiles were scraped successfully[/yellow]",
            style="yellow"
        ))


def scrape_linktree_interactive():
    from app.scrapers.linktree import scrape_linktree, scrape_all

    console.print()
    console.print(Panel(
        f"[bold {ACCENT}]LINK-IN-BIO[/bold {ACCENT}]\n[dim]Linktree, Stan & more[/dim]",
        border_style=ACCENT_DIM,
        box=box.HEAVY
    ))
    console.print()

    console.print(f"[bold {ACCENT}]Select platform:[/bold {ACCENT}]")
    console.print("[1] Linktree (linktr.ee)")
    console.print("[2] Auto-detect (try all)")
    console.print()

    platform_choice = Prompt.ask("[>] Platform", choices=["1", "2"], default="1")

    scraper_map = {
        "1": (scrape_linktree, "linktree"),
        "2": (scrape_all, "linkbio"),
    }
    scraper_func, platform_name = scraper_map[platform_choice]

    console.print()
    console.print("[white]Enter usernames (one per line)[/white]")
    console.print("[dim]Press Enter on empty line when done[/dim]")
    console.print()

    usernames = []
    while True:
        username = Prompt.ask("Username", default="")
        if not username:
            break
        username = username.strip()
        if username:
            usernames.append(username)
            console.print(f"[green]✓[/green] Added {username}")

    if not usernames:
        console.print("[yellow]No usernames entered![/yellow]")
        return

    console.print()
    console.print(f"[bold white]Scraping {len(usernames)} profiles...[/bold white]")
    console.print()

    profiles = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        for i, username in enumerate(usernames, 1):
            task = progress.add_task(
                f"[white]Scraping {username}...",
                total=None
            )

            try:
                profile = scraper_func(username)

                if profile:
                    profiles.append(profile)
                    progress.update(task, description=f"[green]✓ {username}")

                    info_table = Table(show_header=False, box=None, padding=(0, 2))
                    info_table.add_column(style="dim")
                    info_table.add_column(style="white")

                    if profile.get('full_name'):
                        info_table.add_row("Name:", profile['full_name'][:50])
                    if profile.get('link_count'):
                        info_table.add_row("Links:", str(profile['link_count']))
                    if profile.get('bio'):
                        bio = profile['bio'][:80] + '...' if len(profile['bio']) > 80 else profile['bio']
                        info_table.add_row("Bio:", bio)
                    if profile.get('email'):
                        info_table.add_row("Email:", profile['email'])
                    if profile.get('socials'):
                        socials = profile['socials']
                        social_str = ', '.join([f"{k}" for k in list(socials.keys())[:4]])
                        info_table.add_row("Socials:", social_str)

                    console.print(info_table)
                    console.print()
                else:
                    progress.update(task, description=f"[red]✗ {username} - Not found")

            except Exception as e:
                progress.update(task, description=f"[red]✗ {username} - Error")
                console.print(f"[dim red]Error: {str(e)[:100]}[/dim red]")

            if i < len(usernames):
                random_delay(0.5, 1.5)

    console.print()

    if profiles:
        result_panel = Panel(
            f"[bold green]Successfully scraped {len(profiles)}/{len(usernames)} profiles[/bold green]",
            style="green",
            box=box.DOUBLE
        )
        console.print(result_panel)
        console.print()

        profiles = enrich_profiles(profiles)

        if Confirm.ask("[+] Export to CSV?", default=True):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{platform_name}_export_{timestamp}.csv"

            export_profiles = []
            for p in profiles:
                flat = {k: v for k, v in p.items() if k not in ['links', 'socials']}
                if p.get('socials'):
                    for platform, handle in p['socials'].items():
                        flat[f'social_{platform}'] = handle
                export_profiles.append(flat)

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if export_profiles:
                    all_keys = set()
                    for p in export_profiles:
                        all_keys.update(p.keys())
                    writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
                    writer.writeheader()
                    writer.writerows(export_profiles)

            console.print()
            console.print(Panel(
                f"[bold]Exported to:[/bold] [white]{filename}[/white]\n"
                f"[bold]Total profiles:[/bold] {len(profiles)}",
                title="[green]✓ Export Complete[/green]",
                border_style="green"
            ))
    else:
        console.print(Panel(
            "[yellow]No profiles were scraped successfully[/yellow]",
            style="yellow"
        ))


def scrape_pinterest_interactive():
    from app.scrapers.pinterest import scrape_profile

    console.print()
    console.print(Panel(
        f"[bold {ACCENT}]PINTEREST[/bold {ACCENT}]\n[dim]No login required[/dim]",
        border_style=ACCENT_DIM,
        box=box.HEAVY
    ))
    console.print()

    console.print("[white]Enter Pinterest usernames (one per line)[/white]")
    console.print("[dim]Press Enter on empty line when done[/dim]")
    console.print()

    usernames = []
    while True:
        username = Prompt.ask("Username", default="")
        if not username:
            break
        username = username.strip()
        if username:
            usernames.append(username)
            console.print(f"[green]✓[/green] Added {username}")

    if not usernames:
        console.print("[yellow]No usernames entered![/yellow]")
        return

    console.print()
    console.print(f"[bold white]Scraping {len(usernames)} Pinterest profiles...[/bold white]")
    console.print()

    profiles = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        for i, username in enumerate(usernames, 1):
            task = progress.add_task(
                f"[white]Scraping {username}...",
                total=None
            )

            try:
                profile = scrape_profile(username)

                if profile:
                    profiles.append(profile)
                    progress.update(task, description=f"[green]✓ {username}")

                    info_table = Table(show_header=False, box=None, padding=(0, 2))
                    info_table.add_column(style="dim")
                    info_table.add_column(style="white")

                    if profile.get('full_name'):
                        info_table.add_row("Name:", profile['full_name'][:50])
                    if profile.get('follower_count'):
                        info_table.add_row("Followers:", f"{profile['follower_count']:,}")
                    if profile.get('pin_count'):
                        info_table.add_row("Pins:", f"{profile['pin_count']:,}")
                    if profile.get('board_count'):
                        info_table.add_row("Boards:", f"{profile['board_count']:,}")
                    if profile.get('bio'):
                        bio = profile['bio'][:80] + '...' if len(profile['bio']) > 80 else profile['bio']
                        info_table.add_row("Bio:", bio)
                    if profile.get('website'):
                        info_table.add_row("Website:", profile['website'])
                    if profile.get('email'):
                        info_table.add_row("Email:", profile['email'])

                    console.print(info_table)
                    console.print()
                else:
                    progress.update(task, description=f"[red]✗ {username} - Not found")

            except Exception as e:
                progress.update(task, description=f"[red]✗ {username} - Error")
                console.print(f"[dim red]Error: {str(e)[:100]}[/dim red]")

            if i < len(usernames):
                random_delay(1.0, 2.5)

    console.print()

    if profiles:
        result_panel = Panel(
            f"[bold green]Successfully scraped {len(profiles)}/{len(usernames)} profiles[/bold green]",
            style="green",
            box=box.DOUBLE
        )
        console.print(result_panel)
        console.print()

        profiles = enrich_profiles(profiles)

        if Confirm.ask("[+] Export to CSV?", default=True):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"pinterest_export_{timestamp}.csv"

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if profiles:
                    writer = csv.DictWriter(f, fieldnames=profiles[0].keys())
                    writer.writeheader()
                    writer.writerows(profiles)

            console.print()
            console.print(Panel(
                f"[bold]Exported to:[/bold] [white]{filename}[/white]\n"
                f"[bold]Total profiles:[/bold] {len(profiles)}",
                title="[green]✓ Export Complete[/green]",
                border_style="green"
            ))
    else:
        console.print(Panel(
            "[yellow]No profiles were scraped successfully[/yellow]",
            style="yellow"
        ))


def scrape_from_file():
    console.print()
    console.print(Panel(
        f"[bold {ACCENT}]BULK SCRAPE[/bold {ACCENT}]\n[dim]From username list file (TXT or CSV)[/dim]",
        border_style=ACCENT_DIM,
        box=box.HEAVY
    ))
    console.print()

    filename = Prompt.ask("[>] Enter filename", default="usernames.txt")

    try:
        usernames = []
        if filename.lower().endswith('.csv'):
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    username = row.get('username', '') or row.get('Username', '') or row.get('handle', '') or row.get('Handle', '')
                    if not username:
                        first_col = list(row.values())[0] if row else ''
                        username = first_col
                    username = username.strip().replace('@', '')
                    if username:
                        usernames.append(username)
        else:
            with open(filename, 'r', encoding='utf-8') as f:
                usernames = [line.strip().replace('@', '') for line in f if line.strip()]

        if not usernames:
            console.print(f"\n[red]✗ No usernames found in {filename}[/red]")
            return

        console.print(f"\n[white]Found {len(usernames)} usernames in {filename}[/white]")

        console.print()
        console.print(f"[bold {ACCENT}]Select platform:[/bold {ACCENT}]")
        console.print("[1] Instagram")
        console.print("[2] TikTok")
        console.print("[3] LinkedIn")
        console.print("[4] YouTube")
        console.print("[5] GitHub")
        console.print("[6] Twitch")
        console.print("[7] Linktree")
        console.print("[8] Pinterest")
        console.print()

        platform_choice = Prompt.ask("[>] Platform", choices=["1", "2", "3", "4", "5", "6", "7", "8"], default="1")

        platform_map = {
            "1": ("instagram", "Instagram"),
            "2": ("tiktok", "TikTok"),
            "3": ("linkedin", "LinkedIn"),
            "4": ("youtube", "YouTube"),
            "5": ("github", "GitHub"),
            "6": ("twitch", "Twitch"),
            "7": ("linktree", "Linktree"),
            "8": ("pinterest", "Pinterest"),
        }
        platform_key, platform_name = platform_map[platform_choice]

        if platform_key == "instagram":
            from app.scrapers.instagram import scrape_profile_no_login as scraper_func
        elif platform_key == "tiktok":
            from app.scrapers.tiktok import scrape_tiktok_profile as scraper_func
        elif platform_key == "linkedin":
            cookie = os.environ.get('LINKEDIN_COOKIE', '').strip()
            if not cookie:
                console.print("[red]✗ LINKEDIN_COOKIE not set in .env. Cannot bulk scrape LinkedIn.[/red]")
                return
            from app.scrapers.linkedin import scrape_linkedin_profile as scraper_func
        elif platform_key == "youtube":
            from app.scrapers.youtube import scrape_channel as scraper_func
        elif platform_key == "github":
            from app.scrapers.github import scrape_profile as scraper_func
        elif platform_key == "twitch":
            from app.scrapers.twitch import scrape_profile as scraper_func
        elif platform_key == "linktree":
            from app.scrapers.linktree import scrape_linktree as scraper_func
        elif platform_key == "pinterest":
            from app.scrapers.pinterest import scrape_profile as scraper_func

        console.print()
        console.print(f"[white]Scraping {len(usernames)} {platform_name} profiles...[/white]")

        if not Confirm.ask("Continue?", default=True):
            return

        console.print()

        profiles = []
        successful = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:

            for i, username in enumerate(usernames, 1):
                task = progress.add_task(
                    f"[{i}/{len(usernames)}] @{username}...",
                    total=None
                )

                try:
                    profile = scraper_func(username)

                    if profile:
                        profiles.append(profile)
                        successful += 1
                        follower_count = profile.get('follower_count', 0) or profile.get('subscribers', 0) or 0
                        progress.update(
                            task,
                            description=f"[green]✓[/green] [{i}/{len(usernames)}] @{username} ({follower_count:,} followers)"
                        )
                    else:
                        progress.update(
                            task,
                            description=f"[red]✗[/red] [{i}/{len(usernames)}] @{username}"
                        )

                except Exception as e:
                    progress.update(
                        task,
                        description=f"[red]✗[/red] [{i}/{len(usernames)}] @{username}"
                    )

                if i < len(usernames):
                    random_delay(1.5, 4.0)

        console.print()

        if profiles:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            export_filename = f"{platform_key}_export_{timestamp}.csv"

            with open(export_filename, 'w', newline='', encoding='utf-8') as f:
                if profiles:
                    writer = csv.DictWriter(f, fieldnames=profiles[0].keys())
                    writer.writeheader()
                    writer.writerows(profiles)

            console.print(Panel(
                f"[bold green]SUCCESS![/bold green]\n\n"
                f"[bold]Platform:[/bold] {platform_name}\n"
                f"[bold]Scraped:[/bold] {successful}/{len(usernames)} profiles\n"
                f"[bold]Exported to:[/bold] [white]{export_filename}[/white]",
                title="[green]✓ Complete[/green]",
                border_style="green",
                box=box.DOUBLE
            ))
        else:
            console.print(Panel(
                "[yellow]No profiles were scraped successfully[/yellow]",
                style="yellow"
            ))

    except FileNotFoundError:
        console.print(f"\n[red]✗ Error: File '{filename}' not found![/red]")
    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")


def proxy_settings():
    import httpx as _httpx

    console.print()
    console.print(Panel(
        f"[bold {ACCENT}]PROXY SETTINGS[/bold {ACCENT}]\n[dim]Configure proxy for scraping[/dim]",
        border_style=ACCENT_DIM,
        box=box.HEAVY
    ))
    console.print()

    ps = proxy_status()
    current_proxy = os.environ.get('SCOUT_PROXY', '')
    free_enabled = os.environ.get('SCOUT_FREE_PROXY', '').lower() in ('1', 'true', 'yes')

    status_table = Table(show_header=False, box=None, padding=(0, 2))
    status_table.add_column(style="dim")
    status_table.add_column(style="white")
    proxy_file = os.environ.get('SCOUT_PROXY_FILE', '')

    status_table.add_row("Status:", f"[green]{ps}[/green]" if ps != 'none' else "[red]off[/red]")
    if current_proxy:
        status_table.add_row("Proxy URL:", current_proxy[:60])
    if proxy_file:
        status_table.add_row("Proxy File:", proxy_file[:60])
    status_table.add_row("Free Proxy:", "[green]on[/green]" if free_enabled else "[dim]off[/dim]")
    console.print(status_table)
    console.print()

    options = Table(show_header=False, box=box.ROUNDED, style="yellow", padding=(0, 2))
    options.add_column("Option", style="bold yellow", width=8)
    options.add_column("Description", style="white")
    options.add_row("1", "Set proxy URL")
    options.add_row("2", "Set proxy file (rotating list)")
    options.add_row("3", "Toggle free proxy on/off")
    options.add_row("4", "Test proxy connection")
    options.add_row("5", "Remove proxy")
    options.add_row("6", "Back to menu")
    console.print(options)
    console.print()

    choice = Prompt.ask("[bold yellow]Choose[/bold yellow]", choices=["1", "2", "3", "4", "5", "6"], default="6")

    if choice == '1':
        url = Prompt.ask("[>] Enter proxy URL (e.g. http://user:pass@host:port)")
        if url.strip():
            _update_env('SCOUT_PROXY', url.strip())
            console.print(f"[green]✓ Proxy set to {url.strip()[:60]}[/green]")

    elif choice == '2':
        filepath = Prompt.ask("[>] Enter path to proxy list file (one proxy per line)")
        if filepath.strip():
            if os.path.exists(filepath.strip()):
                _update_env('SCOUT_PROXY_FILE', filepath.strip())
                console.print(f"[green]✓ Proxy file set to {filepath.strip()[:60]}[/green]")
            else:
                console.print(f"[red]✗ File not found: {filepath.strip()}[/red]")

    elif choice == '3':
        if free_enabled:
            _update_env('SCOUT_FREE_PROXY', 'false')
            console.print("[yellow]✓ Free proxy disabled[/yellow]")
        else:
            _update_env('SCOUT_FREE_PROXY', 'true')
            console.print("[green]✓ Free proxy enabled[/green]")

    elif choice == '4':
        console.print("[white]Testing proxy connection...[/white]")
        from app.scrapers.stealth import get_proxy
        px = get_proxy()
        if not px:
            console.print("[yellow]No proxy configured. Testing direct connection...[/yellow]")
            try:
                resp = _httpx.get('https://httpbin.org/ip', timeout=10)
                ip = resp.json().get('origin', '?')
                console.print(f"[green]✓ Direct connection works. Your IP: {ip}[/green]")
            except Exception as e:
                console.print(f"[red]✗ Connection failed: {str(e)[:100]}[/red]")
        else:
            console.print(f"[dim]Trying proxy: {px[:60]}[/dim]")
            proxy_url = px if px.startswith('http') else f'http://{px}'
            try:
                resp = _httpx.get('https://httpbin.org/ip', proxy=proxy_url, timeout=10, verify=False)
                ip = resp.json().get('origin', '?')
                console.print(f"[green]✓ Proxy works! IP: {ip}[/green]")
            except Exception as e:
                console.print(f"[red]✗ Proxy failed: {str(e)[:80]}[/red]")
                if free_enabled:
                    console.print("[yellow]Free proxies are unreliable. Trying another...[/yellow]")
                    from app.scrapers.stealth import _fetch_free_proxies
                    import random as _rand
                    proxies = _fetch_free_proxies()
                    for p in proxies[:3]:
                        p_url = p if p.startswith('http') else f'http://{p}'
                        console.print(f"[dim]Trying: {p_url[:60]}[/dim]")
                        try:
                            resp = _httpx.get('https://httpbin.org/ip', proxy=p_url, timeout=8, verify=False)
                            ip = resp.json().get('origin', '?')
                            console.print(f"[green]✓ Found working proxy! IP: {ip}[/green]")
                            break
                        except Exception:
                            console.print(f"[red]✗ Dead[/red]")
                    else:
                        console.print("[red]All free proxies failed. Use a paid proxy for reliability.[/red]")

    elif choice == '5':
        _update_env('SCOUT_PROXY', '')
        _update_env('SCOUT_FREE_PROXY', 'false')
        _update_env('SCOUT_PROXY_FILE', '')
        os.environ.pop('SCOUT_PROXY', None)
        os.environ.pop('SCOUT_PROXY_FILE', None)
        console.print("[yellow]✓ Proxy removed[/yellow]")


def view_exports():
    console.print()
    console.print(Panel(
        f"[bold {ACCENT}]EXPORTS[/bold {ACCENT}]\n[dim]Your scraped data[/dim]",
        border_style=ACCENT_DIM,
        box=box.HEAVY
    ))
    console.print()

    csv_files = list(Path('.').glob('*_export_*.csv'))

    if not csv_files:
        console.print("[yellow]No exports found yet![/yellow]")
        console.print("[dim]Run a scrape to create your first export[/dim]")
        return

    csv_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    table = Table(
        title=f"[bold]Found {len(csv_files)} exports[/bold]",
        box=box.ROUNDED,
        style=ACCENT_DIM
    )

    table.add_column("#", style="dim", width=4)
    table.add_column("Filename", style="white")
    table.add_column("Size", style="white", justify="right")
    table.add_column("Date", style="dim")

    for i, file in enumerate(csv_files[:10], 1):
        size = file.stat().st_size / 1024
        mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(file.stat().st_mtime))

        table.add_row(
            str(i),
            file.name,
            f"{size:.1f} KB",
            mtime
        )

    console.print(table)


def main():
    console.clear()
    show_header()

    while True:
        show_menu()

        try:
            choice = Prompt.ask(
                f"[bold {ACCENT}]>[/bold {ACCENT}] [{ACCENT}]0-11[/{ACCENT}]",
                choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"],
                default="1",
                show_choices=False
            )

            if choice == '1':
                scrape_instagram_interactive()

            elif choice == '2':
                scrape_tiktok_interactive()

            elif choice == '3':
                scrape_linkedin_interactive()

            elif choice == '4':
                scrape_github_interactive()

            elif choice == '5':
                scrape_youtube_interactive()

            elif choice == '6':
                scrape_twitch_interactive()

            elif choice == '7':
                scrape_linktree_interactive()

            elif choice == '8':
                scrape_pinterest_interactive()

            elif choice == '9':
                scrape_from_file()

            elif choice == '10':
                view_exports()

            elif choice == '11':
                proxy_settings()

            elif choice == '0':
                console.print()
                console.print(Panel(
                    f"[bold {ACCENT}]Thanks for using Scout![/bold {ACCENT}]\n\n"
                    "[white]★ Star us on GitHub[/white]\n"
                    "[dim]github.com/kiryano/Scout[/dim]\n\n"
                    "[dim]Made for appointment setters[/dim]",
                    border_style=ACCENT_DIM,
                    box=box.HEAVY
                ))
                break

            console.print(f"\n[{ACCENT_DIM}]{'━' * 50}[/{ACCENT_DIM}]\n")

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Exiting...[/yellow]")
            break
        except Exception as e:
            console.print(f"\n[red]✗ Error: {e}[/red]")


if __name__ == '__main__':
    main()
