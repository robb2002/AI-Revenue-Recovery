"""F7 — page validation: https, same registrable domain/parent, robots.txt."""

from __future__ import annotations

import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger("app.services.f7_page_validate")

USER_AGENT = "LumoraSignalScoutDemo/0.1"

PAGE_HUB_CATEGORIES = (
    "procurement",
    "technology",
    "digital_learning",
    "assessment",
    "funding",
    "leadership",
    "strategic_initiative",
    "partnership",
    "news",
)

SIGNAL_TYPES = (
    "procurement",
    "technology_initiative",
    "leadership_change",
    "funding_budget",
    "strategic_announcement",
    "competitor_vendor",
    "contract_renewal",
)

MAX_HUBS = 8
MAX_NEWS_CHILDREN = 3
MAX_PAGES_TOTAL = 12

_SHORTENER_HOSTS = {
    "bit.ly",
    "t.co",
    "goo.gl",
    "tinyurl.com",
    "ow.ly",
    "buff.ly",
}


def registrable_domain(host: str) -> str:
    host = (host or "").lower().strip().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = [p for p in host.split(".") if p]
    if len(parts) <= 2:
        return host
    multi = {"ac.uk", "edu.au", "co.uk", "gov.au", "edu.cn"}
    last_two = ".".join(parts[-2:])
    if last_two in multi and len(parts) >= 3:
        return ".".join(parts[-3:])
    return last_two


def same_parent_domain(candidate_url: str, base_website_url: str) -> bool:
    try:
        c = urlparse(candidate_url)
        b = urlparse(
            base_website_url if "://" in base_website_url else f"https://{base_website_url}"
        )
        if not c.hostname or not b.hostname:
            return False
        return registrable_domain(c.hostname) == registrable_domain(b.hostname)
    except Exception:
        return False


def validate_candidate_url(
    candidate_url: str,
    base_website_url: str,
) -> tuple[str, str | None]:
    """Returns (status, normalized_url). status: ok | failed | domain_mismatch."""
    raw = (candidate_url or "").strip()
    if not raw:
        return "failed", None
    if not raw.startswith("http"):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme != "https":
        return "failed", None
    host = (parsed.hostname or "").lower()
    if not host or host in _SHORTENER_HOSTS:
        return "failed", None
    if not same_parent_domain(raw, base_website_url):
        return "domain_mismatch", None
    normalized = parsed._replace(fragment="").geturl()
    return "ok", normalized


async def robots_allows(url: str, *, client: httpx.AsyncClient | None = None) -> bool:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        return False
    robots_url = f"{parsed.scheme}://{parsed.hostname}/robots.txt"
    own_client = client is None
    client = client or httpx.AsyncClient(
        timeout=6.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        resp = await client.get(robots_url)
        if resp.status_code >= 400:
            return True
        rp = RobotFileParser()
        rp.parse(resp.text.splitlines())
        return bool(rp.can_fetch(USER_AGENT, url))
    except Exception as exc:
        logger.info("robots check soft-fail allow %s: %s", url, exc)
        return True
    finally:
        if own_client:
            await client.aclose()


async def validate_page(
    candidate_url: str,
    base_website_url: str,
    *,
    page_category: str,
    title: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict:
    status, normalized = validate_candidate_url(candidate_url, base_website_url)
    outcome = {
        "url": normalized or candidate_url,
        "page_category": page_category if page_category in PAGE_HUB_CATEGORIES else "news",
        "status": status,
        "title": title or page_category.replace("_", " "),
    }
    if status != "ok" or not normalized:
        return outcome
    allowed = await robots_allows(normalized, client=client)
    if not allowed:
        outcome["status"] = "skipped_robots"
        outcome["title"] = "robots.txt disallow"
    return outcome
