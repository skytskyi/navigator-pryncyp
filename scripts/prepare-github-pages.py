#!/usr/bin/env python3
"""Build a GitHub Pages artifact with a repository subpath prefix.

The source tree keeps root-absolute paths (/css/, /about/, …) for local dev.
This script copies the site to an output directory and rewrites those paths
for project Pages, e.g. /navigator-pryncyp/css/…
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    ".git",
    ".cursor",
    "__pycache__",
    "_site",
    ".github",
}

SKIP_FILES = {".DS_Store"}

# JS is excluded: runtime code uses site-base.js helpers; rewriting string literals breaks them.
REWRITE_SUFFIXES = {".html", ".htm", ".css", ".json", ".txt"}

# HTML attributes, JSON keys, etc.
ATTR_RE = re.compile(
    r'\b(href|src|action|content|data-internal-layout|data-internal-layout-baked)'
    r'\s*=\s*(["\'])/(?!navigator-pryncyp/)(?!/)([^"\']*)\2'
)

JSON_PATH_RE = re.compile(
    r'"(url|href)"\s*:\s*"(/(?!navigator-pryncyp/)(?!/)[^"]*)"'
)

STRING_PATH_RE = re.compile(r'"(/(?!navigator-pryncyp/)(?!/)[^"<>/][^"<>]*?)"')

CSS_ATTR_RE = re.compile(
    r'\[(href|src)\s*=\s*(["\'])/(?!navigator-pryncyp/)(?!/)([^"\']*)\2\]'
)

HTML_TAG_RE = re.compile(r"<html\b([^>]*)>", re.I)
SITE_BASE_PATH_ATTR_RE = re.compile(r'\s*data-site-base-path="[^"]*"', re.I)
META_BASE_PATH_RE = re.compile(
    r'<meta\s+name="site-base-path"\s+content="[^"]*"\s*/?\s*>',
    re.I,
)
META_BASE_PATH_TAG = '<meta name="site-base-path" content="{base}"/>'


def rewrite_text(text: str, prefix: str) -> str:
    if not prefix:
        return text
    base = prefix.rstrip("/")

    def join_path(path: str) -> str:
        if not path:
            return f"{base}/"
        return f"{base}/{path.lstrip('/')}"

    def attr_sub(match: re.Match[str]) -> str:
        attr, quote, path = match.group(1), match.group(2), match.group(3)
        return f'{attr}={quote}{join_path(path)}{quote}'

    def json_sub(match: re.Match[str]) -> str:
        key, path = match.group(1), match.group(2)
        return f'"{key}": "{join_path(path.lstrip("/"))}"'

    def string_sub(match: re.Match[str]) -> str:
        path = match.group(1)
        return f'"{join_path(path.lstrip("/"))}"'

    def css_sub(match: re.Match[str]) -> str:
        attr, quote, path = match.group(1), match.group(2), match.group(3)
        return f'[{attr}={quote}{join_path(path)}{quote}]'

    text = ATTR_RE.sub(attr_sub, text)
    text = JSON_PATH_RE.sub(json_sub, text)
    text = CSS_ATTR_RE.sub(css_sub, text)
    text = STRING_PATH_RE.sub(string_sub, text)
    return text


def should_copy(rel: Path) -> bool:
    parts = rel.parts
    if parts and parts[0] in SKIP_DIRS:
        return False
    if rel.name in SKIP_FILES:
        return False
    if rel.suffix == ".pyc":
        return False
    return True


def inject_site_base_path(text: str, base_path: str) -> str:
    if not base_path or base_path == "/":
        return text

    base = base_path.rstrip("/")
    meta_tag = META_BASE_PATH_TAG.format(base=base)

    def html_sub(match: re.Match[str]) -> str:
        attrs = match.group(1)
        if SITE_BASE_PATH_ATTR_RE.search(attrs):
            attrs = SITE_BASE_PATH_ATTR_RE.sub(f' data-site-base-path="{base}"', attrs, count=1)
        else:
            attrs = f' data-site-base-path="{base}"{attrs}'
        return f"<html{attrs}>"

    text = HTML_TAG_RE.sub(html_sub, text, count=1)
    if META_BASE_PATH_RE.search(text):
        text = META_BASE_PATH_RE.sub(meta_tag, text, count=1)
    elif "<head>" in text:
        text = text.replace("<head>", f"<head>{meta_tag}", 1)
    return text


def copy_tree(source: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    for item in source.rglob("*"):
        rel = item.relative_to(source)
        if not should_copy(rel):
            continue
        target = dest / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)


def build(source: Path, output: Path, base_path: str) -> int:
    copy_tree(source, output)
    rewritten = 0
    for path in output.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(output)
        if rel.parts[:1] == ("scripts",):
            continue
        if path.suffix.lower() not in REWRITE_SUFFIXES:
            continue
        original = path.read_text(encoding="utf-8")
        updated = rewrite_text(original, base_path)
        if path.suffix.lower() in {".html", ".htm"}:
            updated = inject_site_base_path(updated, base_path)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            rewritten += 1

    (output / ".nojekyll").touch()
    return rewritten


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare static site for GitHub Pages subpath.")
    parser.add_argument(
        "--base-path",
        default="/navigator-pryncyp",
        help="Pages project prefix (default: /navigator-pryncyp)",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "_site"),
        help="Output directory (default: _site)",
    )
    parser.add_argument(
        "--source",
        default=str(ROOT),
        help="Site source root (default: repository root)",
    )
    args = parser.parse_args()

    base_path = args.base_path.strip()
    if base_path != "/" and not base_path.startswith("/"):
        base_path = f"/{base_path}"
    if base_path != "/" and base_path.endswith("/"):
        base_path = base_path.rstrip("/")

    output = Path(args.output).resolve()
    source = Path(args.source).resolve()
    count = build(source, output, base_path)
    print(f"Prepared {output} with base path {base_path!r} ({count} files rewritten)")


if __name__ == "__main__":
    main()
