#!/usr/bin/env python3
"""Inject site-base.js early in the head of all HTML pages."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_TAG = '<script src="/js/site-base.js?v=3"></script>'
SCRIPT_RE = re.compile(r'<script\s+src="/js/site-base\.js\?v=\d+"\s*></script>', re.I)
PATCH_RUNTIME_RE = re.compile(r'(<script\s+src="/js/patch-runtime\.js\?v=\d+"\s*></script>)', re.I)
VIEWPORT_RE = re.compile(
    r'<meta\s+content="width=device-width,\s*initial-scale=1(?:,\s*maximum-scale=1,\s*user-scalable=0)?"\s+name="viewport"\s*/?>',
    re.I,
)
VIEWPORT_TAG = '<meta content="width=device-width, initial-scale=1" name="viewport"/>'
SKIP_LINK_TAG = (
    '<a class="site-skip-link" href="#main-content">Перейти до основного змісту</a>'
)
BODY_OPEN_RE = re.compile(r"(<body[^>]*>)", re.I)


def fix_viewport(text: str) -> tuple[str, bool]:
    new_text, count = VIEWPORT_RE.subn(VIEWPORT_TAG, text)
    return new_text, count > 0


def upsert_skip_link(text: str) -> tuple[str, bool]:
    if "site-skip-link" in text:
        return text, False
    match = BODY_OPEN_RE.search(text)
    if not match:
        return text, False
    insert_at = match.end()
    return text[:insert_at] + SKIP_LINK_TAG + text[insert_at:], True


def upsert_script(text: str) -> tuple[str, bool]:
    if SCRIPT_RE.search(text):
        new_text = SCRIPT_RE.sub(SCRIPT_TAG, text, count=1)
        return new_text, new_text != text
    if PATCH_RUNTIME_RE.search(text):
        return PATCH_RUNTIME_RE.sub(SCRIPT_TAG + r"\1", text, count=1), True
    if "</head>" not in text:
        return text, False
    return text.replace("</head>", f"{SCRIPT_TAG}\n</head>", 1), True


def process_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    changed = False

    text, viewport_changed = fix_viewport(text)
    changed = changed or viewport_changed

    text, skip_changed = upsert_skip_link(text)
    changed = changed or skip_changed

    text, script_changed = upsert_script(text)
    changed = changed or script_changed

    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


def main() -> None:
    updated = 0
    for path in sorted(ROOT.rglob("*.html")):
        if process_file(path):
            updated += 1
    print(f"Updated site-base/accessibility in {updated} file(s).")


if __name__ == "__main__":
    main()
