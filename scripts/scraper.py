"""Web article scraper using only Python stdlib."""

from __future__ import annotations

import base64
import re
import ssl
import sys
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, unquote, urljoin
from urllib.request import Request, urlopen

_SKIP_TAGS = frozenset({"script", "style", "nav", "header", "footer", "aside", "form", "noscript", "iframe", "svg"})

# Content-indicative class/id keywords for div-based content detection
_CONTENT_HINTS = re.compile(
    r"(?i)(article|content|post|entry|text|story|body|main|single|detail|"
    r"news.?body|article.?body|post.?content|entry.?content|page.?content|"
    r"field.?body|node.?content|blog.?post|prose)"
)

_BOILERPLATE = re.compile(
    r"(?i)(accept\s+cookies?|cookie\s+policy|subscribe\s+to\s+our|sign\s+up\s+for|"
    r"we\s+use\s+cookies|privacy\s+policy|terms\s+of\s+(service|use)|"
    r"newsletter|unsubscribe|manage\s+preferences|consent|"
    r"click\s+here\s+to|share\s+this\s+article|all\s+rights\s+reserved|"
    r"усі\s+права\s+захищ|повідомити\s+про\s+помилку|"
    r"підписатися|підписуйтесь|политика\s+конфиденциальности|"
    r"©\s*\d{4}|copyright\s+\d{4}|tutti\s+i\s+diritti|tous\s+droits|"
    r"alle\s+rechte|datenschutz|impressum)"
)

_MAX_LEN = 8000
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Image URL patterns to skip (icons, tracking pixels, avatars, logos)
_IMG_SKIP = re.compile(
    r"(?i)(logo|icon|avatar|badge|button|sprite|pixel|tracking|spacer|blank|"
    r"1x1|\.gif$|\.svg$|data:image|gravatar|favicon|emoji|ad[_-]|banner[_-]?\d)"
)


