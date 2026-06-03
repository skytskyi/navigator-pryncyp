#!/usr/bin/env python3
"""Keep hero search assets on the homepage only; strip them from role landing pages."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROLE_PAGES = [
    "serviceman/index.html",
    "injured-military/index.html",
    "ingured-mia/index.html",
    "veterans/index.html",
    "family/index.html",
    "pow/index.html",
]
SEARCH_BLOCK = re.compile(
    r'<div class="home-hero-search">.*?</form></div>',
    re.DOTALL,
)
HOME_HERO_CSS = re.compile(r'\s*<link[^>]+href="/css/home-hero\.css\?v=\d+"[^>]*/>\s*')
HOME_HERO_JS = re.compile(
    r'\s*<script src="/js/home-hero\.js\?v=\d+"></script>\s*',
)


def strip_role_page_search(text: str) -> tuple[str, bool]:
    changed = False

    new_text, count = SEARCH_BLOCK.subn("", text)
    if count:
        text = new_text
        changed = True

    new_text = HOME_HERO_CSS.sub("\n", text)
    if new_text != text:
        text = new_text
        changed = True

    new_text = HOME_HERO_JS.sub("\n", text)
    if new_text != text:
        text = new_text
        changed = True

    return text, changed


def main() -> None:
    updated = 0
    for rel in ROLE_PAGES:
        path = ROOT / rel
        if not path.exists():
            print(f"Skip missing: {rel}")
            continue

        text = path.read_text(encoding="utf-8")
        text, changed = strip_role_page_search(text)
        if changed:
            path.write_text(text, encoding="utf-8")
            updated += 1
            print(f"Updated {rel}")

    print(f"Done. Updated {updated} role landing page(s).")


if __name__ == "__main__":
    main()
