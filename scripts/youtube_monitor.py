#!/usr/bin/env python3
"""
youtube_monitor.py — Моніторить YouTube для нових відео про промислові коноплі.

Шукає відео через YouTube Data API v3, рерайтить опис через Gemini,
та створює draft-статті з youtube_id у frontmatter.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import API_DELAY_SECONDS
from rewriter import rewrite_article
from publisher import create_article_file
from fetcher import is_drug_related
from utils import load_json, save_json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_FILE = os.path.join(PROJECT_ROOT, "data", "processed_videos.json")
DRAFTS_FILE = os.path.join(PROJECT_ROOT, "data", "drafts.json")
CONTENT_DIR = os.path.join(PROJECT_ROOT, "content", "news")

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

# Maximum videos to process per run (conserve API quota)
MAX_VIDEOS_PER_RUN = 5

# TTL-кеш для YouTube пошукових запитів (години)
SEARCH_CACHE_TTL_HOURS = 12
SEARCH_CACHE_FILE = os.path.join(PROJECT_ROOT, "data", "youtube_search_cache.json")

# How many days to look back for videos
SEARCH_DAYS_BACK = 7

# Search queries for industrial hemp content
SEARCH_QUERIES = [
    "промислові коноплі",
    "hemp ukraine",
    "конопляна індустрія",
    "hempcrete",
    "конопляний бетон",
    "hemp textile",
    "industrial hemp",
    "конопляне волокно",
]


def load_processed():
    """Завантажує список оброблених відео."""
    return load_json(PROCESSED_FILE, {"video_ids": []})


def save_processed(data):
    """Зберігає список оброблених відео (атомарний запис)."""
    # Keep only last 500 entries
    data["video_ids"] = data["video_ids"][-500:]
    save_json(PROCESSED_FILE, data)




def _get_cached_search(query, published_after):
    """Повертає кешовані результати або None якщо кеш відсутній/expired."""
    import hashlib as _hashlib
    cache = load_json(SEARCH_CACHE_FILE, {"queries": {}})
    cache_key = _hashlib.md5(f"{query}|{published_after}".encode()).hexdigest()

    entry = cache["queries"].get(cache_key)
    if not entry:
        return None

    try:
        cached_at = datetime.fromisoformat(entry["cached_at"])
        age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        if age_hours < SEARCH_CACHE_TTL_HOURS:
            return entry["results"]
    except (KeyError, ValueError):
        pass

    return None


def _set_cached_search(query, published_after, results):
    """Кешує результати пошуку (тільки непорожні)."""
    if not results:
        return
    import hashlib as _hashlib
    cache = load_json(SEARCH_CACHE_FILE, {"queries": {}})
    cache_key = _hashlib.md5(f"{query}|{published_after}".encode()).hexdigest()

    cache["queries"][cache_key] = {
        "query": query,
        "results": results,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }

    # Прибрати старі записи (більше 50)
    if len(cache["queries"]) > 50:
        sorted_keys = sorted(
            cache["queries"].keys(),
            key=lambda k: cache["queries"][k].get("cached_at", ""),
        )
        for old_key in sorted_keys[:-50]:
            del cache["queries"][old_key]

    save_json(SEARCH_CACHE_FILE, cache)


def youtube_api_request(endpoint, params):
    """Робить запит до YouTube Data API v3."""
    params["key"] = YOUTUBE_API_KEY

    query_string = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{query_string}"

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            print(f"[ERROR] YouTube API {e.code}: {error_body[:300]}")
            if e.code in (429, 500, 503) and attempt < 2:
                wait = 2 ** (attempt + 1)
                print(f"[RETRY] Waiting {wait}s before retry {attempt + 2}/3...")
                time.sleep(wait)
                continue
            return None
        except Exception as e:
            print(f"[ERROR] YouTube API request failed: {e}")
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            return None


def search_videos(query, published_after, max_results=5):
    """Шукає відео на YouTube за запитом."""
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "date",
        "publishedAfter": published_after,
        "maxResults": max_results,
    }

    data = youtube_api_request("search", params)
    if not data:
        return []

    return data.get("items", [])


def get_video_details(video_id):
    """Отримує деталі відео (повний опис, статистику)."""
    params = {
        "part": "snippet,statistics,contentDetails",
        "id": video_id,
    }

    data = youtube_api_request("videos", params)
    if not data or not data.get("items"):
        return None

    return data["items"][0]


def is_hemp_relevant(title, description):
    """Перевіряє чи відео дійсно про промислові коноплі."""
    text = f"{title} {description}".lower()

    # Must contain at least one hemp keyword
    hemp_keywords = [
        "hemp", "коноплі", "конопля", "конопляний", "конопляне",
        "hempcrete", "промислові", "industrial", "textile", "текстиль",
        "волокно", "fiber", "fibre", "будівництво", "construction",
        "біопластик", "bioplastic", "агро", "farming",
    ]

    has_hemp = any(kw in text for kw in hemp_keywords)
    if not has_hemp:
        return False

    # Must NOT be about drugs
    drug_keywords = [
        "marijuana", "марихуана", "weed", "ganja",
        "stoner", "420", "dispensary", "psychoactive",
        "narcotic", "наркотик", "drug bust", "get high",
        "thc oil", "thc gummies", "delta-8",
        "medical marijuana", "indica", "sativa",
    ]

    has_drug = any(kw in text for kw in drug_keywords)
    return not has_drug


def run_youtube_monitor():
    """Основна функція моніторингу YouTube."""
    print("=" * 60)
    print("🎬 KONOPLA.UA — YouTube Monitor")
    print("=" * 60)

    if not YOUTUBE_API_KEY:
        print("[ERROR] YOUTUBE_API_KEY not set. Exiting.")
        return 1

    processed = load_processed()
    processed_ids = set(processed["video_ids"])

    cutoff = datetime.now(timezone.utc) - timedelta(days=SEARCH_DAYS_BACK)
    published_after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"[INFO] Searching videos published after {published_after}")

    # Collect candidate videos from all queries
    candidates = {}  # video_id -> snippet data
    for query in SEARCH_QUERIES:
        print(f"\n🔍 Query: {query}")

        # Спробувати кеш
        results = _get_cached_search(query, published_after)
        if results is not None:
            print(f"  [CACHE HIT] {len(results)} results")
        else:
            results = search_videos(query, published_after, max_results=5)
            _set_cached_search(query, published_after, results)

        for item in results:
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue
            if video_id in processed_ids:
                print(f"  [SKIP] Already processed: {video_id}")
                continue
            if video_id in candidates:
                continue

            snippet = item.get("snippet", {})
            title = snippet.get("title", "")
            description = snippet.get("description", "")

            if not is_hemp_relevant(title, description):
                print(f"  [SKIP] Not relevant: {title[:60]}")
                continue

            # Also run through the shared drug-content filter from fetcher
            if is_drug_related(title, description):
                print(f"  [SKIP] Drug-related content: {title[:60]}")
                continue

            candidates[video_id] = snippet
            print(f"  [OK] Candidate: {title[:60]}")

        time.sleep(1)  # Brief pause between queries

    print(f"\n[INFO] Found {len(candidates)} new candidate videos")

    if not candidates:
        print("[INFO] No new videos to process. Done.")
        return 0

    # Process top N candidates
    drafts = load_json(DRAFTS_FILE, {"articles": []})
    count = 0

    for video_id, snippet in list(candidates.items())[:MAX_VIDEOS_PER_RUN]:
        print(f"\n{'=' * 40}")
        print(f"🎬 Processing video: {video_id}")

        # Get full video details (only 1 API unit!)
        details = get_video_details(video_id)
        if not details:
            print(f"  [WARN] Failed to get details for {video_id}")
            continue

        full_snippet = details.get("snippet", {})
        title = full_snippet.get("title", "")
        description = full_snippet.get("description", "")
        channel = full_snippet.get("channelTitle", "")
        published_at = full_snippet.get("publishedAt", "")
        thumbnail = full_snippet.get("thumbnails", {}).get("high", {}).get("url", "")

        stats = details.get("statistics", {})
        views = stats.get("viewCount", "0")

        print(f"  Title: {title[:70]}")
        print(f"  Channel: {channel}")
        print(f"  Views: {views}")

        # Rewrite via Gemini with video-specific context
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        video_content = f"""Це YouTube відео про промислові коноплі.

