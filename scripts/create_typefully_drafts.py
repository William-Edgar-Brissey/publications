#!/usr/bin/env python3
"""Create private Typefully drafts from a generated distribution bundle.

This script never publishes or schedules content. TYPEFULLY_API_KEY and
TYPEFULLY_SOCIAL_SET_ID must be supplied as secrets.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


API_BASE = os.environ.get("TYPEFULLY_API_BASE", "https://api.typefully.com/v2").rstrip("/")


def request_json(method: str, endpoint: str, api_key: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{API_BASE}{endpoint}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Typefully returned HTTP {exc.code}: {detail}") from exc


def upload_media(path: Path, social_set_id: str, api_key: str) -> str:
    ticket = request_json(
        "POST",
        f"/social-sets/{social_set_id}/media/upload",
        api_key,
        {"file_name": path.name},
    )
    upload_url = ticket.get("upload_url")
    media_id = ticket.get("media_id")
    if not upload_url or not media_id:
        raise RuntimeError(f"Incomplete Typefully upload ticket for {path.name}")

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    upload = urllib.request.Request(
        upload_url,
        data=path.read_bytes(),
        method="PUT",
        headers={"Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(upload, timeout=90):
            pass
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Media PUT failed HTTP {exc.code} for {path.name}: {detail}") from exc

    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        state = request_json(
            "GET", f"/social-sets/{social_set_id}/media/{media_id}", api_key
        )
        if state.get("status") == "ready":
            return str(media_id)
        if state.get("status") in {"error", "failed"}:
            raise RuntimeError(f"Typefully failed to process {path.name}: {state}")
        time.sleep(2)
    raise RuntimeError(f"Timed out while Typefully processed {path.name}")


def create_draft(social_set_id: str, api_key: str, payload: dict) -> dict:
    return request_json(
        "POST", f"/social-sets/{social_set_id}/drafts", api_key, payload
    )


def try_upload(path: Path, social_set_id: str, api_key: str) -> str | None:
    try:
        return upload_media(path, social_set_id, api_key)
    except Exception as exc:
        print(f"Skipping media {path.name}: {exc}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Create private Typefully drafts. Without this flag, validate and print payloads only.",
    )
    args = parser.parse_args()

    manifest = json.loads((args.bundle / "manifest.json").read_text(encoding="utf-8"))
    x_markdown = (args.bundle / manifest["editions"]["x_article"]).read_text(encoding="utf-8")
    linkedin_text = (args.bundle / manifest["editions"]["linkedin_caption"]).read_text(
        encoding="utf-8"
    )
    site = manifest.get("canonical_url") or "https://william-edgar-brissey.github.io/publications/articles/book-one-coupling-register.html"
    substack_text = (
        f"{manifest['title']}\n\n"
        "Water, Air, Earth, and Fire scored as separate joints. "
        "CL-002 stays pilot. CL-016 stays parked.\n\n"
        f"{site}\n"
    )

    x_payload = {
        "platforms": {"x_article": {"content_markdown": x_markdown}},
        "draft_title": f"{manifest['title']} — X Article",
        "scratchpad_text": (
            "Private review draft generated from GitHub revision "
            f"{manifest['git_revision']}. Do not publish until channel QA is complete."
        ),
    }
    linkedin_payload = {
        "platforms": {
            "linkedin": {"enabled": True, "posts": [{"text": linkedin_text}]}
        },
        "draft_title": f"{manifest['title']} — LinkedIn edition",
        "scratchpad_text": (
            "Private review draft generated from GitHub revision "
            f"{manifest['git_revision']}. Confirm preview before publishing."
        ),
    }
    substack_payload = {
        "platforms": {
            "substack": {"enabled": True, "posts": [{"text": substack_text}]}
        },
        "draft_title": f"{manifest['title']} — Substack Note",
        "scratchpad_text": "Substack Notes beta. Not a newsletter issue.",
    }

    if not args.submit:
        print(json.dumps({"x_article": x_payload, "linkedin": linkedin_payload, "substack": substack_payload}, indent=2))
        return

    api_key = (os.environ.get("TYPEFULLY_API_KEY") or "").strip()
    social_set_id = (os.environ.get("TYPEFULLY_SOCIAL_SET_ID") or "").strip()
    if not api_key or not social_set_id:
        raise RuntimeError("TYPEFULLY_API_KEY and TYPEFULLY_SOCIAL_SET_ID are required")

    cover_name = manifest["editions"].get("cover")
    if cover_name and (args.bundle / cover_name).exists():
        cover_id = try_upload(args.bundle / cover_name, social_set_id, api_key)
        if cover_id:
            x_payload["platforms"]["x_article"]["cover_media_id"] = cover_id

    pdf_name = manifest["editions"].get("linkedin_document")
    if pdf_name and (args.bundle / pdf_name).exists():
        pdf_id = try_upload(args.bundle / pdf_name, social_set_id, api_key)
        if pdf_id:
            linkedin_payload["platforms"]["linkedin"]["posts"][0]["media_ids"] = [pdf_id]
        else:
            linkedin_payload["scratchpad_text"] += " PDF upload skipped; text-only LinkedIn draft."

    results = {
        "x_article": create_draft(social_set_id, api_key, x_payload),
        "linkedin": create_draft(social_set_id, api_key, linkedin_payload),
    }
    try:
        results["substack"] = create_draft(social_set_id, api_key, substack_payload)
    except Exception as exc:
        results["substack"] = {"error": str(exc)}
    (args.bundle / "typefully-draft-results.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
