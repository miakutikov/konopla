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
WORKFLOW_FILE = os.path.join(PROJECT_ROOT, "data", "workflow.json")
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
    from relevance import compute_relevance, is_source_trusted, guess_category

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

        # Compute relevance score
        sources_full = load_sources(full=True)
        rel_score, rel_reasons = compute_relevance(
            title=article["title"],
            content=content_text,
            source_name=article["source"],
            sources=sources_full,
        )

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
            "relevance_score": rel_score,
            "relevance_reasons": rel_reasons,
            "source_trusted": is_source_trusted(article["source"], sources_full),
            "category_hint": guess_category(article["title"], content_text),
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
        from scraper import scrape_article_full
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

    # Also load workflow.json as fallback (candidates are removed from
    # candidates.json when shortlisted, but their data lives in workflow.json)
    workflow = load_json(WORKFLOW_FILE, {"articles": []})
    wf_by_id = {}
    for wf in workflow.get("articles", []):
        if wf.get("candidate_id"):
            wf_by_id[wf["candidate_id"]] = wf
        if wf.get("id"):
            wf_by_id[wf["id"]] = wf

    # Resolve requested candidates
    to_process = []
    for cid in ids:
        cid = cid.strip()
        if not cid:
            continue
        if cid in items_by_id:
            to_process.append(items_by_id[cid])
        elif cid in wf_by_id:
            # Build candidate-like dict from workflow entry
            wf_item = wf_by_id[cid]
            print(f"[INFO] Candidate {cid} found in workflow.json (already shortlisted)")
            to_process.append({
                "id": cid,
                "title": wf_item.get("original_title") or wf_item.get("title", ""),
                "link": wf_item.get("original_url", ""),
                "source": wf_item.get("source_name", ""),
                "summary": wf_item.get("summary", ""),
                "image_url": wf_item.get("image", ""),
                "date": wf_item.get("created_at", ""),
                "hash": "",
                "content_preview": wf_item.get("content_preview") or wf_item.get("summary", ""),
                "category_hint": wf_item.get("category", ""),
            })
        else:
            print(f"[WARN] Candidate ID not found in candidates.json or workflow.json: {cid}")

    if not to_process:
        print("[INFO] No valid candidates to process.")
        return 0

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

            # --- Scrape full text ---
            content = candidate.get("content_preview", "")
            # Always try scraping if we don't have substantial content
            scraped_images = []
            scraped_og_image = ""
            if len(content) < 2000:
                try:
                    print("   Scraping full text...")
                    scrape_result = scrape_article_full(candidate["link"])
                    if scrape_result and scrape_result.get("text") and len(scrape_result["text"]) > len(content):
                        content = scrape_result["text"]
                        scraped_images = scrape_result.get("images", [])
                        scraped_og_image = scrape_result.get("og_image", "")
                        print(f"   Scraped: {len(content)} chars, {len(scraped_images)} images, og_image: {'yes' if scraped_og_image else 'no'}")
                    else:
                        print(f"   [WARN] Scrape returned no usable content from {candidate['link'][:60]}")
                except Exception as e:
                    print(f"   Scrape error: {e}")
                time.sleep(1)

            # If content is too short, mark as failed and skip
            if len(content) < 200:
                print(f"   [ERROR] Insufficient content ({len(content)} chars) — cannot rewrite")
                print(f"   The source page may require JS, have a paywall, or block bots")
                failed_count += 1
                # Update workflow: mark as needing manual URL
                _update_workflow_status(
                    candidate.get("id", ""),
                    status="scrape_failed",
                    stage="feed",
                )
                continue

            # --- Rewrite via AI ---
            rewritten = None
            try:
                print("   Rewriting...")
                source_images = []
                if candidate.get("image_url"):
                    source_images = [{"url": candidate["image_url"], "alt": ""}]
                elif scraped_og_image:
                    source_images = [{"url": scraped_og_image, "alt": ""}]
                elif scraped_images:
                    source_images = scraped_images[:3]

                is_manual = not candidate.get("hash")
                rewritten = rewrite_article(
                    title=candidate["title"],
                    summary=candidate.get("summary", ""),
                    source_url=candidate["link"],
                    content=content,
                    source_images=source_images,
                    force_relevant=is_manual,
                )
            except Exception as e:
                print(f"   Rewrite error: {e}")

            if not rewritten:
                print("   Skipping — rewrite failed (API error)")
                failed_count += 1
                if candidate.get("hash"):
                    processed["articles"].append(candidate["hash"])
                save_processed(processed)
                processed_ids.append(candidate["id"])
                continue

            if rewritten.get("rejected"):
                print("   Skipping — AI rejected as irrelevant")
                skipped_count += 1
                if candidate.get("hash"):
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

            # Fallback: use og:image or first scraped image from the page
            if not image_data and scraped_og_image:
                image_data = {
                    "url": scraped_og_image,
                    "source": "original",
                    "author": "",
                    "author_url": "",
                }
                print(f"   Using scraped og:image: {scraped_og_image[:60]}...")

            if not image_data and scraped_images:
                image_data = {
                    "url": scraped_images[0]["url"],
                    "source": "original",
                    "author": "",
                    "author_url": "",
                }
                print(f"   Using scraped page image: {scraped_images[0]['url'][:60]}...")

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
                if candidate.get("hash"):
                    processed["articles"].append(candidate["hash"])
                save_processed(processed)
                processed_ids.append(candidate["id"])
                continue

            filename = os.path.basename(filepath)

            # Track in workflow.json
            _add_to_workflow(
                article_id=article_id,
                filename=filename,
                rewritten=rewritten,
                candidate=candidate,
                image_data=image_data,
            )

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
            if candidate.get("hash"):
                processed["articles"].append(candidate["hash"])
            if "recent_titles" not in processed:
                processed["recent_titles"] = []
            processed["recent_titles"].append(rewritten["title"])
            processed["recent_titles"] = processed["recent_titles"][-200:]

            rewritten_count += 1
            processed_ids.append(candidate["id"])

            # Save after each article
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
# Workflow state management
# ---------------------------------------------------------------------------

