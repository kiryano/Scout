import random
import time
import os
import logging
import requests
from typing import Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
]

_free_proxy_cache = []
_free_proxy_last_fetch = 0
_FREE_PROXY_TTL = 300


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def random_delay(min_seconds: float = 1.5, max_seconds: float = 4.5):
    time.sleep(random.uniform(min_seconds, max_seconds))


def _fetch_free_proxies() -> list:
    global _free_proxy_cache, _free_proxy_last_fetch

    if _free_proxy_cache and (time.time() - _free_proxy_last_fetch) < _FREE_PROXY_TTL:
        return _free_proxy_cache

    try:
        from fp.fp import FreeProxy
        proxies = []
        for _ in range(5):
            try:
                p = FreeProxy(timeout=1, rand=True, anonym=True).get()
                if p:
                    proxies.append(p)
            except Exception:
                continue

        if proxies:
            _free_proxy_cache = proxies
            _free_proxy_last_fetch = time.time()
            logger.info(f"Fetched {len(proxies)} free proxies")
            return proxies
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Free proxy fetch failed: {e}")

    return []


def get_proxy() -> Optional[str]:
    proxy = os.environ.get('SCOUT_PROXY')
    if proxy:
        return proxy

    proxy_file = os.environ.get('SCOUT_PROXY_FILE')
    if proxy_file and os.path.exists(proxy_file):
        with open(proxy_file, 'r') as f:
            proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        if proxies:
            return random.choice(proxies)

    if os.environ.get('SCOUT_FREE_PROXY', '').lower() in ('1', 'true', 'yes'):
        free_proxies = _fetch_free_proxies()
        if free_proxies:
            return random.choice(free_proxies)

    return None


def get_httpx_proxy() -> Optional[str]:
    proxy = get_proxy()
    if not proxy:
        return None
    if not proxy.startswith('http'):
        proxy = f'http://{proxy}'
    return proxy


def get_requests_proxies() -> Optional[dict]:
    proxy = get_proxy()
    if not proxy:
        return None
    if not proxy.startswith('http'):
        proxy = f'http://{proxy}'
    return {'http': proxy, 'https': proxy}


def proxy_status() -> str:
    if os.environ.get('SCOUT_PROXY'):
        return 'custom'
    if os.environ.get('SCOUT_PROXY_FILE'):
        return 'file'
    if os.environ.get('SCOUT_FREE_PROXY', '').lower() in ('1', 'true', 'yes'):
        return 'free'
    return 'none'


def test_proxy() -> bool:
    """Test if current proxy is working."""
    proxy = get_requests_proxies()
    if not proxy:
        return True

    try:
        r = requests.get('https://httpbin.org/ip', proxies=proxy, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def retry_request(max_retries: int = 3, delay: float = 2.0):
    """Decorator to retry failed requests."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.ProxyError as e:
                    last_error = e
                    logger.warning(f"Proxy error (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                except requests.exceptions.Timeout as e:
                    last_error = e
                    logger.warning(f"Timeout (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                except requests.exceptions.ConnectionError as e:
                    last_error = e
                    logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(delay)
            logger.error(f"All {max_retries} attempts failed: {last_error}")
            return None
        return wrapper
    return decorator
