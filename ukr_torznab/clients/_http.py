from typing import Any

import httpx
from httpx_limiter import AsyncRateLimitedTransport, Rate
from httpx_limiter.aiolimiter import AiolimiterAsyncLimiter

BROWSER_HEADERS: dict[str, str] = {
    "accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "accept-language": "en-US,en;q=0.9,uk;q=0.8,ru;q=0.7,cs;q=0.6",
    "cache-control": "max-age=0",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
}


def make_client(base_url: str, *, rate: Rate, **kwargs: Any) -> httpx.AsyncClient:
    """Build an ``httpx.AsyncClient`` whose requests are throttled to ``rate``."""
    return httpx.AsyncClient(
        base_url=base_url,
        transport=AsyncRateLimitedTransport.create(AiolimiterAsyncLimiter.create(rate)),
        **kwargs,
    )
