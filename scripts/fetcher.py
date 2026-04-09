"""
fetcher.py — Збирає новини з RSS-фідів
"""

import feedparser
import hashlib
import json
import os
import re
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import time
from config import (
    load_sources, STOP_WORDS, SOFT_STOP_WORDS, ALLOW_CONTEXT,
    HEMP_KEYWORDS, FEED_HEALTH_FILE,
    MAX_AGE_DAYS, MIN_TITLE_LENGTH, PROCESSED_FILE, MAX_ARTICLES_PER_RUN,
    SIMILARITY_THRESHOLD
)
from utils import load_json, save_json


def load_processed():
    """Завантажує список вже оброблених статей."""
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"articles": []}


def save_processed(data):
    """Зберігає список оброблених статей. Атомарний запис через tmp-файл."""
    # Keep only last 500 entries to prevent file from growing forever
    data["articles"] = data["articles"][-1000:]
    dirpath = os.path.dirname(PROCESSED_FILE)
    os.makedirs(dirpath, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=dirpath, delete=False, suffix=".tmp", encoding="utf-8"
    ) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path = f.name
    os.replace(tmp_path, PROCESSED_FILE)


def make_hash(title, link):
    """Створює унікальний хеш для статті."""
    raw = f"{title.lower().strip()}|{link.strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


def clean_html(text):
    """Видаляє HTML-теги з тексту."""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def normalize_title(title):
    """Нормалізує заголовок для порівняння."""
    title = title.lower().strip()
    title = re.sub(r'^(breaking|update|new|report|exclusive)[:\s-]+', '', title)
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title)
    return title.strip()


def word_overlap_similarity(title1, title2):
    """Обчислює схожість заголовків за збігом слів."""
    words1 = set(normalize_title(title1).split())
    words2 = set(normalize_title(title2).split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    smaller = min(len(words1), len(words2))
    return len(intersection) / smaller if smaller > 0 else 0.0


def is_semantically_duplicate(title, existing_titles, threshold=None):
    """Перевіряє чи заголовок дублює існуючий."""
    if threshold is None:
        threshold = SIMILARITY_THRESHOLD
    for existing in existing_titles:
        if word_overlap_similarity(title, existing) > threshold:
            return True
    return False


def is_drug_related(title, summary):
    """Перевіряє чи стаття про наркотичну складову. Контекстно-залежна фільтрація."""
    text = f"{title} {summary}".lower()
    
    # Hard stop words — always reject
    for stop_word in STOP_WORDS:
        if stop_word.lower() in text:
            return True
    
    # Soft stop words — reject ONLY if no industrial hemp context present
    has_allow = any(word.lower() in text for word in ALLOW_CONTEXT)
    
    if not has_allow:
        for soft_word in SOFT_STOP_WORDS:
            if soft_word.lower() in text:
                return True
    
    return False


def is_hemp_relevant(title, content):
    """Швидка перевірка: чи містить стаття хоча б одне конопляне ключове слово.
    Використовується як пре-фільтр ПЕРЕД відправкою на AI.
    """
    text = f"{title} {content}".lower()
    return any(kw in text for kw in HEMP_KEYWORDS)


def parse_date(entry):
    """Витягує дату публікації зі запису RSS."""
    for field in ["published_parsed", "updated_parsed"]:
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def extract_images(entry):
    """
    Витягує URL зображень з RSS-запису.
    Повертає список dict: [{"url": "...", "alt": "..."}, ...]
    """
    images = []
    seen_urls = set()

    # Filter out tracking pixels and tiny images
    skip_patterns = ['pixel', 'tracker', '1x1', 'beacon', 'analytics', 'favicon', '.gif', 'spacer']

    def add_image(url, alt=""):
        if not url or url in seen_urls:
            return
        # Only HTTPS
        if not url.startswith('https://'):
            return
        # Skip tracking images
        url_lower = url.lower()
        if any(p in url_lower for p in skip_patterns):
            return
        seen_urls.add(url)
        images.append({"url": url, "alt": alt or ""})

    # 1. Check entry.content HTML for <img> tags
    content_parts = entry.get("content", [])
    if content_parts and isinstance(content_parts, list):
        html = content_parts[0].get("value", "")
        for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html):
            alt_match = re.search(r'alt=["\']([^"\']*)["\']', match.group(0))
            add_image(match.group(1), alt_match.group(1) if alt_match else "")

    # 2. Check entry.summary for <img> tags
    summary_html = entry.get("summary", "")
    if summary_html:
        for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', summary_html):
            alt_match = re.search(r'alt=["\']([^"\']*)["\']', match.group(0))
            add_image(match.group(1), alt_match.group(1) if alt_match else "")

    # 3. Check media_content
    media = entry.get("media_content", [])
    if media:
        for m in media:
            url = m.get("url", "")
            mtype = m.get("type", "")
            if url and ("image" in mtype or url.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))):
                add_image(url)

    # 4. Check enclosures
    for link in entry.get("links", []):
        if link.get("rel") == "enclosure" and "image" in link.get("type", ""):
            add_image(link.get("href", ""))

    return images[:5]


