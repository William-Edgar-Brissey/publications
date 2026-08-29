#!/usr/bin/env python3
"""Create and schedule weekly Coupling Monitor posts on Typefully.

Reads assets/monitor/snapshot.json. Schedules X and LinkedIn for the next
Monday 09:00 America/New_York unless --now is passed.
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


def copy_from_snapshot(snap: dict) -> tuple[str, str]:
    nino = snap.get("nino34") or {}
    if nino.get("ok"):
        nino_line = f"Niño 3.4 {nino.get('time')}: {nino.get('anomaly_c'):+} °C (CPC monthly)"
    else:
        nino_line = f"Niño 3.4 stale ({nino.get('error', 'no fetch')})"
    lock = (snap.get("locked") or {}).get("register_lock") or {}
    sst_line = f"Extra-polar SST locked {lock.get('extra_polar_sst_c')} °C on {lock.get('extra_polar_sst_date')}"
    q = snap.get("quakes_m6") or {}
    q_line = f"USGS M≥6 last 30d: {q.get('count', '?')}" if q.get("ok") else "USGS M≥6 stale"
    x = (
        "Coupling Monitor weekly board\n\n"
        f"{nino_line}\n"
        f"{sst_line}\n"
        f"{q_line}\n"
        "RAPID AMOC remains stale. CL-002 stays pilot. CL-016 stays parked.\n\n"
        f"{MONITOR_URL}\n"
    )
    li = (
        "Coupling Monitor — weekly board\n\n"
        "Water / Air / Earth / Fire tiles from public feeds, graded separately.\n\n"
        f"{nino_line}\n"
        f"{sst_line}\n"
        f"{q_line}\n\n"
        "RAPID AMOC has no 2026 Sv number. CL-002 remains pilot. "
        "CL-016 (volcanic winter) remains parked.\n\n"
        f"Board: {MONITOR_URL}\n"
        "Register: https://william-edgar-brissey.github.io/publications/articles/book-one-coupling-register.html\n"
    )
    return x, li


def schedule_draft(social_set_id: str, draft_id: str, api_key: str, when_iso: str) -> dict:
    errors = []
    for endpoint, body in (
        (f"/social-sets/{social_set_id}/drafts/{draft_id}/schedule", {"scheduled_date": when_iso}),
        (f"/social-sets/{social_set_id}/drafts/{draft_id}/schedule", {"time": when_iso}),
        (f"/social-sets/{social_set_id}/drafts/{draft_id}", {"scheduled_date": when_iso}),
    ):
        try:
            return request_json("POST", endpoint, api_key, body)
        except Exception as exc:
            errors.append(str(exc))
            try:
                return request_json("PATCH", endpoint, api_key, body)
            except Exception as exc2:
                errors.append(str(exc2))
    raise RuntimeError("Schedule failed: " + " | ".join(errors[:4]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", action="store_true", help="Publish-attempt immediately instead of next Monday 09:00 ET")
    args = parser.parse_args()

    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    x_text, li_text = copy_from_snapshot(snap)
    when = datetime.now(timezone.utc) if args.now else next_monday_nine()
    when_iso = when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    api_key = (os.environ.get("TYPEFULLY_API_KEY") or "").strip()
    social_set_id = (os.environ.get("TYPEFULLY_SOCIAL_SET_ID") or "").strip()
    if not api_key or not social_set_id:
        raise RuntimeError("TYPEFULLY_API_KEY and TYPEFULLY_SOCIAL_SET_ID are required")

    created = {}
    created["x"] = request_json(
        "POST",
        f"/social-sets/{social_set_id}/drafts",
        api_key,
        {
            "platforms": {"x": {"enabled": True, "posts": [{"text": x_text}]}},
            "draft_title": f"Coupling Monitor weekly — X — {when.astimezone(ET).date()}",
        },
    )
    created["linkedin"] = request_json(
        "POST",
        f"/social-sets/{social_set_id}/drafts",
        api_key,
        {
            "platforms": {"linkedin": {"enabled": True, "posts": [{"text": li_text}]}},
            "draft_title": f"Coupling Monitor weekly — LinkedIn — {when.astimezone(ET).date()}",
        },
    )

    scheduled = {}
    for name, draft in created.items():
        draft_id = str(draft.get("id") or draft.get("draft_id"))
        try:
            scheduled[name] = schedule_draft(social_set_id, draft_id, api_key, when_iso)
        except Exception as exc:
            scheduled[name] = {"error": str(exc), "draft_id": draft_id, "private_url": draft.get("private_url")}

    out = {
        "when_et": when.astimezone(ET).isoformat(),
        "when_utc": when_iso,
        "created": {k: {"id": v.get("id"), "private_url": v.get("private_url"), "status": v.get("status")} for k, v in created.items()},
        "scheduled": scheduled,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
