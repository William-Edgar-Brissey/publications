#!/usr/bin/env python3
"""Private Typefully drafts for the global weekly brief. Never publishes."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

API_BASE = os.environ.get("TYPEFULLY_API_BASE", "https://api.typefully.com/v2").rstrip("/")
BRIEF_URL = "https://william-edgar-brissey.github.io/publications/articles/weekly-brief-2026-w35.html"
ET = ZoneInfo("America/New_York")

X_TEXT = (
    "This week on the planet — one brief, same for every reader.\n\n"
    "Pacific seasonal index: +1.39. Not your town forecast.\n"
    "Fire satellites: thousands of hotspots, and one large box went blind.\n"
    "Rain memory file: still July. Late is not drought.\n\n"
    "Your national warning service first. This page does not order anyone to move.\n\n"
    f"{BRIEF_URL}\n"
)

LI_TEXT = (
    "This week on the planet (24–30 August 2026)\n\n"
    "One brief for every reader. Not a local forecast.\n\n"
    "• Central Pacific seasonal index (ONI): +1.39. One ocean product. History does not give every coast the same next season.\n"
    "• Daily fire pass: on the order of 5,000 hotspots. One large query box returned zero — that is missing coverage, not a safe zone.\n"
    "• The rain climatology file we keep had not published August yet. A late file is not a failed wet season.\n\n"
    "If your official service says leave or boil water, do that. This board will not try to name eight billion streets.\n\n"
    f"{BRIEF_URL}\n"
)

NOTE_TEXT = (
    "Global week: warm Pacific index, fire map with a hole, rain file late. "
    "Not a reason to relocate. Your warning office first.\n\n"
    f"{BRIEF_URL}\n"
)


def request_json(method: str, endpoint: str, api_key: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"{API_BASE}{endpoint}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Typefully HTTP {exc.code}: {detail}") from exc


def create_platform_draft(social_set_id: str, api_key: str, platform: str, text: str, title: str) -> dict:
    return request_json(
        "POST",
        f"/social-sets/{social_set_id}/drafts",
        api_key,
        {"platforms": {platform: {"enabled": True, "posts": [{"text": text}]}}, "draft_title": title},
    )


def main() -> None:
    day = datetime.now(ET).date()
    api_key = (os.environ.get("TYPEFULLY_API_KEY") or "").strip()
    social_set_id = (os.environ.get("TYPEFULLY_SOCIAL_SET_ID") or "").strip()
    if not api_key or not social_set_id:
        raise RuntimeError("TYPEFULLY_API_KEY and TYPEFULLY_SOCIAL_SET_ID are required")
    created, errors = {}, {}
    jobs = {
        "x": ("x", X_TEXT, f"Weekly field brief — X — {day}"),
        "linkedin": ("linkedin", LI_TEXT, f"Weekly field brief — LinkedIn — {day}"),
        "substack": ("substack", NOTE_TEXT, f"Weekly field brief — Substack Note — {day}"),
    }
    for key, (platform, text, title) in jobs.items():
        try:
            created[key] = create_platform_draft(social_set_id, api_key, platform, text, title)
        except Exception as exc:
            errors[key] = str(exc)
    print(json.dumps({"created": {k: v.get("private_url") for k, v in created.items()}, "errors": errors}, indent=2))
    if errors and not created:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
