#!/usr/bin/env python3
"""Create weekly Coupling Monitor posts on Typefully (X, LinkedIn, Substack Notes).

Reads assets/monitor/snapshot.json. Typefully schedule API is 404; drafts stay
private until scheduled in the UI for Monday 09:00 America/New_York.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API_BASE = os.environ.get("TYPEFULLY_API_BASE", "https://api.typefully.com/v2").rstrip("/")
SNAPSHOT = Path("assets/monitor/snapshot.json")
MONITOR_URL = "https://william-edgar-brissey.github.io/publications/monitor.html"
REGISTER_URL = "https://william-edgar-brissey.github.io/publications/articles/book-one-coupling-register.html"
ET = ZoneInfo("America/New_York")


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


def next_monday_nine(now: datetime | None = None) -> datetime:
    now = now or datetime.now(ET)
    days = (7 - now.weekday()) % 7
    target = (now + timedelta(days=days)).replace(hour=9, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=7)
    return target


def copy_from_snapshot(snap: dict) -> dict[str, str]:
    nino = snap.get("nino34") or {}
    if nino.get("ok"):
        nino_line = f"Niño 3.4 {nino.get('time')}: {nino.get('anomaly_c'):+} °C (CPC monthly)"
    else:
        nino_line = f"Niño 3.4 stale ({nino.get('error', 'no fetch')})"
    lock = (snap.get("locked") or {}).get("register_lock") or {}
    sst_line = f"Extra-polar SST locked {lock.get('extra_polar_sst_c')} °C on {lock.get('extra_polar_sst_date')}"
    q = snap.get("quakes_m6") or {}
    q_line = f"USGS M≥6 last 30d: {q.get('count', '?')}" if q.get("ok") else "USGS M≥6 stale"
    gates = "RAPID AMOC remains stale. CL-002 stays pilot. CL-016 stays parked."
    return {
        "x": (
            "Coupling Monitor weekly board\n\n"
            f"{nino_line}\n{sst_line}\n{q_line}\n{gates}\n\n{MONITOR_URL}\n"
        ),
        "linkedin": (
            "Coupling Monitor — weekly board\n\n"
            "Water / Air / Earth / Fire tiles from public feeds, graded separately.\n\n"
            f"{nino_line}\n{sst_line}\n{q_line}\n\n{gates}\n\n"
            f"Board: {MONITOR_URL}\nRegister: {REGISTER_URL}\n"
        ),
        "substack": (
            "Weekly Coupling Monitor\n\n"
            f"{nino_line}\n{sst_line}\n{q_line}\n\n{gates}\n\n{MONITOR_URL}\n"
        ),
    }


def create_platform_draft(social_set_id: str, api_key: str, platform: str, text: str, title: str) -> dict:
    return request_json(
        "POST",
        f"/social-sets/{social_set_id}/drafts",
        api_key,
        {
            "platforms": {platform: {"enabled": True, "posts": [{"text": text}]}},
            "draft_title": title,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", action="store_true")
    args = parser.parse_args()

    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    texts = copy_from_snapshot(snap)
    when = datetime.now(timezone.utc) if args.now else next_monday_nine()
    day = when.astimezone(ET).date()

    api_key = (os.environ.get("TYPEFULLY_API_KEY") or "").strip()
    social_set_id = (os.environ.get("TYPEFULLY_SOCIAL_SET_ID") or "").strip()
    if not api_key or not social_set_id:
        raise RuntimeError("TYPEFULLY_API_KEY and TYPEFULLY_SOCIAL_SET_ID are required")

    created = {}
    errors = {}
    titles = {
        "x": f"Coupling Monitor weekly — X — {day}",
        "linkedin": f"Coupling Monitor weekly — LinkedIn — {day}",
        "substack": f"Coupling Monitor weekly — Substack Note — {day}",
    }
    for platform, text in texts.items():
        try:
            created[platform] = create_platform_draft(
                social_set_id, api_key, platform, text, titles[platform]
            )
        except Exception as exc:
            errors[platform] = str(exc)

    out = {
        "when_et": when.astimezone(ET).isoformat(),
        "created": {
            k: {"id": v.get("id"), "private_url": v.get("private_url"), "status": v.get("status")}
            for k, v in created.items()
        },
        "errors": errors,
        "note": "Typefully schedule API is 404. Open Drafts and Schedule for Monday 09:00 ET.",
    }
    print(json.dumps(out, indent=2))
    if errors and not created:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
