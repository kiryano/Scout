#!/usr/bin/env python3

import sys
import csv
import time
import os
from pathlib import Path

if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent))

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

from app.scrapers.instagram import scrape_profile_no_login
from app.scrapers.stealth import random_delay, proxy_status

console = Console()


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

    if not Confirm.ask("\n[cyan][+] Enrich leads with contact info?[/cyan]", default=True):
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
        task = progress.add_task("[cyan]Enriching leads...", total=len(profiles))

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
    summary_parts.append(f"[cyan]Avg lead score: {avg_score}/100[/cyan]")

    console.print(Panel(
        "\n".join(summary_parts),
        title="[bold]Enrichment Results[/bold]",
        border_style="cyan"
    ))

    email_leads = [e for e in enriched if e.get('email')]
    if email_leads:
        console.print()
        t = Table(show_header=True, box=box.SIMPLE)
        t.add_column("Lead", style="white")
        t.add_column("Email", style="cyan")
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
    header_text = Text()
    header_text.append("SCOUT", style="bold cyan")
    header_text.append("\n", style="white")
    header_text.append("Free Lead Generation Tool", style="dim")

    console.print(Panel(
        header_text,
        box=box.DOUBLE,
        style="cyan",
        padding=(1, 20)
    ))

    console.print(
        "[dim]Lead generation for appointment setters[/dim]",
        justify="center"
    )
    console.print(
        "[dim]Discord: [cyan]https://discord.gg/eneDNUbzcc[/cyan][/dim]",
        justify="center"
    )

    ps = proxy_status()
    if ps == 'custom':
        console.print("[green]Proxy: custom[/green]", justify="center")
    elif ps == 'file':
        console.print("[green]Proxy: rotating from file[/green]", justify="center")
    elif ps == 'free':
        console.print("[yellow]Proxy: free (unstable)[/yellow]", justify="center")
    else:
        console.print("[dim]Proxy: off (set SCOUT_PROXY or SCOUT_FREE_PROXY=true)[/dim]", justify="center")

    console.print()


def show_menu():
    table = Table(
        show_header=False,
        box=box.ROUNDED,
        style="cyan",
        padding=(0, 2)
    )

    table.add_column("Option", style="bold cyan", width=8)
    table.add_column("Description", style="white")

    table.add_row("1", "[>] Scrape Instagram Profiles")
    table.add_row("2", "[#] Scrape TikTok Profiles")
    table.add_row("3", "[~] Scrape LinkedIn Profiles (Cookie Required)")
    table.add_row("4", "[*] Scrape from Username List File")
    table.add_row("5", "[~] View Recent Exports")
    table.add_row("6", "[⚙] Proxy Settings")
    table.add_row("7", "[X] Exit")

    console.print(Panel(
        table,
        title="[bold]What would you like to do?[/bold]",
        border_style="cyan",
        box=box.ROUNDED
    ))
    console.print()


