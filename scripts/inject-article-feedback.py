#!/usr/bin/env python3
"""Inject article error-feedback assets on the five navigator category sections."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECTION_DIRS = frozenset(
    {"serviceman", "injured", "injured-military", "ingured-mia", "veterans", "pow", "family"}
)
CSS_TAG = '<link rel="stylesheet" href="/css/article-feedback.css?v=7"/>'
JS_TAG = '<script src="/js/article-feedback.js?v=6"></script>'


def is_section_page(path: Path) -> bool:
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return False
    return bool(rel.parts) and rel.parts[0] in SECTION_DIRS


def upsert_css(text: str) -> tuple[str, bool]:
    changed = False
    new_text = re.sub(
        r'href="/css/article-feedback\.css\?v=\d+"',
        'href="/css/article-feedback.css?v=7"',
        text,
    )
    if new_text != text:
        return new_text, True

    if "article-feedback.css" in text or "</head>" not in text:
        return text, False

    layout_link = re.search(
        r'<link[^>]+href="/css/internal-layout\.css\?v=\d+"[^>]*/>\s*',
        text,
    )
    if layout_link:
        insert_at = layout_link.end()
        text = text[:insert_at] + "  " + CSS_TAG + "\n" + text[insert_at:]
        changed = True
    else:
        text = text.replace("</head>", f"  {CSS_TAG}\n</head>", 1)
        changed = True
    return text, changed


def upsert_js(text: str) -> tuple[str, bool]:
    changed = False
    new_text = re.sub(
        r'src="/js/article-feedback\.js\?v=\d+"',
        'src="/js/article-feedback.js?v=6"',
        text,
    )
    if new_text != text:
        return new_text, True

    if "article-feedback.js" in text or "</body>" not in text:
        return text, False

    if 'src="/js/internal-layout.js' in text:
        text = re.sub(
            r'(<script src="/js/internal-layout\.js\?v=\d+"></script>)',
            r"\1" + JS_TAG,
            text,
            count=1,
        )
        changed = True
    else:
        text = text.replace("</body>", f"{JS_TAG}</body>", 1)
        changed = True
    return text, changed


def main() -> None:
    css_added = js_added = files_updated = 0
    for path in sorted(ROOT.rglob("*.html")):
        if not is_section_page(path):
            continue

        original = path.read_text(encoding="utf-8")
        text = original
        had_css = "article-feedback.css" in text
        had_js = "article-feedback.js" in text

        text, css_changed = upsert_css(text)
        text, js_changed = upsert_js(text)
        if text == original:
            continue

        path.write_text(text, encoding="utf-8")
        files_updated += 1
        if css_changed and not had_css:
            css_added += 1
        if js_changed and not had_js:
            js_added += 1

    print(
        f"Updated {files_updated} section HTML file(s); "
        f"new CSS: {css_added}, new JS: {js_added}"
    )


if __name__ == "__main__":
    main()
