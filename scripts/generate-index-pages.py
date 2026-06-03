#!/usr/bin/env python3
"""Create {page}/index.html from {page}.html for clean URLs on static servers.

Standalone info pages (about, documents) use directory URLs only: /about/, /documents/.
After editing flat *.html in nested sections, re-run this script. Do not run
remove-unlinked-duplicates.py on this project — it deletes index.html and breaks
/section/page/ URLs.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ROOT_ASSETS = {
    "index.html",
    "privacy-policy.html",
}


def fix_relative_url(url: str, folder_name: str) -> str:
    if url.startswith(("http://", "https://", "//", "#", "mailto:", "tel:", "data:")):
        return url

    fragment = ""
    if "#" in url:
        url, fragment = url.split("#", 1)
        fragment = "#" + fragment

    up = 0
    rest = url
    while rest.startswith("../"):
        up += 1
        rest = rest[3:]

    # One directory deeper: page.html -> page/index.html
    depth_delta = 1

    if rest.startswith(f"{folder_name}/"):
        rest = rest[len(folder_name) + 1 :]
    elif rest.startswith("_next/") or rest in ROOT_ASSETS:
        up += depth_delta
    elif "/" not in rest and rest.endswith(".html"):
        # Sibling in parent directory (e.g. dismissal.html from main-documents.html)
        up += depth_delta

    prefix = "../" * up
    return prefix + rest + fragment


def transform(content: str, folder_name: str) -> str:
    attr_pattern = re.compile(
        r'(?P<attr>href|src|srcSet)=(["\'])(?P<url>.*?)\2',
        re.IGNORECASE,
    )

    def repl(match: re.Match[str]) -> str:
        url = match.group("url")
        fixed = fix_relative_url(url, folder_name)
        return f'{match.group("attr")}={match.group(2)}{fixed}{match.group(2)}'

    return attr_pattern.sub(repl, content)


def discover_pairs(*, force: bool = False) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for html in ROOT.rglob("*.html"):
        if html.name == "index.html":
            continue
        dest = html.parent / html.stem / "index.html"
        if force or not dest.exists():
            pairs.append((html, dest))
    return sorted(pairs, key=lambda p: str(p[0]))


def main() -> None:
    import sys

    force = "--force" in sys.argv
    pairs = discover_pairs(force=force)
    if not pairs:
        print("No index.html files to generate.")
        return

    for src, dest in pairs:
        folder_name = src.stem
        content = src.read_text(encoding="utf-8")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(transform(content, folder_name), encoding="utf-8")
        print(f"Created {dest.relative_to(ROOT)} from {src.relative_to(ROOT)}")

    print(f"Done: {len(pairs)} file(s).")


if __name__ == "__main__":
    main()
