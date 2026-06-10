"""Normalize Apify search result items into Google Sheets rows."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit, urlunsplit

RESULT_HEADERS = [
    "Query",
    "Title",
    "URL",
    "Snippet",
    "Date",
    "Position",
    "Source",
    "Raw JSON",
]


def normalize_url(url: str | None) -> str:
    """Return a URL without query string or fragment for deduplication/output."""

    if not url:
        return ""
    clean_url = str(url).strip()
    if not clean_url:
        return ""
    parts = urlsplit(clean_url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _first_present(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return ""


def normalize_item(query: str, item: dict[str, Any], source: str) -> tuple[str, list[Any]] | None:
    """Normalize one raw result item.

    Returns a tuple of (dedupe_key, sheet_row), or None when the item has no URL.
    """

    url = normalize_url(_first_present(item, ("url", "link", "href")))
    if not url:
        return None

    title = _first_present(item, ("title", "name", "headline"))
    snippet = _first_present(item, ("snippet", "description", "text", "content"))
    date = _first_present(item, ("date", "publishedDate", "published_at", "time"))
    position = _first_present(item, ("position", "rank", "organicPosition", "index"))

    raw_json = json.dumps(item, ensure_ascii=False, sort_keys=True)
    row = [query, title, url, snippet, date, position, source, raw_json]
    return url, row


def normalize_results(
    query: str,
    items: list[dict[str, Any]],
    source: str = "johnvc/google-forums-search-api",
) -> list[list[Any]]:
    """Normalize and deduplicate result items by normalized URL."""

    rows: list[list[Any]] = []
    seen_urls: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = normalize_item(query=query, item=item, source=source)
        if normalized is None:
            continue
        url, row = normalized
        if url in seen_urls:
            continue
        seen_urls.add(url)
        rows.append(row)

    return rows
