"""
fetcher.py — Збирає новини з RSS-фідів
"""

import feedparser
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from config import (
    RSS_FEEDS, STOP_WORDS, SOFT_STOP_WORDS, ALLOW_CONTEXT,
    MAX_AGE_DAYS, MIN_TITLE_LENGTH, PROCESSED_FILE, MAX_ARTICLES_PER_RUN,
    SIMILARITY_THRESHOLD
)


def load_processed():
    """Завантажує список вже оброблених статей."""
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"articles": []}


def save_processed(data):
    """Зберігає список оброблених статей."""
    os.makedirs(os.path.dirname(PROCESSED_FILE), exist_ok=True)
    # Keep only last 500 entries to prevent file from growing forever
    data["articles"] = data["articles"][-500:]
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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


def fetch_all_feeds(feeds_override=None):
    """
    Збирає всі нові статті з RSS-фідів.
    Повертає список словників з ключами: title, link, summary, date, source, hash

    feeds_override: якщо передано, використовує цей список фідів замість RSS_FEEDS
    """
    processed = load_processed()
    processed_hashes = set(processed["articles"])

    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)

    all_articles = []
    seen_hashes = set()
    accepted_titles = list(processed.get("recent_titles", []))

    feeds_to_use = feeds_override if feeds_override is not None else RSS_FEEDS
    for feed_url in feeds_to_use:
        try:
            feed = feedparser.parse(feed_url)
            source = feed.feed.get("title", feed_url)[:50]
            
            for entry in feed.entries:
                title = clean_html(entry.get("title", ""))
                link = entry.get("link", "")
                # Get full content if available, otherwise summary
                content_parts = entry.get("content", [])
                full_content = ""
                if content_parts and isinstance(content_parts, list):
                    full_content = clean_html(content_parts[0].get("value", ""))
                summary = clean_html(entry.get("summary", entry.get("description", "")))
                
                # Basic quality checks
                if len(title) < MIN_TITLE_LENGTH:
                    continue
                
                # Check date
                pub_date = parse_date(entry)
                if pub_date and pub_date < cutoff:
                    continue
                
                # Deduplication
                article_hash = make_hash(title, link)
                if article_hash in processed_hashes or article_hash in seen_hashes:
                    continue
                
                # Drug filter
                if is_drug_related(title, summary):
                    continue

                # Semantic dedup
                if is_semantically_duplicate(title, accepted_titles):
                    print(f"[DEDUP] Skipping similar: {title[:60]}...")
                    continue

                seen_hashes.add(article_hash)
                accepted_titles.append(title)
                # Use full content if available, otherwise summary
                article_text = full_content if len(full_content) > len(summary) else summary
                # Extract images from source article
                source_images = extract_images(entry)
                all_articles.append({
                    "title": title,
                    "link": link,
                    "summary": summary[:500],
                    "content": article_text[:5000],
                    "date": pub_date.isoformat() if pub_date else datetime.now(timezone.utc).isoformat(),
                    "source": source,
                    "hash": article_hash,
                    "source_images": source_images,
                })
                
        except Exception as e:
            print(f"[WARN] Failed to parse feed {feed_url}: {e}")
            continue
    
    # Sort by date (newest first) and limit
    all_articles.sort(key=lambda x: x["date"], reverse=True)
    all_articles = all_articles[:MAX_ARTICLES_PER_RUN]
    
    print(f"[INFO] Found {len(all_articles)} new articles from {len(feeds_to_use)} feeds")
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
