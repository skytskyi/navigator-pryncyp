#!/usr/bin/env python3
"""Turn visible email addresses into mailto links in static HTML."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString

ROOT = Path(__file__).resolve().parent.parent
EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-@])([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![A-Za-z0-9_%+-])"
)


def _email_from_href(href: str) -> str | None:
    if not href:
        return None
    if href.startswith("mailto:"):
        return href[len("mailto:") :].split("?", 1)[0]
    match = EMAIL_RE.search(href)
    if match:
        return match.group(1)
    return None


def repair_email_links(soup: BeautifulSoup) -> bool:
    changed = False
    for anchor in soup.find_all("a"):
        href = anchor.get("href") or ""
        if href.startswith("mailto:"):
            continue
        email = _email_from_href(href)
        if not email:
            text = anchor.get_text(" ", strip=True)
            match = EMAIL_RE.search(text)
            if match:
                email = match.group(1)
        if not email:
            continue
        anchor["href"] = f"mailto:{email}"
        if not anchor.get_text(strip=True):
            anchor.string = email
        changed = True
    return changed


def linkify_plain_text_emails(soup: BeautifulSoup) -> bool:
    changed = False
    for node in list(soup.find_all(string=True)):
        if isinstance(node, Comment):
            continue
        parent = node.parent
        if not parent or parent.name in ("script", "style", "a"):
            continue
        text = str(node)
        if "@" not in text:
            continue
        matches = list(EMAIL_RE.finditer(text))
        if not matches:
            continue
        parts: list = []
        last = 0
        for match in matches:
            if match.start() > last:
                parts.append(NavigableString(text[last : match.start()]))
            email = match.group(1)
            anchor = soup.new_tag("a", href=f"mailto:{email}")
            anchor.string = email
            parts.append(anchor)
            last = match.end()
        if last < len(text):
            parts.append(NavigableString(text[last:]))
        node.replace_with(*parts)
        changed = True
    return changed


def linkify_email_addresses(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    changed = repair_email_links(soup)
    changed = linkify_plain_text_emails(soup) or changed
    return str(soup) if changed else html


def linkify_html_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = linkify_email_addresses(original)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    if target:
        candidate = ROOT / target.strip("/")
        files = sorted(candidate.rglob("*.html")) if candidate.is_dir() else [candidate]
    else:
        files = sorted(ROOT.rglob("*.html"))

    updated = 0
    for path in files:
        if "_next" in path.parts:
            continue
        if linkify_html_file(path):
            updated += 1
    print(f"Linkified email addresses in {updated} file(s)")


if __name__ == "__main__":
    main()