class _ArticleParser(HTMLParser):
    """Enhanced HTML parser with content zone detection, meta extraction, and image collection."""

    def __init__(self, base_url: str = ""):
        super().__init__()
        self._base_url = base_url
        self._skip_depth = 0

        # Zone tracking: article > main > content-div > body
        self._zone = None          # "article", "main", "content", or None
        self._zone_depth = 0
        self._text = {"article": [], "main": [], "content": [], "body": []}
        self._in_body = False

        # Meta tags
        self._meta: dict[str, str] = {}

        # Images found in content zones
        self._images: list[dict] = []
        self._seen_img_urls: set[str] = set()

        # Track div nesting for content-div detection
        self._div_stack: list[str | None] = []  # stack of div zone names or None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attrs_dict = dict(attrs)

        # Meta tags (always process, even outside body)
        if tag == "meta":
            prop = attrs_dict.get("property", "") or attrs_dict.get("name", "")
            content = attrs_dict.get("content", "")
            if content:
                if prop == "og:image":
                    self._meta["og_image"] = self._abs_url(content)
                elif prop == "og:title":
                    self._meta["og_title"] = content
                elif prop in ("og:description", "description"):
                    self._meta.setdefault("description", content)
                elif prop == "twitter:image":
                    self._meta.setdefault("og_image", self._abs_url(content))
            return

        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return

        if tag == "body":
            self._in_body = True

        # Semantic zone detection
        if tag == "article" and self._zone is None:
            self._zone = "article"
            self._zone_depth = 1
        elif tag == "main" and self._zone is None:
            self._zone = "main"
            self._zone_depth = 1
        elif self._zone and tag == self._zone:
            self._zone_depth += 1

        # Div-based content zone detection (only if no semantic zone found yet)
        if tag == "div" and self._in_body:
            cls = attrs_dict.get("class", "") or ""
            div_id = attrs_dict.get("id", "") or ""
            hint_text = f"{cls} {div_id}"
            if self._zone is None and _CONTENT_HINTS.search(hint_text):
                self._zone = "content"
                self._zone_depth = 1
                self._div_stack.append("content")
            else:
                self._div_stack.append(None)

        # Image extraction (only in content zones or body if no zone)
        if tag == "img" and self._skip_depth == 0 and self._in_body:
            src = attrs_dict.get("src", "") or attrs_dict.get("data-src", "") or attrs_dict.get("data-lazy-src", "")
            if src and not src.startswith("data:"):
                abs_src = self._abs_url(src)
                alt = attrs_dict.get("alt", "") or ""
                if abs_src not in self._seen_img_urls and not _IMG_SKIP.search(abs_src):
                    # Only collect images from content zones (or body as fallback)
                    if self._zone or self._in_body:
                        self._images.append({"url": abs_src, "alt": alt})
                        self._seen_img_urls.add(abs_src)

    def handle_endtag(self, tag: str):
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == "body":
            self._in_body = False
        if self._zone and tag in ("article", "main"):
            if self._zone == tag:
                self._zone_depth -= 1
                if self._zone_depth <= 0:
                    self._zone = None
        if tag == "div" and self._div_stack:
            popped = self._div_stack.pop()
            if popped == "content" and self._zone == "content":
                self._zone_depth -= 1
                if self._zone_depth <= 0:
                    self._zone = None

    def handle_data(self, data: str):
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
        """Return best extracted text, prioritizing article > main > content > body."""
        for key in ("article", "main", "content", "body"):
            if self._text[key]:
                return " ".join(self._text[key])
        return ""

    def get_meta(self) -> dict[str, str]:
        return self._meta

    def get_images(self) -> list[dict]:
        return self._images

    def _abs_url(self, url: str) -> str:
        """Convert relative URL to absolute."""
        if not url or url.startswith("data:"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        return urljoin(self._base_url, url)


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


def _fetch_html(url: str, timeout: int = 15) -> str | None:
    """Fetch HTML from URL with realistic browser headers."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = Request(url, headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,uk;q=0.8",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
        })
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as e:
        print(f"   [WARN] HTTP fetch failed: {e}")
        return None


def scrape_article(url: str, timeout: int = 15) -> str | None:
    """Fetch and extract article text from a URL. Returns None on any error.

    Backward-compatible: returns plain text string.
    """
    result = scrape_article_full(url, timeout)
    if result and result.get("text"):
        return result["text"]
    return None


def scrape_article_full(url: str, timeout: int = 15) -> dict | None:
    """Fetch and extract article text, images and metadata from a URL.

    Returns dict with keys: text, images, og_image, meta_title, meta_description
    or None on complete failure.
    """
    # Resolve Google News redirect URLs to real article URLs
    if "news.google.com" in url:
        resolved = _resolve_google_news_url(url)
        if resolved:
            url = resolved
        else:
            print("   [WARN] Could not resolve Google News URL")

    html = _fetch_html(url, timeout)
    if not html:
        return None

    try:
        parser = _ArticleParser(base_url=url)
        parser.feed(html)
        text = parser.get_text()
    except Exception:
        return None

    if not text:
        return None

    cleaned = _clean(text)
    if not cleaned:
        return None

    meta = parser.get_meta()
    images = parser.get_images()

    return {
        "text": cleaned,
        "images": images,
        "og_image": meta.get("og_image", ""),
        "meta_title": meta.get("og_title", ""),
        "meta_description": meta.get("description", ""),
    }


if __name__ == "__main__":
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://hemptoday.net/"
    result = scrape_article_full(test_url)
    if result:
        print(f"Scraped {len(result['text'])} chars from {test_url}")
        print(f"OG Image: {result['og_image']}")
        print(f"Images found: {len(result['images'])}")
        for img in result["images"][:5]:
            print(f"  - {img['url'][:100]}")
        print()
        print(result["text"][:500] + "..." if len(result["text"]) > 500 else result["text"])
    else:
        print(f"Failed to scrape {test_url}")
