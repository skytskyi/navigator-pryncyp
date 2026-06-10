#!/usr/bin/env python3
"""Aggregate downloadable document sections from all site pages into /documents/."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, Tag

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "generate_internal_layout",
    SCRIPTS_DIR / "generate-internal-layout.py",
)
if _spec is None or _spec.loader is None:
    raise SystemExit("Could not load generate-internal-layout.py")
_gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gen)
SECTION_H3_CLASS = _gen.SECTION_H3_CLASS
document_href_key = _gen.document_href_key

ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS_PATH = ROOT / "documents" / "index.html"
TREE_PATH = ROOT / "data" / "site-nav-tree.json"
SKIP_PREFIXES = (
    "_site/",
    "documents/",
    "about/",
    "faq/",
    "download/",
    "search/",
    "privacy-policy/",
)
INTRO_TEXT = (
    "Шаблони та приклади документів з усіх розділів Правового навігатора — "
    "згруповані за темами так само, як на сторінках статей."
)
DOCUMENTS_PAGE_EXCLUDED_SECTIONS = frozenset(
    {
        "Список регіональних програм та контактів",
        "Місто (обласний центр)",
        "Міська територіальна громада",
        "Старостинський округ",
        "Сільські та селищні громади",
    }
)
H2_CLASS = (
    "mantine-Text-root mantine-Title-root css-o8yj4d mantine-1p58xby internal-section-h2"
)
H3_CLASS = (
    f"mantine-Text-root mantine-Title-root css-1yyhngn mantine-1iwx6kr {SECTION_H3_CLASS}"
)


@dataclass
class SectionEntry:
    category: str
    category_order: int
    page_order: int
    page_label: str
    page_href: str
    h2_text: str
    html: str
    doc_count: int


def slug_id(*parts: str) -> str:
    value = "_".join(part.strip() for part in parts if part and part.strip())
    value = re.sub(r"[^\w\u0400-\u04FF:-]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:180] or "Section"


def clone_tag(tag: Tag) -> Tag:
    return BeautifulSoup(str(tag), "html.parser").find(tag.name)


def load_nav_index() -> tuple[
    dict[str, str],
    dict[str, str],
    dict[str, int],
    dict[str, int],
    list[str],
]:
    tree = json.loads(TREE_PATH.read_text(encoding="utf-8"))
    path_to_category: dict[str, str] = {}
    path_to_label: dict[str, str] = {}
    path_order: dict[str, int] = {}
    category_order: dict[str, int] = {}
    category_labels: list[str] = []
    order = 0

    def walk(nodes: list[dict], category_label: str | None = None, category_idx: int = 0) -> None:
        nonlocal order
        for node in nodes:
            href = node.get("href") or ""
            label = node.get("label") or href
            children = node.get("children") or []
            if category_label is None and children:
                category_idx = len(category_order)
                category_order[label] = category_idx
                category_labels.append(label)
                walk(children, label, category_idx)
                continue
            if category_label:
                path_to_category[href] = category_label
                path_to_label[href] = label
                path_order[href] = order
                order += 1
            if children:
                walk(children, category_label, category_idx)

    walk(tree.get("categories") or [])
    return path_to_category, path_to_label, path_order, category_order, category_labels


def page_href_from_file(html_path: Path) -> str:
    rel = html_path.relative_to(ROOT).as_posix()
    return "/" + rel.replace("index.html", "")


def section_h2_text(block: Tag) -> str:
    heading = block.select_one("h2.internal-section-h2, h2")
    return heading.get_text(strip=True) if heading else ""


def find_doc_sections(content: Tag) -> list[Tag]:
    candidates: list[Tag] = []
    for block in content.select(".css-sdnfq3[id], .mantine-1620ffq[id]"):
        if not block.select(".mantine-1fv3ct a.css-uex5rt"):
            continue
        if not section_h2_text(block):
            continue
        candidates.append(block)

    for block in content.select(".mantine-wnhdd8[id]"):
        if block in candidates:
            continue
        if not block.select(".mantine-1fv3ct a.css-uex5rt"):
            continue
        inner = block.select_one(".css-sdnfq3[id], .mantine-1620ffq[id]")
        if inner and section_h2_text(inner):
            candidates.append(inner)
        elif section_h2_text(block):
            candidates.append(block)

    unique: list[Tag] = []
    seen_ids: set[str] = set()
    for block in candidates:
        block_id = block.get("id") or ""
        if block_id and block_id in seen_ids:
            continue
        if any(other is not block and block in other.descendants for other in unique):
            continue
        if block_id:
            seen_ids.add(block_id)
        unique.append(block)
    return unique


def extract_doc_anchors(source_html: str) -> list[Tag]:
    block = BeautifulSoup(source_html, "html.parser").find("div")
    if not block:
        return []

    anchors: list[Tag] = []
    seen: set[str] = set()
    for anchor in block.select(".mantine-1fv3ct a.css-uex5rt[href]"):
        key = document_href_key(anchor.get("href") or "")
        if key in seen:
            continue
        seen.add(key)
        anchors.append(clone_tag(anchor))
    return anchors


def build_category_section(
    soup: BeautifulSoup,
    category: str,
    entries: list[SectionEntry],
    section_id: str,
) -> Tag:
    outer = soup.new_tag("div", attrs={"class": "mantine-wnhdd8", "id": section_id})
    card = soup.new_tag("div", attrs={"class": "css-sdnfq3 mantine-1hdrj7p"})

    h2 = soup.new_tag("h2", attrs={"class": H2_CLASS})
    h2.string = category
    card.append(h2)

    for entry in entries:
        h3 = soup.new_tag("h3", attrs={"class": H3_CLASS})
        h3.string = entry.h2_text
        card.append(h3)

        anchors = extract_doc_anchors(entry.html)
        if not anchors:
            continue
        doc_wrap = soup.new_tag("div", attrs={"class": "mantine-1fv3ct"})
        for anchor in anchors:
            doc_wrap.append(anchor)
        card.append(doc_wrap)

    outer.append(card)
    return outer


def is_excluded_documents_section(title: str) -> bool:
    normalized = re.sub(r"\s+", " ", title.strip())
    if normalized in DOCUMENTS_PAGE_EXCLUDED_SECTIONS:
        return True
    for excluded in DOCUMENTS_PAGE_EXCLUDED_SECTIONS:
        if normalized.endswith(f" — {excluded}") or normalized.endswith(f" - {excluded}"):
            return True
    return False


def collect_sections() -> tuple[list[SectionEntry], list[str]]:
    path_to_category, path_to_label, path_order, category_order, category_labels = load_nav_index()
    entries: list[SectionEntry] = []

    for html_path in sorted(ROOT.rglob("index.html")):
        rel = html_path.relative_to(ROOT).as_posix()
        if any(rel.startswith(prefix) for prefix in SKIP_PREFIXES):
            continue
        page_href = page_href_from_file(html_path)
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
        content = soup.select_one(".internal-article-content")
        if not content:
            continue

        page_label = path_to_label.get(page_href)
        if not page_label:
            h1 = soup.select_one("h1.internal-page-title")
            page_label = h1.get_text(strip=True) if h1 else page_href
        category = path_to_category.get(page_href, "Інше")

        for block in find_doc_sections(content):
            h2_text = section_h2_text(block)
            if not h2_text:
                continue
            doc_count = len(block.select(".mantine-1fv3ct a.css-uex5rt[href]"))
            if doc_count == 0:
                continue
            entries.append(
                SectionEntry(
                    category=category,
                    category_order=category_order.get(category, 999),
                    page_order=path_order.get(page_href, 9999),
                    page_label=page_label,
                    page_href=page_href,
                    h2_text=h2_text,
                    html=str(block),
                    doc_count=doc_count,
                )
            )

    h2_counts = Counter(entry.h2_text for entry in entries)
    for entry in entries:
        if h2_counts[entry.h2_text] > 1:
            entry.h2_text = f"{entry.page_label} — {entry.h2_text}"

    entries = [entry for entry in entries if not is_excluded_documents_section(entry.h2_text)]
    entries.sort(key=lambda item: (item.category_order, item.page_order, item.h2_text))
    return entries, category_labels


def rebuild_documents_page(entries: list[SectionEntry], category_labels: list[str]) -> None:
    if not DOCUMENTS_PATH.exists():
        raise SystemExit(f"Missing {DOCUMENTS_PATH}")

    soup = BeautifulSoup(DOCUMENTS_PATH.read_text(encoding="utf-8"), "html.parser")
    main_col = soup.select_one(".internal-article-content .css-7nll2u, .css-7nll2u")
    if not main_col:
        raise SystemExit("Documents page main column not found")

    wrapper = soup.new_tag("div", attrs={"class": "mantine-1fr50if"})
    intro = soup.new_tag("p", attrs={"class": "css-1xvvgf7 internal-article-intro", "color": "#000000"})
    intro.string = INTRO_TEXT
    wrapper.append(intro)

    entries_by_category: dict[str, list[SectionEntry]] = {}
    for entry in entries:
        entries_by_category.setdefault(entry.category, []).append(entry)

    used_ids: set[str] = set()
    ordered_categories = [
        *category_labels,
        *(cat for cat in sorted(entries_by_category) if cat not in category_labels),
    ]

    for category in ordered_categories:
        cat_entries = entries_by_category.get(category)
        if not cat_entries:
            continue

        section_id = slug_id("Docs", category)
        suffix = 2
        base = section_id
        while section_id in used_ids:
            section_id = f"{base}_{suffix}"
            suffix += 1
        used_ids.add(section_id)

        wrapper.append(build_category_section(soup, category, cat_entries, section_id))

    for legacy in main_col.select(".css-1sctyhq"):
        legacy.decompose()
    main_col.clear()
    main_col.append(wrapper)

    DOCUMENTS_PATH.write_text(str(soup), encoding="utf-8")


def main() -> None:
    entries, category_labels = collect_sections()
    if not entries:
        raise SystemExit("No document sections found across the site")
    rebuild_documents_page(entries, category_labels)
    total_docs = sum(entry.doc_count for entry in entries)
    print(
        f"Updated {DOCUMENTS_PATH.relative_to(ROOT)} with "
        f"{len(category_labels)} main sections, {len(entries)} subsections, "
        f"and {total_docs} document cards"
    )
    subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "generate-internal-layout.py"), "--path", "documents"],
        check=True,
        cwd=ROOT,
    )


if __name__ == "__main__":
    main()
