#!/usr/bin/env python3
"""Private Typefully drafts for the human weekly field brief. Never publishes."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

API_BASE = os.environ.get("TYPEFULLY_API_BASE", "https://api.typefully.com/v2").rstrip("/")
BRIEF_URL = "https://william-edgar-brissey.github.io/publications/articles/weekly-brief-2026-w35.html"
PAGASA = "https://bagong.pagasa.dost.gov.ph/"
ET = ZoneInfo("America/New_York")

X_TEXT = (
    "If you are in Luzon this weekend: open PAGASA, not a dashboard.\n\n"
    "Pilandok is a tropical depression. Western Luzon already has monsoon flood warnings. "
    "If they say move, move.\n\n"
    "A warm Pacific number (+1.39) is not why the streets are wet today.\n\n"
    f"PAGASA: {PAGASA}\n"
    f"Brief: {BRIEF_URL}\n"
)

LI_TEXT = (
    "This week: rain where people live, not a dashboard\n\n"
    "Philippines, 30 August 2026: PAGASA has named Tropical Depression Pilandok and kept southwest-monsoon flood warnings on parts of western Luzon. That is the product that can save a life this weekend.\n\n"
    "Our board keeps a 30-year memory and a fire count. It does not replace a national warning office. A warm Pacific index (+1.39 for May–July) is not the cause of today’s street flooding.\n\n"
    "If officials tell you to leave, leave. If they have not, do not invent an evacuation from a chart.\n\n"
    f"PAGASA: {PAGASA}\n"
    f"Brief: {BRIEF_URL}\n"
)

NOTE_TEXT = (
    "Luzon this weekend: PAGASA first. Pilandok + monsoon rain. "
    "A Pacific index is not your flood map.\n\n"
    f"{PAGASA}\n{BRIEF_URL}\n"
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
