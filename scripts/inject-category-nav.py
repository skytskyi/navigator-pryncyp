#!/usr/bin/env python3
"""Inject category submenu assets on all HTML pages except the homepage."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_TAG = '<link rel="stylesheet" href="/css/category-nav.css?v=13"/>'
JS_TAG = '<script src="/js/category-nav.js?v=15"></script>'


def is_homepage(path: Path) -> bool:
    return path.resolve() == (ROOT / "index.html").resolve()


def main() -> None:
    css_added = js_added = updated = 0
    for path in sorted(ROOT.rglob("*.html")):
        if is_homepage(path):
            continue

        text = path.read_text(encoding="utf-8")
        changed = False

        new_text = re.sub(
            r'href="/css/category-nav\.css\?v=\d+"',
            'href="/css/category-nav.css?v=13"',
            text,
        )
        if new_text != text:
            text = new_text
            changed = True
            updated += 1

        if "category-nav.css" not in text and "</head>" in text:
            text = text.replace("</head>", f"  {CSS_TAG}\n</head>", 1)
            css_added += 1
            changed = True

        if "category-nav.js" not in text and "</body>" in text:
            text = text.replace("</body>", f"{JS_TAG}</body>", 1)
            js_added += 1
            changed = True
        else:
            new_text = re.sub(
                r'src="/js/category-nav\.js\?v=\d+"',
                'src="/js/category-nav.js?v=15"',
                text,
            )
            if new_text != text:
                text = new_text
                changed = True
                updated += 1

        if changed:
            path.write_text(text, encoding="utf-8")

    print(f"Added CSS to {css_added} file(s), JS to {js_added} file(s), version bumps: {updated}.")


if __name__ == "__main__":
    main()
