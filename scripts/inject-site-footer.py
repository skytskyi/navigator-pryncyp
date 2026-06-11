#!/usr/bin/env python3
"""Replace legacy footer markup with unified site footer on all HTML pages."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_TAG = '<link rel="stylesheet" href="/css/site-footer.css?v=9"/>'

FOOTER_HTML = (
    "<footer>"
    '<div class="site-footer">'
    '<div class="site-footer__inner">'
    '<div class="site-footer__left">'
    '<span class="site-footer__text">'
    "© 2026 Громадська організація «Правозахисний центр «Принцип» 2026"
    "</span>"
    '<a class="site-footer__link" href="/privacy-policy/">Політика конфіденційності</a>'
    "</div>"
    '<div class="site-footer__right">'
    '<a class="site-footer__link" href="https://opentech.softserveinc.com/" target="_blank" rel="noopener noreferrer">'
    "Дизайн OpenTech SoftServe"
    "</a>"
    '<a class="site-footer__link" href="https://buildapps.pro/" target="_blank" rel="noopener noreferrer">'
    "Розроблено BuildApps"
    "</a>"
    "</div>"
    "</div>"
    "</div>"
    "</footer>"
)

FOOTER_RE = re.compile(r"<footer\b[^>]*>.*?</footer>", re.I | re.S)
CSS_RE = re.compile(r'<link rel="stylesheet" href="/css/site-footer\.css\?v=\d+"/>', re.I)


def upsert_css(text: str) -> tuple[str, bool]:
    if CSS_RE.search(text):
        new_text = CSS_RE.sub(CSS_TAG, text, count=1)
        return new_text, new_text != text
    if "</head>" not in text:
        return text, False
    anchor = 'rel="stylesheet"/>'
    idx = text.rfind(anchor)
    if idx == -1:
        return text.replace("</head>", f"  {CSS_TAG}\n</head>", 1), True
    insert_at = idx + len(anchor)
    return text[:insert_at] + f"\n{CSS_TAG}" + text[insert_at:], True


def upsert_footer(text: str) -> tuple[str, bool]:
    if not FOOTER_RE.search(text):
        return text, False
    new_text = FOOTER_RE.sub(FOOTER_HTML, text, count=1)
    return new_text, new_text != text


def process_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    changed = False

    text, css_changed = upsert_css(text)
    changed |= css_changed

    text, footer_changed = upsert_footer(text)
    changed |= footer_changed

    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


def main() -> None:
    updated = 0
    for path in sorted(ROOT.rglob("*.html")):
        if process_file(path):
            updated += 1
    print(f"Updated footer in {updated} file(s).")


if __name__ == "__main__":
    main()
