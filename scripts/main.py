#!/usr/bin/env python3
"""
main.py — Головний скрипт Konopla.UA v4 (final)

Pipeline: RSS → фільтрація → Gemini рерайт → Unsplash фото → Hugo markdown → Telegram → Instagram
З повним error handling та моніторингом.
"""

import os
import sys
import time
import traceback

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import API_DELAY_SECONDS, TELEGRAM_DELAY_SECONDS


def run_pipeline():
    """Запускає повний pipeline з error handling."""
    
    start_time = time.time()
    
    print("=" * 60)
    print("🌿 KONOPLA.UA — News Pipeline v4 (final)")
    print("=" * 60)
    
    # Import modules (wrapped to catch missing dependencies)
    try:
        from fetcher import fetch_all_feeds, load_processed, save_processed
        from rewriter import rewrite_article
        from publisher import create_article_file, create_telegram_message
        from telegram_bot import send_message, send_photo
        from images import get_unsplash_image
        from monitor import send_pipeline_report, send_crash_alert
    except ImportError as e:
        print(f"[CRITICAL] Missing dependency: {e}")
        print("Run: pip install feedparser Pillow")
        return 1
    
    # Try importing Instagram (optional — needs Pillow)
    try:
        from instagram import generate_story_image
        has_instagram = True
        print("[INFO] Instagram Stories: enabled")
    except ImportError:
        has_instagram = False
        print("[INFO] Instagram Stories: disabled (install Pillow to enable)")
    
    published_count = 0
    failed_count = 0
    total_found = 0
    
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
        
        # === STEP 2: Process each article ===
        processed = load_processed()
        
        content_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "content", "news"
        )
        
        ig_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "instagram"
        )
        
        for i, article in enumerate(articles):
            print(f"\n{'='*40}")
            print(f"📰 Article {i+1}/{len(articles)}")
            print(f"   Title: {article['title'][:70]}...")
            
            # --- 2a: Rewrite with Gemini ---
            rewritten = None
            try:
                print("   ✍️  Rewriting...")
                rewritten = rewrite_article(
                    title=article["title"],
                    summary=article["summary"],
                    source_url=article["link"]
                )
            except Exception as e:
                print(f"   ❌ Gemini error: {e}")
            
            if not rewritten:
                print("   ⏭️  Skipping — rewrite failed")
                failed_count += 1
                continue
            
            print(f"   ✅ {rewritten['title'][:60]}...")
            
            # --- 2b: Get image (non-critical) ---
            image_data = None
            try:
                if os.environ.get("UNSPLASH_ACCESS_KEY"):
                    image_query = rewritten.get("image_query", "")
                    category = rewritten.get("category", "інше")
                    print(f"   🖼️  Image: {image_query or category}...")
                    image_data = get_unsplash_image(
                        query=image_query,
                        fallback_category=category
                    )
            except Exception as e:
                print(f"   ⚠️  Image error (non-critical): {e}")
            
            # --- 2c: Create Hugo file ---
            filepath = None
            try:
                print("   📝 Creating article...")
                filepath = create_article_file(
                    article_data=rewritten,
                    source_url=article["link"],
                    source_name=article["source"],
                    image_data=image_data,
                    content_dir=content_dir
                )
            except Exception as e:
                print(f"   ❌ File creation error: {e}")
            
            if not filepath:
                failed_count += 1
                continue
            
            # --- 2d: Telegram (non-critical) ---
            try:
                print("   📨 Telegram...")
                tg_message = create_telegram_message(rewritten)
                if image_data and image_data.get("url"):
                    send_photo(photo_url=image_data["url"], caption=tg_message)
                else:
                    send_message(tg_message)
            except Exception as e:
                print(f"   ⚠️  Telegram error (non-critical): {e}")
            
            # --- 2e: Instagram Story (non-critical) ---
            if has_instagram:
                try:
                    print("   📸 Instagram Story...")
                    generate_story_image(
                        title=rewritten["title"],
                        category=rewritten.get("category", "інше"),
                        summary=rewritten.get("summary", ""),
                        output_dir=ig_dir
                    )
                except Exception as e:
                    print(f"   ⚠️  Instagram error (non-critical): {e}")
            
            # Mark as processed
            processed["articles"].append(article["hash"])
            published_count += 1
            
            # Rate limiting
            if i < len(articles) - 1:
                delay = max(API_DELAY_SECONDS, TELEGRAM_DELAY_SECONDS)
                print(f"   ⏳ {delay}s...")
                time.sleep(delay)
        
        # Save processed articles
        try:
            save_processed(processed)
        except Exception as e:
            print(f"[WARN] Failed to save processed list: {e}")
        
    except Exception as e:
        # Catch-all for unexpected errors
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
    print(f"   ✅ Published: {published_count}")
    print(f"   ❌ Failed: {failed_count}")
    print(f"   📰 Total found: {total_found}")
    print(f"   ⏱  Duration: {duration:.0f}s")
    if has_instagram:
        print(f"   📸 Instagram stories: {published_count}")
    print("=" * 60)
    
    # Send monitoring report
    try:
        send_pipeline_report(published_count, failed_count, total_found, duration)
    except Exception:
        pass
    
    return 0


if __name__ == "__main__":
    exit_code = run_pipeline()
    sys.exit(exit_code)
