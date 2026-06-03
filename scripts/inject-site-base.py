#!/usr/bin/env python3
"""Inject site-base.js early in the head of all HTML pages."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_TAG = '<script src="/js/site-base.js?v=1"></script>'
SCRIPT_RE = re.compile(r'<script\s+src="/js/site-base\.js\?v=\d+"\s*></script>', re.I)
PATCH_RUNTIME_RE = re.compile(r'(<script\s+src="/js/patch-runtime\.js\?v=\d+"\s*></script>)', re.I)


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
    text, changed = upsert_script(text)
    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


def main() -> None:
    updated = 0
    for path in sorted(ROOT.rglob("*.html")):
        if process_file(path):
            updated += 1
    print(f"Injected site-base.js in {updated} file(s).")


if __name__ == "__main__":
    main()
