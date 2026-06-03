#!/usr/bin/env python3
"""Verify baked internal layout in static HTML (no browser required).

Usage:
  python3 scripts/verify-layout.py
  python3 scripts/verify-layout.py --base-url http://localhost:8080
  python3 scripts/verify-layout.py --path serviceman/main-documents/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
TREE_PATH = ROOT / "data" / "site-nav-tree.json"
STANDALONE_PAGES = {"/about/", "/documents/", "/faq/", "/download/", "/search/"}


def normalize_path(pathname: str) -> str:
    path = pathname or "/"
    if path.endswith("/index.html"):
        path = path[: -len("/index.html")] or "/"
    if path.endswith(".html"):
        path = path[: -len(".html")]
    if path != "/" and not path.endswith("/"):
        path += "/"
    return path


def path_from_file(html_path: Path) -> str:
    rel = html_path.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return normalize_path("/" + rel[: -len("index.html")])
    return normalize_path("/" + rel)


def load_tree() -> dict:
    return json.loads(TREE_PATH.read_text(encoding="utf-8"))


def path_in_category(path: str, category: dict) -> bool:
    if normalize_path(path) == normalize_path(category["href"]):
        return True
    if category["id"] == "injured":
        for child in category.get("children") or []:
            if path.startswith(child["href"]):
                return True
        return normalize_path(path) == normalize_path(category["href"])
    return path.startswith(category["href"])


def find_category(tree: dict, path: str) -> dict | None:
    for category in tree.get("categories") or []:
        if path_in_category(path, category):
            return category
    return None


def find_trail(nodes: list[dict], path: str, trail: list[dict] | None = None) -> list[dict] | None:
    trail = trail or []
    for node in nodes:
        next_trail = trail + [node]
        if normalize_path(node["href"]) == normalize_path(path):
            return next_trail
        children = node.get("children") or []
        if children:
            found = find_trail(children, path, next_trail)
            if found:
                return found
    return None


def resolve_cards(category: dict, path: str, trail: list[dict]) -> bool:
    if normalize_path(path) == normalize_path(category["href"]):
        return bool(category.get("children"))
    if trail:
        current = trail[-1]
        return bool(current.get("children"))
    return False


def discover_html_files(path_filter: str | None) -> list[Path]:
    if path_filter:
        candidate = ROOT / path_filter.strip("/")
        if candidate.is_dir():
            candidate = candidate / "index.html"
        elif not candidate.suffix:
            candidate = Path(str(candidate) + "/index.html")
        if not candidate.exists():
            candidate = ROOT / path_filter
        if not candidate.exists():
            raise FileNotFoundError(f"Path not found: {path_filter}")
        return [candidate.resolve()]

    files: list[Path] = []
    for html_path in sorted(ROOT.rglob("*.html")):
        if html_path.resolve() == (ROOT / "index.html").resolve():
            continue
        files.append(html_path)
    return files


@dataclass
class PageResult:
    rel: str
    url_path: str
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    http_status: int | None = None

    def fail(self, message: str) -> None:
        self.ok = False
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def fetch_http(base_url: str, url_path: str, timeout: float) -> tuple[int | None, str | None]:
    url = base_url.rstrip("/") + url_path
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as error:
        return None, str(error.reason)


def verify_page(
    html_path: Path,
    tree: dict,
    *,
    base_url: str | None,
    http_timeout: float,
) -> PageResult:
    rel = html_path.relative_to(ROOT).as_posix()
    url_path = path_from_file(html_path)
    result = PageResult(rel=rel, url_path=url_path)

    text = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(text, "html.parser")
    html = soup.find("html")

    category = find_category(tree, url_path)
    standalone = url_path in STANDALONE_PAGES
    expects_layout = bool(category or standalone)

    if html.get("data-header-layout-baked") != "1":
        result.fail("html missing data-header-layout-baked")

    if soup.select('header img[alt="search"]') or soup.select("header .mantine-us64po"):
        result.fail("header still contains search UI")

    logos = soup.select_one("header .site-header-logos")
    if not logos:
        result.fail("header missing .site-header-logos")
    elif not logos.select_one('img[alt="Правовий навігатор"][src*="Logo_navigator"]'):
        result.fail("header logos block is incomplete")

    if "header-persist.js" in text:
        result.fail("header-persist.js still injected (causes navigation flicker)")

    if expects_layout and html.get("data-static-page") != "1":
        result.fail("internal page missing data-static-page after Next strip")

    if expects_layout and "_next/static/chunks/" in text:
        result.fail("Next.js runtime scripts still present on static page")

    if expects_layout and "__NEXT_DATA__" in text:
        result.fail("__NEXT_DATA__ still present on static page")

    if 'id="internal-layout-critical"' in text and "visibility:hidden" in text.split(
        "internal-layout-critical", 1
    )[1][:300]:
        result.fail("internal-layout-critical still hides main")

    active_category = None
    if url_path != "/":
        for category in [
            {"href": "/serviceman/", "prefixes": ["/serviceman"]},
            {"href": "/injured/", "prefixes": ["/injured", "/injured-military", "/ingured-mia"]},
            {"href": "/veterans/", "prefixes": ["/veterans"]},
            {"href": "/pow/", "prefixes": ["/pow"]},
            {"href": "/family/", "prefixes": ["/family"]},
        ]:
            for prefix in category["prefixes"]:
                if url_path.startswith(prefix):
                    active_category = category
                    break
            if active_category:
                break

    nav = soup.select_one(".category-nav")
    if active_category:
        if not nav:
            result.fail("category page missing baked .category-nav")
        elif not nav.select_one(".category-nav__link--active"):
            result.fail("category nav missing active link")
    elif url_path != "/" and nav:
        result.fail("page outside categories unexpectedly has .category-nav")

    if not expects_layout:
        result.warn("outside nav tree — internal layout not required")
        return _verify_http(result, base_url, http_timeout, text)

    html_classes = html.get("class") or [] if html else []
    if "internal-layout-pending" in html_classes:
        result.fail("html still has internal-layout-pending")
    if "internal-layout-ready" not in html_classes:
        result.fail("html missing internal-layout-ready")

    if re.search(
        r"internal-layout-pending\s+main\.css-yp9swi\s*\{\s*visibility\s*:\s*hidden",
        text,
    ):
        result.fail("critical CSS still hides main until JS runs")

    main = soup.select_one("main.css-yp9swi") or soup.select_one("main")
    if not main:
        result.fail("missing <main>")
        return result

    baked = main.get("data-internal-layout-baked")
    if not baked:
        result.fail("main missing data-internal-layout-baked")
    elif normalize_path(baked) != normalize_path(url_path):
        result.fail(f"data-internal-layout-baked mismatch: {baked!r}")

    if standalone:
        if not soup.select_one(".internal-article-layout, .css-k1l4fw.internal-article-layout"):
            result.fail("standalone page missing internal-article-layout")
        if not soup.select_one(".internal-breadcrumbs-row--standalone, .internal-breadcrumbs-row"):
            result.fail("standalone page missing breadcrumbs/toc row")
        toc_items = soup.select(".internal-toc-dropdown .mantine-List-item")
        if not toc_items:
            result.warn("standalone page has empty mobile TOC")
        return _verify_http(result, base_url, http_timeout, text)

    shell = soup.select_one(".internal-page-shell")
    if not shell:
        result.fail("missing .internal-page-shell")
        return _verify_http(result, base_url, http_timeout, text)

    if not soup.select_one(".internal-sidebar"):
        result.fail("missing .internal-sidebar")

    if not soup.select_one(".internal-main"):
        result.fail("missing .internal-main")

    if not soup.select_one(".internal-breadcrumbs-row"):
        result.fail("missing .internal-breadcrumbs-row")

    if not soup.select_one(".internal-page-title"):
        result.fail("missing .internal-page-title")

    trail = find_trail(category.get("children") or [], url_path) or []
    hub_page = resolve_cards(category, url_path, trail) or bool(
        soup.select_one(".internal-subcats-panel")
    )

    if hub_page:
        if not soup.select_one(".internal-subcats-panel"):
            result.fail("hub page missing .internal-subcats-panel")
        if soup.select_one(".internal-article-layout"):
            result.warn("hub page unexpectedly has .internal-article-layout")
    else:
        main_col = soup.select_one(".internal-article-content, .css-7nll2u")
        if main_col and len(main_col.get_text(" ", strip=True)) < 80:
            result.fail("article page main content is empty or too short")
        if not soup.select_one(".internal-article-layout"):
            result.fail("article page missing .internal-article-layout")
        if not soup.select_one(".internal-article-content"):
            result.fail("article page missing .internal-article-content")
        if not soup.select_one(".internal-article-toc"):
            result.warn("article page missing .internal-article-toc")

    return _verify_http(result, base_url, http_timeout, text)


def _verify_http(
    result: PageResult,
    base_url: str | None,
    http_timeout: float,
    disk_html: str,
) -> PageResult:
    if not base_url:
        return result

    status, body = fetch_http(base_url, result.url_path, http_timeout)
    result.http_status = status

    if status is None:
        result.fail(f"HTTP unreachable: {body}")
        return result
    if status != 200:
        result.fail(f"HTTP status {status}")
        return result
    if body is None:
        result.fail("empty HTTP response")
        return result
    if "data-internal-layout-baked" not in body:
        result.fail("HTTP response missing data-internal-layout-baked")
    if "internal-layout-pending" in body:
        result.fail("HTTP response still contains internal-layout-pending")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify baked internal page layout.")
    parser.add_argument(
        "--base-url",
        default="",
        help="Optional origin for HTTP checks, e.g. http://localhost:8080",
    )
    parser.add_argument(
        "--path",
        default="",
        help="Verify one page or directory instead of all internal pages",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="HTTP timeout in seconds (default: 5)",
    )
    args = parser.parse_args()

    tree = load_tree()
    files = discover_html_files(args.path or None)
    base_url = args.base_url.strip() or None

    results: list[PageResult] = []
    for html_path in files:
        results.append(
            verify_page(
                html_path,
                tree,
                base_url=base_url,
                http_timeout=args.timeout,
            )
        )

    failed = [r for r in results if not r.ok]
    warned = [r for r in results if r.warnings]

    for result in results:
        if result.ok and not result.warnings:
            suffix = f" [HTTP {result.http_status}]" if result.http_status else ""
            print(f"OK   {result.rel}{suffix}")
            continue

        status = "FAIL" if not result.ok else "WARN"
        suffix = f" [HTTP {result.http_status}]" if result.http_status else ""
        print(f"{status} {result.rel}{suffix}")
        for error in result.errors:
            print(f"  ✗ {error}")
        for warning in result.warnings:
            print(f"  ! {warning}")

    checked = len([r for r in results if find_category(tree, r.url_path) or r.url_path in STANDALONE_PAGES])
    print()
    print(
        f"Checked {len(results)} HTML files "
        f"({checked} expect baked layout): "
        f"{len(results) - len(failed)} passed, {len(failed)} failed, {len(warned)} with warnings"
    )
    if base_url:
        print(f"HTTP checks against {base_url}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
