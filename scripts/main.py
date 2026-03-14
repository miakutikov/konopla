#!/usr/bin/env python3
"""
main.py — KONOPLA.UA News Pipeline

Pipeline: RSS → фільтрація → рерайт → зображення → створення draft .md → деплой.
Статті створюються як draft (чернетка) — адмін модерує через /admin/ панель на сайті.
"""

import argparse
import json
import os
import sys
import tempfile
import time
import traceback
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import API_DELAY_SECONDS

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFTS_FILE = os.path.join(PROJECT_ROOT, "data", "drafts.json")
CONTENT_DIR = os.path.join(PROJECT_ROOT, "content", "news")


def load_json(filepath, default):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(filepath, data):
    """Atomic JSON write: write to tmp then rename to prevent corruption on crash."""
    dirpath = os.path.dirname(filepath)
    os.makedirs(dirpath, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=dirpath, delete=False, suffix=".tmp", encoding="utf-8"
    ) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path = f.name
    os.replace(tmp_path, filepath)


def run_pipeline(region='all'):
    """Запускає pipeline: збір, рерайт, створення draft-статей.

    region: 'all' | 'global' | 'ua' — які джерела сканувати (з data/sources.json)
    """

    # Validate required API keys before starting
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("OPENROUTER_API_KEY"):
        print("[CRITICAL] Neither GEMINI_API_KEY nor OPENROUTER_API_KEY is set — aborting")
        return 1

    start_time = time.time()

    region_labels = {'ua': '🇺🇦 UA', 'global': '🌍 Global', 'all': '🌐 All'}
    mode_label = region_labels.get(region, f'🌐 {region}')
    print("=" * 60)
    print(f"🌿 KONOPLA.UA — News Pipeline ({mode_label})")
    print("=" * 60)

    try:
        from fetcher import fetch_all_feeds, load_processed, save_processed
        from rewriter import rewrite_article
        from images import get_article_image
        from publisher import create_article_file
        from telegram_bot import send_message, ADMIN_CHAT_ID
        from monitor import send_pipeline_report, send_crash_alert
    except ImportError as e:
        print(f"[CRITICAL] Missing dependency: {e}")
        print("Run: pip install feedparser Pillow")
        return 1

    total_found = 0
    rewritten_count = 0
    failed_count = 0
    skipped_count = 0

    try:
        # === STEP 1: Fetch articles ===
        from config import load_sources
        feeds = load_sources(region=region)
        print(f"\n📡 Step 1: Fetching feeds [{mode_label}] ({len(feeds)} sources)...")
        try:
            articles = fetch_all_feeds(region=region)
        except Exception as e:
            print(f"[ERROR] RSS fetching failed: {e}")
            send_crash_alert(f"RSS fetching failed: {e}")
            return 1

        total_found = len(articles)

        if not articles:
            print("[INFO] No new articles found. Done.")
            duration = time.time() - start_time
            send_pipeline_report(0, 0, 0, duration)
            return 0

        print(f"[INFO] Processing {len(articles)} articles...\n")

        # Load drafts tracking file
        drafts = load_json(DRAFTS_FILE, {"articles": []})
        processed = load_processed()

        for i, article in enumerate(articles):
            print(f"\n{'='*40}")
            print(f"📰 Article {i+1}/{len(articles)}")
            print(f"   Title: {article['title'][:70]}...")

            # --- Rewrite ---
            rewritten = None
            try:
                print("   ✍️  Rewriting...")
                rewritten = rewrite_article(
                    title=article["title"],
                    summary=article["summary"],
                    source_url=article["link"],
                    content=article.get("content", ""),
                    source_images=article.get("source_images", [])
                )
            except Exception as e:
                print(f"   ❌ Rewrite error: {e}")

            if not rewritten:
                print("   ⏭️  Skipping — rewrite failed (API error)")
                failed_count += 1
                # Mark as processed to avoid re-fetching failed articles
                processed["articles"].append(article["hash"])
                save_processed(processed)
                continue

            if rewritten.get("rejected"):
                print(f"   ⏭️  Skipping — AI rejected as irrelevant")
                skipped_count += 1
                # Mark as processed to avoid re-fetching rejected articles
                processed["articles"].append(article["hash"])
                save_processed(processed)
                continue

            print(f"   ✅ {rewritten['title'][:60]}...")

            # --- Get image: prefer original source, fallback to Unsplash/Gemini ---
            article_id = str(uuid.uuid4())[:8]
            image_data = None

            # Priority 1: use first image from original RSS article
            if article.get("source_images"):
                first_img = article["source_images"][0]
                image_data = {
                    "url": first_img["url"],
                    "source": "original",
                    "author": "",
                    "author_url": "",
                }
                print(f"   🖼️  Using source image: {first_img['url'][:60]}...")

            # Priority 2: fallback to Unsplash/Gemini if no source image
            if not image_data:
                try:
                    image_query = rewritten.get("image_query", "")
                    category = rewritten.get("category", "інше")
                    print(f"   🖼️  No source image, searching: {image_query or category}...")
                    image_data = get_article_image(
                        query=image_query,
                        fallback_category=category,
                        article_id=article_id
                    )
                except Exception as e:
                    print(f"   ⚠️  Image error (non-critical): {e}")

            # --- Create draft Hugo .md file ---
            print("   📝 Creating draft article...")
            filepath = create_article_file(
                article_data=rewritten,
                source_url=article["link"],
                source_name=article["source"],
                image_data=image_data,
                content_dir=CONTENT_DIR,
                draft=True,
            )

            if not filepath:
                print(f"   ❌ Failed to create draft file")
                failed_count += 1
                # Mark as processed to avoid re-fetching
                processed["articles"].append(article["hash"])
                save_processed(processed)
                continue

            filename = os.path.basename(filepath)

            # Track draft for admin panel
            drafts["articles"].append({
                "id": article_id,
                "filename": filename,
                "title": rewritten.get("title", ""),
                "summary": rewritten.get("summary", ""),
                "category": rewritten.get("category", ""),
                "image": image_data.get("url", "") if image_data else "",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

            # Notify admin (simple message, no buttons)
            try:
                title = rewritten.get("title", "?")
                notify_text = (
                    f"📰 <b>Нова стаття на модерації</b>\n\n"
                    f"<b>{title}</b>\n\n"
                    f"👉 <a href=\"https://konopla.ua/admin/\">Модерувати</a>"
                )
                send_message(notify_text, chat_id=ADMIN_CHAT_ID)
            except Exception as e:
                print(f"   ⚠️  Admin notification error: {e}")

            # Mark as processed
            processed["articles"].append(article["hash"])
            if "recent_titles" not in processed:
                processed["recent_titles"] = []
            processed["recent_titles"].append(rewritten["title"])
            processed["recent_titles"] = processed["recent_titles"][-200:]

            rewritten_count += 1

            # Save after each article to prevent data loss on crash
            save_json(DRAFTS_FILE, drafts)
            save_processed(processed)

            if i < len(articles) - 1:
                print(f"   ⏳ {API_DELAY_SECONDS}s...")
                time.sleep(API_DELAY_SECONDS)

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        print(f"\n[CRITICAL] Pipeline crashed: {error_msg}")
        try:
            send_crash_alert(str(e))
        except Exception:
            pass
        return 1

    # === SUMMARY ===
    duration = time.time() - start_time

    print("\n" + "=" * 60)
    print(f"📊 Pipeline complete!")
    print(f"   📰 Total found: {total_found}")
    print(f"   ✍️  Rewritten: {rewritten_count}")
    print(f"   🚫 Skipped (irrelevant): {skipped_count}")
    print(f"   ❌ Failed (API errors): {failed_count}")
    print(f"   ⏱  Duration: {duration:.0f}s")
    print(f"   📋 Draft articles created (waiting for admin approval at /admin/)")
    print("=" * 60)

    try:
        send_pipeline_report(rewritten_count, failed_count, total_found, duration, skipped_count)
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KONOPLA.UA News Pipeline")
    parser.add_argument("--region", default="all", choices=["all", "global", "ua"],
                        help="Які джерела сканувати: all (default) | global | ua")
    args = parser.parse_args()

    exit_code = run_pipeline(region=args.region)
    sys.exit(exit_code)