def _update_workflow_status(candidate_id, status, stage=None):
    """Update status of an existing workflow entry (e.g. mark scrape_failed)."""
    if not candidate_id:
        return
    workflow = load_json(WORKFLOW_FILE, {"articles": []})
    for a in workflow.get("articles", []):
        if a.get("candidate_id") == candidate_id or a.get("id") == candidate_id:
            a["status"] = status
            if stage:
                a["stage"] = stage
            a["updated_at"] = datetime.now(timezone.utc).isoformat()
            save_json(WORKFLOW_FILE, workflow)
            print(f"   Workflow status → {status}")
            return
    print(f"   [WARN] Workflow entry not found for {candidate_id}")


def _add_to_workflow(article_id, filename, rewritten, candidate, image_data):
    """Add or update a processed article in workflow.json for the editorial pipeline."""
    workflow = load_json(WORKFLOW_FILE, {"articles": []})

    now_iso = datetime.now(timezone.utc).isoformat()
    cand_id = candidate.get("id", "")

    # Check if workflow entry already exists (from shortlisting)
    existing = None
    for a in workflow.get("articles", []):
        if a.get("candidate_id") == cand_id or a.get("id") == cand_id:
            existing = a
            break

    if existing:
        # Update existing entry with processed data
        existing["id"] = article_id
        existing["filename"] = filename
        existing["title"] = rewritten.get("title", "")
        existing["summary"] = rewritten.get("summary", "")
        existing["category"] = rewritten.get("category", "")
        existing["image"] = image_data.get("url", "") if image_data else ""
        existing["stage"] = "editorial"
        existing["status"] = "ready_for_edit"
        existing["channels"] = {
            "website": {"enabled": True, "status": "pending", "scheduled_at": None},
            "telegram": {"enabled": True, "status": "pending", "scheduled_at": None, "custom_text": rewritten.get("telegram_hook", "")},
            "threads": {"enabled": True, "status": "pending", "scheduled_at": None, "custom_text": rewritten.get("threads_hook", "")},
        }
        existing["updated_at"] = now_iso
        print(f"   Updated existing workflow entry for candidate {cand_id}")
    else:
        # Create new entry
        entry = {
            "id": article_id,
            "filename": filename,
            "title": rewritten.get("title", ""),
            "summary": rewritten.get("summary", ""),
            "category": rewritten.get("category", ""),
            "image": image_data.get("url", "") if image_data else "",
            "candidate_id": cand_id,
            "original_title": candidate.get("title", ""),
            "original_url": candidate.get("link", ""),
            "stage": "editorial",
            "status": "ready_for_edit",
            "channels": {
                "website": {"enabled": True, "status": "pending", "scheduled_at": None},
                "telegram": {"enabled": True, "status": "pending", "scheduled_at": None, "custom_text": rewritten.get("telegram_hook", "")},
                "threads": {"enabled": True, "status": "pending", "scheduled_at": None, "custom_text": rewritten.get("threads_hook", "")},
            },
            "created_at": now_iso,
            "updated_at": now_iso,
            "published_at": None,
        }
        workflow["articles"].append(entry)

    save_json(WORKFLOW_FILE, workflow)


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
