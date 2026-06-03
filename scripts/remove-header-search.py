#!/usr/bin/env python3
"""Remove search icon block from header in all HTML files."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SEARCH_BLOCK = re.compile(
    r'<div class="css-97zv20 mantine-6bln36">'
    r'(?:<style data-emotion="css xniwh8">.*?</style>)?'
    r'<img alt="search"[^>]*/>'
    r'<div class="mantine-us64po">.*?</div>'
    r"</div>",
    re.DOTALL,
)


def main() -> None:
    updated = 0
    for path in sorted(ROOT.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        new_text, count = SEARCH_BLOCK.subn("", text)
        if count:
            path.write_text(new_text, encoding="utf-8")
            updated += 1
    print(f"Removed search block from {updated} file(s).")


if __name__ == "__main__":
    main()