Назва: {title}
Канал: {channel}
Опис: {description[:2000]}
Переглядів: {views}
Посилання: {video_url}

ВАЖЛИВО: Це відео, а не текстова стаття. Напиши анонс/огляд цього відео для сайту Konopla.UA.
Зазнач що це відео і хто його автор. Заохоть читача переглянути відео на сайті."""

        try:
            print("  ✍️ Rewriting...")
            rewritten = rewrite_article(
                title=title,
                summary=description[:500],
                source_url=video_url,
                content=video_content,
            )
        except Exception as e:
            print(f"  ❌ Rewrite error: {e}")
            rewritten = None

        if not isinstance(rewritten, dict) or "title" not in rewritten:
            reason = rewritten.get("reason", "rewrite failed") if isinstance(rewritten, dict) else "rewrite failed"
            print(f"  ⏭️ Skipping — {reason}")
            processed["video_ids"].append(video_id)
            continue
        if rewritten.get("rejected"):
            print(f"  ⏭️ Skipping — AI rejected: {rewritten.get('reason', 'irrelevant')}")
            processed["video_ids"].append(video_id)
            continue

        # Force category to "відео"
        rewritten["category"] = "відео"
        # Add youtube_id
        rewritten["youtube_id"] = video_id

        # Use thumbnail as image
        image_data = None
        if thumbnail:
            image_data = {
                "url": thumbnail,
                "author": channel,
                "author_url": f"https://www.youtube.com/@{channel.replace(' ', '')}",
                "unsplash_url": video_url,
                "source": "youtube",
            }

        print(f"  ✅ {rewritten['title'][:60]}...")

        # Create draft file
        filepath = create_article_file(
            article_data=rewritten,
            source_url=video_url,
            source_name=f"YouTube: {channel}",
            image_data=image_data,
            content_dir=CONTENT_DIR,
            draft=True,
        )

        if filepath:
            import uuid
            article_id = uuid.uuid4().hex[:12]
            filename = os.path.basename(filepath)

            drafts["articles"].append({
                "id": article_id,
                "filename": filename,
                "title": rewritten.get("title", ""),
                "summary": rewritten.get("summary", ""),
                "category": "відео",
                "image": thumbnail,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

            count += 1
            print(f"  📝 Draft created: {filename}")

        processed["video_ids"].append(video_id)

        if count < MAX_VIDEOS_PER_RUN:
            time.sleep(API_DELAY_SECONDS)

    # Save everything
    save_processed(processed)
    save_json(DRAFTS_FILE, drafts)

    print(f"\n{'=' * 60}")
    print(f"📊 YouTube Monitor complete!")
    print(f"   🎬 Candidates found: {len(candidates)}")
    print(f"   ✍️ Drafts created: {count}")
    print("=" * 60)

    # Notify admin via Telegram
    try:
        from telegram_bot import send_message, ADMIN_CHAT_ID
        if count > 0:
            send_message(
                f"🎬 <b>YouTube Monitor</b>\n\n"
                f"Знайдено {count} нових відео.\n"
                f"👉 <a href=\"https://konopla.ua/admin/\">Модерувати</a>",
                chat_id=ADMIN_CHAT_ID
            )
    except Exception as e:
        print(f"[WARN] Admin notification failed: {e}")

    return 0


if __name__ == "__main__":
    exit_code = run_youtube_monitor()
    sys.exit(exit_code)
