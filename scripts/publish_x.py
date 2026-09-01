#!/usr/bin/env python3
"""Validate or publish a short X announcement for a distribution bundle.

Default behavior is dry-run only. --submit requires X_USER_ACCESS_TOKEN and uses
the X API v2 POST /2/tweets endpoint with user-context OAuth.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


API_URL = "https://api.x.com/2/tweets"


def build_text(manifest: dict) -> str:
    title = str(manifest.get("title") or "New publication").strip()
    url = str(manifest.get("canonical_url") or "").strip()
    text = f"{title}\n\n{url}" if url else title
    if len(text) <= 280:
        return text
    reserve = len(url) + 5 if url else 2
    clipped = title[: max(1, 280 - reserve - 1)].rstrip() + "…"
    return f"{clipped}\n\n{url}" if url else clipped[:280]


def post(text: str, token: str) -> dict:
    payload = json.dumps({"text": text}).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1500]
        raise RuntimeError(f"X API HTTP {exc.code}: {detail}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()

    manifest = json.loads((args.bundle / "manifest.json").read_text(encoding="utf-8"))
    text = build_text(manifest)
    result = {"submit": args.submit, "text": text, "length": len(text), "canonical_url": manifest.get("canonical_url")}

    if args.submit:
        token = (os.environ.get("X_USER_ACCESS_TOKEN") or "").strip()
        if not token:
            raise RuntimeError("X_USER_ACCESS_TOKEN is required for --submit")
        result["response"] = post(text, token)

    output = args.bundle / "x-direct-result.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
