#!/usr/bin/env python3
"""Build full-text search index from baked article HTML pages."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "search-index.json"

SKIP_TOP_DIRS = frozenset(
    {
        "_next",
        "about",
        "faq",
        "download",
        "documents",
        "privacy-policy",
        "search",
        "img",
        "css",
        "js",
        "data",
        "scripts",
    }
)

CONTENT_ROOTS = frozenset(
    {
        "serviceman",
        "injured",
        "injured-military",
        "ingured-mia",
        "veterans",
        "pow",
        "family",
    }
)

CATEGORIES: list[tuple[str, str, tuple[str, ...]]] = [
    ("serviceman", "Військові", ("/serviceman",)),
    ("injured", "Поранені", ("/injured", "/injured-military", "/ingured-mia")),
    ("veterans", "Ветерани", ("/veterans",)),
    ("pow", "Звільнені з полону", ("/pow",)),
    ("family", "Родини військових та ветеранів", ("/family",)),
]

MAX_TEXT_LEN = 12000
WHITESPACE_RE = re.compile(r"\s+")


def normalize_path(rel: Path) -> str:
    parts = list(rel.parts)
    if parts and parts[-1] == "index.html":
        parts = parts[:-1]
    path = "/" + "/".join(parts)
    if path != "/" and not path.endswith("/"):
        path += "/"
    return path


def category_for_url(url: str) -> tuple[str, str]:
    for _cid, label, prefixes in CATEGORIES:
        for prefix in prefixes:
            if url == prefix + "/" or url.startswith(prefix + "/"):
                return _cid, label
    return "", ""


def is_article_page(soup: BeautifulSoup) -> bool:
    content = soup.select_one(".internal-article-content")
    if not content:
        return False
    main = soup.select_one(".internal-main")
    if main and main.select_one(".internal-subcats-panel"):
        return False
    return bool(
        content.select_one(".internal-article-layout")
        or content.select_one(".css-7nll2u")
    )


def page_title(soup: BeautifulSoup) -> str:
    h1 = soup.select_one(".internal-page-title")
    if h1:
        text = h1.get_text(strip=True)
        if text:
            return text
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        for suffix in (" | Правовий навігатор", " | Принцип"):
            if title.endswith(suffix):
                title = title[: -len(suffix)].strip()
        return title
    return ""


def should_skip_element(el: Tag) -> bool:
    classes = set(el.get("class") or [])
    if el.name in ("script", "style", "noscript"):
        return True
    if "article-feedback-callout" in classes:
        return True
    if "internal-article-toc" in classes or "internal-toc-toggle-wrap" in classes:
        return True
    if "internal-subcats-panel" in classes:
        return True
    if el.get("data-article-feedback-callout") is not None:
        return True
    return False


def extract_visible_text(root: Tag) -> str:
    chunks: list[str] = []

    def walk(node: Tag) -> None:
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text:
                chunks.append(text)
            return
        if not isinstance(node, Tag):
            return
        if should_skip_element(node):
            return
        for child in node.children:
            if isinstance(child, Tag):
                walk(child)
            elif isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    chunks.append(text)

    walk(root)
    text = WHITESPACE_RE.sub(" ", " ".join(chunks)).strip()
    if len(text) > MAX_TEXT_LEN:
        text = text[:MAX_TEXT_LEN].rstrip() + "…"
    return text


def extract_document(path: Path) -> dict | None:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    if not is_article_page(soup):
        return None

    url = normalize_path(path.relative_to(ROOT))
    title = page_title(soup)
    if not title:
        return None

    content = soup.select_one(".internal-article-content")
    if not content:
        return None

    category, _ = category_for_url(url)
    text = extract_visible_text(content)
    doc_id = url.strip("/").replace("/", "-") or "home"

    return {
        "id": doc_id,
        "url": url,
        "title": title,
        "category": category,
        "text": text,
    }


def build_index() -> dict:
    documents: list[dict] = []
    for html_path in sorted(ROOT.rglob("index.html")):
        rel = html_path.relative_to(ROOT)
        if not rel.parts or rel.parts[0] in SKIP_TOP_DIRS:
            continue
        if rel.parts[0] not in CONTENT_ROOTS:
            continue
        doc = extract_document(html_path)
        if doc:
            documents.append(doc)

    documents.sort(key=lambda item: (item["category"], item["title"]))
    return {
        "version": 1,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "documents": documents,
    }


def main() -> None:
    index = build_index()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(index['documents'])} documents to {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
