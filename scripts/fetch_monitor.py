#!/usr/bin/env python3
"""Pull public Earth-system feeds into a Coupling Monitor snapshot.

This script does not promote claims. Failed fetches become STALE tiles.
RAPID AMOC is never invented from these feeds.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT = Path("assets/monitor/snapshot.json")
UA = {"User-Agent": "RealignmentCouplingMonitor/1.0 (+https://william-edgar-brissey.github.io/publications/)"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def get_json(url: str):
    return json.loads(get(url).decode("utf-8"))


def nino34() -> dict:
    url = (
        "https://coastwatch.pfeg.noaa.gov/erddap/tabledap/ncepNinoSSTwk.json"
        "?time,Nino34_sst,Nino34_ssta&orderByMax(%22time%22)"
    )
    raw = get_json(url)
    rows = raw.get("table", {}).get("rows") or []
    if not rows:
        raise RuntimeError("ERDDAP returned no Nino 3.4 rows")
    time_s, sst, ssta = rows[0]
    return {
        "ok": True,
        "source": "NOAA / CoastWatch ERDDAP ncepNinoSSTwk (OISST.v2 weekly)",
        "source_url": "https://coastwatch.pfeg.noaa.gov/erddap/tabledap/ncepNinoSSTwk.html",
        "time": time_s,
        "sst_c": sst,
        "anomaly_c": ssta,
        "note": "Weekly Nino 3.4. Not extra-polar SST and not AMOC.",
    }


def quakes(days: int = 30, minmag: float = 6.0) -> dict:
    start = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    url = (
        "https://earthquake.usgs.gov/fdsnws/event/1/query"
        f"?format=geojson&starttime={start}&minmagnitude={minmag}&orderby=magnitude"
    )
    raw = get_json(url)
    events = []
    for feat in raw.get("features") or []:
        p = feat.get("properties") or {}
        g = (feat.get("geometry") or {}).get("coordinates") or [None, None, None]
        events.append(
            {
                "id": feat.get("id"),
                "mag": p.get("mag"),
                "place": p.get("place"),
                "time_ms": p.get("time"),
                "url": p.get("url"),
                "lon": g[0],
                "lat": g[1],
                "depth_km": g[2],
            }
        )
    return {
        "ok": True,
        "source": "USGS FDSN event service",
        "source_url": url,
        "window_days": days,
        "min_magnitude": minmag,
        "count": len(events),
        "events": events[:25],
    }


def eonet(category: str, limit: int = 20) -> dict:
    url = f"https://eonet.gsfc.nasa.gov/api/v3/events?category={category}&status=open&limit={limit}"
    raw = get_json(url)
    events = []
    for ev in raw.get("events") or []:
        cats = ev.get("categories") or []
        events.append(
            {
                "id": ev.get("id"),
                "title": ev.get("title"),
                "category": cats[0]["id"] if cats else category,
                "link": (ev.get("sources") or [{}])[0].get("url") or ev.get("link"),
            }
        )
    return {
        "ok": True,
        "source": "NASA EONET v3 open events",
        "source_url": url,
        "category": category,
        "count": len(events),
        "events": events,
    }


def locked_tiles() -> dict:
    return {
        "amoc_rapid": {
            "status": "STALE",
            "claim": "CL-001 / CL-002 predictor",
            "value": "No 2026 RAPID Sv number",
            "vintage": "Published through February 2024",
            "note": "Do not infer AMOC from Nino 3.4 or extra-polar SST.",
            "source_url": "https://rapid.ac.uk/",
        },
        "cl002": {
            "status": "PILOT",
            "claim": "CL-002 AMOC to tropical Atlantic / ITCZ",
            "note": "Surface boxes updated through June 2026. Mechanism not promoted.",
        },
        "cl003": {
            "status": "DEVELOPING",
            "claim": "CL-003 infrastructural scissors",
            "note": "No clock compression. Labor-hour series still absent.",
        },
        "cl016": {
            "status": "PARKED",
            "claim": "CL-016 synchronized Ring of Fire / volcanic winter",
            "note": "Appendix K long tail. Open EONET volcanoes are not this claim.",
        },
        "biology": {
            "status": "PARKED",
            "claim": "Blended whale / krill / phytoplankton collapse",
            "note": "No honest global pulse in v1 feeds.",
        },
        "register_lock": {
            "extra_polar_sst_c": 21.1,
            "extra_polar_sst_date": "2026-08-22",
            "extra_polar_sst_source": "Copernicus C3S/ERA5 as cited in RA-CR-2026-08-29",
            "note": "Manual lock from the Coupling Register. Not refreshed by this job.",
        },
    }


def main() -> None:
    fetched_at = now_iso()
    errors = []
    payload = {
        "schema": "coupling-monitor-v1",
        "fetched_at": fetched_at,
        "disclaimer": "Operational monitor of public feeds. Not a collapse forecast, not a promotion of CL-002, not a 2026 AMOC value.",
        "canonical_register": "https://william-edgar-brissey.github.io/publications/articles/book-one-coupling-register.html",
        "locked": locked_tiles(),
    }
    try:
        payload["nino34"] = nino34()
    except Exception as exc:
        errors.append(f"nino34: {exc}")
        payload["nino34"] = {"ok": False, "error": str(exc)}
    try:
        payload["quakes_m6"] = quakes(30, 6.0)
    except Exception as exc:
        errors.append(f"quakes: {exc}")
        payload["quakes_m6"] = {"ok": False, "error": str(exc)}
    try:
        payload["volcanoes_open"] = eonet("volcanoes", 20)
    except Exception as exc:
        errors.append(f"volcanoes: {exc}")
        payload["volcanoes_open"] = {"ok": False, "error": str(exc)}
    try:
        payload["wildfires_open"] = eonet("wildfires", 20)
    except Exception as exc:
        errors.append(f"wildfires: {exc}")
        payload["wildfires_open"] = {"ok": False, "error": str(exc)}
    payload["errors"] = errors
    payload["health"] = "degraded" if errors else "ok"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(OUT), "health": payload["health"], "errors": errors}, indent=2))


if __name__ == "__main__":
    main()
