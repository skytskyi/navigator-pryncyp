#!/usr/bin/env python3
"""Replace straight and curly double quotes in visible text with Ukrainian guillemets."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Comment

ROOT = Path(__file__).resolve().parent.parent


def find_innermost_quote_pair(text: str) -> tuple[int, int] | None:
    best: tuple[int, int, int] | None = None
    for i, ch in enumerate(text):
        if ch != '"':
            continue
        for j in range(i + 1, len(text)):
            if text[j] != '"':
                continue
            inner = text[i + 1 : j]
            if '"' in inner or not inner:
                continue
            span = j - i + 1
            if best is None or span < best[0]:
                best = (span, i, j)
    if best is None:
        return None
    return best[1], best[2]


def normalize_quotes_in_text(text: str) -> str:
    if '"' not in text:
        return text
    while '"' in text:
        pair = find_innermost_quote_pair(text)
        if pair is None:
            break
        start, end = pair
        text = text[:start] + f"«{text[start + 1 : end]}»" + text[end + 1 :]
    if '"' in text:
        text = re.sub(r'"\s*$', "»", text)
        text = re.sub(r'^\s*"', "«", text)
    return text


def repair_known_broken_quote_patterns(html: str) -> str:
    replacements = {
        '«Правозахисний центр »ПРИНЦИП""': "«Правозахисний центр «ПРИНЦИП»»",
        '«Правозахисний центр »ПРИНЦИП"»': "«Правозахисний центр «ПРИНЦИП»»",
        '«Правозахисний центр »Принцип"': "«Правозахисний центр «Принцип»",
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    return html


def normalize_typographic_quotes(html: str) -> str:
    html = repair_known_broken_quote_patterns(html)
    html = (
        html.replace("\u201e", "\u00ab")
        .replace("\u201c", "\u00ab")
        .replace("\u201d", "\u00bb")
    )
    if '"' not in html:
        return html

    soup = BeautifulSoup(html, "html.parser")
    changed = False

    if soup.title and soup.title.string:
        old = str(soup.title.string)
        new = normalize_quotes_in_text(old)
        if new != old:
            soup.title.string.replace_with(new)
            changed = True

    for tag in soup.find_all("meta"):
        content = tag.get("content")
        if not isinstance(content, str) or '"' not in content:
            continue
        new = normalize_quotes_in_text(content)
        if new != content:
            tag["content"] = new
            changed = True

    for node in soup.find_all(string=True):
        if isinstance(node, Comment):
            continue
        parent = node.parent
        if parent and parent.name in ("script", "style"):
            continue
        old = str(node)
        if '"' not in old:
            continue
        new = normalize_quotes_in_text(old)
        if new != old:
            node.replace_with(new)
            changed = True

    return str(soup) if changed else html


def normalize_html_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = normalize_typographic_quotes(original)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    if target:
        candidate = ROOT / target.strip("/")
        if candidate.is_dir():
            files = sorted(candidate.rglob("*.html"))
        else:
            files = [candidate]
    else:
        files = sorted(ROOT.rglob("*.html"))

    updated = 0
    for path in files:
        if "_next" in path.parts:
            continue
        if normalize_html_file(path):
            updated += 1
    print(f"Updated quote marks in {updated} file(s)")


if __name__ == "__main__":
    main()
