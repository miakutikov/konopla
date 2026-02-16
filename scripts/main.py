#!/usr/bin/env python3
"""
main.py — KONOPLA.UA News Pipeline

Pipeline: RSS → фільтрація → рерайт → зображення → збереження в pending → відправка на модерацію адміну.
Публікація відбувається тільки після схвалення адміном (moderator.py).
"""

import json
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import API_DELAY_SECONDS, PENDING_FILE


def run_pipeline():
    """Запускає pipeline: збір, рерайт, збереження в pending."""

    start_time = time.time()

    print("=" * 60)
    print("🌿 KONOPLA.UA — News Pipeline")
    print("=" * 60)

    try:
        from fetcher import fetch_all_feeds, load_processed, save_processed
        from rewriter import rewrite_article
        from images import get_article_image
        from telegram_bot import send_for_moderation
        from monitor import send_pipeline_report, send_crash_alert
    except ImportError as e:
        print(f"[CRITICAL] Missing dependency: {e}")
        print("Run: pip install feedparser Pillow")
        return 1

    total_found = 0
    rewritten_count = 0
    failed_count = 0

    try:
        # === STEP 1: Fetch articles ===
        print("\n📡 Step 1: Fetching RSS feeds...")
        try:
            articles = fetch_all_feeds()
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

        # === STEP 2: Load pending ===
        pending = {"articles": []}
        if os.path.exists(PENDING_FILE):
            with open(PENDING_FILE, "r", encoding="utf-8") as f:
                pending = json.load(f)

        processed = load_processed()

        for i, article in enumerate(articles):
            print(f"\n{'='*40}")
            print(f"📰 Article {i+1}/{len(articles)}")
            print(f"   Title: {article['title'][:70]}...")

            # --- 2a: Rewrite ---
            rewritten = None
            try:
                print("   ✍️  Rewriting...")
                rewritten = rewrite_article(
                    title=article["title"],
                    summary=article["summary"],
                    source_url=article["link"],
                    content=article.get("content", "")
                )
            except Exception as e:
                print(f"   ❌ Rewrite error: {e}")

            if not rewritten:
                print("   ⏭️  Skipping — rewrite failed")
                failed_count += 1
                continue

            print(f"   ✅ {rewritten['title'][:60]}...")

            # --- 2b: Get image (non-critical) ---
            article_id = str(uuid.uuid4())[:8]
            image_data = None
            try:
                image_query = rewritten.get("image_query", "")
                category = rewritten.get("category", "інше")
                print(f"   🖼️  Image: {image_query or category}...")
                image_data = get_article_image(
                    query=image_query,
                    fallback_category=category,
                    article_id=article_id
                )
            except Exception as e:
                print(f"   ⚠️  Image error (non-critical): {e}")

            # --- 2c: Save to pending + send for moderation ---

            pending_article = {
                "id": article_id,
                "rewritten": rewritten,
                "source_url": article["link"],
                "source_name": article["source"],
                "image_data": image_data,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            # Send preview to admin
            try:
                print("   📨 Sending for moderation...")
                msg_id = send_for_moderation(rewritten, article_id)
                if msg_id:
                    pending_article["telegram_message_id"] = msg_id
            except Exception as e:
                print(f"   ⚠️  Moderation send error: {e}")

            pending["articles"].append(pending_article)

            # Mark as processed (to avoid re-fetching)
            processed["articles"].append(article["hash"])
            # Store title for dedup
            if "recent_titles" not in processed:
                processed["recent_titles"] = []
            processed["recent_titles"].append(rewritten["title"])
            processed["recent_titles"] = processed["recent_titles"][-200:]

            rewritten_count += 1

            if i < len(articles) - 1:
                print(f"   ⏳ {API_DELAY_SECONDS}s...")
                time.sleep(API_DELAY_SECONDS)

        # Save pending and processed
        os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump(pending, f, ensure_ascii=False, indent=2)

        save_processed(processed)

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
    print(f"   ❌ Failed: {failed_count}")
    print(f"   ⏱  Duration: {duration:.0f}s")
    print(f"   📋 Sent for moderation (waiting for admin approval)")
    print("=" * 60)

    try:
        send_pipeline_report(rewritten_count, failed_count, total_found, duration)
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    exit_code = run_pipeline()
    sys.exit(exit_code)
