#!/usr/bin/env python3
"""Create private Typefully drafts for the human weekly field brief.

Never publishes. Schedule in the Typefully UI after preview.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

API_BASE = os.environ.get("TYPEFULLY_API_BASE", "https://api.typefully.com/v2").rstrip("/")
BRIEF_URL = "https://william-edgar-brissey.github.io/publications/articles/weekly-brief-2026-w35.html"
COVER_URL = "https://william-edgar-brissey.github.io/publications/coverage.html"
ET = ZoneInfo("America/New_York")

X_TEXT = (
    "This week, in ordinary language\n\n"
    "The Pacific seasonal index is warm (+1.39). That is not your town forecast.\n\n"
    "Satellites counted about 5,000 fire hotspots in a day. One large region came back zero — that is a blind spot, not a safe zone.\n\n"
    "The rain history file is still on July. Missing August is not drought.\n\n"
    "Read your own weather service first. This page does not order anyone to move.\n\n"
    f"{BRIEF_URL}\n"
)

LI_TEXT = (
    "This week, in ordinary language (24–30 August 2026)\n\n"
    "What the instruments show — not a siren.\n\n"
    "• Pacific ONI (May–July): +1.39. One ocean product, not a local forecast.\n"
    "• Fire hotspots in one daily pass: about 5,000. One map box was empty while another was full — treat empty as blind, not safe.\n"
    "• Rain climatology file: still July. August from that source is late, not ‘no rain.’\n"
    "• The Atlantic current people argue about is not updated on this board.\n\n"
    "If officials tell you to evacuate or boil water, do that. If they have not, do not invent an evacuation from a dashboard.\n\n"
    f"Brief: {BRIEF_URL}\n"
    f"Gauges: {COVER_URL}\n"
)

NOTE_TEXT = (
    "Weekly field brief\n\n"
    "Warm Pacific index. Thousands of fire dots. One blind region. Rain file late.\n"
    "Not a reason to leave your country. Read your met service.\n\n"
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

    out = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "created": {
            k: {"id": v.get("id"), "private_url": v.get("private_url"), "status": v.get("status")}
            for k, v in created.items()
        },
        "errors": errors,
        "note": "Drafts only. Open Typefully, preview, then you publish.",
    }
    print(json.dumps(out, indent=2))
    if errors and not created:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
