"""Web article scraper using only Python stdlib."""

from __future__ import annotations

import base64
import re
import ssl
import sys
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, unquote
from urllib.request import Request, urlopen

_SKIP_TAGS = frozenset({"script", "style", "nav", "header", "footer", "aside", "form", "noscript"})
_BOILERPLATE = re.compile(
    r"(?i)(accept\s+cookies?|cookie\s+policy|subscribe\s+to\s+our|sign\s+up\s+for|"
    r"we\s+use\s+cookies|privacy\s+policy|terms\s+of\s+(service|use)|"
    r"newsletter|unsubscribe|manage\s+preferences|consent|"
    r"click\s+here\s+to|share\s+this\s+article|all\s+rights\s+reserved)"
)
_MAX_LEN = 8000
_UA = "Mozilla/5.0 (compatible; KONOPLA.UA/1.0)"


class _ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._zone = None          # "article", "main", or None (body)
        self._zone_depth = 0
        self._text = {"article": [], "main": [], "body": []}
        self._in_body = False

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "body":
            self._in_body = True
        if tag in ("article", "main") and self._zone is None:
            self._zone = tag
            self._zone_depth = 1
        elif self._zone and tag == self._zone:
            self._zone_depth += 1

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == "body":
            self._in_body = False
        if self._zone and tag == self._zone:
            self._zone_depth -= 1
            if self._zone_depth <= 0:
                self._zone = None

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        text = data.strip()
        if not text:
            return
        if self._zone:
            self._text[self._zone].append(text)
        elif self._in_body:
            self._text["body"].append(text)

    def get_text(self) -> str:
        for key in ("article", "main", "body"):
            if self._text[key]:
                return " ".join(self._text[key])
        return ""


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    lines = text.split(". ")
    lines = [ln for ln in lines if not _BOILERPLATE.search(ln)]
    text = ". ".join(lines)
    return text[:_MAX_LEN] if len(text) > _MAX_LEN else text


def _resolve_google_news_url(url: str) -> str | None:
    """Extract real article URL from Google News redirect URL.

    Google News RSS URLs encode the destination in the path as base64.
    Format: https://news.google.com/rss/articles/CBMi<base64>...
    The base64 payload contains the real URL prefixed with a few header bytes.
    """
    parsed = urlparse(url)
    if "news.google.com" not in parsed.hostname:
        return None

    # Extract the base64 part from the path
    path = parsed.path
    # /rss/articles/CBMi... or /articles/CBMi...
    for prefix in ("/rss/articles/", "/articles/"):
        if prefix in path:
            b64_part = path.split(prefix, 1)[1].split("?")[0]
            break
    else:
        return None

    # Try to decode the base64 payload
    try:
        # Add padding if needed
        padded = b64_part + "=" * (4 - len(b64_part) % 4)
        decoded = base64.urlsafe_b64decode(padded)

        # Find URLs in the decoded bytes
        text = decoded.decode("utf-8", errors="replace")
        # Look for http(s):// in the decoded payload
        match = re.search(r"https?://[^\s\x00-\x1f\"'<>]+", text)
        if match:
            real_url = match.group(0)
            print(f"   Resolved Google News URL → {real_url[:80]}...")
            return real_url
    except Exception:
        pass

    # Fallback: try HTTP redirect following
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = Request(url, headers={"User-Agent": _UA})
        with urlopen(req, timeout=10, context=ctx) as resp:
            final_url = resp.url
            if final_url and "news.google.com" not in final_url:
                print(f"   Resolved via redirect → {final_url[:80]}...")
                return final_url
    except Exception:
        pass

    return None


def scrape_article(url: str, timeout: int = 15) -> str | None:
    """Fetch and extract article text from a URL. Returns None on any error."""
    # Resolve Google News redirect URLs to real article URLs
    if "news.google.com" in url:
        resolved = _resolve_google_news_url(url)
        if resolved:
            url = resolved
        else:
            print("   [WARN] Could not resolve Google News URL")

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = Request(url, headers={"User-Agent": _UA})
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            html = resp.read().decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return None

    try:
        parser = _ArticleParser()
        parser.feed(html)
        text = parser.get_text()
    except Exception:
        return None

    if not text:
        return None
    return _clean(text) or None


if __name__ == "__main__":
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://hemptoday.net/"
    result = scrape_article(test_url)
    if result:
        print(f"Scraped {len(result)} chars from {test_url}")
        print(result[:500] + "..." if len(result) > 500 else result)
    else:
        print(f"Failed to scrape {test_url}")
