"""F7 — discover official page hubs from the target website_url (SIS-shaped, clean-room)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.ai.azure_openai import AzureChatClient
from app.services import f7_homepage_links as links
from app.services import f7_page_validate as pages

logger = logging.getLogger("app.services.f7_discovery")

PAGE_CATEGORIES_CSV = ", ".join(pages.PAGE_HUB_CATEGORIES)


@dataclass
class SourceCandidate:
    url: str
    title: str | None
    page_category: str
    reason: str


@dataclass
class FetchedPage:
    url: str
    final_url: str
    html: str
    text: str
    title: str | None
    page_category: str
    status: str  # ok | failed | skipped_robots | domain_mismatch


async def discover_and_fetch_pages(
    *,
    organization_name: str,
    website_url: str,
    client: httpx.AsyncClient,
) -> tuple[list[FetchedPage], list[dict[str, Any]], str]:
    """
    Live path:
      fetch homepage → same-domain candidate links → AI (or rules) pick hubs
      → validate (domain + robots) → fetch bodies → news hub articles (capped).

    Returns (fetched_ok_pages, page_outcomes, discovery_mode_label).
    """
    root = _normalize_root(website_url)
    official_host = pages.registrable_domain(urlparse(root).hostname or "")
    if not official_host:
        return [], [], "no_official_host"

    outcomes: list[dict[str, Any]] = []
    fetched: list[FetchedPage] = []

    root_result = await _fetch_html(client, root, website_url)
    if root_result["status"] != "ok":
        outcomes.append(
            {
                "url": root,
                "page_category": "strategic_initiative",
                "status": root_result["status"],
                "title": root_result.get("title") or "Homepage",
            }
        )
        return [], outcomes, "homepage_fetch_failed"

    homepage_html = root_result["html"]
    homepage_final = root_result["final_url"]
    hrefs = _extract_hrefs(homepage_html, homepage_final)
    discovered = links.candidate_links(
        hrefs, root_url=homepage_final, official_host=official_host
    )

    selected = await _ai_propose_pages(
        organization_name=organization_name,
        official_domain=official_host,
        candidate_urls=discovered,
    )
    if not selected:
        selected = [
            SourceCandidate(
                url=u,
                title=links.title_from_path(u) or f"{organization_name} official page",
                page_category=links.guess_page_category(u),
                reason="Rule-based selection from official homepage links",
            )
            for u in discovered[: pages.MAX_HUBS]
        ]

    # Always include root
    selected = [
        SourceCandidate(
            homepage_final,
            f"{organization_name} official site",
            "strategic_initiative",
            "Official domain root",
        ),
        *selected,
    ]
    if not any(links.is_news_hub(c.url) for c in selected):
        hub = next((u for u in discovered if links.is_news_hub(u)), None)
        if hub:
            selected.append(
                SourceCandidate(hub, f"{organization_name} news", "news", "Official news hub")
            )

    selected = _dedupe_prioritize(selected, homepage_final)[: pages.MAX_HUBS]

    # Validate + fetch hubs
    for cand in selected:
        outcome = await pages.validate_page(
            cand.url,
            website_url,
            page_category=cand.page_category,
            title=cand.title,
            client=client,
        )
        if outcome["status"] != "ok":
            outcomes.append(outcome)
            continue
        body = await _fetch_html(client, outcome["url"], website_url)
        if body["status"] != "ok":
            outcomes.append(
                {
                    **outcome,
                    "status": body["status"],
                    "title": body.get("title") or outcome["title"],
                }
            )
            continue
        page = FetchedPage(
            url=outcome["url"],
            final_url=body["final_url"],
            html=body["html"],
            text=body["text"],
            title=body.get("title") or cand.title,
            page_category=outcome["page_category"],
            status="ok",
        )
        fetched.append(page)
        outcomes.append(
            {
                "url": page.final_url,
                "page_category": page.page_category,
                "status": "ok",
                "title": page.title or page.page_category,
            }
        )

    # News hub → limited article children
    news_pages = [p for p in fetched if p.page_category == "news" or links.is_news_hub(p.final_url)]
    article_budget = pages.MAX_NEWS_CHILDREN
    for hub in news_pages:
        if article_budget <= 0 or len(fetched) >= pages.MAX_PAGES_TOTAL:
            break
        article_hrefs = _extract_hrefs(hub.html, hub.final_url)
        articles = links.select_article_links(
            article_hrefs,
            hub_url=hub.final_url,
            official_host=official_host,
            limit=article_budget,
        )
        for article_url in articles:
            if len(fetched) >= pages.MAX_PAGES_TOTAL:
                break
            outcome = await pages.validate_page(
                article_url,
                website_url,
                page_category="news",
                title=links.title_from_path(article_url),
                client=client,
            )
            if outcome["status"] != "ok":
                outcomes.append(outcome)
                continue
            body = await _fetch_html(client, outcome["url"], website_url)
            if body["status"] != "ok":
                outcomes.append({**outcome, "status": body["status"]})
                continue
            page = FetchedPage(
                url=outcome["url"],
                final_url=body["final_url"],
                html=body["html"],
                text=body["text"],
                title=body.get("title") or outcome.get("title"),
                page_category="news",
                status="ok",
            )
            fetched.append(page)
            outcomes.append(
                {
                    "url": page.final_url,
                    "page_category": "news",
                    "status": "ok",
                    "title": page.title or "News article",
                }
            )
            article_budget -= 1

    label = "live_homepage_discovery"
    return fetched, outcomes, label


async def _ai_propose_pages(
    *,
    organization_name: str,
    official_domain: str,
    candidate_urls: list[str],
) -> list[SourceCandidate]:
    if not candidate_urls:
        return []
    client = AzureChatClient()
    if not client.configured:
        return []
    allow = set(candidate_urls[:30])
    result = await client.chat_json(
        system=(
            "Select official pages for US EdTech sales intelligence. "
            "Return JSON only. Copy urls exactly from candidate_urls — never invent a URL or host."
        ),
        user=(
            f"Org: {organization_name}\n"
            f"Domain: {official_domain}\n"
            f"page_category one of: {PAGE_CATEGORIES_CSV}\n\n"
            f"Pick up to {pages.MAX_HUBS} high-value public pages "
            "(procurement, tech/LMS/assessment, funding, leadership, strategy, "
            "partnerships, official news hub). Skip generic contact/legal/login pages.\n\n"
            "candidate_urls:\n"
            + "\n".join(f"- {u}" for u in candidate_urls[:30])
            + '\n\nJSON: {"candidates":[{"url":"<exact from list>","title":"<short>",'
            '"page_category":"<enum>"}]}'
        ),
        temperature=0.1,
        timeout_seconds=20.0,
    )
    if not result:
        return []
    out: list[SourceCandidate] = []
    for item in result.get("candidates") or []:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        if url not in allow:
            continue
        cat = item.get("page_category") or links.guess_page_category(url)
        if cat not in pages.PAGE_HUB_CATEGORIES:
            cat = links.guess_page_category(url)
        out.append(
            SourceCandidate(
                url=url,
                title=(item.get("title") or links.title_from_path(url) or "")[:200] or None,
                page_category=cat,
                reason="AI selection from homepage candidates",
            )
        )
    return out


def _normalize_root(website_url: str) -> str:
    raw = (website_url or "").strip()
    if not raw.startswith("http"):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    return f"{parsed.scheme}://{parsed.netloc}/"


def _extract_hrefs(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        abs_url = urljoin(base_url, href)
        if abs_url.startswith("https://"):
            out.append(abs_url.split("#")[0])
    return out


async def _fetch_html(
    client: httpx.AsyncClient, url: str, base_website_url: str
) -> dict[str, Any]:
    status, normalized = pages.validate_candidate_url(url, base_website_url)
    if status != "ok" or not normalized:
        return {"status": status, "html": "", "text": "", "final_url": url, "title": None}
    if not await pages.robots_allows(normalized, client=client):
        return {
            "status": "skipped_robots",
            "html": "",
            "text": "",
            "final_url": normalized,
            "title": "robots.txt disallow",
        }
    try:
        resp = await client.get(normalized)
        if resp.status_code >= 400:
            return {
                "status": "failed",
                "html": "",
                "text": "",
                "final_url": str(resp.url),
                "title": f"HTTP {resp.status_code}",
            }
        # Redirect must stay same parent
        final = str(resp.url)
        if not pages.same_parent_domain(final, base_website_url):
            return {
                "status": "domain_mismatch",
                "html": "",
                "text": "",
                "final_url": final,
                "title": "Redirect left official domain",
            }
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        title = soup.title.string.strip() if soup.title and soup.title.string else None
        text = " ".join(soup.get_text(" ", strip=True).split())
        return {
            "status": "ok",
            "html": html,
            "text": text[:20_000],
            "final_url": final,
            "title": title,
        }
    except Exception as exc:
        logger.info("fetch failed %s: %s", url, exc)
        return {
            "status": "failed",
            "html": "",
            "text": "",
            "final_url": normalized,
            "title": str(exc)[:120],
        }


def _dedupe_prioritize(
    candidates: list[SourceCandidate], root_url: str
) -> list[SourceCandidate]:
    seen: set[str] = set()
    normalized: list[SourceCandidate] = []
    for item in candidates:
        key = item.url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        cat = "news" if links.is_news_hub(item.url) else item.page_category
        normalized.append(
            SourceCandidate(item.url, item.title, cat, item.reason)
        )
    return sorted(
        normalized,
        key=lambda item: (
            item.url.rstrip("/").lower() != root_url.rstrip("/").lower(),
            item.page_category != "news",
        ),
    )
