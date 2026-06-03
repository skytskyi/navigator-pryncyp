#!/usr/bin/env python3
"""Remove Next.js/React runtime from static internal pages."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NEXT_SCRIPT_RE = re.compile(
    r'<script\b[^>]*\bsrc="[^"]*_next/static/[^"]*"[^>]*>\s*</script>\s*',
    re.IGNORECASE,
)
NEXT_DATA_RE = re.compile(
    r'<script\b[^>]*\bid="__NEXT_DATA__"[^>]*>.*?</script>\s*',
    re.IGNORECASE | re.DOTALL,
)
BROKEN_CRITICAL_RE = re.compile(
    r'<style id="internal-layout-critical">.*?</style>\s*'
    r'<script>document\.documentElement\.classList\.add\("internal-layout-active","internal-layout-ready"\);</script>\s*',
    re.DOTALL,
)
GOOD_CRITICAL = (
    '<style id="internal-layout-critical">'
    "html.internal-layout-active main.css-yp9swi{visibility:visible}"
    "</style>\n"
    '  <script>'
    'document.documentElement.classList.add("internal-layout-active","internal-layout-ready");'
    "</script>\n"
)


def is_homepage(path: Path) -> bool:
    return path.resolve() == (ROOT / "index.html").resolve()


def should_strip(html_path: Path, text: str) -> bool:
    if 'data-header-layout-baked="1"' not in text:
        return False
    if is_homepage(html_path):
        return True
    if 'data-internal-layout-baked="' in text:
        return True
    rel = html_path.relative_to(ROOT).as_posix()
    return rel in {
        "about/index.html",
        "documents/index.html",
        "faq/index.html",
        "download/index.html",
        "search/index.html",
        "privacy-policy/index.html",
    }


def mark_static(text: str) -> str:
    if 'data-static-page="1"' in text:
        return text
    return re.sub(
        r"(<html\b)",
        r'\1 data-static-page="1"',
        text,
        count=1,
        flags=re.IGNORECASE,
    )


def strip_next_runtime(text: str) -> tuple[str, dict[str, int]]:
    stats = {"next_scripts": 0, "next_data": 0, "critical_fixed": 0}

    def count_scripts(match: re.Match[str]) -> str:
        stats["next_scripts"] += 1
        return ""

    text = NEXT_SCRIPT_RE.sub(count_scripts, text)

    def count_data(match: re.Match[str]) -> str:
        stats["next_data"] += 1
        return ""

    text = NEXT_DATA_RE.sub(count_data, text)

    if BROKEN_CRITICAL_RE.search(text):
        text = BROKEN_CRITICAL_RE.sub(GOOD_CRITICAL, text, count=1)
        stats["critical_fixed"] += 1
    elif 'id="internal-layout-critical"' in text and "visibility:hidden" in text:
        text = re.sub(
            r'<style id="internal-layout-critical">.*?</style>',
            '<style id="internal-layout-critical">'
            "html.internal-layout-active main.css-yp9swi{visibility:visible}"
            "</style>",
            text,
            count=1,
            flags=re.DOTALL,
        )
        stats["critical_fixed"] += 1

    return text, stats


def strip_page(html_path: Path, force: bool = False) -> tuple[bool, dict[str, int] | None]:
    text = html_path.read_text(encoding="utf-8")
    if not should_strip(html_path, text):
        return False, None
    if (
        not force
        and 'data-static-page="1"' in text
        and "_next/static/chunks/" not in text
        and "__NEXT_DATA__" not in text
    ):
        return False, None

    text, stats = strip_next_runtime(text)
    text = mark_static(text)
    html_path.write_text(text, encoding="utf-8")
    return True, stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Strip Next.js runtime from static internal pages.")
    parser.add_argument("--path", default="", help="Process one page or directory only")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.path:
        candidate = ROOT / args.path.strip("/")
        if candidate.is_dir():
            files = [candidate / "index.html"]
        elif candidate.suffix == ".html":
            files = [candidate]
        else:
            files = [Path(str(candidate) + "/index.html"), candidate]
        files = [p.resolve() for p in files if p.exists()]
    else:
        files = sorted(ROOT.rglob("*.html"))

    stripped = skipped = 0
    totals = {"next_scripts": 0, "next_data": 0, "critical_fixed": 0}
    for html_path in files:
        ok, stats = strip_page(html_path, force=args.force)
        if ok:
            stripped += 1
            for key, value in (stats or {}).items():
                totals[key] += value
        else:
            skipped += 1

    print(
        f"Stripped Next runtime: {stripped}, skipped: {skipped}, "
        f"scripts removed: {totals['next_scripts']}, "
        f"__NEXT_DATA__ removed: {totals['next_data']}, "
        f"critical CSS fixed: {totals['critical_fixed']}"
    )


if __name__ == "__main__":
    main()
