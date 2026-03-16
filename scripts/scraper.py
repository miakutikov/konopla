"""Web article scraper using only Python stdlib."""

from __future__ import annotations

import re
import ssl
import sys
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
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


def scrape_article(url: str, timeout: int = 15) -> str | None:
    """Fetch and extract article text from a URL. Returns None on any error."""
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
