"""F7 — same-domain homepage link ranking (clean-room; mirrors SIS discovery shape)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.services.f7_page_validate import PAGE_HUB_CATEGORIES, same_parent_domain

_RELEVANT_HINTS = (
    "news",
    "newsroom",
    "press",
    "president",
    "leadership",
    "provost",
    "cio",
    "technology",
    "it.",
    "/it/",
    "digital",
    "online",
    "learning",
    "assessment",
    "procurement",
    "purchasing",
    "rfp",
    "bid",
    "budget",
    "finance",
    "funding",
    "strategic",
    "initiative",
    "partnership",
    "vendor",
    "contract",
    "board",
    "about",
    "research",
    "foundation",
)

_NEWS_SEGMENTS = frozenset({"news", "newsroom", "press", "press-releases", "announcements"})
_NON_ARTICLE_SEGMENTS = frozenset(
    {
        "tag",
        "tags",
        "category",
        "categories",
        "author",
        "authors",
        "page",
        "topic",
        "topics",
        "search",
        "feed",
        "rss",
        "archive",
        "archives",
        "events",
        "calendar",
        "subscribe",
        "contact",
    }
)
_SKIPPED_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".css", ".js", ".zip", ".xml", ".ics")
_ARTICLE_PATH = re.compile(
    r"(?:/20\d{2}/\d{2}/|/20\d{2}\d{2}\d{2}-|/news/\d{8}-)",
    re.IGNORECASE,
)


def is_reusable_source_url(url: str) -> bool:
    """Prefer section hubs over one-off article URLs for discovery candidates."""
    parsed = urlparse(url)
    path = parsed.path or "/"
    if _ARTICLE_PATH.search(path):
        return False
    parts = [part for part in path.split("/") if part]
    lowered = path.lower()
    if "/news/" in lowered and len(parts) >= 2:
        return False
    if len(parts) > 3:
        return False
    return True


def is_news_hub(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    parts = [part.lower() for part in (parsed.path or "/").split("/") if part]
    if host.startswith(("news.", "newsroom.")) and not parts:
        return True
    return 0 < len(parts) <= 2 and parts[-1] in _NEWS_SEGMENTS


def candidate_links(
    links: list[str], *, root_url: str, official_host: str, max_links: int = 40
) -> list[str]:
    """Rank same-domain links from the fetched homepage. Deterministic, no LLM."""
    ranked: list[tuple[int, int, str]] = []
    for position, link in enumerate(links):
        parsed = urlparse(link)
        if not same_parent_domain(link, f"https://{official_host}"):
            continue
        if (parsed.path or "/").lower().endswith(_SKIPPED_EXTENSIONS):
            continue
        if not is_reusable_source_url(link):
            continue
        score = sum(1 for hint in _RELEVANT_HINTS if hint in link.lower())
        if is_news_hub(link):
            score += 5
        ranked.append((score, position, link))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    urls = [root_url]
    for score, _position, link in ranked:
        if score == 0 and len(urls) >= 12:
            continue
        if link not in urls:
            urls.append(link)
        if len(urls) >= max_links:
            break
    return urls


def select_article_links(
    links: list[str], *, hub_url: str, official_host: str, limit: int
) -> list[str]:
    """Article links on a news hub (same host path under the hub)."""
    if limit <= 0:
        return []
    hub = urlparse(hub_url)
    hub_host = (hub.hostname or "").lower()
    hub_path = (hub.path or "/").rstrip("/")

    articles: list[str] = []
    seen: set[str] = set()
    for link in links:
        parsed = urlparse(link)
        host = (parsed.hostname or "").lower()
        if host != hub_host or not same_parent_domain(link, f"https://{official_host}"):
            continue
        path = (parsed.path or "/").rstrip("/")
        if parsed.query or path.lower().endswith(_SKIPPED_EXTENSIONS):
            continue
        if hub_path and not path.startswith(hub_path + "/") and hub_path != "":
            # news.example.edu/ with articles at /slug
            if hub_path not in ("", "/"):
                continue
        parts = [part.lower() for part in path.split("/") if part]
        if not parts or any(part in _NON_ARTICLE_SEGMENTS for part in parts):
            continue
        if not _looks_like_article_slug(parts[-1]):
            continue
        key = f"{host}{path}".lower()
        if key in seen:
            continue
        seen.add(key)
        articles.append(f"{parsed.scheme}://{parsed.netloc}{path}")
        if len(articles) >= limit:
            break
    return articles


def _looks_like_article_slug(slug: str) -> bool:
    tokens = [token for token in re.split(r"[-_]", slug) if token]
    has_digit = any(char.isdigit() for char in slug)
    return len(tokens) >= 5 or (len(tokens) >= 3 and has_digit)


def guess_page_category(url: str, title: str | None = None) -> str:
    if is_news_hub(url):
        return "news"
    text = f"{url} {title or ''}".lower()
    rules = (
        ("procurement", ("procurement", "purchasing", "rfp", "bid", "solicitation")),
        ("leadership", ("president", "leadership", "provost", "cio", "cabinet", "board")),
        ("funding", ("budget", "finance", "funding", "grant")),
        ("assessment", ("assessment", "evaluation", "accreditation")),
        ("digital_learning", ("online", "digital-learning", "elearning", "distance")),
        ("technology", ("technology", "/it/", "cio", "digital-transformation")),
        ("partnership", ("partner", "vendor", "supplier")),
        ("strategic_initiative", ("strategic", "initiative", "charter", "vision", "about")),
    )
    for category, hints in rules:
        if any(hint in text for hint in hints):
            return category if category in PAGE_HUB_CATEGORIES else "strategic_initiative"
    return "strategic_initiative"


def title_from_path(url: str) -> str | None:
    path = urlparse(url).path.strip("/")
    if not path:
        return None
    part = path.split("/")[-1].replace("-", " ").replace("_", " ")
    part = re.sub(r"\s+", " ", part).strip()
    return part.title() if part else None
