#!/usr/bin/env python3
"""Replace header logo with Logo_navigator + divider + Logo_pryncyp."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LOGO_PATTERN = re.compile(
    r'<a href="[^"]*"><img alt="logo"[^>]*/></a>'
    r'|<a href="[^"]*"><img alt="logo"[^>]*></img></a>'
    r'|<a href="[^"]*"><img alt="logo"[^>]*></a>',
    re.IGNORECASE,
)


def depth_to_root(html_path: Path) -> int:
    rel = html_path.relative_to(ROOT)
    if rel.name == "index.html":
        return len(rel.parts) - 1
    return len(rel.parts)


def build_logos_block(prefix: str, home_href: str) -> str:
    img = f"{prefix}img/"
    return (
        '<div class="site-header-logos" style="display:flex;align-items:center;">'
        f'<a class="site-header-logos__link" href="{home_href}">'
        f'<img alt="Правовий навігатор" loading="lazy" height="30" decoding="async" '
        f'style="height:30px;width:auto;display:block" src="{img}Logo_navigator.png"/>'
        '<span aria-hidden="true" class="site-header-logos__divider" style="width:1px;height:30px;background-color:#D9D9D9;'
        'flex-shrink:0;display:block"></span>'
        f'<img alt="Принцип" loading="lazy" height="30" decoding="async" '
        f'style="height:30px;width:auto;display:block" src="{img}Logo_pryncyp.png"/>'
        f"</a></div>"
    )


def main() -> None:
    updated = 0
    skipped = 0

    for path in sorted(ROOT.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        if not LOGO_PATTERN.search(text):
            skipped += 1
            continue

        depth = depth_to_root(path)
        prefix = "../" * depth
        home_href = f"{prefix}index.html" if depth else "index.html"
        block = build_logos_block(prefix, home_href)

        new_text = LOGO_PATTERN.sub(block, text, count=1)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            updated += 1

    print(f"Updated {updated} file(s), skipped {skipped} (no legacy logo).")


if __name__ == "__main__":
    main()
