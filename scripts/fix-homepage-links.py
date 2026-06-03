#!/usr/bin/env python3
"""Fix homepage category card links to canonical directory URLs."""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"

HREF_BY_FILE = {
    "serviceman.html": "/serviceman/",
    "veterans.html": "/veterans/",
    "family.html": "/family/",
    "pow.html": "/pow/",
    "injured.html": "/injured/",
}

TITLE_HREF = {
    "Військові": "/serviceman/",
    "Поранені": "/injured/",
    "Ветерани": "/veterans/",
    "Родини військових та ветеранів": "/family/",
    "Звільнені з полону": "/pow/",
}


def card_title(anchor) -> str:
    label = anchor.select_one("p.css-6ixod5")
    return label.get_text(strip=True) if label else ""


def fix_homepage_links(html_path: Path = INDEX) -> int:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    changed = 0

    for anchor in soup.select("main a.css-1gooe0, main a.css-1q51wqn"):
        href = (anchor.get("href") or "").strip()
        title = card_title(anchor)
        target = HREF_BY_FILE.get(href) or TITLE_HREF.get(title)
        if target and href != target:
            anchor["href"] = target
            changed += 1

    for old, new in HREF_BY_FILE.items():
        if f'href="{old}"' in str(soup):
            pass

    text = str(soup)
    html_path.write_text(text, encoding="utf-8")
    return changed


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"Missing {INDEX}")
    count = fix_homepage_links()
    print(f"Updated {count} homepage category link(s).")


if __name__ == "__main__":
    main()
