#!/usr/bin/env python3
"""Replace broken /_next/image URLs with direct storage.googleapis.com URLs."""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GCS_ASSET = re.compile(
    r"(?:https?:)?(?:%252F%252F|%2F%2F|//)?storage\.googleapis\.com"
    r"(?:%252F|%2F|/)([^&\"'\s]+?\.(?:png|svg|jpg|jpeg|gif|webp))",
    re.IGNORECASE,
)


def decode_chain(value: str, rounds: int = 5) -> str:
    current = value.replace("&amp;", "&")
    for _ in range(rounds):
        decoded = urllib.parse.unquote(current)
        if decoded == current:
            break
        current = decoded
    return current


def extract_gcs_url(fragment: str) -> str | None:
    fragment = decode_chain(fragment)

    if "storage.googleapis.com" not in fragment:
        return None

    match = re.search(r"url=([^&\s\"']+)", fragment)
    if match:
        candidate = decode_chain(match.group(1))
        if candidate.startswith("http") and "storage.googleapis.com" in candidate:
            return candidate.split(" ", 1)[0]

    match = GCS_ASSET.search(fragment)
    if not match:
        return None

    path = decode_chain(match.group(1)).lstrip("/")
    return f"https://storage.googleapis.com/{path}"


def fix_img_tag(tag: str) -> str:
    if "_next/image" not in tag:
        return tag

    src_match = re.search(r'\bsrc="([^"]*)"', tag)
    if not src_match:
        return tag

    direct = extract_gcs_url(src_match.group(1))
    if not direct:
        return tag

    tag = re.sub(r'\bsrc="[^"]*"', f'src="{direct}"', tag)
    tag = re.sub(r'\bsrcSet="[^"]*"', "", tag)
    return tag


def fix_html(content: str) -> tuple[str, int]:
    changes = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal changes
        fixed = fix_img_tag(match.group(0))
        if fixed != match.group(0):
            changes += 1
        return fixed

    updated = re.sub(r"<img\b[^>]*>", repl, content, flags=re.IGNORECASE)
    return updated, changes


def main() -> None:
    total_files = 0
    total_imgs = 0

    for path in sorted(ROOT.rglob("*.html")):
        original = path.read_text(encoding="utf-8")
        updated, count = fix_html(original)
        if count:
            path.write_text(updated, encoding="utf-8")
            total_files += 1
            total_imgs += count
            print(f"Fixed {count} image(s) in {path.relative_to(ROOT)}")

    print(f"Done: {total_imgs} image(s) in {total_files} file(s).")


if __name__ == "__main__":
    main()
