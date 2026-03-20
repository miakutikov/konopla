#!/usr/bin/env python3
"""
main.py — KONOPLA.UA News Pipeline

Two modes:
  --action discover  (default) — fetch RSS, save raw candidates to candidates.json (no AI)
  --action process --ids id1,id2 — rewrite selected candidates via Gemini, create draft .md files
"""

import argparse
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import API_DELAY_SECONDS, load_sources
from utils import load_json, save_json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFTS_FILE = os.path.join(PROJECT_ROOT, "data", "drafts.json")
CONTENT_DIR = os.path.join(PROJECT_ROOT, "content", "news")
CANDIDATES_FILE = os.path.join(PROJECT_ROOT, "data", "candidates.json")

CANDIDATES_MAX_AGE_DAYS = 7
CANDIDATES_MAX_ITEMS = 200


# ---------------------------------------------------------------------------
# Mode 1: discover
# ---------------------------------------------------------------------------

def run_discover(region='all'):
    """Fetch RSS feeds and save raw candidates. No AI calls required."""
    from fetcher import fetch_all_feeds, load_processed
    from monitor import send_pipeline_report, send_crash_alert

    start_time = time.time()

    region_labels = {'ua': 'UA', 'global': 'Global', 'all': 'All'}
    mode_label = region_labels.get(region, region)
    print("=" * 60)
    print(f"KONOPLA.UA — Discover ({mode_label})")
    print("=" * 60)

    try:
        articles = fetch_all_feeds(region=region)
    except Exception as e:
        print(f"[CRITICAL] RSS fetching failed: {e}")
        try:
            send_crash_alert(f"RSS fetching failed: {e}")
        except Exception:
            pass
        return 1

    if not articles:
        print("[INFO] No new articles found.")
        duration = time.time() - start_time
        try:
            send_pipeline_report(0, 0, 0, duration)
        except Exception:
            pass
        return 0

    # Load existing candidates and processed hashes
    candidates = load_json(CANDIDATES_FILE, {"items": []})
    processed = load_processed()
    existing_hashes = {c["hash"] for c in candidates.get("items", [])}
    processed_hashes = set(processed.get("articles", []))

    new_count = 0
    for article in articles:
        h = article["hash"]
        if h in existing_hashes or h in processed_hashes:
            continue

        first_image = ""
        if article.get("source_images"):
            first_image = article["source_images"][0].get("url", "")

        content_text = article.get("content", "") or article.get("summary", "")

        candidate = {
            "id": str(uuid.uuid4())[:8],
            "type": "article",
            "title": article["title"],
            "link": article["link"],
            "source": article["source"],
            "summary": article.get("summary", "")[:500],
            "image_url": first_image,
            "date": article["date"],
            "hash": h,
            "content_preview": content_text[:300],
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        candidates.setdefault("items", []).append(candidate)
        existing_hashes.add(h)
        new_count += 1

    # Cleanup: remove old candidates and enforce max size
    candidates["items"] = _cleanup_candidates(candidates.get("items", []))

    save_json(CANDIDATES_FILE, candidates)

    duration = time.time() - start_time
    print(f"\n[INFO] Found {new_count} new candidates (total: {len(candidates['items'])})")
    print(f"[INFO] Duration: {duration:.0f}s")

    try:
        send_pipeline_report(0, 0, len(articles), duration)
    except Exception:
        pass

    return 0


def _cleanup_candidates(items):
    """Remove candidates older than 7 days and cap at 200 items."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=CANDIDATES_MAX_AGE_DAYS)
    cleaned = []
    for item in items:
        added = item.get("added_at") or item.get("date", "")
        try:
            dt = datetime.fromisoformat(added.replace("Z", "+00:00"))
            if dt < cutoff:
                continue
        except (ValueError, AttributeError):
            pass
        cleaned.append(item)

    # Keep newest first, cap at max
    cleaned.sort(key=lambda x: x.get("added_at", x.get("date", "")), reverse=True)
    return cleaned[:CANDIDATES_MAX_ITEMS]


# ---------------------------------------------------------------------------
# Mode 2: process
# ---------------------------------------------------------------------------

def run_process(ids):
    """Process selected candidates: scrape, rewrite, create draft .md files."""

    # Validate required API keys
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("OPENROUTER_API_KEY"):
        print("[CRITICAL] Neither GEMINI_API_KEY nor OPENROUTER_API_KEY is set — aborting")
        return 1

    try:
        from fetcher import load_processed, save_processed
        from scraper import scrape_article
        from rewriter import rewrite_article
        from images import get_article_image
        from publisher import create_article_file
        from telegram_bot import send_message, ADMIN_CHAT_ID
        from monitor import send_crash_alert
    except ImportError as e:
        print(f"[CRITICAL] Missing dependency: {e}")
        return 1

    start_time = time.time()
    print("=" * 60)
    print(f"KONOPLA.UA — Process ({len(ids)} candidates)")
    print("=" * 60)

    candidates = load_json(CANDIDATES_FILE, {"items": []})
    items_by_id = {c["id"]: c for c in candidates.get("items", [])}

    # Resolve requested candidates
    to_process = []
    for cid in ids:
        cid = cid.strip()
        if not cid:
            continue
        if cid in items_by_id:
            to_process.append(items_by_id[cid])
        else:
            print(f"[WARN] Candidate ID not found: {cid}")

    if not to_process:
        print("[INFO] No valid candidates to process.")
        return 0

    drafts = load_json(DRAFTS_FILE, {"articles": []})
    processed = load_processed()
    processed_ids = []

    rewritten_count = 0
    failed_count = 0
    skipped_count = 0

    try:
        for i, candidate in enumerate(to_process):
            print(f"\n{'='*40}")
            print(f"Article {i+1}/{len(to_process)}")
            print(f"   Title: {candidate['title'][:70]}...")

            # --- Scrape full text if content_preview is short ---
            content = candidate.get("content_preview", "")
            if len(content) < 500:
                try:
                    print("   Scraping full text...")
                    scraped = scrape_article(candidate["link"])
                    if scraped and len(scraped) > len(content):
                        content = scraped
                        print(f"   Scraped: {len(content)} chars")
                except Exception as e:
                    print(f"   Scrape error (non-critical): {e}")
                time.sleep(1)

            # --- Rewrite via AI ---
            rewritten = None
            try:
                print("   Rewriting...")
                source_images = []
                if candidate.get("image_url"):
                    source_images = [{"url": candidate["image_url"], "alt": ""}]

                rewritten = rewrite_article(
                    title=candidate["title"],
                    summary=candidate.get("summary", ""),
                    source_url=candidate["link"],
                    content=content,
                    source_images=source_images,
                )
            except Exception as e:
                print(f"   Rewrite error: {e}")

            if not rewritten:
                print("   Skipping — rewrite failed (API error)")
                failed_count += 1
                processed["articles"].append(candidate["hash"])
                save_processed(processed)
                processed_ids.append(candidate["id"])
                continue

            if rewritten.get("rejected"):
                print("   Skipping — AI rejected as irrelevant")
                skipped_count += 1
                processed["articles"].append(candidate["hash"])
                save_processed(processed)
                processed_ids.append(candidate["id"])
                continue

            print(f"   OK: {rewritten['title'][:60]}...")

            # --- Get image: prefer original source, fallback to Unsplash/Gemini ---
            article_id = str(uuid.uuid4())[:8]
            image_data = None

            if candidate.get("image_url"):
                image_data = {
                    "url": candidate["image_url"],
                    "source": "original",
                    "author": "",
                    "author_url": "",
                }
                print(f"   Using source image: {candidate['image_url'][:60]}...")

            if not image_data:
                try:
                    image_query = rewritten.get("image_query", "")
                    category = rewritten.get("category", "інше")
                    print(f"   No source image, searching: {image_query or category}...")
                    image_data = get_article_image(
                        query=image_query,
                        fallback_category=category,
                        article_id=article_id,
                    )
                except Exception as e:
                    print(f"   Image error (non-critical): {e}")

            # --- Create draft Hugo .md file ---
            print("   Creating draft article...")
            filepath = create_article_file(
                article_data=rewritten,
                source_url=candidate["link"],
                source_name=candidate["source"],
                image_data=image_data,
                content_dir=CONTENT_DIR,
                draft=True,
            )

            if not filepath:
                print("   Failed to create draft file")
                failed_count += 1
                processed["articles"].append(candidate["hash"])
                save_processed(processed)
                processed_ids.append(candidate["id"])
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

            # Notify admin
            try:
                title = rewritten.get("title", "?")
                notify_text = (
                    f"<b>Nova stattia na moderatsii</b>\n\n"
                    f"<b>{title}</b>\n\n"
                    f"<a href=\"https://konopla.ua/admin/\">Moderuvaty</a>"
                )
                send_message(notify_text, chat_id=ADMIN_CHAT_ID)
            except Exception as e:
                print(f"   Admin notification error: {e}")

            # Mark as processed
            processed["articles"].append(candidate["hash"])
            if "recent_titles" not in processed:
                processed["recent_titles"] = []
            processed["recent_titles"].append(rewritten["title"])
            processed["recent_titles"] = processed["recent_titles"][-200:]

            rewritten_count += 1
            processed_ids.append(candidate["id"])

            # Save after each article
            save_json(DRAFTS_FILE, drafts)
            save_processed(processed)

            if i < len(to_process) - 1:
                print(f"   Waiting {API_DELAY_SECONDS}s...")
                time.sleep(API_DELAY_SECONDS)

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        print(f"\n[CRITICAL] Pipeline crashed: {error_msg}")
        try:
            send_crash_alert(str(e))
        except Exception:
            pass
        # Still remove successfully processed candidates before returning
        _remove_processed_candidates(processed_ids)
        return 1

    # Remove processed candidates from candidates.json
    _remove_processed_candidates(processed_ids)

    # Summary
    duration = time.time() - start_time
    print("\n" + "=" * 60)
    print("Process complete!")
    print(f"   Rewritten: {rewritten_count}")
    print(f"   Skipped (irrelevant): {skipped_count}")
    print(f"   Failed (API errors): {failed_count}")
    print(f"   Duration: {duration:.0f}s")
    print("=" * 60)

    return 0


def _remove_processed_candidates(processed_ids):
    """Remove processed candidates from candidates.json."""
    if not processed_ids:
        return
    candidates = load_json(CANDIDATES_FILE, {"items": []})
    id_set = set(processed_ids)
    candidates["items"] = [c for c in candidates.get("items", []) if c["id"] not in id_set]
    save_json(CANDIDATES_FILE, candidates)
    print(f"[INFO] Removed {len(processed_ids)} processed candidates from candidates.json")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KONOPLA.UA News Pipeline")
    parser.add_argument(
        "--action", default="discover",
        choices=["discover", "process"],
        help="discover: fetch RSS, save candidates (default). process: rewrite selected candidates.",
    )
    parser.add_argument(
        "--ids", default="",
        help="Comma-separated candidate IDs for process mode",
    )
    parser.add_argument(
        "--region", default="all",
        choices=["all", "global", "ua"],
        help="Which sources to scan: all (default) | global | ua",
    )
    args = parser.parse_args()

    if args.action == "discover":
        exit_code = run_discover(region=args.region)
    elif args.action == "process":
        if not args.ids:
            print("[ERROR] --ids is required for process mode")
            sys.exit(1)
        id_list = [x.strip() for x in args.ids.split(",") if x.strip()]
        exit_code = run_process(id_list)
    else:
        print(f"[ERROR] Unknown action: {args.action}")
        exit_code = 1

    sys.exit(exit_code)
