#!/usr/bin/env python3
"""Normalize about/documents/faq links to canonical directory URLs, remove flat duplicates."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urldefrag

ROOT = Path(__file__).resolve().parent.parent

ABOUT_HREF = re.compile(r"^(?:\.\./)*about\.html$|^about\.html$|^/about$")
FAQ_HREF = re.compile(r"^(?:\.\./)*faq\.html$|^faq\.html$|^/faq$")
FAQ_HREF = re.compile(r"^(?:\.\./)*faq\.html$|^faq\.html$|^/faq$")
DOCUMENTS_HREF = re.compile(r"^(?:\.\./)*documents\.html$|^documents\.html$|^/documents$")
PRIVACY_HREF = re.compile(r"^(?:\.\./)*privacy-policy\.html$|^privacy-policy\.html$|^/privacy-policy\.html$")
PRIVACY_ANCHOR_RE = re.compile(
    r"(<a\b[^>]*href=(['\"])/privacy-policy/\2)([^>]*>)",
    re.IGNORECASE,
)
ATTR_RE = re.compile(r'(?P<attr>href)=(["\'])(?P<url>.*?)\2', re.IGNORECASE)

CANONICAL = {
    "about": "/about/",
    "faq": "/faq/",
    "documents": "/documents/",
    "privacy-policy": "/privacy-policy/",
}

FLAT_DUPLICATES = [ROOT / "about.html", ROOT / "documents.html", ROOT / "privacy-policy.html"]


def normalize_standalone_href(url: str) -> str | None:
    if not url or url.startswith(("http://", "https://", "//", "mailto:", "tel:", "data:")):
        return None

    base, fragment = urldefrag(url)
    if not base or base.startswith("#"):
        return None

    if ABOUT_HREF.fullmatch(base):
        return CANONICAL["about"] + fragment
    if FAQ_HREF.fullmatch(base):
        return CANONICAL["faq"] + fragment
    if DOCUMENTS_HREF.fullmatch(base):
        return CANONICAL["documents"] + fragment
    if PRIVACY_HREF.fullmatch(base):
        return CANONICAL["privacy-policy"] + fragment
    return None


def strip_privacy_target_blank(text: str) -> tuple[str, int]:
    changed = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        attrs = re.sub(r'\s*target=(["\'])_blank\1', "", match.group(3), flags=re.IGNORECASE)
        if attrs != match.group(3):
            changed += 1
        return f"{match.group(1)}{attrs}"

    return PRIVACY_ANCHOR_RE.sub(repl, text), changed


def fix_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    changed = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        url = match.group("url")
        fixed = normalize_standalone_href(url)
        if not fixed or fixed == url:
            return match.group(0)
        changed += 1
        return f'{match.group("attr")}={match.group(2)}{fixed}{match.group(2)}'

    new_text = ATTR_RE.sub(repl, text)
    new_text, target_changes = strip_privacy_target_blank(new_text)
    changed += target_changes
    if changed:
        path.write_text(new_text, encoding="utf-8")
    return changed


def remove_flat_duplicates() -> list[Path]:
    removed: list[Path] = []
    for path in FLAT_DUPLICATES:
        if path.exists():
            path.unlink()
            removed.append(path)
    return removed


def main() -> None:
    total = 0
    files = 0
    for path in sorted(ROOT.rglob("*.html")):
        count = fix_file(path)
        if count:
            files += 1
            total += count

    removed = remove_flat_duplicates()
    print(f"Updated {total} link(s) in {files} file(s).")
    if removed:
        print("Removed:", ", ".join(p.name for p in removed))
    else:
        print("No flat duplicate files to remove.")


if __name__ == "__main__":
    main()
