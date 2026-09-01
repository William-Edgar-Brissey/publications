#!/usr/bin/env python3
"""GitHub-native publication release orchestrator.

Safety model:
- queue entry must be state=scheduled and approved=true
- release_at must be due
- target PR must be open and non-draft
- target PR must carry the human-applied release-approved label
- dry-run is supported locally and by workflow_dispatch
- scheduled execution never edits publication content itself; it only merges the pre-reviewed PR

The existing main-branch workflows then publish GitHub Pages and build the
channel distribution bundle.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path
from typing import Any


UTC = dt.timezone.utc


def parse_time(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"release_at must include a timezone offset: {value}")
    return parsed.astimezone(UTC)


def now_utc(override: str | None = None) -> dt.datetime:
    return parse_time(override) if override else dt.datetime.now(UTC)


def load_queue(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "0.1":
        raise ValueError("Unsupported release queue schema_version")
    if not isinstance(data.get("releases"), list):
        raise ValueError("release queue must contain a releases list")
    return data


def validate_release(item: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("id", "title", "source", "pr_number", "state", "approved", "channels"):
        if key not in item:
            errors.append(f"missing {key}")
    if item.get("state") not in {"planned", "scheduled", "released", "cancelled"}:
        errors.append("state must be planned, scheduled, released, or cancelled")
    if item.get("state") == "scheduled":
        if item.get("approved") is not True:
            errors.append("scheduled release must have approved=true")
        if not item.get("release_at"):
            errors.append("scheduled release must have release_at")
        else:
            try:
                parse_time(str(item["release_at"]))
            except Exception as exc:
                errors.append(str(exc))
    if not isinstance(item.get("pr_number"), int) or int(item.get("pr_number", 0)) < 1:
        errors.append("pr_number must be a positive integer")
    return errors


def due_releases(queue: dict[str, Any], at: dt.datetime) -> list[dict[str, Any]]:
    due: list[dict[str, Any]] = []
    for item in queue["releases"]:
        errors = validate_release(item)
        if errors:
            raise ValueError(f"release {item.get('id', '<unknown>')}: " + "; ".join(errors))
        if item["state"] != "scheduled" or item["approved"] is not True:
            continue
        if parse_time(item["release_at"]) <= at:
            due.append(item)
    return due


def run_gh(args: list[str]) -> str:
    proc = subprocess.run(
        ["gh", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def pr_snapshot(pr_number: int) -> dict[str, Any]:
    raw = run_gh([
        "pr", "view", str(pr_number),
        "--json", "state,isDraft,labels,mergedAt,mergeable,url,headRefName,baseRefName",
    ])
    return json.loads(raw)


def label_names(snapshot: dict[str, Any]) -> set[str]:
    return {str(label.get("name")) for label in snapshot.get("labels", []) if label.get("name")}


def execute_release(
    item: dict[str, Any], required_label: str, dry_run: bool
) -> dict[str, Any]:
    pr_number = int(item["pr_number"])
    snap = pr_snapshot(pr_number)
    result: dict[str, Any] = {
        "id": item["id"],
        "pr_number": pr_number,
        "source": item["source"],
        "pr_url": snap.get("url"),
        "dry_run": dry_run,
    }

    if snap.get("mergedAt"):
        result["status"] = "already_merged"
        return result
    if snap.get("state") != "OPEN":
        result.update(status="blocked", reason=f"PR state is {snap.get('state')}")
        return result
    if snap.get("isDraft"):
        result.update(status="blocked", reason="PR is still draft")
        return result
    if required_label not in label_names(snap):
        result.update(status="blocked", reason=f"missing required label {required_label}")
        return result
    if snap.get("baseRefName") != "main":
        result.update(status="blocked", reason=f"PR base is {snap.get('baseRefName')}, expected main")
        return result
    if snap.get("mergeable") == "CONFLICTING":
        result.update(status="blocked", reason="PR has merge conflicts")
        return result

    if dry_run:
        result["status"] = "ready"
        return result

    run_gh(["pr", "merge", str(pr_number), "--merge"])
    result["status"] = "merged"

    if item.get("channels", {}).get("distribution_bundle", True):
        run_gh([
            "workflow", "run", "distribution.yml",
            "--ref", "main",
            "-f", f"source={item['source']}",
            "-f", "create_typefully_drafts=false",
        ])
        result["distribution_workflow"] = "requested"

    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("queue", type=Path, nargs="?", default=Path("release/release-queue.json"))
    parser.add_argument("--now", help="ISO-8601 time override for deterministic testing")
    parser.add_argument("--execute", action="store_true", help="Merge eligible release PRs")
    parser.add_argument("--result-file", type=Path, default=Path("release-orchestrator-result.json"))
    args = parser.parse_args()

    queue = load_queue(args.queue)
    at = now_utc(args.now)
    due = due_releases(queue, at)
    policy = queue.get("policy", {})
    required_label = str(policy.get("required_pr_label", "release-approved"))

    summary: dict[str, Any] = {
        "evaluated_at": at.isoformat(),
        "due_count": len(due),
        "dry_run": not args.execute,
        "due": [item["id"] for item in due],
        "results": [],
    }

    if args.execute:
        if not os.environ.get("GH_TOKEN"):
            raise RuntimeError("GH_TOKEN is required for --execute")
        for item in due:
            summary["results"].append(execute_release(item, required_label, dry_run=False))
    else:
        for item in due:
            summary["results"].append(execute_release(item, required_label, dry_run=True))

    args.result_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
