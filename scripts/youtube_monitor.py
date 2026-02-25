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
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import API_DELAY_SECONDS
from rewriter import rewrite_article
from publisher import create_article_file

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_FILE = os.path.join(PROJECT_ROOT, "data", "processed_videos.json")
DRAFTS_FILE = os.path.join(PROJECT_ROOT, "data", "drafts.json")
CONTENT_DIR = os.path.join(PROJECT_ROOT, "content", "news")

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

# Maximum videos to process per run (conserve API quota)
MAX_VIDEOS_PER_RUN = 3

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
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"video_ids": []}


def save_processed(data):
    """Зберігає список оброблених відео."""
    os.makedirs(os.path.dirname(PROCESSED_FILE), exist_ok=True)
    # Keep only last 500 entries
    data["video_ids"] = data["video_ids"][-500:]
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(filepath, default):
    """Завантажує JSON файл."""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(filepath, data):
    """Зберігає JSON файл."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def youtube_api_request(endpoint, params):
    """Робить запит до YouTube Data API v3."""
    params["key"] = YOUTUBE_API_KEY

    query_string = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{query_string}"

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"[ERROR] YouTube API {e.code}: {error_body[:300]}")
        return None
    except Exception as e:
        print(f"[ERROR] YouTube API request failed: {e}")
        return None


def search_videos(query, published_after, max_results=5):
    """Шукає відео на YouTube за запитом."""
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "date",
        "publishedAfter": published_after,
        "relevanceLanguage": "uk",
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
        results = search_videos(query, published_after, max_results=5)

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

        if not rewritten:
            print(f"  ⏭️ Skipping — rewrite failed")
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
            article_id = str(uuid.uuid4())[:8]
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
