#!/usr/bin/env python3
"""Build platform-native publication assets from one Quarto source file.

The script uses only the Python standard library. It deliberately creates
reviewable files and never calls a publishing service.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


SITE_URL = "https://william-edgar-brissey.github.io/publications/"


def parse_source(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path} has no YAML front matter")
    try:
        _, raw_meta, body = text.split("---\n", 2)
    except ValueError as exc:
        raise ValueError(f"{path} has malformed YAML front matter") from exc

    metadata: dict[str, str] = {}
    for line in raw_meta.splitlines():
        match = re.match(r"^([a-zA-Z0-9_-]+):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip().strip('"').strip("'")
        if value:
            metadata[key] = value
    return metadata, body.strip()


def cell_values(line: str) -> list[str]:
    return [part.strip() for part in line.strip().strip("|").split("|")]


def is_separator(line: str) -> bool:
    cells = cell_values(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def expand_tables(markdown: str, heading_level: int) -> str:
    """Convert GFM tables into readable native blocks.

    X Articles do not document table support, and Substack has no native table
    node. Converting each row to a labeled block preserves meaning and avoids a
    broken pipe-delimited paragraph.
    """

    lines = markdown.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        if (
            index + 1 < len(lines)
            and "|" in lines[index]
            and is_separator(lines[index + 1])
        ):
            headers = cell_values(lines[index])
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(cell_values(lines[index]))
                index += 1
            for row in rows:
                row += [""] * (len(headers) - len(row))
                label = row[0] or "Record"
                output.append(f"{'#' * heading_level} {label}")
                output.append("")
                for header, value in zip(headers[1:], row[1:]):
                    if value:
                        output.append(f"- **{header}:** {value}")
                output.append("")
            continue
        output.append(lines[index])
        index += 1
    return "\n".join(output)


def clean_quarto(markdown: str, canonical_url: str) -> str:
    markdown = re.sub(
        r"^:::\s*\{\.release-status\}\s*$\n(.*?)\n^:::\s*$",
        r"## Publication record\n\n\1",
        markdown,
        flags=re.MULTILINE | re.DOTALL,
    )
    markdown = re.sub(r"^:::\s*(?:\{[^}]*\})?\s*$", "", markdown, flags=re.MULTILINE)
    markdown = re.sub(
        r"\(([^)]+)\.qmd\)",
        lambda match: f"({SITE_URL}articles/{Path(match.group(1)).name}.html)",
        markdown,
    )
    markdown = markdown.replace("\u00a0", " ")
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip() + f"\n\nSource and revision record: {canonical_url}\n"


def x_article(markdown: str, title: str, subtitle: str, canonical_url: str) -> str:
    markdown = expand_tables(markdown, heading_level=3)
    markdown = clean_quarto(markdown, canonical_url)

    normalized: list[str] = []
    for line in markdown.splitlines():
        if re.match(r"^#{2}\s", line):
            line = "# " + line[3:]
        elif re.match(r"^#{3,}\s", line):
            line = "## " + re.sub(r"^#{3,}\s+", "", line)
        if re.fullmatch(r"-{3,}", line.strip()):
            continue
        normalized.append(line)

    intro = f"# {title}\n\n*{subtitle}*\n\n"
    return intro + "\n".join(normalized).strip() + "\n"


def substack_article(markdown: str, title: str, subtitle: str, canonical_url: str) -> str:
    markdown = expand_tables(markdown, heading_level=3)
    markdown = clean_quarto(markdown, canonical_url)
    return f"# {title}\n\n*{subtitle}*\n\n{markdown}\n"


def linkedin_caption(metadata: dict[str, str], canonical_url: str) -> str:
    title = metadata.get("title", "New publication")
    subtitle = metadata.get("subtitle", "")
    status = metadata.get("status", "Public release")
    revision = metadata.get("revision", "")
    description = metadata.get("description", "")
    return (
        f"{title}\n\n"
        f"{subtitle}\n\n"
        f"{description}\n\n"
        "The complete publication is attached as a native LinkedIn document. "
        "The canonical HTML edition, downloadable PDF, and revision history remain available here:\n"
        f"{canonical_url}\n\n"
        f"{status}" + (f" · Revision {revision}" if revision else "") + "\n\n"
        "#SystemsArchitecture #AIEngineering #ResilienceEngineering #Research"
    )


def git_revision() -> str:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def copy_if_present(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    shutil.copy2(source, target)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--site-dir", type=Path, default=Path("_site"))
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    args = parser.parse_args()

    metadata, body = parse_source(args.source)
    slug = args.source.stem
    title = metadata.get("title", slug.replace("-", " ").title())
    subtitle = metadata.get("subtitle", "")
    canonical_url = f"{SITE_URL}articles/{slug}.html"
    bundle = args.output_dir / slug
    bundle.mkdir(parents=True, exist_ok=True)

    x_text = x_article(body, title, subtitle, canonical_url)
    substack_text = substack_article(body, title, subtitle, canonical_url)
    linkedin_text = linkedin_caption(metadata, canonical_url)

    (bundle / "x-article.md").write_text(x_text, encoding="utf-8")
    (bundle / "substack-article.md").write_text(substack_text, encoding="utf-8")
    (bundle / "linkedin-caption.txt").write_text(linkedin_text + "\n", encoding="utf-8")

    rendered_pdf = args.site_dir / "articles" / f"{slug}.pdf"
    pdf_name = f"{slug}.pdf"
    copied_pdf = copy_if_present(rendered_pdf, bundle / pdf_name)

    raw_image = metadata.get("image", "")
    cover_source = (args.source.parent / raw_image).resolve() if raw_image else Path()
    if raw_image and not cover_source.exists():
        cover_source = (Path.cwd() / raw_image).resolve()
    cover_name = f"{slug}-cover{cover_source.suffix or '.png'}"
    copied_cover = bool(raw_image) and copy_if_present(cover_source, bundle / cover_name)

    manifest = {
        "title": title,
        "subtitle": subtitle,
        "slug": slug,
        "source": str(args.source),
        "canonical_url": canonical_url,
        "status": metadata.get("status", ""),
        "revision": metadata.get("revision", ""),
        "git_revision": git_revision(),
        "editions": {
            "x_article": "x-article.md",
            "linkedin_caption": "linkedin-caption.txt",
            "linkedin_document": pdf_name if copied_pdf else None,
            "substack_article": "substack-article.md",
            "cover": cover_name if copied_cover else None,
        },
        "release_policy": "Private drafts first; publication requires human confirmation.",
    }
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    qa = f"""# Channel QA — {title}

- [ ] Canonical HTML reviewed on desktop and mobile
- [ ] PDF title page, table of contents, tables, links, headers, and page breaks reviewed
- [ ] X Article cover and realistic preview reviewed
- [ ] X Article headings, lists, links, and converted table records reviewed
- [ ] LinkedIn document preview checked for readability and cropping
- [ ] LinkedIn caption checked for the canonical URL and release label
- [ ] Substack article headings, images, links, and converted table records reviewed
- [ ] Substack email preview reviewed on desktop and mobile
- [ ] Status, revision, canonical URL, and publication date agree across editions
- [ ] Final publish/send approved by William Edgar Brissey
"""
    (bundle / "channel-qa.md").write_text(qa, encoding="utf-8")

    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
