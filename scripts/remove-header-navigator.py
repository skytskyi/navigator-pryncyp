#!/usr/bin/env python3
"""Remove Navigator dropdown from header in all HTML files."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NAV_BLOCK = re.compile(
    r'<div class="mantine-1xkg0b8"><div></div>'
    r'(?:<style data-emotion="css 1h5x3dy">.*?</style>)?'
    r'<div class=" css-1h5x3dy mantine-1jggmkl" aria-haspopup="menu"[^>]*>'
    r'.*?Навігатор.*?</div></div></div>',
    re.DOTALL,
)


def main() -> None:
    updated = 0
    for path in sorted(ROOT.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        new_text, count = NAV_BLOCK.subn("", text)
        if count:
            path.write_text(new_text, encoding="utf-8")
            updated += 1
    print(f"Removed Navigator menu from {updated} file(s).")


if __name__ == "__main__":
    main()