MAX_FETCH_THREADS = 5


def _fetch_single_feed(feed_url, processed_hashes, cutoff, trusted=False):
    """Завантажує та парсить один RSS-фід. Повертає список сирих статей (без dedup)."""
    raw_articles = []
    try:
        req = urllib.request.Request(
            feed_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; KONOPLA.UA/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            feed_content = resp.read()
        feed = feedparser.parse(feed_content)
        source = feed.feed.get("title", feed_url)[:50]

        for entry in feed.entries:
            title = clean_html(entry.get("title", ""))
            link = entry.get("link", "")

            # Try to resolve Google News redirect URL to real article URL.
            # If resolution fails, keep original Google News link — scraper will
            # attempt resolution again, and RSS summary/content already provides
            # enough text for hemp pre-filter + AI rewrite.
            if link and "news.google.com" in link:
                try:
                    from scraper import _resolve_google_news_url
                    resolved = _resolve_google_news_url(link)
                    if resolved:
                        link = resolved
                    else:
                        print(f"[WARN] Google News URL not resolved, keeping original: {link[:80]}")
                except Exception as e:
                    print(f"[WARN] Google News resolve error (keeping original): {e}")
            content_parts = entry.get("content", [])
            full_content = ""
            if content_parts and isinstance(content_parts, list):
                full_content = clean_html(content_parts[0].get("value", ""))
            summary = clean_html(entry.get("summary", entry.get("description", "")))

            if len(title) < MIN_TITLE_LENGTH:
                continue

            pub_date = parse_date(entry)
            if pub_date and pub_date < cutoff:
                continue

            article_hash = make_hash(title, link)
            if article_hash in processed_hashes:
                continue

            if is_drug_related(title, summary):
                continue

            article_text = full_content if len(full_content) > len(summary) else summary

            # === Пре-фільтр за ключовими словами ===
            # Trusted feeds (hemptoday.net, hempgazette.com) пропускають цю перевірку
            if not trusted and not is_hemp_relevant(title, article_text):
                print(f"[PRE-FILTER] Skipped: \"{title[:70]}...\" (no hemp keywords)")
                continue

            # === Скрейпінг повного тексту якщо RSS-контент короткий ===
            if len(article_text) < 500:
                try:
                    from scraper import scrape_article
                    scraped = scrape_article(link)
                    if scraped and len(scraped) > len(article_text):
                        article_text = scraped
                        print(f"[SCRAPER] Enriched: \"{title[:50]}...\" ({len(article_text)} chars)")
                except Exception as e:
                    print(f"[SCRAPER] Failed for {link[:60]}: {e}")
                time.sleep(1)  # Be polite to origin servers

            source_images = extract_images(entry)
            raw_articles.append({
                "title": title,
                "link": link,
                "summary": summary[:500],
                "content": article_text[:8000],
                "date": pub_date.isoformat() if pub_date else datetime.now(timezone.utc).isoformat(),
                "source": source,
                "hash": article_hash,
                "source_images": source_images,
            })

    except Exception as e:
        print(f"[WARN] Failed to parse feed {feed_url}: {e}")

    return raw_articles


def _update_feed_health(health, feed_url, success, articles_found=0, hemp_relevant=0):
    """Оновлює статистику здоров'я фіду."""
    now = datetime.now(timezone.utc).isoformat()
    entry = health.get(feed_url, {
        "last_ok": None, "last_fail": None,
        "fail_count": 0, "consecutive_fails": 0,
        "articles_found": 0, "hemp_relevant": 0
    })
    if success:
        entry["last_ok"] = now
        entry["consecutive_fails"] = 0
        entry["articles_found"] += articles_found
        entry["hemp_relevant"] += hemp_relevant
    else:
        entry["last_fail"] = now
        entry["fail_count"] += 1
        entry["consecutive_fails"] += 1
        if entry["consecutive_fails"] >= 10:
            print(f"[HEALTH] ⚠️ Feed has {entry['consecutive_fails']} consecutive failures: {feed_url[:60]}")
    health[feed_url] = entry


def fetch_all_feeds(region='all'):
    """
    Збирає всі нові статті з RSS-фідів.
    Повертає список словників з ключами: title, link, summary, date, source, hash

    region: 'all' | 'global' | 'ua' — фільтрує джерела за регіоном
    """
    processed = load_processed()
    processed_hashes = set(processed["articles"])
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)

    sources = load_sources(region=region, full=True)
    feed_health = load_json(FEED_HEALTH_FILE, default={})

    # === Паралельний fetch ===
    raw_articles = []
    feed_fail_count = 0
    with ThreadPoolExecutor(max_workers=MAX_FETCH_THREADS) as executor:
        futures = {}
        for src in sources:
            url = src["url"]
            trusted = src.get("trusted", False)
            futures[executor.submit(_fetch_single_feed, url, processed_hashes, cutoff, trusted)] = src

        for future in as_completed(futures):
            src = futures[future]
            try:
                articles = future.result()
                raw_articles.extend(articles)
                _update_feed_health(feed_health, src["url"], success=True,
                                   articles_found=len(articles), hemp_relevant=len(articles))
            except Exception as e:
                print(f"[WARN] Feed thread error ({src.get('name', '?')}): {e}")
                _update_feed_health(feed_health, src["url"], success=False)
                feed_fail_count += 1

    # Save feed health
    try:
        save_json(FEED_HEALTH_FILE, feed_health)
    except Exception:
        pass

    # === Однопотокова дедуплікація ===
    seen_hashes = set()
    accepted_titles = list(processed.get("recent_titles", []))
    all_articles = []

    for article in raw_articles:
        article_hash = article["hash"]
        if article_hash in seen_hashes:
            continue

        if is_semantically_duplicate(article["title"], accepted_titles):
            print(f"[DEDUP] Skipping similar: {article['title'][:60]}...")
            continue

        seen_hashes.add(article_hash)
        accepted_titles.append(article["title"])
        all_articles.append(article)

    # Sort by date (newest first) and limit
    all_articles.sort(key=lambda x: x["date"], reverse=True)
    all_articles = all_articles[:MAX_ARTICLES_PER_RUN]

    total_rss = len(raw_articles)
    print(f"[INFO] Found {len(all_articles)} new articles from {len(sources)} feeds ({feed_fail_count} failed)")
    print(f"[INFO] RSS entries total: {total_rss}, after dedup: {len(all_articles)}")
    return all_articles


def mark_processed(articles, processed=None):
    """Позначає статті як оброблені."""
    if processed is None:
        processed = load_processed()
    for article in articles:
        processed["articles"].append(article["hash"])
    save_processed(processed)


if __name__ == "__main__":
    articles = fetch_all_feeds()
    for a in articles:
        print(f"  [{a['source'][:30]}] {a['title'][:80]}")