def scrape_instagram_interactive():
    console.print()
    console.print(Panel(
        "[bold]Instagram Profile Scraper[/bold]\n[dim]No login required![/dim]",
        style="green",
        box=box.DOUBLE
    ))
    console.print()

    console.print("[cyan]Enter Instagram usernames (one per line)[/cyan]")
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
    console.print(f"[bold cyan]Scraping {len(usernames)} profiles...[/bold cyan]")
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
                f"[cyan]Scraping @{username}...",
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
                f"[bold]Exported to:[/bold] [cyan]{filename}[/cyan]\n"
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
    from app.scrapers.tiktok_scraper import scrape_tiktok_profile

    console.print()
    console.print(Panel(
        "[bold]TikTok Profile Scraper[/bold]",
        style="magenta",
        box=box.DOUBLE
    ))
    console.print()

    console.print("[cyan]Enter TikTok usernames (one per line, without @)[/cyan]")
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
    console.print(f"[bold cyan]Scraping {len(usernames)} TikTok profiles...[/bold cyan]")
    console.print()

    profiles = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        for i, username in enumerate(usernames, 1):
            task = progress.add_task(
                f"[cyan]Scraping @{username}...",
                total=None
            )

            try:
                result = scrape_tiktok_profile(username)

                if result.get('status') == 'success' and result.get('profile'):
                    profile = result['profile']
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
                f"[bold]Exported to:[/bold] [cyan]{filename}[/cyan]\n"
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
    from app.scrapers.linkedin_scraper import scrape_linkedin_profile

    console.print()

    cookie = os.environ.get('LINKEDIN_COOKIE', '').strip()
    if not cookie:
        console.print(Panel(
            "[bold yellow]LinkedIn Cookie Required[/bold yellow]\n\n"
            "[cyan]To scrape LinkedIn profiles:[/cyan]\n"
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
        "[bold]LinkedIn Profile Scraper[/bold]\n[dim]Using session cookie[/dim]",
        style="blue",
        box=box.DOUBLE
    ))
    console.print()

    console.print("[cyan]Enter LinkedIn usernames or profile URLs (one per line)[/cyan]")
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
    console.print(f"[bold cyan]Scraping {len(usernames)} LinkedIn profiles...[/bold cyan]")
    console.print()

    profiles = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        for i, username in enumerate(usernames, 1):
            task = progress.add_task(
                f"[cyan]Scraping {username}...",
                total=None
            )

            try:
                result = scrape_linkedin_profile(username)

                if result.get('status') == 'success' and result.get('profile'):
                    profile = result['profile']
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
                    msg = result.get('message', 'Failed')
                    progress.update(task, description=f"[red]✗ {username} - {msg[:60]}")

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
                f"[bold]Exported to:[/bold] [cyan]{filename}[/cyan]\n"
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
        "[bold]Scrape from File[/bold]\n[dim]Bulk scrape from username list[/dim]",
        style="blue",
        box=box.DOUBLE
    ))
    console.print()

    filename = Prompt.ask("[>] Enter filename", default="usernames.txt")

    try:
        with open(filename, 'r') as f:
            usernames = [line.strip().replace('@', '') for line in f if line.strip()]

        console.print(f"\n[cyan]Found {len(usernames)} usernames in {filename}[/cyan]")

        if not Confirm.ask("Continue?", default=True):
            return

        console.print()
        console.print(f"[bold cyan]Scraping {len(usernames)} profiles...[/bold cyan]")
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
                    profile = scrape_profile_no_login(username)

                    if profile:
                        profiles.append(profile)
                        successful += 1
                        progress.update(
                            task,
                            description=f"[green]✓[/green] [{i}/{len(usernames)}] @{username} ({profile['follower_count']:,} followers)"
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
            export_filename = f"instagram_export_{timestamp}.csv"

            with open(export_filename, 'w', newline='', encoding='utf-8') as f:
                if profiles:
                    writer = csv.DictWriter(f, fieldnames=profiles[0].keys())
                    writer.writeheader()
                    writer.writerows(profiles)

            console.print(Panel(
                f"[bold green]SUCCESS![/bold green]\n\n"
                f"[bold]Scraped:[/bold] {successful}/{len(usernames)} profiles\n"
                f"[bold]Exported to:[/bold] [cyan]{export_filename}[/cyan]",
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
        "[bold]Proxy Settings[/bold]\n[dim]Configure proxy for scraping[/dim]",
        style="yellow",
        box=box.DOUBLE
    ))
    console.print()

    ps = proxy_status()
    current_proxy = os.environ.get('SCOUT_PROXY', '')
    free_enabled = os.environ.get('SCOUT_FREE_PROXY', '').lower() in ('1', 'true', 'yes')

    status_table = Table(show_header=False, box=None, padding=(0, 2))
    status_table.add_column(style="dim")
    status_table.add_column(style="white")
    status_table.add_row("Status:", f"[green]{ps}[/green]" if ps != 'none' else "[red]off[/red]")
    if current_proxy:
        status_table.add_row("Proxy URL:", current_proxy[:60])
    status_table.add_row("Free Proxy:", "[green]on[/green]" if free_enabled else "[dim]off[/dim]")
    console.print(status_table)
    console.print()

    options = Table(show_header=False, box=box.ROUNDED, style="yellow", padding=(0, 2))
    options.add_column("Option", style="bold yellow", width=8)
    options.add_column("Description", style="white")
    options.add_row("1", "Set proxy URL")
    options.add_row("2", "Toggle free proxy on/off")
    options.add_row("3", "Test proxy connection")
    options.add_row("4", "Remove proxy")
    options.add_row("5", "Back to menu")
    console.print(options)
    console.print()

    choice = Prompt.ask("[bold yellow]Choose[/bold yellow]", choices=["1", "2", "3", "4", "5"], default="5")

    if choice == '1':
        url = Prompt.ask("[>] Enter proxy URL (e.g. http://user:pass@host:port)")
        if url.strip():
            _update_env('SCOUT_PROXY', url.strip())
            console.print(f"[green]✓ Proxy set to {url.strip()[:60]}[/green]")

    elif choice == '2':
        if free_enabled:
            _update_env('SCOUT_FREE_PROXY', 'false')
            console.print("[yellow]✓ Free proxy disabled[/yellow]")
        else:
            _update_env('SCOUT_FREE_PROXY', 'true')
            console.print("[green]✓ Free proxy enabled[/green]")

    elif choice == '3':
        console.print("[cyan]Testing proxy connection...[/cyan]")
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

    elif choice == '4':
        _update_env('SCOUT_PROXY', '')
        _update_env('SCOUT_FREE_PROXY', 'false')
        os.environ.pop('SCOUT_PROXY', None)
        console.print("[yellow]✓ Proxy removed[/yellow]")


def view_exports():
    console.print()
    console.print(Panel(
        "[bold]Recent Exports[/bold]\n[dim]Your scraped data[/dim]",
        style="magenta",
        box=box.DOUBLE
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
        style="magenta"
    )

    table.add_column("#", style="dim", width=4)
    table.add_column("Filename", style="cyan")
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
                "[bold cyan]Choose an option[/bold cyan]",
                choices=["1", "2", "3", "4", "5", "6", "7"],
                default="1"
            )

            if choice == '1':
                scrape_instagram_interactive()

            elif choice == '2':
                scrape_tiktok_interactive()

            elif choice == '3':
                scrape_linkedin_interactive()

            elif choice == '4':
                scrape_from_file()

            elif choice == '5':
                view_exports()

            elif choice == '6':
                proxy_settings()

            elif choice == '7':
                console.print()
                console.print(Panel(
                    "[bold]Thanks for using Scout![/bold]\n\n"
                    "[cyan]Star us on GitHub:[/cyan]\n"
                    "[link]https://github.com/kiryano/scout[/link]\n\n"
                    "[dim]Made by appointment setters, for appointment setters[/dim]",
                    style="green",
                    box=box.DOUBLE
                ))
                break

            console.print("\n" + "─" * 60 + "\n")

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Exiting...[/yellow]")
            break
        except Exception as e:
            console.print(f"\n[red]✗ Error: {e}[/red]")


if __name__ == '__main__':
    main()
