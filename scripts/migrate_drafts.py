#!/usr/bin/env python3
"""One-time migration: drafts.json → workflow.json.

Reads existing drafts.json entries and adds them to workflow.json
with proper stage/status/channel fields. Safe to run multiple times
(skips entries already present by filename).

Usage:
    python scripts/migrate_drafts.py
"""

import json
import os
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFTS_FILE = os.path.join(PROJECT_ROOT, "data", "drafts.json")
WORKFLOW_FILE = os.path.join(PROJECT_ROOT, "data", "workflow.json")


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default or {}


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def migrate():
    drafts = load_json(DRAFTS_FILE, {"articles": []})
    workflow = load_json(WORKFLOW_FILE, {"articles": []})

    existing_filenames = {a["filename"] for a in workflow["articles"] if a.get("filename")}

    migrated = 0
    skipped = 0

    for d in drafts.get("articles", []):
        if not d.get("filename"):
            continue
        if d["filename"] in existing_filenames:
            skipped += 1
            continue

        now_iso = datetime.now(timezone.utc).isoformat()
        entry = {
            "id": d.get("id", ""),
            "filename": d["filename"],
            "title": d.get("title", ""),
            "summary": d.get("summary", ""),
            "category": d.get("category", ""),
            "image": d.get("image", ""),
            "candidate_id": "",
            "original_title": "",
            "original_url": "",
            "stage": "editorial",
            "status": "ready_for_edit",
            "channels": {
                "website": {"enabled": True, "status": "pending", "scheduled_at": None},
                "telegram": {"enabled": True, "status": "pending", "scheduled_at": None, "custom_text": ""},
                "threads": {"enabled": True, "status": "pending", "scheduled_at": None, "custom_text": ""},
            },
            "created_at": d.get("created_at", now_iso),
            "updated_at": now_iso,
            "published_at": None,
        }
        workflow["articles"].append(entry)
        migrated += 1

    if migrated > 0:
        save_json(WORKFLOW_FILE, workflow)

    print(f"Migration complete: {migrated} migrated, {skipped} skipped (already in workflow.json)")
    print(f"Total workflow articles: {len(workflow['articles'])}")


if __name__ == "__main__":
    migrate()
