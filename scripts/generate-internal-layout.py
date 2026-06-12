#!/usr/bin/env python3
"""Bake internal page layout into static HTML (sidebar, breadcrumbs, article shell)."""

from __future__ import annotations

import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from html import escape
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from linkify_email_addresses import linkify_email_addresses
from normalize_typographic_quotes import normalize_typographic_quotes

ROOT = Path(__file__).resolve().parent.parent
TREE_PATH = ROOT / "data" / "site-nav-tree.json"
HOME_LABEL = "Головна"
SUBCAT_LABEL = "Виберіть підкатегорію:"
INJURED_CHATBOT_PATHS = frozenset({
    "/injured/",
    "/injured-military/",
    "/ingured-mia/",
    "/ingured-mia/health-mvs/",
    "/ingured-mia/vlk-mia/",
    "/injured-military/prosthetics/",
})
INJURED_CHATBOT_URL = "https://t.me/pryncyp_bot"
INJURED_CHATBOT_TEXT = (
    "За допомогою цього чат-бота можна отримати безоплатну юридичну консультацію. "
    "З військовослужбовцями працюватимуть юристи та юристки-волонтери, "
    "які попередньо пройшли навчання з військового права."
)
STANDALONE_PAGES = {"/about/", "/documents/", "/faq/", "/download/", "/search/", "/privacy-policy/"}
PRIVACY_PAGE_TITLE = (
    "Політика конфіденційності Громадської організації "
    "«Правозахисний центр «ПРИНЦИП»»"
)

ABOUT_STYLE_PAGES = {"/about/", "/faq/"}
TITLE_SUFFIX = " | Правовий навігатор"
CARD_PALETTE = (
    "#686F4E",
    "#61523A",
    "#503334",
    "#47515A",
    "#434A3A",
    "#383C3B",
    "#37332E",
    "#151D23",
    "#2B3A62",
)
DOCUMENT_DOWNLOAD_ICON = "/img/download_24dp.svg"
TOC_DOC_BADGE_ICON = "/img/paperclip.svg"
MOBILE_TOC_TOGGLE_ICON = "/img/toc_icon.svg"
EXTERNAL_LINK_ARROW_ICON = "/img/Arrow%20small%2045.svg"
INLINE_ATTACH_ICON = "/img/Attach.svg"
SECTION_DOCUMENTS_H4_ICON = "/img/File.svg"
EXTERNAL_LINK_ICON_SIZE = "16"
INLINE_ATTACH_ICON_SIZE = "16"
SECTION_DOCUMENTS_H4_ICON_SIZE = "20"
SECTION_H2_CLASS = "internal-section-h2"
SECTION_H3_CLASS = "internal-section-h3"
SECTION_H4_CLASS = "internal-section-h4"
ARTICLE_UPDATED_YEAR = 2026
ARTICLE_UPDATED_MONTHS = (
    "січня",
    "лютого",
    "березня",
    "квітня",
    "травня",
    "червня",
    "липня",
    "серпня",
    "вересня",
    "жовтня",
    "листопада",
    "грудня",
)
ARTICLE_UPDATED_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
ARTICLE_UPDATED_OVERRIDES = {
    "/injured-military/vlk/": "Оновлено 8 червня 2026",
}
ARTICLE_SECTION_PREFIXES = (
    "/serviceman/",
    "/injured/",
    "/injured-military/",
    "/ingured-mia/",
    "/veterans/",
    "/pow/",
    "/family/",
)


def article_hash_path(path: str) -> int:
    h = 0
    for ch in path:
        h = (31 * h + ord(ch)) & 0xFFFFFFFF
        if h >= 2**31:
            h -= 2**32
    return abs(h)


def article_updated_label_for_path(path: str) -> str:
    override = ARTICLE_UPDATED_OVERRIDES.get(path)
    if override:
        return override
    h = article_hash_path(path)
    month = h % 12
    day = (h % ARTICLE_UPDATED_DAYS_IN_MONTH[month]) + 1
    return f"Оновлено {day} {ARTICLE_UPDATED_MONTHS[month]} {ARTICLE_UPDATED_YEAR}"


def is_article_updated_label_page(path: str, soup: BeautifulSoup) -> bool:
    if not any(path == prefix or path.startswith(prefix) for prefix in ARTICLE_SECTION_PREFIXES):
        return False
    content = soup.select_one(".internal-article-content")
    if not content:
        return False
    main = soup.select_one(".internal-main")
    if main and main.select_one(".internal-subcats-panel"):
        return False
    return bool(content.select_one(".internal-article-layout, .css-7nll2u"))


def ensure_article_updated_label(soup: BeautifulSoup, path: str) -> bool:
    if not is_article_updated_label_page(path, soup):
        return False
    header = soup.select_one(".internal-main-header")
    if not header:
        return False
    label_text = article_updated_label_for_path(path)
    existing = header.select_one("[data-article-updated-label]")
    if existing:
        if existing.get_text(strip=True) != label_text:
            existing.string = label_text
            return True
        return False
    h1 = header.select_one(".internal-page-title")
    if not h1:
        return False
    label = soup.new_tag(
        "p",
        attrs={"class": "article-updated-label", "data-article-updated-label": ""},
    )
    label.string = label_text
    h1.insert_after(label)
    return True


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


def paths_equal(a: str, b: str) -> bool:
    return normalize_path(a) == normalize_path(b)


def load_tree() -> dict:
    return json.loads(TREE_PATH.read_text(encoding="utf-8"))


def path_in_category(path: str, category: dict) -> bool:
    if paths_equal(path, category["href"]):
        return True
    if category["id"] == "injured":
        for child in category.get("children") or []:
            if path.startswith(child["href"]):
                return True
        return paths_equal(path, category["href"])
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
        if paths_equal(node["href"], path):
            return next_trail
        children = node.get("children") or []
        if children:
            found = find_trail(children, path, next_trail)
            if found:
                return found
    return None


def build_breadcrumb_trail(category: dict | None, path: str) -> list[dict]:
    trail: list[dict] = [{"label": HOME_LABEL, "href": "/"}]
    if not category:
        return trail

    node_trail = find_trail(category.get("children") or [], path) or []
    trail.append({"label": category["label"], "href": category["href"]})
    if paths_equal(path, category["href"]):
        trail[-1]["current"] = True
        return trail

    for i, node in enumerate(node_trail):
        trail.append(
            {
                "label": node["label"],
                "href": node["href"],
                "current": i == len(node_trail) - 1,
            }
        )
    return trail


def should_expand_node(href: str, path: str) -> bool:
    if paths_equal(href, path):
        return False
    return path.startswith(href)


def breadcrumbs_html(trail: list[dict]) -> str:
    parts: list[str] = []
    for i, item in enumerate(trail):
        if i > 0:
            parts.append(
                '<span class="internal-breadcrumbs__sep" aria-hidden="true">'
                '<img src="/img/breadcrumbs_arrow.svg" alt="" width="7" height="11" />'
                "</span>"
            )
        if item.get("current"):
            parts.append(
                f'<span class="internal-breadcrumbs__item internal-breadcrumbs__item--current">'
                f'{escape(item["label"])}</span>'
            )
        else:
            parts.append(
                f'<a class="internal-breadcrumbs__item" href="{escape(item["href"], quote=True)}">'
                f'{escape(item["label"])}</a>'
            )
    return f'<nav class="internal-breadcrumbs" aria-label="Breadcrumb">{"".join(parts)}</nav>'


def render_tree_nodes(nodes: list[dict], path: str) -> str:
    html_parts: list[str] = []
    for node in nodes:
        children = node.get("children") or []
        has_children = bool(children)
        is_active = paths_equal(node["href"], path)
        is_expanded = has_children and should_expand_node(node["href"], path)
        toggle_class = "internal-tree-toggle"
        if not has_children:
            toggle_class += " internal-tree-toggle--hidden"

        html_parts.append('<li class="internal-tree-item">')
        html_parts.append('<div class="internal-tree-row">')
        html_parts.append(
            f'<button type="button" class="{toggle_class}" data-tree-href="{escape(node["href"], quote=True)}" '
            f'aria-expanded="{"true" if is_expanded else "false"}">'
            '<img class="internal-tree-toggle__icon" src="/img/arrow_down.svg" alt="" width="12" height="12" aria-hidden="true" />'
            "</button>"
        )
        link_class = "internal-tree-link"
        if is_active:
            link_class += " internal-tree-link--active"
        html_parts.append(
            f'<a class="{link_class}" href="{escape(node["href"], quote=True)}">{escape(node["label"])}</a>'
        )
        html_parts.append("</div>")
        if has_children:
            style = "" if is_expanded else ' style="display:none"'
            html_parts.append(f'<ul class="internal-tree-list"{style}>')
            html_parts.append(render_tree_nodes(children, path))
            html_parts.append("</ul>")
        html_parts.append("</li>")
    return "".join(html_parts)


def sidebar_html(category: dict, path: str) -> str:
    return (
        f'<aside class="internal-sidebar">'
        f'<div class="internal-sidebar__title">{escape(category["label"])}</div>'
        f'<nav class="internal-sidebar__tree" aria-label="{escape(category["label"])}">'
        f'<ul class="internal-tree-list">{render_tree_nodes(category.get("children") or [], path)}</ul>'
        f"</nav></aside>"
    )


def build_mobile_toc_list_item_html(href: str, title: str, badge_html: str = "") -> str:
    return (
        '<li class="mantine-List-item">'
        '<div class="internal-toc-item-text">'
        f'<a class="css-16clbz5" href="{escape(href, quote=True)}">{escape(title)}</a>'
        f"{badge_html}"
        "</div></li>"
    )


def collect_mobile_toc_items_from_wrap(toc_wrap: Tag) -> list[tuple[str, str, str]]:
    items: list[tuple[str, str, str]] = []
    for link in toc_wrap.select(".mantine-List-item a[href*='#']"):
        href = link.get("href") or ""
        hash_idx = href.find("#")
        if hash_idx >= 0:
            href = href[hash_idx:]
        title = link.get_text(strip=True)
        if not href or not title:
            continue
        container = _toc_item_container(link)
        badge = container.select_one(".internal-toc-doc-badge") if container else None
        badge_html = str(badge) if badge else ""
        items.append((href, title, badge_html))
    return items


def mobile_toc_toggle_button_inner_html() -> str:
    return (
        f'<img class="internal-toc-toggle__icon" src="{MOBILE_TOC_TOGGLE_ICON}" alt="" '
        'width="16" height="16" aria-hidden="true" />'
        '<span class="internal-toc-toggle__label">Зміст</span>'
    )


def mobile_toc_toggle_markup_from_wrap(toc_wrap: Tag) -> str:
    items = collect_mobile_toc_items_from_wrap(toc_wrap)
    items_html = "".join(
        build_mobile_toc_list_item_html(href, title, badge_html)
        for href, title, badge_html in items
    )
    empty_class = "" if items else " internal-toc-toggle-wrap--empty"
    return (
        f'<div class="internal-toc-toggle-wrap{empty_class}">'
        '<button type="button" class="internal-toc-toggle" aria-label="Зміст" aria-expanded="false">'
        f"{mobile_toc_toggle_button_inner_html()}"
        "</button>"
        '<div class="internal-toc-dropdown" hidden>'
        '<div class="internal-toc-dropdown__panel">'
        '<h4 class="mantine-Text-root mantine-Title-root">Зміст сторінки</h4>'
        f'<ul class="mantine-List-root">{items_html}</ul>'
        "</div></div></div>"
    )


def mobile_toc_toggle_markup(toc_items: list[tuple[str, str]]) -> str:
    items_html = "".join(
        build_mobile_toc_list_item_html(href, title)
        for href, title in toc_items
    )
    empty_class = "" if toc_items else " internal-toc-toggle-wrap--empty"
    return (
        f'<div class="internal-toc-toggle-wrap{empty_class}">'
        '<button type="button" class="internal-toc-toggle" aria-label="Зміст" aria-expanded="false">'
        f"{mobile_toc_toggle_button_inner_html()}"
        "</button>"
        '<div class="internal-toc-dropdown" hidden>'
        '<div class="internal-toc-dropdown__panel">'
        '<h4 class="mantine-Text-root mantine-Title-root">Зміст сторінки</h4>'
        f'<ul class="mantine-List-root">{items_html}</ul>'
        "</div></div></div>"
    )


def breadcrumbs_row_html(trail: list[dict], toc_items: list[tuple[str, str]]) -> str:
    return (
        f'<div class="internal-breadcrumbs-row">'
        f"{breadcrumbs_html(trail)}"
        f"{mobile_toc_toggle_markup(toc_items)}"
        "</div>"
    )


def collect_baked_toc_items(content_host: Tag) -> list[tuple[str, str]]:
    toc_wrap = content_host.select_one(".internal-article-toc")
    if not toc_wrap:
        return []

    toc_items = fix_toc_wrap(toc_wrap)
    if toc_items:
        return toc_items

    main_col = content_host.select_one(".css-7nll2u")
    if main_col:
        return toc_nav_items(collect_toc_entries(main_col))
    return []


def sync_baked_mobile_toc(content_host: Tag) -> bool:
    row = content_host.select_one(".internal-breadcrumbs-row")
    if not row:
        return False

    toc_wrap = content_host.select_one(".internal-article-toc")
    if toc_wrap and toc_wrap.select(".mantine-List-item a[href*='#']"):
        toggle_html = mobile_toc_toggle_markup_from_wrap(toc_wrap)
    else:
        toc_items = collect_baked_toc_items(content_host)
        toggle_html = mobile_toc_toggle_markup(toc_items)

    toggle_markup = BeautifulSoup(toggle_html, "html.parser")
    toggle = row.select_one(".internal-toc-toggle-wrap")
    if toggle:
        toggle.replace_with(toggle_markup)
    else:
        row.append(toggle_markup)
    return True


def injured_chatbot_promo_html(path: str) -> str:
    if normalize_path(path) not in INJURED_CHATBOT_PATHS:
        return ""
    return (
        '<section class="internal-injured-chatbot" aria-labelledby="internal-injured-chatbot-title">'
        '<div class="internal-injured-chatbot__inner">'
        '<div class="internal-injured-chatbot__panel">'
        '<p class="internal-injured-chatbot__eyebrow">Безоплатна юридична допомога</p>'
        '<h2 class="internal-injured-chatbot__title" id="internal-injured-chatbot-title">'
        "Чат-бот для поранених військових"
        "</h2>"
        f'<p class="internal-injured-chatbot__text">{escape(INJURED_CHATBOT_TEXT)}</p>'
        f'<a class="internal-injured-chatbot__btn" href="{escape(INJURED_CHATBOT_URL, quote=True)}" '
        'target="_blank" rel="noopener noreferrer">'
        '<span class="internal-injured-chatbot__btn-icon" aria-hidden="true">'
        '<img src="/img/telegram.svg" alt="" width="24" height="24"/>'
        "</span>"
        "Відкрити чат-бот"
        f'<span class="internal-injured-chatbot__btn-arrow" aria-hidden="true">'
        f'<img src="{EXTERNAL_LINK_ARROW_ICON}" alt="" width="24" height="24"/>'
        "</span>"
        "</a>"
        "</div>"
        "</div>"
        "</section>"
    )


def strip_html_cards(cards: list[dict]) -> str:
    if not cards:
        return ""
    items = []
    for card in cards:
        style = f' style="background-color:{escape(card["color"])}"' if card.get("color") else ""
        icon = (
            f'<img class="internal-strip__icon" src="{escape(card["icon"], quote=True)}" alt="" aria-hidden="true"/>'
            if card.get("icon")
            else ""
        )
        items.append(
            f'<a class="internal-strip"{style} href="{escape(card["href"], quote=True)}">'
            f"{icon}<span class=\"internal-strip__label\">{escape(card['label'])}</span></a>"
        )
    return (
        f'<div class="internal-subcats-panel">'
        f'<p class="internal-subcats__label">{SUBCAT_LABEL}</p>'
        f'<div class="internal-subcats__list">{"".join(items)}</div></div>'
    )


def load_next_data(soup: BeautifulSoup) -> dict | None:
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return None
    return json.loads(script.string)


def page_title(soup: BeautifulSoup, data: dict | None) -> str:
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True).replace(TITLE_SUFFIX, "") if title_tag else ""
    if not data:
        return title
    pp = data.get("props", {}).get("pageProps", {})
    api = pp.get("apiData", {})
    if "stages" in api and api["stages"].get("data"):
        stage = api["stages"]["data"][0]["attributes"]
        return stage.get("SEO_Block", {}).get("Title") or stage.get("Stage_Title") or title
    if "substages" in api and api["substages"].get("data"):
        sub = api["substages"]["data"][0]["attributes"]
        return sub.get("Substage_Title") or title
    return title


def standalone_page_title(main: Tag, soup: BeautifulSoup, data: dict | None) -> str:
    for selector in ("h1.mantine-Title-root", "h1.internal-page-title", "h1"):
        h1 = main.select_one(selector)
        if not h1:
            continue
        text = h1.get_text(strip=True)
        if text and "|" not in text:
            return text
    return page_title(soup, data)


def enrich_cards(cards: list[dict]) -> list[dict]:
    enriched: list[dict] = []
    for index, card in enumerate(cards):
        item = dict(card)
        item["color"] = CARD_PALETTE[index % len(CARD_PALETTE)]
        enriched.append(item)
    return enriched


def cards_from_nodes(nodes: list[dict]) -> list[dict]:
    return enrich_cards(
        [
            {
                "href": node["href"],
                "label": node["label"],
                "icon": node.get("icon") or "",
                "color": node.get("color") or "",
            }
            for node in nodes
        ]
    )


def extract_cards_from_dom(soup: BeautifulSoup) -> list[dict]:
    container = soup.select_one(".css-1jbx5ca")
    if not container:
        return []
    seen: set[str] = set()
    cards: list[dict] = []
    for link in container.select("a.css-1q51wqn, a.css-1gooe0"):
        href = link.get("href") or ""
        if not href or href in seen:
            continue
        seen.add(href)
        label_node = link.select_one("p.css-6ixod5, p.css-1nnvzuy")
        icon_node = link.find("img")
        bg = link.select_one(".css-bxqx5h, .css-5km5in")
        color = bg.get("style", "") if bg else ""
        m = re.search(r"background-color:\s*([^;]+)", color)
        cards.append(
            {
                "href": href,
                "label": label_node.get_text(strip=True) if label_node else href,
                "icon": icon_node.get("src") if icon_node else "",
                "color": m.group(1).strip() if m else "",
            }
        )
    return enrich_cards(cards)


def resolve_cards(category: dict, path: str, trail: list[dict], soup: BeautifulSoup) -> list[dict]:
    if paths_equal(path, category["href"]):
        return cards_from_nodes(category.get("children") or [])
    dom_cards = extract_cards_from_dom(soup)
    if dom_cards:
        return dom_cards
    if trail:
        current = trail[-1]
        children = current.get("children") or []
        if children:
            return cards_from_nodes(children)
    return []


def _in_accordion_label(tag: Tag) -> bool:
    return bool(tag.find_parent(class_=lambda value: value and "mantine-Accordion-label" in value))


def _in_toc_widget(tag: Tag) -> bool:
    return bool(
        tag.find_parent(
            class_=lambda value: value
            and (
                "internal-article-toc" in value
                or "internal-toc-dropdown" in value
                or "internal-toc-generated" in value
            )
        )
    )


def _is_intentional_section_h2(tag: Tag) -> bool:
    classes = tag.get("class") or []
    if SECTION_H2_CLASS in classes:
        return True
    if _in_accordion_label(tag):
        return True
    parent = tag.parent
    if (
        tag.name == "h2"
        and isinstance(parent, Tag)
        and "css-sdnfq3" in (parent.get("class") or [])
        and parent.find("h2", recursive=False) is tag
    ):
        return True
    return False


def privacy_page_title(main: Tag | None = None) -> str:
    if main:
        for h1 in main.select("h1"):
            text = h1.get_text(strip=True)
            if text and "Політика конфіденційності" in text:
                return text
    return PRIVACY_PAGE_TITLE


def upsert_privacy_page_title(soup: BeautifulSoup) -> bool:
    h1 = soup.select_one("h1.internal-page-title")
    if not h1:
        return False
    if h1.get_text(strip=True) == PRIVACY_PAGE_TITLE:
        return False
    h1.clear()
    h1.append(PRIVACY_PAGE_TITLE)
    return True


def prepare_privacy_standalone_layout(content_host: Tag, soup: BeautifulSoup) -> bool:
    """Convert legacy privacy-policy markup into standard standalone article layout."""
    changed = False

    for old_toc in content_host.select(".css-12mrpgq"):
        old_toc.decompose()
        changed = True

    if content_host.select_one(".css-k1l4fw.internal-article-layout"):
        return changed

    content_wrap = content_host.select_one(".css-10gvhst")
    if not content_wrap:
        return changed

    for el in content_wrap.select(".css-1sctyhq"):
        el.decompose()
        changed = True

    layout = soup.new_tag(
        "div",
        attrs={"class": "css-k1l4fw mantine-1y9n8s7 internal-article-layout"},
    )
    white = soup.new_tag("div", attrs={"class": "internal-article-content"})
    main_col = soup.new_tag("div", attrs={"class": "css-7nll2u mantine-vdx6qn"})

    for child in list(content_wrap.children):
        if isinstance(child, Tag) and child.name != "style":
            main_col.append(child.extract())

    for h1 in main_col.select("h1"):
        h1.decompose()
        changed = True

    content_wrap.decompose()
    white.append(main_col)
    layout.append(white)
    content_host.append(layout)
    return True


PRIVACY_BODY_P_CLASS = "css-zcvv7c"
PRIVACY_MISTAGGED_H3_MIN_LEN = 100


def repair_privacy_subsection_h2_to_paragraph(soup: BeautifulSoup, content: Tag) -> bool:
    """Demote h2 that follows h3 inside a section block (e.g. organization name)."""
    changed = False
    for block in content.select(".css-bw3xdm"):
        children = [
            child
            for child in block.children
            if isinstance(child, Tag) and child.name != "style"
        ]
        for index, child in enumerate(children):
            if child.name != "h2" or index == 0:
                continue
            prev = children[index - 1]
            if prev.name != "h3":
                continue
            p = soup.new_tag("p", attrs={"class": PRIVACY_BODY_P_CLASS})
            for node in list(child.contents):
                if isinstance(node, Tag):
                    p.append(node.extract())
                else:
                    p.append(node)
            child.replace_with(p)
            changed = True
    return changed


def repair_privacy_mistagged_headings(soup: BeautifulSoup, content: Tag) -> bool:
    changed = False
    for h3 in content.select("h3.css-1kjtes2"):
        text = h3.get_text(strip=True)
        if len(text) <= PRIVACY_MISTAGGED_H3_MIN_LEN:
            continue
        p = soup.new_tag("p", attrs={"class": PRIVACY_BODY_P_CLASS})
        for child in list(h3.contents):
            if isinstance(child, Tag):
                p.append(child.extract())
            else:
                p.append(child)
        h3.replace_with(p)
        changed = True
    return changed


def repair_privacy_section_wrappers(main_col: Tag, soup: BeautifulSoup) -> bool:
    """Stack privacy white cards like article pages (20px gap, no double margins)."""
    if main_col.select_one(":scope > .mantine-wfw6r2"):
        return False

    blocks = [
        child
        for child in list(main_col.children)
        if isinstance(child, Tag) and "css-bw3xdm" in (child.get("class") or [])
    ]
    if not blocks:
        return False

    outer = soup.new_tag("div", attrs={"class": "mantine-wfw6r2"})
    middle = soup.new_tag("div", attrs={"class": "mantine-vdx6qn"})
    container = soup.new_tag("div", attrs={"class": "css-64gglc mantine-1fr50if"})

    for block in blocks:
        section_wrap = soup.new_tag("div", attrs={"class": "mantine-1fr50if"})
        section_wrap.append(block.extract())
        container.append(section_wrap)

    middle.append(container)
    outer.append(middle)
    main_col.append(outer)

    classes = [cls for cls in (main_col.get("class") or []) if cls != "mantine-1fr50if"]
    if "mantine-vdx6qn" not in classes:
        classes.append("mantine-vdx6qn")
    main_col["class"] = classes
    return True


def repair_privacy_page_layout(soup: BeautifulSoup, content: Tag) -> bool:
    changed = False
    main_col = content.select_one(".css-7nll2u")
    if not main_col:
        return False

    if repair_privacy_mistagged_headings(soup, content):
        changed = True

    if repair_privacy_subsection_h2_to_paragraph(soup, content):
        changed = True

    for block in content.select(".css-bw3xdm[id]"):
        h2 = block.select_one("h2")
        if h2:
            _ensure_section_h2(h2)
            changed = True
        block_classes = list(block.get("class") or [])
        if "css-sdnfq3" not in block_classes:
            block_classes.append("css-sdnfq3")
            block["class"] = block_classes
            changed = True

    for wrap in list(main_col.select(":scope > .css-jvj7uf")):
        moved = False
        for child in list(wrap.children):
            if isinstance(child, Tag) and child.name != "style":
                wrap.insert_before(child.extract())
                moved = True
        if moved or not wrap.get_text(strip=True):
            wrap.decompose()
            changed = True

    if repair_privacy_section_wrappers(main_col, soup):
        changed = True

    return changed


def finalize_privacy_layout(content_host: Tag, soup: BeautifulSoup, title: str | None = None) -> bool:
    changed = False
    article = content_host.select_one(".internal-article-content")
    header = content_host.select_one(".internal-main-header")
    if not article:
        return False

    title_in_article = article.select_one(":scope > .internal-page-title")
    if title_in_article and header:
        if not header.select_one(".internal-page-title"):
            breadcrumb = header.select_one(".internal-breadcrumbs-row")
            if breadcrumb:
                breadcrumb.insert_after(title_in_article.extract())
            else:
                header.append(title_in_article.extract())
            changed = True
        else:
            title_in_article.decompose()
            changed = True
    elif title and header and not header.select_one(".internal-page-title"):
        h1 = soup.new_tag("h1", attrs={"class": "internal-page-title"})
        h1.string = title
        breadcrumb = header.select_one(".internal-breadcrumbs-row")
        if breadcrumb:
            breadcrumb.insert_after(h1)
        else:
            header.append(h1)
        changed = True

    if repair_privacy_page_layout(soup, article):
        changed = True
    return changed


def normalize_heading_levels(content: Tag) -> bool:
    """Promote accordion section titles h4→h2; demote in-content h2→h3."""
    changed = False

    for h2 in content.select(".mantine-wnhdd8 > .mantine-j9g3bi > h2"):
        classes = h2.get("class") or []
        if "css-o8yj4d" not in classes:
            continue
        h2.name = "h3"
        classes = [cls for cls in classes if cls != SECTION_H2_CLASS]
        if SECTION_H3_CLASS not in classes:
            classes.append(SECTION_H3_CLASS)
        h2["class"] = classes
        changed = True

    for h2 in list(content.find_all("h2")):
        if _in_toc_widget(h2) or _is_intentional_section_h2(h2):
            continue
        h2.name = "h3"
        classes = h2.get("class") or []
        if SECTION_H3_CLASS not in classes:
            h2["class"] = [*classes, SECTION_H3_CLASS]
        changed = True

    for label in content.select(".mantine-Accordion-label"):
        for h4 in label.find_all("h4"):
            h4.name = "h2"
            classes = h4.get("class") or []
            if SECTION_H2_CLASS not in classes:
                h4["class"] = [*classes, SECTION_H2_CLASS]
            changed = True

    for h3 in content.select(".mantine-wnhdd8 > .mantine-j9g3bi > h3"):
        classes = h3.get("class") or []
        if "css-su8tkm" not in classes:
            continue
        h3.name = "h2"
        classes = [cls for cls in classes if cls not in (SECTION_H3_CLASS,)]
        if SECTION_H2_CLASS not in classes:
            classes.append(SECTION_H2_CLASS)
        h3["class"] = classes
        changed = True

    return changed


def _promote_heading_to_h3(heading: Tag) -> None:
    heading.name = "h3"
    classes = [
        cls
        for cls in (heading.get("class") or [])
        if cls not in (SECTION_H2_CLASS, SECTION_H4_CLASS)
    ]
    if SECTION_H3_CLASS not in classes:
        classes.append(SECTION_H3_CLASS)
    heading["class"] = classes


def _is_card_section_h2(heading: Tag, scope: Tag) -> bool:
    if heading.name != "h2":
        return False
    classes = heading.get("class") or []
    if SECTION_H2_CLASS in classes:
        return True
    if scope.name == "div" and "css-sdnfq3" in (scope.get("class") or []):
        first_h2 = scope.select_one(":scope > h2")
        return heading is first_h2
    return False


def fix_orphan_h4_headings(content: Tag) -> bool:
    """Promote h4 to h3 when a card/section has no preceding h3 subheading."""
    changed = False
    scopes = content.select(".css-sdnfq3") or [content]
    for scope in scopes:
        seen_h3 = False
        for heading in scope.find_all(["h2", "h3", "h4"]):
            if _in_toc_widget(heading):
                continue
            if heading.find_parent(
                class_=lambda value: value and "mantine-Accordion-label" in value
            ):
                continue
            if _is_card_section_h2(heading, scope):
                seen_h3 = False
                continue
            if heading.name == "h3":
                seen_h3 = True
                continue
            if heading.name == "h4" and not seen_h3:
                if is_section_documents_h4_heading(heading):
                    continue
                _promote_heading_to_h3(heading)
                seen_h3 = True
                changed = True
    return changed


def _ensure_section_h2(heading: Tag) -> None:
    heading.name = "h2"
    classes = [cls for cls in (heading.get("class") or []) if cls != SECTION_H3_CLASS]
    if SECTION_H2_CLASS not in classes:
        classes.append(SECTION_H2_CLASS)
    heading["class"] = classes


def demote_about_card_subheadings(card: Tag, section_h2: Tag) -> bool:
    changed = False
    for heading in list(card.find_all(["h2", "h3", "h4"])):
        if heading is section_h2:
            continue
        classes = heading.get("class") or []
        in_label = bool(
            heading.find_parent(class_=lambda value: value and "mantine-Accordion-label" in value)
        )
        if in_label:
            if heading.name != "h3":
                heading.name = "h3"
                changed = True
            classes = [cls for cls in classes if cls not in (SECTION_H2_CLASS, SECTION_H4_CLASS)]
            if SECTION_H3_CLASS not in classes:
                classes.append(SECTION_H3_CLASS)
                changed = True
        elif heading.name == "h2":
            heading.name = "h3"
            classes = [cls for cls in classes if cls != SECTION_H2_CLASS]
            if SECTION_H3_CLASS not in classes:
                classes.append(SECTION_H3_CLASS)
            changed = True
        elif heading.name == "h3":
            heading.name = "h4"
            classes = [cls for cls in classes if cls not in (SECTION_H2_CLASS, SECTION_H3_CLASS)]
            if SECTION_H4_CLASS not in classes:
                classes.append(SECTION_H4_CLASS)
            changed = True
        elif SECTION_H4_CLASS not in classes:
            classes.append(SECTION_H4_CLASS)
            changed = True
        heading["class"] = classes
    return changed


def repair_about_card_layout(content: Tag) -> bool:
    """Move about-page section titles into white cards as h2."""
    changed = False
    for block in content.select(".mantine-wnhdd8"):
        card = block.select_one(":scope > .css-sdnfq3")
        header = block.select_one(":scope > .mantine-j9g3bi")
        if header and card:
            heading = header.find(["h2", "h3", "h4"])
            if heading:
                _ensure_section_h2(heading)
                card.insert(0, heading.extract())
                changed = True
            if not header.find(True) and not header.get_text(strip=True):
                header.decompose()
                changed = True
        if not card:
            continue
        section_h2 = card.select_one(":scope > h2.internal-section-h2, :scope > h2")
        if section_h2:
            _ensure_section_h2(section_h2)
            if demote_about_card_subheadings(card, section_h2):
                changed = True
    return changed


def wrap_about_intro_card(main_col: Tag, soup: BeautifulSoup) -> bool:
    intros = main_col.select(
        ":scope > p.css-tualuh.internal-article-intro, :scope > p.internal-article-intro"
    )
    if not intros:
        return False
    if intros[0].find_parent(class_=lambda value: value and "internal-article-intro-card" in value):
        return False
    card = soup.new_tag(
        "div",
        attrs={"class": "css-sdnfq3 mantine-1hdrj7p internal-article-intro-card"},
    )
    intros[0].insert_before(card)
    for paragraph in intros:
        card.append(paragraph.extract())
    return True


def flatten_sections_wrap(root: Tag) -> bool:
    changed = False
    while True:
        wrap = root.select_one(".mantine-1jhay8j")
        if not wrap:
            break
        for child in list(wrap.children):
            if isinstance(child, Tag):
                wrap.insert_before(child.extract())
                changed = True
        wrap.decompose()
        changed = True
    return changed


def flatten_about_sections_wrap(main_col: Tag) -> bool:
    return flatten_sections_wrap(main_col)


def repair_documents_page_layout(content: Tag) -> bool:
    main_col = content.select_one(".css-7nll2u")
    if not main_col:
        return False
    changed = False
    content_host = content.find_parent(class_=lambda value: value and "internal-main" in value)
    if content_host and remove_stage_step_badges(content_host):
        changed = True
    for label in content.select(".mantine-Accordion-label h4"):
        label.name = "h2"
        classes = label.get("class") or []
        if SECTION_H2_CLASS not in classes:
            label["class"] = [*classes, SECTION_H2_CLASS]
        changed = True
    if flatten_sections_wrap(main_col):
        changed = True
    return changed


def repair_faq_page_intro(content: Tag, soup: BeautifulSoup) -> bool:
    """Match FAQ lead copy styling to standalone documents page intro."""
    main_col = content.select_one(".css-7nll2u")
    if not main_col:
        return False

    changed = False
    header = main_col.select_one(".mantine-vgkn1f")
    if header:
        h3 = header.select_one("h3")
        text = (h3.get_text(strip=True) if h3 else "") or "Відповідаємо на найпоширеніші запитання:"
        intro = soup.new_tag(
            "p",
            attrs={"class": "css-1xvvgf7 internal-article-intro", "color": "#000000"},
        )
        intro.string = text
        header.replace_with(intro)
        changed = True

    wrap = main_col.select_one(":scope > .mantine-1fr50if")
    if not wrap:
        wrap = soup.new_tag("div", attrs={"class": "mantine-1fr50if"})
        for child in list(main_col.children):
            if not isinstance(child, Tag):
                continue
            if "css-1sctyhq" in (child.get("class") or []):
                continue
            wrap.append(child.extract())
        main_col.append(wrap)
        changed = True

    return changed


def repair_about_page_layout(content: Tag, soup: BeautifulSoup) -> bool:
    main_col = content.select_one(".css-7nll2u")
    if not main_col:
        return False
    changed = repair_about_card_layout(content)
    if wrap_about_intro_card(main_col, soup):
        changed = True
    if flatten_sections_wrap(main_col):
        changed = True
    if repair_about_card_layout(content):
        changed = True
    return changed


def apply_heading_normalization(soup: BeautifulSoup) -> bool:
    changed = False
    main = soup.select_one("main")
    path = normalize_path(main.get("data-internal-layout-baked") or "") if main else ""
    for content in soup.select(".internal-article-content"):
        if path in ABOUT_STYLE_PAGES:
            if path == "/faq/" and repair_faq_page_intro(content, soup):
                changed = True
            if repair_about_page_layout(content, soup):
                changed = True
        elif path == "/documents/":
            if repair_documents_page_layout(content):
                changed = True
        elif path == "/download/":
            pass
        elif path == "/privacy-policy/":
            if repair_privacy_page_layout(soup, content):
                changed = True
        elif normalize_heading_levels(content):
            changed = True
        if flatten_article_accordions(content):
            changed = True
        if fix_orphan_h4_headings(content):
            changed = True
    return changed


def get_section_title(section: Tag) -> str:
    heading = section.select_one(
        ":scope > h2.internal-section-h2, :scope > h2, "
        ".mantine-Accordion-label h2, .mantine-Accordion-label h4, "
        ".mantine-Accordion-label .mantine-Title-root, "
        ".mantine-Accordion-label .mantine-Text-root"
    )
    if heading:
        title = heading.get_text(strip=True)
        if title:
            return title
    section_id = section.get("id") or ""
    return section_id.replace("_", " ") if section_id else ""


TOC_ENTRY_SELECTOR = (
    ".css-sdnfq3[id], section[id], .mantine-wnhdd8[id], "
    ".mantine-1ng34cm[id], .css-g0tr8[id], .css-bw3xdm[id], h2[id], h3[id]"
)


def toc_entry_title(el: Tag) -> str:
    if "css-bw3xdm" in (el.get("class") or []):
        headings = el.find_all(["h2", "h3"], limit=2)
        if headings:
            first = headings[0]
            if first.name == "h3":
                return first.get_text(strip=True).rstrip(":")
            return first.get_text(strip=True)
        section_id = el.get("id") or ""
        return section_id.replace("_", " ") if section_id else ""

    if "mantine-wnhdd8" in (el.get("class") or []):
        heading = el.select_one(
            ".css-sdnfq3 > h2.internal-section-h2, .css-sdnfq3 > h2, "
            ".mantine-j9g3bi > h2, h2, h3"
        )
        if heading:
            text = heading.get_text(strip=True)
            if text:
                return text
    title = get_section_title(el)
    if title:
        return title
    heading = el.select_one("h2, h3, h4")
    if heading:
        text = heading.get_text(strip=True)
        if text:
            return text
    if el.name in {"h2", "h3", "h4"}:
        text = el.get_text(strip=True)
        if text:
            return text
    section_id = el.get("id") or ""
    return section_id.replace("_", " ") if section_id else ""


def ukrainian_document_count_label(count: int) -> str:
    if count == 1:
        return "1 документ"
    if 2 <= count <= 4:
        return f"{count} документи"
    return f"{count} документів"


def _normalize_section_id(value: str) -> str:
    return (
        value.replace("«", '"')
        .replace("»", '"')
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def find_toc_section(main_col: Tag, section_id: str) -> Tag | None:
    if not section_id or not main_col:
        return None
    match = main_col.find(id=section_id)
    if match:
        return match
    target = _normalize_section_id(section_id)
    for candidate in main_col.select(TOC_ENTRY_SELECTOR):
        candidate_id = candidate.get("id") or ""
        if candidate_id == section_id or _normalize_section_id(candidate_id) == target:
            return candidate
    return None


def count_section_downloads(section: Tag | None) -> int:
    if not section:
        return 0
    scope = section
    classes = section.get("class") or []
    if section.name in {"h2", "h3"} or "internal-section-h2" in classes:
        card = section.find_parent(class_=lambda value: value and "css-sdnfq3" in value)
        if card:
            scope = card
    return len(scope.select('a.css-uex5rt img[alt="file-icon"]'))


def parse_legacy_toc_doc_count(block: Tag) -> int:
    match = re.search(r"(\d+)", block.get_text(strip=True))
    return int(match.group(1)) if match else 0


def build_toc_doc_badge_html(count: int) -> str:
    if count <= 0:
        return ""
    label = ukrainian_document_count_label(count)
    if count == 1:
        aria = "1 документ для завантаження"
    elif count <= 4:
        aria = f"{count} документи для завантаження"
    else:
        aria = f"{count} документів для завантаження"
    return (
        f'<span class="internal-toc-doc-badge" aria-label="{escape(aria, quote=True)}">'
        f'<img src="{TOC_DOC_BADGE_ICON}" alt="" width="12" height="12" aria-hidden="true" />'
        f'<span class="internal-toc-doc-badge__text">{escape(label)}</span>'
        "</span>"
    )


def _toc_item_container(link: Tag) -> Tag:
    container = link.find_parent(
        class_=lambda value: value
        and ("mantine-12e74aa" in value or "internal-toc-item-text" in value)
    )
    return container if container else link.parent


def normalize_toc_document_badges(toc_wrap: Tag, main_col: Tag | None = None) -> bool:
    changed = False
    if not main_col:
        layout = toc_wrap.find_parent(
            class_=lambda value: value and "internal-article-layout" in value
        )
        if layout:
            main_col = layout.select_one(
                ".internal-article-content .css-7nll2u, .css-7nll2u"
            )

    for item in toc_wrap.select(".mantine-List-item"):
        link = item.select_one("a[href*='#']")
        if not link:
            continue
        container = _toc_item_container(link)
        href = link.get("href") or ""
        hash_idx = href.find("#")
        section_id = unquote(href[hash_idx + 1 :]) if hash_idx >= 0 else ""

        legacy = container.select_one(".mantine-16hexn0")
        if legacy:
            legacy.decompose()
            changed = True

        doc_count = 0
        if main_col and section_id:
            section = find_toc_section(main_col, section_id)
            if section:
                actual_id = section.get("id")
                if actual_id and actual_id != section_id and hash_idx >= 0:
                    link["href"] = "#" + quote(actual_id, safe="")
                    changed = True
                doc_count = count_section_downloads(section)

        title = re.sub(r"\s*x\s*\d+\s*$", "", link.get_text(strip=True), flags=re.IGNORECASE).strip()
        if title != link.get_text(strip=True):
            link.string = title
            changed = True

        classes = container.get("class") or []
        if "internal-toc-item-text" not in classes:
            container["class"] = [*classes, "internal-toc-item-text"]
            changed = True

        existing_badge = container.select_one(".internal-toc-doc-badge")
        if existing_badge:
            existing_badge.decompose()
            changed = True

        badge_html = build_toc_doc_badge_html(doc_count)
        if badge_html:
            container.append(BeautifulSoup(badge_html, "html.parser"))
            changed = True

    return changed


def collect_toc_entries(main_col: Tag) -> list[tuple[str, str, int]]:
    entries: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    for el in main_col.select(TOC_ENTRY_SELECTOR):
        section_id = el.get("id")
        if not section_id or section_id in seen:
            continue
        seen.add(section_id)
        title = toc_entry_title(el)
        if not title:
            continue
        doc_count = count_section_downloads(el)
        entries.append((f"#{quote(section_id, safe='')}", title, doc_count))
    return entries


def toc_nav_items(entries: list[tuple[str, str, int]] | list[tuple[str, str]]) -> list[tuple[str, str]]:
    nav: list[tuple[str, str]] = []
    for item in entries:
        if len(item) >= 2:
            nav.append((item[0], item[1]))
    return nav


def collect_toc_from_wrap(toc_wrap: Tag) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for link in toc_wrap.select(".mantine-List-item a[href*='#']"):
        href = link.get("href") or ""
        title = link.get_text(strip=True)
        if href and title:
            hash_idx = href.find("#")
            if hash_idx >= 0:
                href = href[hash_idx:]
            items.append((href, title))
    return items


def collect_toc_doc_counts_from_wrap(toc_wrap: Tag) -> list[int]:
    counts: list[int] = []
    for item in toc_wrap.select(".mantine-List-item"):
        badge_text = item.select_one(".internal-toc-doc-badge__text")
        if badge_text:
            counts.append(parse_legacy_toc_doc_count(badge_text))
        else:
            counts.append(0)
    return counts


def build_toc_list_item_html(href: str, title: str, doc_count: int = 0) -> str:
    badge = build_toc_doc_badge_html(doc_count)
    return (
        '<li class="mantine-List-item mantine-riob0u" data-with-icon="true">'
        '<div class="___ref-itemWrapper mantine-iwg4hh mantine-List-itemWrapper">'
        '<span class="mantine-uezznj mantine-List-itemIcon">'
        '<div class="mantine-ThemeIcon-root mantine-1tnkqq"></div></span>'
        f'<span><div class="internal-toc-item-text mantine-12e74aa">'
        f'<a class="css-16clbz5" href="{escape(href, quote=True)}">'
        f"{escape(title)}</a>{badge}</div></span></div></li>"
    )


def build_generated_toc_html(entries: list[tuple[str, str, int]]) -> str:
    items = "".join(
        build_toc_list_item_html(href, title, doc_count)
        for href, title, doc_count in entries
    )
    return (
        '<div class="css-gfn0ts mantine-1fr50if internal-toc-generated"><div class="mantine-1fr50if">'
        '<h4 class="mantine-Text-root mantine-Title-root mantine-1pop5c3">Зміст сторінки</h4>'
        f'<ul class="mantine-List-root mantine-e6qakj">{items}</ul></div></div>'
    )


def generated_toc_needs_upgrade(toc_wrap: Tag) -> bool:
    generated = toc_wrap.select_one(".internal-toc-generated")
    if not generated:
        return True
    if not (
        generated.select_one("h4.mantine-1pop5c3")
        and generated.select_one("ul.mantine-e6qakj")
        and generated.select_one(".mantine-List-item.mantine-riob0u")
    ):
        return True
    if toc_wrap.select_one(".mantine-16hexn0"):
        return True
    if not generated.select_one(".internal-toc-item-text"):
        return True
    return False


def ensure_generated_toc(toc_wrap: Tag, main_col: Tag) -> bool:
    if toc_wrap.select_one(".css-gfn0ts:not(.internal-toc-generated), .css-12mrpgq"):
        return False

    entries = collect_toc_entries(main_col)
    if not entries:
        return False

    generated = toc_wrap.select_one(".internal-toc-generated")
    if (
        generated
        and collect_toc_from_wrap(toc_wrap) == [(href, title) for href, title, _ in entries]
        and collect_toc_doc_counts_from_wrap(toc_wrap) == [count for _, _, count in entries]
        and not generated_toc_needs_upgrade(toc_wrap)
    ):
        return True

    new_gen = BeautifulSoup(build_generated_toc_html(entries), "html.parser")
    if generated:
        generated.replace_with(new_gen)
    else:
        toc_wrap.append(new_gen)
    return True


def expand_accordions(root: Tag) -> None:
    for control in root.select("[data-accordion-control]"):
        control["aria-expanded"] = "true"
        control["data-active"] = "true"
        panel_id = control.get("aria-controls")
        panel = root.find(id=panel_id) if panel_id else None
        if panel:
            panel["aria-hidden"] = "false"
            style = panel.get("style") or ""
            if "display" not in style:
                panel["style"] = (style + ";display:block!important;height:auto!important;overflow:visible!important").strip(";")
            for node in panel.select('[style*="opacity"]'):
                node["style"] = re.sub(r"opacity:\s*[^;]+", "opacity:1", node.get("style") or "") or "opacity:1"
    for item in root.select(".mantine-Accordion-item"):
        item["data-active"] = "true"
    for chevron in root.select(".mantine-Accordion-chevron, [class*='Accordion-chevron']"):
        chevron["data-rotate"] = "true"


def _accordion_panel_content_nodes(content_host: Tag) -> list[Tag]:
    inner = content_host.select_one(".mantine-1fr50if")
    host = inner if inner else content_host
    nodes = [child for child in list(host.children) if isinstance(child, Tag)]
    if len(nodes) == 1 and nodes[0].name == "div":
        classes = nodes[0].get("class") or []
        if not classes:
            inner_nodes = [child for child in nodes[0].children if isinstance(child, Tag)]
            if inner_nodes:
                nodes = inner_nodes
    if nodes:
        return [node.extract() for node in nodes]
    if content_host.get_text(strip=True):
        return [content_host.extract()]
    return []


def _extract_accordion_heading(item: Tag) -> Tag | None:
    label = item.select_one(".mantine-Accordion-label")
    if not label:
        return None
    heading = label.select_one(
        "h2, h4, .mantine-Title-root, .mantine-Text-root"
    )
    if not heading:
        return None
    _ensure_section_h2(heading)
    return heading.extract()


def _accordion_wrapper(item: Tag, card: Tag) -> Tag | None:
    wrapper = item.find_parent(attrs={"data-accordion": True})
    if wrapper and wrapper in card.descendants:
        return wrapper
    parent = item.parent
    while parent and parent is not card:
        classes = parent.get("class") or []
        if parent.get("data-accordion") or "mantine-5n4x4z" in classes:
            return parent
        parent = parent.parent
    return item.parent if item.parent in card.descendants else None


def flatten_article_accordions(root: Tag) -> bool:
    """Replace dead Mantine accordions with flat h2 + body inside white cards."""
    changed = False
    for card in root.select(".css-sdnfq3"):
        for item in list(card.select(".mantine-Accordion-item")):
            heading = _extract_accordion_heading(item)
            panel = item.select_one(".mantine-Accordion-panel")
            if not heading or not panel:
                continue
            content_host = panel.select_one(".mantine-Accordion-content") or panel
            content_nodes = _accordion_panel_content_nodes(content_host)
            if not content_nodes:
                continue
            wrapper = _accordion_wrapper(item, card)
            if not wrapper:
                wrapper = item
            wrapper.replace_with(heading, *content_nodes)
            changed = True

    for accordion in list(root.select("[data-accordion]")):
        if accordion.get_text(strip=True):
            continue
        if accordion.select(".mantine-Accordion-item"):
            continue
        accordion.decompose()
        changed = True
    return changed


INTRO_BODY_CLASSES = frozenset({"css-tualuh", "css-1xvvgf7"})


def mark_intro_text(main_col: Tag) -> None:
    for el in main_col.select(".internal-article-intro"):
        el["class"] = [c for c in el.get("class", []) if c != "internal-article-intro"]

    def is_intro(el: Tag) -> bool:
        classes = el.get("class") or []
        return (
            (
                "mantine-Text-root" in classes
                or el.name == "p"
                or INTRO_BODY_CLASSES.intersection(classes)
            )
            and "css-370pco" not in classes
            and "mantine-172zsy7" not in classes
            and bool(el.get_text(strip=True))
        )

    for wrapper in [main_col, *main_col.select(".mantine-1fr50if")]:
        for child in wrapper.children:
            if not isinstance(child, Tag):
                continue
            if "css-sdnfq3" in (child.get("class") or []):
                continue
            if is_intro(child):
                child_classes = child.get("class") or []
                if "internal-article-intro" not in child_classes:
                    child["class"] = [*child_classes, "internal-article-intro"]


def remove_duplicate_title(main_col: Tag, title_text: str) -> None:
    if not title_text:
        return
    title_block = main_col.select_one(".css-153xe5m")
    if title_block:
        title_block.decompose()
    for heading in main_col.find_all(["h1", "h2", "h3"]):
        if heading.get_text(strip=True) == title_text:
            heading.decompose()


def fix_toc_wrap(toc_wrap: Tag) -> list[tuple[str, str]]:
    for heading in toc_wrap.select("h4.mantine-Title-root"):
        if heading.get_text(strip=True) == "Зміст":
            heading.string = "Зміст сторінки"
        classes = heading.get("class") or []
        if "mantine-1pop5c3" not in classes:
            heading["class"] = [*classes, "mantine-1pop5c3"]
    layout = toc_wrap.find_parent(
        class_=lambda value: value and "internal-article-layout" in value
    )
    main_col = None
    if layout:
        main_col = layout.select_one(".internal-article-content .css-7nll2u, .css-7nll2u")
    if normalize_toc_document_badges(toc_wrap, main_col):
        pass
    if generated_toc_needs_upgrade(toc_wrap):
        if main_col:
            ensure_generated_toc(toc_wrap, main_col)
    for link in toc_wrap.select("a[href*='#']"):
        href = link.get("href") or ""
        hash_idx = href.find("#")
        if hash_idx >= 0:
            link["href"] = href[hash_idx:]
    return collect_toc_from_wrap(toc_wrap)


def build_external_link_icon_tag(soup: BeautifulSoup, class_name: str) -> Tag:
    return soup.new_tag(
        "img",
        src=EXTERNAL_LINK_ARROW_ICON,
        alt="",
        width=EXTERNAL_LINK_ICON_SIZE,
        height=EXTERNAL_LINK_ICON_SIZE,
        **{
            "class": class_name,
            "aria-hidden": "true",
            "decoding": "async",
            "loading": "lazy",
        },
    )


LEGAL_BASIS_ICON_CLASS = "internal-article-legal-basis__icon"
RECOMMENDATION_CALLOUT_CLASS = "internal-article-recommendation"
RECOMMENDATION_ICON = "/_next/static/media/question-icon.ed30c185.svg"
RECOMMENDATION_LABEL = "Рекомендуємо:"


def build_legal_basis_html(href: str, title: str) -> str:
    icon = (
        f'<img class="{LEGAL_BASIS_ICON_CLASS}" src="{EXTERNAL_LINK_ARROW_ICON}" alt="" '
        f'width="{EXTERNAL_LINK_ICON_SIZE}" height="{EXTERNAL_LINK_ICON_SIZE}" '
        'aria-hidden="true" decoding="async" loading="lazy"/>'
    )
    return (
        '<aside class="internal-article-legal-basis" aria-label="Нормативна основа">'
        '<p class="internal-article-legal-basis__label">Що регулює</p>'
        '<p class="internal-article-legal-basis__doc">'
        f'<a class="internal-article-legal-basis__link" href="{escape(href, quote=True)}" '
        'target="_blank" rel="noopener noreferrer">'
        f'<span class="internal-article-legal-basis__link-text">{escape(title)}</span>'
        f"{icon}"
        '<span class="internal-article-legal-basis__sr-only"> (відкривається в новій вкладці)</span>'
        "</a></p></aside>"
    )


def _legal_basis_title_from_link(link: Tag) -> str:
    sr = link.select_one(".internal-article-legal-basis__sr-only")
    title = link.get_text(strip=True)
    if sr:
        title = title.replace(sr.get_text(strip=True), "").strip()
    return title


def _is_legal_basis_block(block: Tag) -> Tag | None:
    if block.select_one(".internal-article-legal-basis"):
        return None
    bold = block.find("b")
    if not bold or "Що регулює" not in bold.get_text():
        return None
    link = block.find("a", href=True)
    if not link:
        return None
    title = link.get_text(strip=True)
    href = link.get("href") or ""
    if not title or not href:
        return None
    return link


def normalize_legal_basis_blocks(soup: BeautifulSoup) -> bool:
    changed = False
    content = soup.select_one(".internal-article-content") or soup
    candidates: list[Tag] = []
    for intro_card in content.select(".internal-article-intro-card"):
        inner = intro_card.find(class_=lambda value: value and "mantine-172zsy7" in value)
        if inner and _is_legal_basis_block(inner):
            candidates.append(intro_card)
    for block in content.select(".mantine-172zsy7"):
        if block.find_parent(class_=lambda value: value and "internal-article-legal-basis" in (value or [])):
            continue
        if block.find_parent(class_=lambda value: value and "internal-article-intro-card" in (value or [])):
            continue
        if _is_legal_basis_block(block):
            candidates.append(block)

    for block in candidates:
        link = _is_legal_basis_block(
            block if "internal-article-intro-card" not in (block.get("class") or []) else block.find(class_=lambda value: value and "mantine-172zsy7" in value)
        )
        if not link:
            continue
        href = link.get("href") or ""
        title = link.get_text(strip=True)
        replacement = BeautifulSoup(build_legal_basis_html(href, title), "html.parser")
        block.replace_with(replacement)
        changed = True

    for aside in list(content.select(".internal-article-legal-basis")):
        link = aside.select_one("a[href]")
        if not link:
            continue
        href = link.get("href") or ""
        title = _legal_basis_title_from_link(link)
        if not href or not title:
            continue
        if aside.select_one(".internal-article-legal-basis__meta"):
            aside.replace_with(BeautifulSoup(build_legal_basis_html(href, title), "html.parser"))
            changed = True
            continue
        if not aside.select_one(".internal-article-legal-basis__link-text"):
            aside.replace_with(BeautifulSoup(build_legal_basis_html(href, title), "html.parser"))
            changed = True
            continue
        icon = aside.select_one(f"img.{LEGAL_BASIS_ICON_CLASS}")
        if icon and icon.get("src") == EXTERNAL_LINK_ARROW_ICON:
            continue
        if aside.select_one("svg.internal-article-legal-basis__icon") or (
            icon and icon.get("src") != EXTERNAL_LINK_ARROW_ICON
        ):
            aside.replace_with(BeautifulSoup(build_legal_basis_html(href, title), "html.parser"))
            changed = True

    return changed


def _is_recommendation_label_el(el: Tag) -> bool:
    if el.find_parent(
        class_=lambda value: value and RECOMMENDATION_CALLOUT_CLASS in (value or [])
    ):
        return False
    text = el.get_text(strip=True)
    return text in (RECOMMENDATION_LABEL, RECOMMENDATION_LABEL.rstrip(":"))


def repair_recommendation_callouts(soup: BeautifulSoup) -> bool:
    content = soup.select_one(".internal-article-content")
    if not content:
        return False

    changed = False
    for label_el in list(
        content.find_all(
            ["div", "p"],
            class_=lambda value: value and "mantine-172zsy7" in (value or []),
        )
    ):
        if not _is_recommendation_label_el(label_el):
            continue

        ul = label_el.find_next_sibling("ul")
        if ul is None or "internal-article-list" not in (ul.get("class") or []):
            continue
        if len(ul.find_all("li", recursive=False)) != 3:
            continue

        aside = soup.new_tag(
            "aside",
            attrs={
                "class": RECOMMENDATION_CALLOUT_CLASS,
                "aria-label": "Рекомендації",
            },
        )
        header = soup.new_tag(
            "div",
            attrs={"class": f"{RECOMMENDATION_CALLOUT_CLASS}__header"},
        )
        icon = soup.new_tag(
            "img",
            attrs={
                "class": f"{RECOMMENDATION_CALLOUT_CLASS}__icon",
                "src": RECOMMENDATION_ICON,
                "alt": "",
                "width": "26",
                "height": "26",
                "aria-hidden": "true",
                "decoding": "async",
                "loading": "lazy",
            },
        )
        label_p = soup.new_tag(
            "p",
            attrs={"class": f"{RECOMMENDATION_CALLOUT_CLASS}__label"},
        )
        strong = soup.new_tag("strong")
        strong.string = RECOMMENDATION_LABEL
        label_p.append(strong)
        header.append(icon)
        header.append(label_p)
        aside.append(header)
        aside.append(ul.extract())
        label_el.replace_with(aside)
        changed = True

    return changed


AUDIENCE_SWITCH_CLASS = "internal-article-audience-switch"
AUDIENCE_SWITCH_PAGES: dict[str, dict[str, str]] = {
    "/injured-military/vlk/": {
        "audience_id": "mou",
        "audience_label": "МОУ",
        "description": "Процедура ВЛК для військовослужбовців ЗСУ (МОУ).",
        "peer_href": "/ingured-mia/vlk-mia/council/",
        "peer_id": "mia",
        "peer_label": "МВС",
    },
    "/ingured-mia/vlk-mia/council/": {
        "audience_id": "mia",
        "audience_label": "МВС",
        "description": "Процедура ВЛК для працівників системи МВС (поліція, ДСНС тощо).",
        "peer_href": "/injured-military/vlk/",
        "peer_id": "mou",
        "peer_label": "МОУ",
    },
}


AUDIENCE_SWITCH_TABS = (
    {"id": "mou", "label": "МОУ", "href": "/injured-military/vlk/"},
    {"id": "mia", "label": "МВС", "href": "/ingured-mia/vlk-mia/council/"},
)


def _build_audience_tab(soup: BeautifulSoup, tab: dict[str, str], active_id: str) -> Tag:
    is_active = tab["id"] == active_id
    classes = [
        "internal-article-audience-switch__tab",
        f"internal-article-audience-switch__tab--{tab['id']}",
    ]
    if is_active:
        classes.append("internal-article-audience-switch__tab--active")
        element = soup.new_tag(
            "span",
            attrs={"class": classes, "aria-current": "page"},
        )
        element.string = tab["label"]
        return element

    element = soup.new_tag(
        "a",
        href=tab["href"],
        attrs={"class": classes},
    )
    element.string = tab["label"]
    return element


def build_audience_switch(soup: BeautifulSoup, config: dict[str, str]) -> Tag:
    aside = soup.new_tag(
        "aside",
        attrs={
            "class": AUDIENCE_SWITCH_CLASS,
            "aria-label": "Для кого ця інструкція",
        },
    )
    content = soup.new_tag("div", attrs={"class": "internal-article-audience-switch__content"})
    label = soup.new_tag("p", attrs={"class": "internal-article-audience-switch__label"})
    label.string = "Для кого ця інструкція"
    text = soup.new_tag("p", attrs={"class": "internal-article-audience-switch__text"})
    text.string = config["description"]
    content.append(label)
    content.append(text)

    tabs = soup.new_tag(
        "div",
        attrs={
            "class": "internal-article-audience-switch__tabs",
            "role": "group",
            "aria-label": "Оберіть систему",
        },
    )
    for tab in AUDIENCE_SWITCH_TABS:
        tabs.append(_build_audience_tab(soup, tab, config["audience_id"]))

    aside.append(content)
    aside.append(tabs)
    return aside


def _audience_switch_matches_config(existing: Tag, config: dict[str, str]) -> bool:
    if not existing.select_one(".internal-article-audience-switch__content"):
        return False
    text_el = existing.select_one(".internal-article-audience-switch__text")
    tab_elements = existing.select(".internal-article-audience-switch__tab")
    if not text_el or len(tab_elements) != 2:
        return False
    if text_el.get_text(strip=True) != config["description"]:
        return False
    for tab, expected in zip(tab_elements, AUDIENCE_SWITCH_TABS, strict=True):
        if tab.get_text(strip=True) != expected["label"]:
            return False
        is_active = expected["id"] == config["audience_id"]
        if is_active != ("internal-article-audience-switch__tab--active" in (tab.get("class") or [])):
            return False
        if not is_active and tab.name != "a":
            return False
        if not is_active and tab.get("href") != expected["href"]:
            return False
    return True


def find_audience_switch_insertion_point(content: Tag) -> Tag | None:
    legal = content.select_one(".internal-article-legal-basis")
    if legal:
        return legal
    intro = content.select_one(".internal-article-intro-card")
    if intro:
        return intro
    section = content.select_one(".css-sdnfq3[id]")
    if section:
        return section
    return content.select_one(".mantine-1fr50if")


def normalize_audience_switch(soup: BeautifulSoup, path: str) -> bool:
    config = AUDIENCE_SWITCH_PAGES.get(normalize_path(path))
    if not config:
        return False

    content = soup.select_one(".internal-article-content")
    if not content:
        return False

    existing = content.select_one(f"aside.{AUDIENCE_SWITCH_CLASS}")
    if existing and _audience_switch_matches_config(existing, config):
        return False

    anchor = find_audience_switch_insertion_point(content)
    if not anchor:
        return False

    switch = build_audience_switch(soup, config)
    if existing:
        existing.replace_with(switch)
        return True

    anchor.insert_before(switch)
    return True


ADDITIONAL_SOURCES_H2_RE = re.compile(r"^Додаткові джерела", re.IGNORECASE)


def _ensure_sources_list(section: Tag, soup: BeautifulSoup) -> Tag:
    ul = section.select_one("ul.internal-article-list")
    if ul:
        return ul
    ul = soup.new_tag("ul", attrs={"class": "internal-article-list"})
    section.append(ul)
    return ul


def _apply_external_link_attrs(link: Tag) -> None:
    href = link.get("href") or ""
    if href.startswith("http"):
        link["target"] = "_blank"
        link["rel"] = "noopener noreferrer"


def normalize_additional_sources_sections(soup: BeautifulSoup) -> bool:
    changed = False
    content = soup.select_one(".internal-article-content") or soup
    for section in content.select(".css-sdnfq3[id]"):
        h2 = section.find("h2", class_=lambda value: value and "internal-section-h2" in value)
        if not h2:
            continue
        title = h2.get_text(strip=True)
        if not ADDITIONAL_SOURCES_H2_RE.match(title):
            continue

        clean_title = title.rstrip(":?").strip()
        if clean_title != title:
            h2.string = clean_title
            changed = True

        ul = _ensure_sources_list(section, soup)

        for wrap in section.select(".mantine-1fv3ct"):
            for anchor in wrap.select("a.css-uex5rt"):
                href = anchor.get("href") or ""
                label_el = anchor.select_one(
                    f".{DOCUMENT_CARD_TITLE_CLASS}, .css-enb2gh"
                )
                label = label_el.get_text(strip=True) if label_el else anchor.get_text(strip=True)
                if not href or not label:
                    continue
                li = soup.new_tag("li")
                link = soup.new_tag("a", href=href)
                _apply_external_link_attrs(link)
                link.string = label
                li.append(link)
                ul.append(li)
                changed = True
            wrap.decompose()
            changed = True

        for li in ul.find_all("li", recursive=False):
            for child in list(li.children):
                if isinstance(child, NavigableString) and child.strip() in {
                    ";",
                    ".",
                    ",",
                    ";.",
                }:
                    child.extract()
                    changed = True
            link = li.find("a", href=True)
            if link:
                before = link.get("rel"), link.get("target")
                _apply_external_link_attrs(link)
                if (link.get("rel"), link.get("target")) != before:
                    changed = True

    return changed


DOCUMENT_DOWNLOAD_HOSTS = (
    "storage.googleapis.com",
    "drive.google.com",
    "docs.google.com",
    "view.officeapps.live.com",
    "turbota.mil.gov.ua",
)
OFFICE_VIEWER_RE = re.compile(
    r"https://view\.officeapps\.live\.com/op/view\.aspx\?src=(.+)",
    re.IGNORECASE,
)
SECTION_DOCUMENTS_H4_LABEL = "Шаблони документів:"
SECTION_DOCUMENTS_H4_CLASS = (
    "mantine-Text-root mantine-Title-root mantine-pzgqay internal-section-h4"
)
SECTION_DOCUMENTS_H4_DOCUMENTS_CLASS = "internal-section-h4--documents"
SECTION_DOCUMENTS_H4_ICON_CLASS = "internal-section-doc-icon"
SECTION_DOCUMENTS_H4_RE = re.compile(
    r"^📎?\s*(?:Документи|Шаблони документів)\s*:?\s*$",
    re.IGNORECASE,
)


def is_section_documents_h4_heading(tag: Tag) -> bool:
    if getattr(tag, "name", None) not in ("h3", "h4"):
        return False
    classes = tag.get("class") or []
    if SECTION_DOCUMENTS_H4_DOCUMENTS_CLASS in classes:
        return True
    text = tag.get_text(" ", strip=True)
    return bool(SECTION_DOCUMENTS_H4_RE.match(text))


def is_proper_section_documents_h4(tag: Tag) -> bool:
    if getattr(tag, "name", None) != "h4":
        return False
    classes = tag.get("class") or []
    if (
        SECTION_DOCUMENTS_H4_DOCUMENTS_CLASS not in classes
        or SECTION_H4_CLASS not in classes
    ):
        return False
    icon = tag.select_one(f"img.{SECTION_DOCUMENTS_H4_ICON_CLASS}")
    if not icon:
        return False
    if icon.get("src") != SECTION_DOCUMENTS_H4_ICON:
        return False
    if icon.get("width") != SECTION_DOCUMENTS_H4_ICON_SIZE:
        return False
    return tag.get_text(" ", strip=True) == SECTION_DOCUMENTS_H4_LABEL


def build_section_documents_h4(soup: BeautifulSoup) -> Tag:
    h4 = soup.new_tag(
        "h4",
        attrs={
            "class": [
                *SECTION_DOCUMENTS_H4_CLASS.split(),
                SECTION_DOCUMENTS_H4_DOCUMENTS_CLASS,
            ],
        },
    )
    icon = soup.new_tag(
        "img",
        src=SECTION_DOCUMENTS_H4_ICON,
        alt="",
        width=SECTION_DOCUMENTS_H4_ICON_SIZE,
        height=SECTION_DOCUMENTS_H4_ICON_SIZE,
        **{
            "class": SECTION_DOCUMENTS_H4_ICON_CLASS,
            "aria-hidden": "true",
            "decoding": "async",
            "loading": "lazy",
        },
    )
    h4.append(icon)
    h4.append(NavigableString(f" {SECTION_DOCUMENTS_H4_LABEL}"))
    return h4


def normalize_section_documents_h4_headings(soup: BeautifulSoup) -> bool:
    changed = False
    content = soup.select_one(".internal-article-content") or soup

    for heading in content.find_all(["h3", "h4"]):
        if not is_section_documents_h4_heading(heading):
            continue
        if is_proper_section_documents_h4(heading):
            continue
        heading.replace_with(build_section_documents_h4(soup))
        changed = True

    for section in content.select(".css-sdnfq3[id]"):
        h2 = section.find("h2", class_=lambda value: value and SECTION_H2_CLASS in value)
        if h2 and ADDITIONAL_SOURCES_H2_RE.match(h2.get_text(strip=True)):
            continue
        doc_wrap = section.select_one(".mantine-1fv3ct")
        if not doc_wrap or not doc_wrap.select("a.css-uex5rt"):
            continue

        prev = doc_wrap.find_previous_sibling()
        while isinstance(prev, NavigableString) and not str(prev).strip():
            prev = prev.find_previous_sibling()

        if isinstance(prev, Tag) and is_proper_section_documents_h4(prev):
            continue

        if isinstance(prev, Tag) and is_section_documents_h4_heading(prev):
            prev.decompose()
            changed = True

        doc_wrap.insert_before(build_section_documents_h4(soup))
        changed = True

    return changed


def normalize_document_href(href: str) -> str:
    if not href:
        return href
    match = OFFICE_VIEWER_RE.match(href)
    if match:
        return unquote(match.group(1))
    malformed = re.match(
        r"^(https://storage\.googleapis\.com/.+\.(?:docx|doc|pdf|xlsx|xls|pptx|ppt|zip))&.+$",
        href,
        re.IGNORECASE,
    )
    if malformed:
        return malformed.group(1)
    return href


def document_href_key(href: str) -> str:
    return normalize_document_href(href).split("?")[0].lower()


def is_document_href(href: str) -> bool:
    if not href:
        return False
    normalized = normalize_document_href(href)
    host = urlparse(normalized).netloc.lower()
    if any(host.endswith(item) or host == item for item in DOCUMENT_DOWNLOAD_HOSTS):
        return True
    if host.endswith("zakon.rada.gov.ua") and "/laws/file/" in normalized.lower():
        return True
    return normalized.lower().split("?")[0].endswith((".docx", ".pdf", ".doc", ".xlsx", ".xls"))


def is_inside_document_card(tag: Tag) -> bool:
    if tag.find_parent("a", class_=lambda value: value and "css-uex5rt" in value):
        return True
    return (
        tag.find_parent(class_=lambda value: value and "mantine-1fv3ct" in (value or []))
        is not None
    )


def clean_document_card_label(text: str) -> str:
    cleaned = re.sub(r"\s*\(завантажити документ\)\s*", " ", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\(відкривається в новій вкладці\)\s*", " ", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def document_label_from_link(text: str, href: str) -> str:
    label = re.sub(r"\s+", " ", text.strip()).rstrip(".,;")
    label = clean_document_card_label(label)
    if label and len(label) <= 200:
        return label[0].upper() + label[1:] if len(label) > 1 else label.upper()
    name = Path(urlparse(normalize_document_href(href)).path).name
    fallback = unquote(name).replace("_", " ").rsplit(".", 1)[0]
    return fallback or label or "Документ"


DOCUMENT_CARD_CLASS = "internal-article-doc-card"
DOCUMENT_CARD_TITLE_CLASS = "internal-article-doc-card__title"
DOCUMENT_CARD_META_CLASS = "internal-article-doc-card__meta"
DOCUMENT_CARD_BADGE_CLASS = "internal-article-doc-card__badge"
DOCUMENT_FILE_SIZE_CACHE_PATH = ROOT / "data" / "document-file-sizes.json"
KNOWN_FILE_EXTENSIONS = (
    ".pdf",
    ".docx",
    ".doc",
    ".xlsx",
    ".xls",
    ".pptx",
    ".ppt",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".bmp",
    ".zip",
    ".rar",
    ".7z",
    ".rtf",
    ".csv",
)
CONTENT_TYPE_TO_EXT = {
    "application/pdf": "PDF",
    "application/msword": "DOC",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
    "application/vnd.ms-excel": "XLS",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX",
    "application/vnd.ms-powerpoint": "PPT",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PPTX",
    "image/png": "PNG",
    "image/jpeg": "JPG",
    "image/gif": "GIF",
    "image/webp": "WEBP",
    "image/svg+xml": "SVG",
    "application/zip": "ZIP",
}
_file_size_cache: dict[str, dict[str, object]] | None = None
_file_size_cache_dirty = False


def get_file_size_cache() -> dict[str, dict[str, object]]:
    global _file_size_cache
    if _file_size_cache is not None:
        return _file_size_cache
    if DOCUMENT_FILE_SIZE_CACHE_PATH.exists():
        try:
            loaded = json.loads(DOCUMENT_FILE_SIZE_CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                _file_size_cache = loaded
                return _file_size_cache
        except (json.JSONDecodeError, OSError):
            pass
    _file_size_cache = {}
    return _file_size_cache


def persist_file_size_cache_if_needed() -> None:
    global _file_size_cache_dirty
    if not _file_size_cache_dirty:
        return
    DOCUMENT_FILE_SIZE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCUMENT_FILE_SIZE_CACHE_PATH.write_text(
        json.dumps(get_file_size_cache(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _file_size_cache_dirty = False


def extension_from_href_path(href: str) -> str | None:
    path = urlparse(normalize_document_href(href)).path.lower()
    for ext in KNOWN_FILE_EXTENSIONS:
        if path.endswith(ext):
            return ext.lstrip(".").upper()
    return None


def file_badge_variant(ext: str) -> str:
    ext_l = ext.lower()
    if ext_l == "pdf":
        return "pdf"
    if ext_l in ("doc", "docx", "rtf", "odt"):
        return "word"
    if ext_l in ("xls", "xlsx", "csv", "ods"):
        return "sheet"
    if ext_l in ("ppt", "pptx", "odp"):
        return "slides"
    if ext_l in ("png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "ico"):
        return "image"
    if ext_l in ("zip", "rar", "7z", "tar", "gz"):
        return "archive"
    return "generic"


def badge_label(ext: str) -> str:
    ext = ext.upper()
    aliases = {"JPEG": "JPG"}
    ext = aliases.get(ext, ext)
    return ext[:4]


def format_file_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{round(num_bytes / 1024)} KB"
    formatted = f"{num_bytes / (1024 * 1024):.1f} MB"
    return formatted.replace(".0 MB", " MB")


def format_file_meta(ext: str, size: int | None, storage: str | None = None) -> str:
    if storage == "google-drive":
        return f"{ext} · Google Drive"
    if size is not None and size > 0:
        return f"{ext} · {format_file_size(size)}"
    return ext


GOOGLE_DRIVE_FILE_RE = re.compile(
    r"https://drive\.google\.com/file/d/([^/?#]+)",
    re.IGNORECASE,
)


def google_drive_file_id(href: str) -> str | None:
    match = GOOGLE_DRIVE_FILE_RE.search(normalize_document_href(href))
    return match.group(1) if match else None


def google_drive_export_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def _head_request_size(href: str) -> tuple[int | None, str | None]:
    contexts = [ssl.create_default_context(), ssl._create_unverified_context()]
    last_error: Exception | None = None
    for context in contexts:
        try:
            request = urllib.request.Request(
                href,
                method="HEAD",
                headers={"User-Agent": "navigator.pryncyp.org layout-baker/1.0"},
            )
            with urllib.request.urlopen(request, timeout=15, context=context) as response:
                content_length = response.headers.get("Content-Length")
                content_type = response.headers.get("Content-Type")
                size = int(content_length) if content_length and content_length.isdigit() else None
                return size, content_type
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return None, None


def _fetch_bytes_range(href: str, start: int, end: int) -> bytes:
    contexts = [ssl.create_default_context(), ssl._create_unverified_context()]
    last_error: Exception | None = None
    for context in contexts:
        try:
            request = urllib.request.Request(
                href,
                headers={
                    "User-Agent": "navigator.pryncyp.org layout-baker/1.0",
                    "Range": f"bytes={start}-{end}",
                },
            )
            with urllib.request.urlopen(request, timeout=15, context=context) as response:
                return response.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return b""


def extension_from_magic_bytes(payload: bytes) -> str | None:
    if payload.startswith(b"%PDF"):
        return "PDF"
    if payload.startswith(b"\xff\xd8\xff"):
        return "JPG"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if payload[:4] == b"RIFF" and len(payload) >= 12 and payload[8:12] == b"WEBP":
        return "WEBP"
    if payload.startswith(b"GIF8"):
        return "GIF"
    return None


def _fetch_google_drive_metadata(file_id: str) -> tuple[str, int | None]:
    export_url = google_drive_export_url(file_id)
    size: int | None = None
    content_type: str | None = None
    try:
        size, content_type = _head_request_size(export_url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        size = None

    ext: str | None = None
    if content_type:
        normalized_type = content_type.split(";", 1)[0].strip().lower()
        ext = CONTENT_TYPE_TO_EXT.get(normalized_type)
        if normalized_type == "application/pdf":
            ext = "PDF"

    if not ext:
        try:
            ext = extension_from_magic_bytes(_fetch_bytes_range(export_url, 0, 15))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
            ext = None

    return ext or "FILE", size


def resolve_file_metadata(href: str) -> tuple[str, int | None, str | None]:
    global _file_size_cache_dirty
    normalized = normalize_document_href(href)
    key = document_href_key(href)
    cache = get_file_size_cache()
    ext = extension_from_href_path(href)
    drive_id = google_drive_file_id(href)

    if drive_id:
        cached = cache.get(key)
        if isinstance(cached, dict) and cached.get("storage") == "google-drive":
            cached_ext = str(cached.get("ext") or "FILE")
            if cached_ext != "FILE":
                cached_size = cached.get("size")
                return (
                    cached_ext,
                    cached_size if isinstance(cached_size, int) else None,
                    "google-drive",
                )

        ext, size = _fetch_google_drive_metadata(drive_id)
        cache[key] = {"ext": ext, "size": size, "storage": "google-drive"}
        _file_size_cache_dirty = True
        return ext, size, "google-drive"

    cached = cache.get(key)
    if isinstance(cached, dict):
        cached_ext = str(cached.get("ext") or ext or "FILE")
        cached_size = cached.get("size")
        return cached_ext, cached_size if isinstance(cached_size, int) else None, None

    size: int | None = None
    content_type: str | None = None
    try:
        size, content_type = _head_request_size(normalized)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        size = None

    if not ext and content_type:
        ext = CONTENT_TYPE_TO_EXT.get(content_type.split(";", 1)[0].strip().lower())
    if not ext:
        ext = "FILE"
    if content_type and "text/html" in content_type.lower():
        size = None

    cache[key] = {"ext": ext, "size": size}
    _file_size_cache_dirty = True
    return ext, size, None


def build_document_card_inner(
    soup: BeautifulSoup,
    label: str,
    ext: str,
    meta_text: str,
) -> Tag:
    inner = soup.new_tag(
        "div",
        attrs={"class": f"css-1h5x3dy mantine-1qq82n7 {DOCUMENT_CARD_CLASS}"},
    )
    leading = soup.new_tag("div", attrs={"class": "internal-article-doc-card__leading"})
    badge = soup.new_tag(
        "span",
        attrs={
            "class": [
                DOCUMENT_CARD_BADGE_CLASS,
                f"{DOCUMENT_CARD_BADGE_CLASS}--{file_badge_variant(ext)}",
            ],
            "aria-hidden": "true",
        },
    )
    badge.string = badge_label(ext)
    leading.append(badge)

    content = soup.new_tag("div", attrs={"class": "internal-article-doc-card__content"})
    title = soup.new_tag("p", attrs={"class": f"css-enb2gh {DOCUMENT_CARD_TITLE_CLASS}"})
    title.string = label
    meta = soup.new_tag("p", attrs={"class": DOCUMENT_CARD_META_CLASS})
    meta.string = meta_text
    content.append(title)
    content.append(meta)

    icon = soup.new_tag(
        "img",
        alt="file-icon",
        decoding="async",
        loading="lazy",
        src=DOCUMENT_DOWNLOAD_ICON,
        style="color:transparent",
    )
    inner.append(leading)
    inner.append(content)
    inner.append(icon)
    return inner


def append_document_card(doc_wrap: Tag, soup: BeautifulSoup, label: str, href: str) -> Tag:
    normalized_href = normalize_document_href(href)
    ext, size, storage = resolve_file_metadata(normalized_href)
    meta_text = format_file_meta(ext, size, storage)
    anchor = soup.new_tag(
        "a",
        href=normalized_href,
        **{"class": "css-uex5rt", "download": "", "target": "_blank"},
    )
    anchor.append(build_document_card_inner(soup, clean_document_card_label(label), ext, meta_text))
    doc_wrap.append(anchor)
    return anchor


def normalize_section_document_blocks(soup: BeautifulSoup) -> bool:
    changed = False
    content = soup.select_one(".internal-article-content") or soup

    for section in content.select(".css-sdnfq3[id]"):
        h2 = section.find("h2", class_=lambda value: value and SECTION_H2_CLASS in value)
        if h2 and ADDITIONAL_SOURCES_H2_RE.match(h2.get_text(strip=True)):
            continue

        docs_h4 = next(
            (h4 for h4 in section.find_all("h4") if is_section_documents_h4_heading(h4)),
            None,
        )
        doc_wrap = section.select_one(".mantine-1fv3ct")

        known_keys: set[str] = set()
        if doc_wrap:
            for anchor in list(doc_wrap.select("a.css-uex5rt")):
                href = anchor.get("href") or ""
                key = document_href_key(href)
                if key in known_keys:
                    anchor.decompose()
                    changed = True
                    continue
                known_keys.add(key)
                normalized = normalize_document_href(href)
                if normalized != href:
                    anchor["href"] = normalized
                    changed = True

        pending: list[tuple[str, str]] = []
        inline_labels: dict[str, str] = {}
        for anchor in section.find_all("a", href=True):
            if is_inside_document_card(anchor):
                continue
            href = anchor.get("href") or ""
            if not is_document_href(href):
                continue
            key = document_href_key(href)
            label = document_label_from_link(anchor.get_text(strip=True), href)
            inline_labels[key] = label
            if key in known_keys:
                continue
            pending.append((label, href))
            known_keys.add(key)

        if doc_wrap:
            for anchor in doc_wrap.select("a.css-uex5rt"):
                href = anchor.get("href") or ""
                key = document_href_key(href)
                label_el = anchor.select_one(
                    f".{DOCUMENT_CARD_TITLE_CLASS}, .css-enb2gh"
                )
                if not label_el or key not in inline_labels:
                    continue
                desired = inline_labels[key]
                current = label_el.get_text(strip=True)
                if desired and current != desired and (
                    len(desired) > len(current) or current.lower() in key
                ):
                    label_el.string = desired
                    changed = True

        if not pending:
            continue

        if not docs_h4:
            docs_h4 = build_section_documents_h4(soup)
            section.append(docs_h4)
            changed = True

        if not doc_wrap:
            doc_wrap = soup.new_tag("div", attrs={"class": "mantine-1fv3ct"})
            section.append(doc_wrap)
            changed = True

        for label, href in pending:
            append_document_card(doc_wrap, soup, label, href)
            changed = True

    return changed


INLINE_EXTERNAL_LINK_CLASS = "internal-article-external-link"
INLINE_DOC_LINK_CLASS = "internal-article-doc-link"
INLINE_VIEW_DOC_LINK_CLASS = "internal-article-view-doc-link"
INLINE_ATTACH_ICON_CLASS = "internal-article-doc-link__icon"
INLINE_EXTERNAL_LINK_ICON_CLASS = "internal-article-external-link__icon"
HEADER_FOREIGNERS_LABEL = "For Foreigners"
HEADER_LANGUAGE_ICON = "/img/language.svg"


def classify_inline_article_link(href: str) -> str | None:
    if not href or href.startswith("#") or href.startswith("mailto:"):
        return None
    normalized = normalize_document_href(href)
    host = urlparse(normalized).netloc.lower()
    path = urlparse(normalized).path.lower()
    if host.endswith("docs.google.com") and "/document/" in path:
        return "view-doc"
    if is_document_href(href):
        return "download"
    if href.startswith("http://") or href.startswith("https://"):
        return "external"
    return None


def is_inside_additional_sources_section(anchor: Tag) -> bool:
    section = anchor.find_parent(class_=lambda value: value and "css-sdnfq3" in (value or []))
    if not section:
        return False
    h2 = section.find("h2", class_=lambda value: value and "internal-section-h2" in value)
    if not h2:
        return False
    return bool(ADDITIONAL_SOURCES_H2_RE.match(h2.get_text(strip=True)))


INLINE_LINK_SKIP_COMPONENT_CLASSES = frozenset(
    {
        "about-partner-btn",
        "download-store-btn",
        "internal-injured-chatbot__btn",
    }
)
INLINE_LINK_SKIP_PARENT_CLASSES = frozenset(
    {
        "about-partners-list",
        "about-page__social-buttons",
        "download-page-card__stores",
        "about-page__intro",
        "internal-article-recommendation",
        "internal-injured-chatbot",
        "site-footer",
    }
)


def _tag_has_class(value, class_name: str) -> bool:
    if not value:
        return False
    if isinstance(value, list):
        return class_name in value
    return value == class_name


def _tag_has_any_class(value, class_names: frozenset[str]) -> bool:
    if not value:
        return False
    if isinstance(value, list):
        return bool(class_names & set(value))
    return value in class_names


def should_skip_inline_link_decor(anchor: Tag) -> bool:
    href = anchor.get("href") or ""
    if anchor.find_parent("header") or (
        "foreigners.navigator" in href and anchor.find_parent(class_=lambda value: value and "css-zfqabr" in value)
    ):
        return True
    classes = anchor.get("class") or []
    decorated = {
        INLINE_EXTERNAL_LINK_CLASS,
        INLINE_DOC_LINK_CLASS,
        INLINE_VIEW_DOC_LINK_CLASS,
    } & set(classes)
    if decorated:
        if (
            INLINE_VIEW_DOC_LINK_CLASS in decorated
            and is_inside_additional_sources_section(anchor)
        ):
            pass
        else:
            return True
    if is_inside_document_card(anchor):
        return True
    if anchor.find_parent(class_=lambda value: value and "internal-article-legal-basis" in (value or [])):
        return True
    if anchor.find_parent(class_=lambda value: value and "internal-article-toc" in (value or [])):
        return True
    if anchor.find_parent(class_=lambda value: value and "internal-toc-dropdown" in (value or [])):
        return True
    if anchor.find_parent(class_=lambda value: value and "article-feedback-callout" in (value or [])):
        return True
    if INLINE_LINK_SKIP_COMPONENT_CLASSES & set(classes):
        return True
    if "site-footer__link" in classes:
        return True
    if anchor.find_parent(
        class_=lambda value: _tag_has_any_class(value, INLINE_LINK_SKIP_PARENT_CLASSES)
    ):
        return True
    if "css-16clbz5" in classes or "css-1kb7s85" in classes:
        return True
    return False


def extract_inline_link_text(anchor: Tag) -> str:
    text = anchor.get_text(" ", strip=True)
    for sr in anchor.select(".internal-article-link__sr-only, .internal-article-legal-basis__sr-only"):
        text = text.replace(sr.get_text(strip=True), "").strip()
    if anchor.select_one(".internal-article-view-doc-link__suffix"):
        text = text.replace("відкрити документ", "").strip(" ·")
    return re.sub(r"\s+", " ", text).strip()


def decorate_inline_link(anchor: Tag, soup: BeautifulSoup, link_type: str) -> bool:
    href = anchor.get("href") or ""
    text = extract_inline_link_text(anchor)
    if not text:
        return False

    preserved_classes = [
        cls
        for cls in (anchor.get("class") or [])
        if not cls.startswith("internal-article-")
    ]
    anchor.clear()

    text_span = soup.new_tag("span")
    text_span.string = text
    sr = soup.new_tag("span", attrs={"class": "internal-article-link__sr-only"})

    if link_type == "external":
        anchor["class"] = [*preserved_classes, INLINE_EXTERNAL_LINK_CLASS]
        anchor["target"] = "_blank"
        anchor["rel"] = "noopener noreferrer"
        text_span["class"] = "internal-article-external-link__text"
        sr.string = " (відкривається в новій вкладці)"
        anchor.append(text_span)
        anchor.append(build_external_link_icon_tag(soup, INLINE_EXTERNAL_LINK_ICON_CLASS))
        anchor.append(sr)
        return True

    if link_type == "download":
        anchor["href"] = normalize_document_href(href)
        anchor["class"] = [*preserved_classes, INLINE_DOC_LINK_CLASS]
        anchor["target"] = "_blank"
        anchor["download"] = ""
        text_span["class"] = "internal-article-doc-link__text"
        sr.string = " (завантажити документ)"
        anchor.append(text_span)
        icon = soup.new_tag(
            "img",
            src=INLINE_ATTACH_ICON,
            alt="",
            width=INLINE_ATTACH_ICON_SIZE,
            height=INLINE_ATTACH_ICON_SIZE,
            **{
                "class": INLINE_ATTACH_ICON_CLASS,
                "aria-hidden": "true",
                "decoding": "async",
                "loading": "lazy",
            },
        )
        anchor.append(icon)
        anchor.append(sr)
        return True

    if link_type == "view-doc":
        anchor["class"] = [*preserved_classes, INLINE_VIEW_DOC_LINK_CLASS]
        anchor["target"] = "_blank"
        anchor["rel"] = "noopener noreferrer"
        text_span["class"] = "internal-article-view-doc-link__text"
        suffix = soup.new_tag("span", attrs={"class": "internal-article-view-doc-link__suffix"})
        suffix.string = "відкрити документ"
        sr.string = " (відкрити документ у новій вкладці)"
        anchor.append(text_span)
        anchor.append(suffix)
        anchor.append(build_external_link_icon_tag(soup, INLINE_EXTERNAL_LINK_ICON_CLASS))
        anchor.append(sr)
        return True

    return False


def _external_link_icon_is_current(icon: Tag | None) -> bool:
    if not icon:
        return False
    src = icon.get("src") or ""
    return src == EXTERNAL_LINK_ARROW_ICON or src.endswith("/Arrow small 45.svg")


def normalize_external_link_icons(soup: BeautifulSoup) -> bool:
    changed = False
    content = soup.select_one(".internal-article-content") or soup.select_one(".internal-main")
    if not content:
        return False
    targets = (
        ("a.internal-article-external-link", INLINE_EXTERNAL_LINK_ICON_CLASS),
        ("a.internal-article-view-doc-link", INLINE_EXTERNAL_LINK_ICON_CLASS),
        ("a.internal-article-legal-basis__link", LEGAL_BASIS_ICON_CLASS),
    )
    for selector, icon_class in targets:
        for anchor in content.select(selector):
            for old_svg in anchor.select("svg"):
                old_svg.decompose()
                changed = True
            icon = anchor.select_one(f"img.{icon_class}")
            if _external_link_icon_is_current(icon) and icon.get("width") == EXTERNAL_LINK_ICON_SIZE:
                continue
            if icon:
                icon["src"] = EXTERNAL_LINK_ARROW_ICON
                icon["width"] = EXTERNAL_LINK_ICON_SIZE
                icon["height"] = EXTERNAL_LINK_ICON_SIZE
                changed = True
                continue
            sr = anchor.select_one(
                ".internal-article-link__sr-only, .internal-article-legal-basis__sr-only"
            )
            new_icon = build_external_link_icon_tag(soup, icon_class)
            if sr:
                sr.insert_before(new_icon)
            else:
                anchor.append(new_icon)
            changed = True
    return changed


def normalize_inline_doc_link_icons(soup: BeautifulSoup) -> bool:
    changed = False
    content = soup.select_one(".internal-article-content") or soup.select_one(".internal-main")
    if not content:
        return False
    for anchor in content.select("a.internal-article-doc-link"):
        icon = anchor.select_one(f"img.{INLINE_ATTACH_ICON_CLASS}")
        if (
            icon
            and icon.get("src") == INLINE_ATTACH_ICON
            and icon.get("width") == INLINE_ATTACH_ICON_SIZE
        ):
            continue
        if icon:
            icon["src"] = INLINE_ATTACH_ICON
            icon["width"] = INLINE_ATTACH_ICON_SIZE
            icon["height"] = INLINE_ATTACH_ICON_SIZE
            changed = True
            continue
        text_el = anchor.select_one(".internal-article-doc-link__text")
        sr = anchor.select_one(".internal-article-link__sr-only")
        new_icon = soup.new_tag(
            "img",
            src=INLINE_ATTACH_ICON,
            alt="",
            width=INLINE_ATTACH_ICON_SIZE,
            height=INLINE_ATTACH_ICON_SIZE,
            **{
                "class": INLINE_ATTACH_ICON_CLASS,
                "aria-hidden": "true",
                "decoding": "async",
                "loading": "lazy",
            },
        )
        if sr:
            sr.insert_before(new_icon)
        elif text_el:
            text_el.insert_after(new_icon)
        else:
            anchor.append(new_icon)
        changed = True
    return changed


def inline_link_normalize_root(soup: BeautifulSoup) -> Tag | None:
    return (
        soup.select_one(".internal-article-content")
        or soup.select_one(".internal-main")
        or soup.select_one("main")
    )


def repair_header_foreigners_links(soup: BeautifulSoup) -> bool:
    """Restore header For Foreigners link if article inline-link decoration leaked in."""
    header = soup.select_one("header")
    if not header:
        return False

    changed = False
    for link in header.select('a[href*="foreigners.navigator"]'):
        classes = [cls for cls in (link.get("class") or []) if cls != INLINE_EXTERNAL_LINK_CLASS]
        if "css-bho8e5" not in classes:
            classes.append("css-bho8e5")
        if "css-clvzh3" in classes:
            classes = [cls for cls in classes if cls != "css-clvzh3"]
        if classes != list(link.get("class") or []):
            link["class"] = classes
            changed = True

        for attr in ("target", "rel"):
            if attr in link.attrs:
                del link[attr]
                changed = True

        icon = link.select_one(".header-foreigners-link__icon")
        label = link.select_one(".mantine-Text-root")
        if (
            icon
            and label
            and label.get_text(strip=True) == HEADER_FOREIGNERS_LABEL
            and icon.get("width") == "18"
            and not link.select_one(".internal-article-link__sr-only")
            and not link.select_one(f".{INLINE_EXTERNAL_LINK_ICON_CLASS}")
        ):
            continue

        for svg in link.select("svg"):
            svg.decompose()
            changed = True

        link.clear()
        wrap = soup.new_tag("div")
        wrap["class"] = ["mantine-1uguyhf"]
        icon = soup.new_tag(
            "img",
            src=HEADER_LANGUAGE_ICON,
            alt="",
            width="18",
            height="18",
        )
        icon["class"] = ["header-foreigners-link__icon"]
        icon["aria-hidden"] = "true"
        label = soup.new_tag("div")
        label["class"] = ["mantine-Text-root", "mantine-ykctob"]
        label.string = HEADER_FOREIGNERS_LABEL
        wrap.append(icon)
        wrap.append(label)
        link.append(wrap)
        changed = True
    return changed


def repair_site_footer_links(soup: BeautifulSoup) -> bool:
    """Strip article-style external-link decoration accidentally applied to footer."""
    footer = soup.select_one("footer")
    if not footer:
        return False

    changed = False
    for anchor in footer.select("a.site-footer__link"):
        classes = anchor.get("class") or []
        if not (
            INLINE_EXTERNAL_LINK_CLASS in classes
            or anchor.select_one(".internal-article-link__sr-only")
            or anchor.select_one(".internal-article-external-link__icon")
        ):
            continue

        href = anchor.get("href") or ""
        text = extract_inline_link_text(anchor)
        if not text:
            text = re.sub(r"\s*\(відкривається в новій вкладці\)\s*", " ", anchor.get_text(" ", strip=True)).strip()

        anchor.clear()
        anchor["class"] = ["site-footer__link"]
        anchor["href"] = href
        if href.startswith("http://") or href.startswith("https://"):
            anchor["target"] = "_blank"
            anchor["rel"] = "noopener noreferrer"
        else:
            anchor.attrs.pop("target", None)
            anchor.attrs.pop("rel", None)
        anchor.string = text
        changed = True
    return changed


def normalize_inline_article_links(soup: BeautifulSoup) -> bool:
    changed = False
    content = inline_link_normalize_root(soup)
    if not content:
        return False
    for anchor in content.find_all("a", href=True):
        if should_skip_inline_link_decor(anchor):
            continue
        href = anchor.get("href") or ""
        link_type = classify_inline_article_link(href)
        if link_type == "view-doc" and is_inside_additional_sources_section(anchor):
            link_type = "external"
        if not link_type:
            continue
        if decorate_inline_link(anchor, soup, link_type):
            changed = True
    if repair_site_footer_links(soup):
        changed = True
    return changed


def normalize_document_download_blocks(soup: BeautifulSoup) -> bool:
    changed = False
    for anchor in soup.select(".internal-article-content .mantine-1fv3ct a.css-uex5rt"):
        href = anchor.get("href") or ""
        normalized_href = normalize_document_href(href)
        if normalized_href != href:
            anchor["href"] = normalized_href
            changed = True

        inner = anchor.select_one(".css-1h5x3dy, .mantine-1qq82n7")
        if not inner:
            continue

        title_el = inner.select_one(f".{DOCUMENT_CARD_TITLE_CLASS}") or inner.select_one(
            ".css-enb2gh"
        )
        label = clean_document_card_label(
            title_el.get_text(strip=True) if title_el else "Документ"
        )
        ext, size, storage = resolve_file_metadata(normalized_href or href)
        meta_text = format_file_meta(ext, size, storage)

        has_new_layout = inner.select_one(f".{DOCUMENT_CARD_META_CLASS}") is not None
        meta_el = inner.select_one(f".{DOCUMENT_CARD_META_CLASS}")
        current_meta = meta_el.get_text(strip=True) if meta_el else ""
        badge_el = inner.select_one(f".{DOCUMENT_CARD_BADGE_CLASS}")
        current_badge = badge_el.get_text(strip=True) if badge_el else ""
        current_title = title_el.get_text(strip=True) if title_el else ""

        if (
            has_new_layout
            and DOCUMENT_CARD_CLASS in (inner.get("class") or [])
            and current_meta == meta_text
            and current_badge == badge_label(ext)
            and current_title == label
        ):
            download_icon = inner.select_one('img[alt="file-icon"]')
            if download_icon:
                src = download_icon.get("src") or ""
                if DOCUMENT_DOWNLOAD_ICON not in src:
                    download_icon["src"] = DOCUMENT_DOWNLOAD_ICON
                    changed = True
                if download_icon.get("width"):
                    del download_icon["width"]
                    changed = True
                if download_icon.get("height"):
                    del download_icon["height"]
                    changed = True
            continue

        anchor.clear()
        anchor["class"] = "css-uex5rt"
        anchor["download"] = ""
        anchor["target"] = "_blank"
        anchor.append(build_document_card_inner(soup, label, ext, meta_text))
        changed = True
    return changed


BULLET_PREFIX_RE = re.compile(
    r"^\s*(?:[\-–—−‐‒↓•]|[а-яіїєґa-zA-Z][\)\.])\s*",
    re.IGNORECASE,
)
NUMBERED_PREFIX_RE = re.compile(r"^\s*\d+[\)\.]\s*")
BULLET_DIV_CLASS = "mantine-172zsy7"
ARTICLE_LIST_CLASS = "internal-article-list"
NUMBERED_LIST_CLASS = "internal-article-numbered-list"
DOUBLE_BR_RE = re.compile(r"(?:<br\s*/?>\s*){2,}")
LEADING_WS_RE = re.compile(r"^[\s\u00a0\t]+")
INTERNAL_WS_RE = re.compile(r"[ \u00a0\t]+")


def _segment_text(segment: list) -> str:
    wrapper = BeautifulSoup("", "html.parser")
    container = wrapper.new_tag("div")
    for node in segment:
        if isinstance(node, NavigableString):
            container.append(NavigableString(str(node)))
        else:
            container.append(node)
    return container.get_text(" ", strip=True)


def _is_bullet_segment(segment: list) -> bool:
    return bool(BULLET_PREFIX_RE.match(_segment_text(segment)))


def _strip_bullet_prefix(container: Tag) -> None:
    for node in container.descendants:
        if isinstance(node, NavigableString):
            stripped = BULLET_PREFIX_RE.sub("", str(node), count=1)
            if stripped != str(node):
                node.replace_with(stripped)
                return


def _split_nodes_by_br(nodes: list) -> list[list]:
    segments: list[list] = [[]]
    for node in nodes:
        if isinstance(node, Tag) and node.name == "br":
            if segments[-1]:
                segments.append([])
            continue
        segments[-1].append(node)
    return [segment for segment in segments if segment]


def _append_nodes(parent: Tag, segment: list) -> None:
    for node in segment:
        parent.append(node)


def _make_bullet_list(soup: BeautifulSoup, segments: list[list]) -> Tag:
    ul = soup.new_tag("ul", attrs={"class": ARTICLE_LIST_CLASS})
    for segment in segments:
        li = soup.new_tag("li")
        _append_nodes(li, segment)
        _strip_bullet_prefix(li)
        ul.append(li)
    return ul


def _trim_edge_breaks(nodes: list) -> list:
    trimmed = list(nodes)
    while trimmed and (
        (isinstance(trimmed[-1], Tag) and trimmed[-1].name == "br")
        or (isinstance(trimmed[-1], NavigableString) and not str(trimmed[-1]).strip())
    ):
        trimmed.pop()
    while trimmed and (
        (isinstance(trimmed[0], Tag) and trimmed[0].name == "br")
        or (isinstance(trimmed[0], NavigableString) and not str(trimmed[0]).strip())
    ):
        trimmed.pop(0)
    return trimmed


def _meaningful_br_count(container: Tag) -> int:
    return sum(
        1
        for node in _trim_edge_breaks(list(container.contents))
        if isinstance(node, Tag) and node.name == "br"
    )


def _div_is_bullet_only(div: Tag) -> bool:
    classes = div.get("class") or []
    if BULLET_DIV_CLASS not in classes:
        return False
    if div.find("ul", class_=ARTICLE_LIST_CLASS):
        return False
    text = div.get_text(" ", strip=True)
    if not BULLET_PREFIX_RE.match(text):
        return False
    return _meaningful_br_count(div) == 0


def _is_annotation_div(div: Tag) -> bool:
    classes = div.get("class") or []
    if BULLET_DIV_CLASS not in classes:
        return False
    text = div.get_text(" ", strip=True)
    if BULLET_PREFIX_RE.match(text):
        return False
    return text.startswith("(") and ")" in text


def _convert_singleton_bullet_divs(soup: BeautifulSoup, root: Tag) -> bool:
    changed = False
    for div in list(root.select(f".{BULLET_DIV_CLASS}")):
        if not _div_is_bullet_only(div):
            continue
        ul = _make_bullet_list(soup, [_trim_edge_breaks(list(div.contents))])
        div.replace_with(ul)
        changed = True
    return changed


def _merge_bullet_lists_across_annotations(soup: BeautifulSoup, root: Tag) -> bool:
    changed = False
    for parent in list(root.find_all(True)):
        child_tags = [child for child in parent.children if isinstance(child, Tag)]
        if not child_tags:
            continue
        i = 0
        while i < len(child_tags):
            child = child_tags[i]
            if child.name != "ul" or ARTICLE_LIST_CLASS not in (child.get("class") or []):
                i += 1
                continue
            group = [child]
            j = i + 1
            while j < len(child_tags):
                nxt = child_tags[j]
                if _is_annotation_div(nxt):
                    j += 1
                    continue
                if nxt.name == "ul" and ARTICLE_LIST_CLASS in (nxt.get("class") or []):
                    group.append(nxt)
                    j += 1
                    continue
                if _div_is_bullet_only(nxt):
                    group.append(nxt)
                    j += 1
                    continue
                break
            if len(group) < 2:
                i += 1
                continue
            anchor = group[0]
            merged = soup.new_tag("ul", attrs={"class": ARTICLE_LIST_CLASS})
            for item in group:
                if item.name == "ul":
                    for li in list(item.find_all("li", recursive=False)):
                        merged.append(li.extract())
                    continue
                li = soup.new_tag("li")
                for node in _trim_edge_breaks(list(item.contents)):
                    li.append(node)
                _strip_bullet_prefix(li)
                merged.append(li)
            anchor.insert_before(merged)
            for item in group:
                item.decompose()
            changed = True
            child_tags = [child for child in parent.children if isinstance(child, Tag)]
            i = child_tags.index(merged) + 1 if merged in child_tags else j
    return changed


def _repair_bullet_div(soup: BeautifulSoup, div: Tag) -> bool:
    if div.find("ul", class_=ARTICLE_LIST_CLASS):
        return False
    if not re.search(r"<br\s*/?>", str(div), re.I):
        return False

    nodes = list(div.contents)
    segments = _split_nodes_by_br(nodes)
    bullet_count = sum(1 for segment in segments if _is_bullet_segment(segment))
    if bullet_count < 1 or len(segments) < 2:
        return False

    if bullet_count >= 2:
        bullet_indices = [index for index, segment in enumerate(segments) if _is_bullet_segment(segment)]
        first_bullet = bullet_indices[0]
        last_bullet = bullet_indices[-1]
        for index in range(first_bullet, last_bullet + 1):
            if not _is_bullet_segment(segments[index]):
                return False

    div.clear()
    bullet_batch: list[list] = []
    changed = False

    def flush_batch() -> None:
        nonlocal changed
        if not bullet_batch:
            return
        div.append(_make_bullet_list(soup, bullet_batch))
        bullet_batch.clear()
        changed = True

    for index, segment in enumerate(segments):
        if _is_bullet_segment(segment):
            bullet_batch.append(segment)
            continue
        flush_batch()
        _append_nodes(div, segment)
        next_segment = segments[index + 1] if index + 1 < len(segments) else None
        if next_segment and not _is_bullet_segment(next_segment):
            div.append(soup.new_tag("br"))
    flush_batch()
    return changed


def _direct_edge_list(container: Tag, edge: str) -> Tag | None:
    child_tags = [child for child in container.children if isinstance(child, Tag)]
    if not child_tags:
        return None
    target = child_tags[-1] if edge == "last" else child_tags[0]
    if target.name != "ul" or ARTICLE_LIST_CLASS not in (target.get("class") or []):
        return None
    return target


def _merge_adjacent_div_bullet_lists(root: Tag) -> bool:
    changed = False
    for parent in list(root.find_all(True)):
        child_tags = [child for child in parent.children if isinstance(child, Tag)]
        i = 0
        while i < len(child_tags) - 1:
            current = child_tags[i]
            nxt = child_tags[i + 1]
            classes = current.get("class") or []
            next_classes = nxt.get("class") or []
            if BULLET_DIV_CLASS not in classes or BULLET_DIV_CLASS not in next_classes:
                i += 1
                continue
            trailing = _direct_edge_list(current, "last")
            leading = _direct_edge_list(nxt, "first")
            if not trailing or not leading:
                i += 1
                continue
            for li in list(leading.find_all("li", recursive=False)):
                trailing.append(li.extract())
            leading.decompose()
            changed = True
            child_tags = [child for child in parent.children if isinstance(child, Tag)]
            i += 1
    return changed


def _p_is_bullet_only(p: Tag) -> bool:
    if p.name != "p":
        return False
    classes = p.get("class") or []
    if PRIVACY_BODY_P_CLASS not in classes:
        return False
    if p.find("ul", class_=ARTICLE_LIST_CLASS):
        return False
    text = p.get_text(" ", strip=True)
    if not BULLET_PREFIX_RE.match(text):
        return False
    return _meaningful_br_count(p) == 0


def _convert_singleton_bullet_paragraphs(soup: BeautifulSoup, root: Tag) -> bool:
    changed = False
    for p in list(root.select(f"p.{PRIVACY_BODY_P_CLASS}")):
        if not _p_is_bullet_only(p):
            continue
        ul = _make_bullet_list(soup, [_trim_edge_breaks(list(p.contents))])
        p.replace_with(ul)
        changed = True
    return changed


def _merge_consecutive_bullet_paragraphs(soup: BeautifulSoup, root: Tag) -> bool:
    changed = False
    for parent in list(root.find_all(True)):
        child_tags = [child for child in parent.children if isinstance(child, Tag)]
        if not child_tags:
            continue
        i = 0
        while i < len(child_tags):
            child = child_tags[i]
            if not _p_is_bullet_only(child):
                i += 1
                continue
            group = [child]
            j = i + 1
            while j < len(child_tags) and _p_is_bullet_only(child_tags[j]):
                group.append(child_tags[j])
                j += 1
            ul = _make_bullet_list(
                soup,
                [_trim_edge_breaks(list(item.contents)) for item in group],
            )
            group[0].insert_before(ul)
            for item in group:
                item.decompose()
            changed = True
            child_tags = [child for child in parent.children if isinstance(child, Tag)]
            i = child_tags.index(ul) + 1 if ul in child_tags else j
    return changed


def _dedupe_bullet_list_intro_paragraph(root: Tag) -> bool:
    changed = False
    for ul in root.select(f"ul.{ARTICLE_LIST_CLASS}"):
        prev = ul.find_previous_sibling()
        while prev and isinstance(prev, Tag) and prev.name == "style":
            prev = prev.find_previous_sibling()
        if not prev or prev.name != "p":
            continue
        first_li = ul.find("li", recursive=False)
        if not first_li:
            continue
        if prev.get_text(" ", strip=True) != first_li.get_text(" ", strip=True):
            continue
        first_li.decompose()
        changed = True
    return changed


def _merge_consecutive_bullet_divs(soup: BeautifulSoup, root: Tag) -> bool:
    changed = False
    for parent in list(root.find_all(True)):
        child_tags = [child for child in parent.children if isinstance(child, Tag)]
        if not child_tags:
            continue
        i = 0
        while i < len(child_tags):
            child = child_tags[i]
            if not _div_is_bullet_only(child):
                i += 1
                continue
            group = [child]
            j = i + 1
            while j < len(child_tags) and _div_is_bullet_only(child_tags[j]):
                group.append(child_tags[j])
                j += 1
            ul = _make_bullet_list(soup, [_trim_edge_breaks(list(item.contents)) for item in group])
            group[0].insert_before(ul)
            for item in group:
                item.decompose()
            changed = True
            child_tags = [child for child in parent.children if isinstance(child, Tag)]
            i = child_tags.index(ul) + 1 if ul in child_tags else j
    return changed


LONE_LI_WRAPPER_CLASS = "css-1vd3b3g"
LONE_LI_SHELL_CLASS = "mantine-1jggmkl"


def _div_is_lone_bullet_li_div(div: Tag) -> bool:
    classes = div.get("class") or []
    if LONE_LI_WRAPPER_CLASS not in classes or LONE_LI_SHELL_CLASS not in classes:
        return False
    if div.find("ul", class_=ARTICLE_LIST_CLASS) or div.find("ol", class_=NUMBERED_LIST_CLASS):
        return False
    lis = div.find_all("li", recursive=False)
    if len(lis) != 1:
        return False
    text = lis[0].get_text(" ", strip=True)
    return bool(BULLET_PREFIX_RE.match(text))


def _li_from_lone_bullet_div(soup: BeautifulSoup, div: Tag) -> Tag:
    source_li = div.find("li", recursive=False)
    li = soup.new_tag("li")
    for node in _trim_edge_breaks(list(source_li.contents)):
        if isinstance(node, NavigableString):
            li.append(NavigableString(str(node)))
        else:
            li.append(node.extract())
    _strip_bullet_prefix(li)
    _strip_edge_breaks_from_tag(li)
    return li


def _merge_consecutive_lone_li_bullet_divs(soup: BeautifulSoup, root: Tag) -> bool:
    changed = False
    for parent in list(root.find_all(True)):
        child_tags = [child for child in parent.children if isinstance(child, Tag)]
        if not child_tags:
            continue
        i = 0
        while i < len(child_tags):
            child = child_tags[i]
            if not _div_is_lone_bullet_li_div(child):
                i += 1
                continue
            group = [child]
            j = i + 1
            while j < len(child_tags) and _div_is_lone_bullet_li_div(child_tags[j]):
                group.append(child_tags[j])
                j += 1
            ul = soup.new_tag("ul", attrs={"class": ARTICLE_LIST_CLASS})
            for item in group:
                ul.append(_li_from_lone_bullet_div(soup, item))
            group[0].insert_before(ul)
            for item in group:
                item.decompose()
            changed = True
            child_tags = [child for child in parent.children if isinstance(child, Tag)]
            i = child_tags.index(ul) + 1 if ul in child_tags else j
    return changed


def _is_numbered_segment(segment: list) -> bool:
    return bool(NUMBERED_PREFIX_RE.match(_segment_text(segment)))


def _strip_numbered_prefix(container: Tag) -> None:
    for node in container.descendants:
        if isinstance(node, NavigableString):
            stripped = NUMBERED_PREFIX_RE.sub("", str(node), count=1)
            if stripped != str(node):
                node.replace_with(stripped)
                return


def _make_numbered_list(soup: BeautifulSoup, segments: list[list]) -> Tag:
    ol = soup.new_tag("ol", attrs={"class": NUMBERED_LIST_CLASS})
    for segment in segments:
        li = soup.new_tag("li")
        _append_nodes(li, segment)
        _strip_numbered_prefix(li)
        ol.append(li)
    return ol


def _div_is_numbered_only(div: Tag) -> bool:
    classes = div.get("class") or []
    if BULLET_DIV_CLASS not in classes:
        return False
    if div.find("ul", class_=ARTICLE_LIST_CLASS) or div.find("ol", class_=NUMBERED_LIST_CLASS):
        return False
    text = div.get_text(" ", strip=True)
    if not NUMBERED_PREFIX_RE.match(text):
        return False
    if BULLET_PREFIX_RE.match(text):
        return False
    return _meaningful_br_count(div) == 0


def _repair_numbered_div(soup: BeautifulSoup, div: Tag) -> bool:
    if div.find("ol", class_=NUMBERED_LIST_CLASS):
        return False
    if not re.search(r"<br\s*/?>", str(div), re.I):
        return False

    nodes = list(div.contents)
    segments = _split_nodes_by_br(nodes)
    numbered_count = sum(1 for segment in segments if _is_numbered_segment(segment))
    if numbered_count < 2:
        return False

    numbered_indices = [index for index, segment in enumerate(segments) if _is_numbered_segment(segment)]
    first_numbered = numbered_indices[0]
    last_numbered = numbered_indices[-1]
    for index in range(first_numbered, last_numbered + 1):
        if not _is_numbered_segment(segments[index]):
            return False

    div.clear()
    numbered_batch: list[list] = []
    changed = False

    def flush_batch() -> None:
        nonlocal changed
        if not numbered_batch:
            return
        div.append(_make_numbered_list(soup, numbered_batch))
        numbered_batch.clear()
        changed = True

    for index, segment in enumerate(segments):
        if _is_numbered_segment(segment):
            numbered_batch.append(segment)
            continue
        flush_batch()
        _append_nodes(div, segment)
        next_segment = segments[index + 1] if index + 1 < len(segments) else None
        if next_segment and not _is_numbered_segment(next_segment):
            div.append(soup.new_tag("br"))
    flush_batch()
    return changed


def _merge_consecutive_numbered_divs(soup: BeautifulSoup, root: Tag) -> bool:
    changed = False
    for parent in list(root.find_all(True)):
        child_tags = [child for child in parent.children if isinstance(child, Tag)]
        if not child_tags:
            continue
        i = 0
        while i < len(child_tags):
            child = child_tags[i]
            if not _div_is_numbered_only(child):
                i += 1
                continue
            group = [child]
            j = i + 1
            while j < len(child_tags) and _div_is_numbered_only(child_tags[j]):
                group.append(child_tags[j])
                j += 1
            ol = _make_numbered_list(
                soup,
                [_trim_edge_breaks(list(item.contents)) for item in group],
            )
            group[0].insert_before(ol)
            for item in group:
                item.decompose()
            changed = True
            child_tags = [child for child in parent.children if isinstance(child, Tag)]
            i = child_tags.index(ol) + 1 if ol in child_tags else j
    return changed


def _merge_numbered_lists_across_annotations(soup: BeautifulSoup, root: Tag) -> bool:
    changed = False
    for parent in list(root.find_all(True)):
        child_tags = [child for child in parent.children if isinstance(child, Tag)]
        if not child_tags:
            continue
        i = 0
        while i < len(child_tags):
            child = child_tags[i]
            if child.name != "ol" or NUMBERED_LIST_CLASS not in (child.get("class") or []):
                i += 1
                continue
            group = [child]
            j = i + 1
            while j < len(child_tags):
                nxt = child_tags[j]
                if _is_annotation_div(nxt):
                    j += 1
                    continue
                if nxt.name == "ol" and NUMBERED_LIST_CLASS in (nxt.get("class") or []):
                    group.append(nxt)
                    j += 1
                    continue
                if _div_is_numbered_only(nxt):
                    group.append(nxt)
                    j += 1
                    continue
                break
            if len(group) < 2:
                i += 1
                continue
            anchor = group[0]
            merged = soup.new_tag("ol", attrs={"class": NUMBERED_LIST_CLASS})
            for item in group:
                if item.name == "ol":
                    for li in list(item.find_all("li", recursive=False)):
                        merged.append(li.extract())
                    continue
                li = soup.new_tag("li")
                for node in _trim_edge_breaks(list(item.contents)):
                    li.append(node)
                _strip_numbered_prefix(li)
                merged.append(li)
            anchor.insert_before(merged)
            for item in group:
                item.decompose()
            changed = True
            child_tags = [child for child in parent.children if isinstance(child, Tag)]
            i = child_tags.index(merged) + 1 if merged in child_tags else j
    return changed


def repair_numbered_lists(soup: BeautifulSoup) -> bool:
    content = soup.select_one(".internal-article-content")
    if not content:
        return False
    changed = False
    for div in list(content.select(f".{BULLET_DIV_CLASS}")):
        if _repair_numbered_div(soup, div):
            changed = True
    if _merge_consecutive_numbered_divs(soup, content):
        changed = True
    if _merge_numbered_lists_across_annotations(soup, content):
        changed = True
    return changed


def _strip_edge_breaks_from_tag(container: Tag) -> bool:
    changed = False
    while container.contents:
        node = container.contents[-1]
        if isinstance(node, Tag) and node.name == "br":
            node.decompose()
            changed = True
            continue
        if isinstance(node, NavigableString) and not str(node).strip():
            node.extract()
            changed = True
            continue
        break
    while container.contents:
        node = container.contents[0]
        if isinstance(node, Tag) and node.name == "br":
            node.decompose()
            changed = True
            continue
        if isinstance(node, NavigableString) and not str(node).strip():
            node.extract()
            changed = True
            continue
        break
    return changed


def _collapse_consecutive_breaks(container: Tag) -> bool:
    changed = False
    previous_was_break = False
    for node in list(container.contents):
        if isinstance(node, Tag) and node.name == "br":
            if previous_was_break:
                node.decompose()
                changed = True
                continue
            previous_was_break = True
            continue
        if isinstance(node, NavigableString) and not str(node).strip():
            continue
        previous_was_break = False
    return changed


def _is_empty_text_container(el: Tag) -> bool:
    if el.get_text(strip=True):
        return False
    return not el.find(["img", "a", "table", "ul", "ol", "iframe", "svg", "video", "audio"])


def _section_wrap_content_tags(section: Tag) -> list[Tag]:
    return [
        child
        for child in section.children
        if isinstance(child, Tag) and child.name != "style"
    ]


def _is_card_only_section(section: Tag) -> bool:
    if "mantine-1fr50if" not in (section.get("class") or []):
        return False
    tags = _section_wrap_content_tags(section)
    return bool(tags) and all("css-sdnfq3" in (tag.get("class") or []) for tag in tags)


def remove_section_card_spacers(soup: BeautifulSoup) -> bool:
    content = soup.select_one(".internal-article-content")
    if not content:
        return False
    changed = False
    for section in content.select(".mantine-1fr50if"):
        for child in list(section.children):
            if not isinstance(child, Tag) or child.name == "style":
                continue
            if "css-sdnfq3" in (child.get("class") or []):
                break
            if _is_empty_text_container(child):
                child.decompose()
                changed = True
            else:
                break
    return changed


def merge_consecutive_article_card_sections(soup: BeautifulSoup) -> bool:
    content = soup.select_one(".internal-article-content")
    if not content:
        return False
    container = content.select_one(".css-64gglc")
    if not container:
        return False
    changed = False
    while True:
        sections = [
            child
            for child in container.children
            if isinstance(child, Tag) and "mantine-1fr50if" in (child.get("class") or [])
        ]
        merged_once = False
        for index in range(len(sections) - 1):
            first, second = sections[index], sections[index + 1]
            if not (_is_card_only_section(first) and _is_card_only_section(second)):
                continue
            for node in list(second.children):
                if isinstance(node, Tag):
                    first.append(node.extract())
            second.decompose()
            changed = True
            merged_once = True
            break
        if not merged_once:
            break
    return changed


def repair_article_card_sections(soup: BeautifulSoup) -> bool:
    changed = remove_section_card_spacers(soup)
    if merge_consecutive_article_card_sections(soup):
        changed = True
    return changed


def remove_paragraph_spacer_breaks(soup: BeautifulSoup) -> bool:
    content = soup.select_one(".internal-article-content")
    if not content:
        return False
    changed = False
    for el in list(content.select(f".{BULLET_DIV_CLASS}, p, .internal-article-intro")):
        if _collapse_consecutive_breaks(el):
            changed = True
        if _strip_edge_breaks_from_tag(el):
            changed = True
        if _is_empty_text_container(el):
            el.decompose()
            changed = True
    return changed


def remove_empty_mantine_1fv3ct(soup: BeautifulSoup) -> bool:
    content = soup.select_one(".internal-article-content")
    if not content:
        return False
    changed = False
    for el in list(content.select(".mantine-1fv3ct")):
        if _is_empty_text_container(el):
            el.decompose()
            changed = True
    return changed


def collapse_article_whitespace(soup: BeautifulSoup) -> bool:
    content = soup.select_one(".internal-article-content")
    if not content:
        return False
    changed = False
    for node in content.find_all(string=True):
        if not isinstance(node, NavigableString):
            continue
        parent = node.parent
        if parent and parent.name in ("script", "style"):
            continue
        original = str(node)
        if not original:
            continue
        normalized = INTERNAL_WS_RE.sub(" ", original)
        if not normalized.strip():
            if original:
                node.replace_with("")
                changed = True
            continue
        if normalized != original:
            node.replace_with(normalized)
            changed = True
    return changed


def _trim_leading_text(container: Tag) -> bool:
    changed = False
    for node in container.descendants:
        if not isinstance(node, NavigableString):
            continue
        text = str(node)
        if not text.strip():
            if text:
                node.replace_with("")
                changed = True
            continue
        trimmed = LEADING_WS_RE.sub("", text)
        if trimmed != text:
            node.replace_with(trimmed)
            changed = True
        return changed
    return changed


def trim_leading_paragraph_whitespace(soup: BeautifulSoup) -> bool:
    content = soup.select_one(".internal-article-content")
    if not content:
        return False
    changed = False
    for el in content.select(f".{BULLET_DIV_CLASS}, p, .internal-article-intro"):
        if _trim_leading_text(el):
            changed = True
    return changed


def _continuation_starts_lowercase(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped:
        return False
    return stripped[0].islower() or stripped[0] in "іїє"


def _li_bold_lead_tag(li: Tag) -> Tag | None:
    for node in li.children:
        if isinstance(node, NavigableString) and not str(node).strip():
            continue
        if isinstance(node, Tag) and node.name in ("b", "strong") and node.get_text(strip=True):
            return node
        return None
    return None


def _li_continuation_text(li: Tag, bold: Tag) -> str:
    parts: list[str] = []
    after_bold = False
    for node in li.children:
        if node is bold:
            after_bold = True
            continue
        if not after_bold:
            continue
        if isinstance(node, NavigableString):
            parts.append(str(node))
        else:
            parts.append(node.get_text())
    return "".join(parts)


def _split_bold_lead_from_single_item_list(soup: BeautifulSoup, ul: Tag, li: Tag) -> bool:
    classes = ul.get("class") or []
    if ARTICLE_LIST_CLASS not in classes:
        return False
    if len(ul.find_all("li", recursive=False)) != 1:
        return False
    bold = _li_bold_lead_tag(li)
    if not bold:
        return False
    bold_text = bold.get_text(strip=True)
    if len(bold_text) < 15:
        return False
    continuation_text = _li_continuation_text(li, bold)
    if not _continuation_starts_lowercase(continuation_text):
        return False

    continuation_nodes: list = []
    after_bold = False
    for node in list(li.children):
        if node is bold:
            after_bold = True
            continue
        if after_bold:
            continuation_nodes.append(node.extract())

    div = soup.new_tag("div", attrs={"class": ["mantine-Text-root", BULLET_DIV_CLASS]})
    div.append(bold.extract())
    ul.insert_before(div)

    li.clear()
    for node in continuation_nodes:
        li.append(node)
    if li.contents and isinstance(li.contents[0], NavigableString):
        first = str(li.contents[0])
        stripped = first.lstrip()
        if stripped != first:
            li.contents[0].replace_with(stripped)
    return True


def _strip_leading_breaks_from_li(li: Tag) -> bool:
    changed = False
    while li.contents:
        node = li.contents[0]
        if isinstance(node, NavigableString) and not str(node).strip():
            node.extract()
            changed = True
            continue
        if isinstance(node, Tag) and node.name == "br":
            node.decompose()
            changed = True
            continue
        if isinstance(node, Tag) and node.name in ("b", "strong") and not node.get_text(strip=True):
            node.decompose()
            changed = True
            continue
        break
    return changed


def _strip_trailing_breaks_from_li(li: Tag) -> bool:
    changed = False
    while li.contents:
        node = li.contents[-1]
        if isinstance(node, NavigableString) and not str(node).strip():
            node.extract()
            changed = True
            continue
        if isinstance(node, Tag) and node.name == "br":
            node.decompose()
            changed = True
            continue
        break
    return changed


def _merge_div_trailing_list_with_sibling_ul(root: Tag) -> bool:
    changed = False
    for parent in list(root.find_all(True)):
        child_tags = [child for child in parent.children if isinstance(child, Tag)]
        i = 0
        while i < len(child_tags) - 1:
            current = child_tags[i]
            nxt = child_tags[i + 1]
            classes = current.get("class") or []
            if BULLET_DIV_CLASS not in classes:
                i += 1
                continue
            if nxt.name != "ul" or ARTICLE_LIST_CLASS not in (nxt.get("class") or []):
                i += 1
                continue
            trailing = _direct_edge_list(current, "last")
            if not trailing:
                i += 1
                continue
            for li in list(nxt.find_all("li", recursive=False)):
                trailing.append(li.extract())
            nxt.decompose()
            changed = True
            child_tags = [child for child in parent.children if isinstance(child, Tag)]
    return changed


def _merge_adjacent_sibling_uls(root: Tag) -> bool:
    changed = False
    for parent in list(root.find_all(True)):
        child_tags = [child for child in parent.children if isinstance(child, Tag)]
        i = 0
        while i < len(child_tags) - 1:
            current = child_tags[i]
            nxt = child_tags[i + 1]
            if current.name != "ul" or nxt.name != "ul":
                i += 1
                continue
            if ARTICLE_LIST_CLASS not in (current.get("class") or []):
                i += 1
                continue
            if ARTICLE_LIST_CLASS not in (nxt.get("class") or []):
                i += 1
                continue
            for li in list(nxt.find_all("li", recursive=False)):
                current.append(li.extract())
            nxt.decompose()
            changed = True
            child_tags = [child for child in parent.children if isinstance(child, Tag)]
    return changed


def _repair_all_list_items(content: Tag) -> bool:
    changed = False
    for li in list(content.find_all("li")):
        if _strip_leading_breaks_from_li(li):
            changed = True
        if _strip_trailing_breaks_from_li(li):
            changed = True
        if _collapse_consecutive_breaks(li):
            changed = True
        if _is_empty_text_container(li):
            li.decompose()
            changed = True
    return changed


def repair_split_list_leads(soup: BeautifulSoup) -> bool:
    content = soup.select_one(".internal-article-content")
    if not content:
        return False
    changed = False
    for ul in list(content.select(f"ul.{ARTICLE_LIST_CLASS}")):
        lis = ul.find_all("li", recursive=False)
        if len(lis) != 1:
            continue
        if _split_bold_lead_from_single_item_list(soup, ul, lis[0]):
            changed = True
    if _repair_all_list_items(content):
        changed = True
    return changed


def repair_dash_bullet_lists(soup: BeautifulSoup) -> bool:
    content = soup.select_one(".internal-article-content")
    if not content:
        return False
    changed = False
    if _merge_consecutive_lone_li_bullet_divs(soup, content):
        changed = True
    for div in list(content.select(f".{BULLET_DIV_CLASS}")):
        if _repair_bullet_div(soup, div):
            changed = True
    if _merge_consecutive_bullet_divs(soup, content):
        changed = True
    if _merge_adjacent_div_bullet_lists(content):
        changed = True
    if _merge_div_trailing_list_with_sibling_ul(content):
        changed = True
    if _merge_adjacent_sibling_uls(content):
        changed = True
    if _convert_singleton_bullet_divs(soup, content):
        changed = True
    if _merge_bullet_lists_across_annotations(soup, content):
        changed = True
    if _merge_consecutive_bullet_paragraphs(soup, content):
        changed = True
    if _convert_singleton_bullet_paragraphs(soup, content):
        changed = True
    if _dedupe_bullet_list_intro_paragraph(content):
        changed = True
    if trim_leading_paragraph_whitespace(soup):
        changed = True
    if remove_paragraph_spacer_breaks(soup):
        changed = True
    if remove_empty_mantine_1fv3ct(soup):
        changed = True
    if repair_numbered_lists(soup):
        changed = True
    if repair_split_list_leads(soup):
        changed = True
    if collapse_article_whitespace(soup):
        changed = True
    return changed


def hide_stage_interlinks(soup: BeautifulSoup) -> None:
    for wrap in soup.select(".css-1sz33jp"):
        for el in wrap.select(":scope > .css-1tq4v0d, :scope > .mantine-Carousel-root, :scope > [class*='mantine-Carousel-root']"):
            el.decompose()
    for link in soup.select("a.css-lnlfjp, a.css-1wi3il6"):
        row = link.find_parent(class_=lambda c: c and ("mantine-Carousel-root" in c or "css-1tq4v0d" in c))
        if row:
            row.decompose()
    for el in soup.select(".css-1iehrax, .mantine-73o8aw.css-1iehrax"):
        el.decompose()


def remove_duplicate_toc_sections(content_host: Tag) -> bool:
    if not content_host.select_one(".internal-article-toc"):
        return False

    removed = False
    for child in list(content_host.children):
        if not isinstance(child, Tag):
            continue
        if child.name != "section":
            continue
        classes = child.get("class") or []
        if not {"css-1napgkq", "css-1m99gl8", "css-t97qev"} & set(classes):
            continue
        if child.select_one(".css-2y3zsr, .css-1sz33jp"):
            child.decompose()
            removed = True
    return removed


def _about_section_block(
    soup: BeautifulSoup,
    section_id: str,
    heading: Tag,
    content_nodes: list[Tag],
) -> Tag:
    """Wrap a section title and body in a white card (about page)."""
    block = soup.new_tag("div", attrs={"class": "mantine-wnhdd8", "id": section_id})
    card = soup.new_tag("div", attrs={"class": "css-sdnfq3 mantine-1hdrj7p"})
    _ensure_section_h2(heading)
    card.append(heading.extract())
    for node in content_nodes:
        card.append(node.extract())
    section_h2 = card.find("h2")
    if section_h2:
        demote_about_card_subheadings(card, section_h2)
    block.append(card)
    return block


def _about_faq_item_block(soup: BeautifulSoup, item: Tag) -> Tag | None:
    section_id = item.get("id") or ""
    if not section_id:
        return None

    heading = item.select_one(
        ".mantine-Accordion-label h2, .mantine-Accordion-label h4, "
        ".mantine-Accordion-label .mantine-Title-root"
    )
    panel = item.select_one(".mantine-Accordion-panel")
    if not heading or not panel:
        return None

    content_host = panel.select_one(".mantine-Accordion-content") or panel
    inner = content_host.select_one(".mantine-1fr50if") or content_host
    content_nodes = [child for child in list(inner.children) if isinstance(child, Tag)]
    if not content_nodes:
        content_nodes = [inner]

    h2 = soup.new_tag("h2")
    h2["class"] = heading.get("class") or []
    for cls in ("css-su8tkm", "mantine-1p58xby", SECTION_H2_CLASS):
        if cls not in h2["class"]:
            h2["class"].append(cls)
    h2.string = heading.get_text(strip=True)
    return _about_section_block(soup, section_id, h2, content_nodes)


def repair_about_faq_order(sections_wrap: Tag) -> bool:
    """Place the FAQ group header before its items and restore question order."""
    group_header = sections_wrap.select_one(":scope > .mantine-vgkn1f")
    if not group_header:
        return False

    faq_blocks: list[Tag] = []
    partners_block: Tag | None = None
    abbrev_block: Tag | None = None
    for child in sections_wrap.children:
        if not isinstance(child, Tag):
            continue
        if child is group_header:
            continue
        classes = child.get("class") or []
        if "mantine-wnhdd8" not in classes:
            continue
        section_id = child.get("id") or ""
        if section_id == "Скорочення_та_абревіатури":
            abbrev_block = child
        elif section_id == "Наші_партнери":
            partners_block = child
        else:
            faq_blocks.append(child)

    if not faq_blocks:
        return False

    first_id = faq_blocks[0].get("id") or ""
    if first_id.startswith("Чи_надаєте"):
        ordered = faq_blocks
    elif first_id.startswith("Якщо"):
        ordered = list(reversed(faq_blocks))
    else:
        ordered = faq_blocks

    children = [c for c in sections_wrap.children if isinstance(c, Tag)]
    try:
        header_idx = children.index(group_header)
        first_faq_idx = children.index(ordered[0])
    except ValueError:
        header_idx = -1
        first_faq_idx = -1
    if header_idx >= 0 and first_faq_idx == header_idx + 1:
        current_ids = [c.get("id") for c in children[first_faq_idx : first_faq_idx + len(ordered)]]
        if current_ids == [block.get("id") for block in ordered]:
            return False

    for block in faq_blocks:
        block.extract()
    group_header.extract()

    anchor = abbrev_block
    if not isinstance(anchor, Tag):
        anchor = partners_block.find_previous_sibling(lambda tag: isinstance(tag, Tag)) if partners_block else None
    if not isinstance(anchor, Tag):
        return False

    for block in [group_header, *ordered]:
        anchor.insert_after(block)
        anchor = block
    return True


def restructure_about_sections(main_col: Tag, soup: BeautifulSoup) -> bool:
    """Convert about-page sections to css-sdnfq3 cards so gray breaks appear before subheadings."""
    changed = False
    sections_wrap = main_col.select_one(".mantine-1jhay8j")
    if not sections_wrap:
        sections_wrap = soup.new_tag("div", attrs={"class": "mantine-1jhay8j"})
        moved = False
        for child in list(main_col.children):
            if not isinstance(child, Tag):
                continue
            classes = set(child.get("class") or [])
            if child.name == "section" or classes & {"css-1sctyhq"}:
                if not moved:
                    child.insert_before(sections_wrap)
                    moved = True
                sections_wrap.append(child.extract())
        if not moved:
            sections_wrap.decompose()
            return False
        changed = True

    for section in list(sections_wrap.find_all("section", recursive=False)):
        section_id = section.get("id") or ""

        if section_id:
            card = section.select_one(".css-1suv430, .mantine-1hdrj7p")
            heading = section.select_one("h2, h3")
            body = section.select_one(".css-1uu9wx8, .mantine-1fr50if")
            if card and heading and body and heading.parent is card:
                h2 = soup.new_tag("h2")
                h2["class"] = heading.get("class") or []
                if "css-o8yj4d" not in h2["class"]:
                    h2["class"].append("css-o8yj4d")
                if "mantine-1p58xby" not in h2["class"]:
                    h2["class"].append("mantine-1p58xby")
                h2.string = heading.get_text(strip=True)
                block = _about_section_block(soup, section_id, h2, [body])
                section.replace_with(block)
                changed = True
            continue

        faq_items = section.select(".css-g0tr8[id], .mantine-1ng34cm[id]")
        if faq_items:
            group_header = section.select_one(".mantine-vgkn1f")
            new_blocks: list[Tag] = []
            if group_header:
                new_blocks.append(group_header.extract())
            for item in faq_items:
                block = _about_faq_item_block(soup, item)
                if block:
                    new_blocks.append(block)
                    item.decompose()
            if new_blocks:
                anchor = section.find_previous_sibling(
                    lambda tag: isinstance(tag, Tag)
                )
                if not isinstance(anchor, Tag):
                    anchor = section
                    for block in reversed(new_blocks):
                        section.insert_before(block)
                else:
                    for block in new_blocks:
                        anchor.insert_after(block)
                        anchor = block
                section.decompose()
                changed = True
            continue

        partners_heading = section.select_one("h2[id], h3[id]")
        if partners_heading and section.select(".css-1s0m78j, .mantine-1hdrj7p"):
            section_id = partners_heading.get("id") or "partners"
            h2 = soup.new_tag("h2")
            h2["class"] = partners_heading.get("class") or []
            if "css-o8yj4d" not in h2["class"]:
                h2["class"].append("css-o8yj4d")
            if "mantine-1p58xby" not in h2["class"]:
                h2["class"].append("mantine-1p58xby")
            h2.string = partners_heading.get_text(strip=True)
            content_nodes = [
                child
                for child in section.children
                if isinstance(child, Tag) and child is not partners_heading
            ]
            block = _about_section_block(soup, section_id, h2, content_nodes)
            section.replace_with(block)
            changed = True

    if sections_wrap and repair_about_faq_order(sections_wrap):
        changed = True

    return changed


def remove_stage_step_badges(content_host: Tag) -> bool:
    """Remove numbered step circles (1, 2, 3…) before stage headings on documents page."""
    removed = False
    for header in content_host.select(".mantine-j9g3bi"):
        for child in list(header.children):
            if not isinstance(child, Tag) or child.name == "style":
                continue
            classes = set(child.get("class") or [])
            if classes & {"css-13t4hvv", "mantine-11q5icf"}:
                child.decompose()
                removed = True
                break
    return removed


def remove_orphan_toc_columns(content_host: Tag) -> bool:
    removed = False
    for child in list(content_host.children):
        if not isinstance(child, Tag) or child.name == "style":
            continue
        classes = set(child.get("class") or [])
        if "internal-main-header" in classes:
            continue
        if "internal-article-layout" in classes or child.select_one(".internal-article-layout"):
            continue
        if classes & {"css-12mrpgq", "css-gfn0ts", "css-2y3zsr"}:
            child.decompose()
            removed = True
    return removed


def repair_shell_layout(shell: Tag) -> bool:
    content_host = shell.select_one(".internal-main")
    if not content_host:
        return False

    orphaned = None
    for child in shell.children:
        if isinstance(child, Tag) and "internal-article-layout" in (child.get("class") or []):
            orphaned = child
            break

    if not orphaned or orphaned in content_host.descendants:
        return False

    for sec in list(content_host.select("section")):
        if len(sec.get_text(" ", strip=True)) < 20 and not sec.select(".css-7nll2u"):
            sec.decompose()

    header = content_host.select_one(".internal-main-header")
    if header:
        header.insert_after(orphaned.extract())
    else:
        content_host.append(orphaned.extract())
    return True


def _doc_root(node: Tag) -> Tag:
    root = node
    while root.parent is not None:
        root = root.parent
    return root


def unwrap_baked_layout(main: Tag, standalone: bool) -> None:
    shell = main.select_one(".internal-page-shell")
    if shell:
        if standalone and "internal-page-shell--standalone" in (shell.get("class") or []):
            content_host = shell.select_one(".internal-main")
            if content_host:
                header = content_host.select_one(".internal-main-header")
                if header:
                    header.decompose()
                section = _doc_root(main).new_tag("section", attrs={"class": "css-t97qev"})
                for child in list(content_host.children):
                    if isinstance(child, Tag):
                        section.append(child.extract())
                shell.replace_with(section)
            else:
                shell.decompose()
            return

        repair_shell_layout(shell)
        content_host = shell.select_one(".internal-main")
        if content_host:
            header = content_host.select_one(".internal-main-header")
            if header:
                header.decompose()
            for child in list(content_host.children):
                if isinstance(child, Tag):
                    main.append(child.extract())
        shell.decompose()
        return

    for row in main.select(".internal-breadcrumbs-row--standalone"):
        row.decompose()

    layout = main.select_one(".internal-article-layout")
    if not layout:
        return

    white = layout.select_one(".internal-article-content")
    if not white:
        toc_wrap = layout.select_one(".internal-article-toc")
        if toc_wrap:
            for child in list(toc_wrap.children):
                if isinstance(child, Tag):
                    layout.insert_before(child.extract())
            toc_wrap.decompose()
        layout["class"] = [c for c in (layout.get("class") or []) if c != "internal-article-layout"]
        return

    main_col = white.select_one(".css-7nll2u")
    if main_col:
        section = layout.find_parent("section")
        body_row = section.select_one(".css-2y3zsr, .css-k1l4fw") if section else None
        if body_row and main_col not in body_row.descendants:
            body_row.clear()
            body_row.append(main_col.extract())
    layout.decompose()


def restructure_article(
    soup: BeautifulSoup,
    content_host: Tag,
    page_title_text: str,
    breadcrumb_trail: list[dict] | None,
    standalone: bool,
) -> list[tuple[str, str]]:
    body_row = content_host.select_one(".css-2y3zsr, .css-k1l4fw")
    if not body_row:
        return []

    main_col = body_row.select_one(".css-7nll2u")
    toc_col = body_row.select_one(":scope > .css-gfn0ts, :scope > .css-12mrpgq")
    if not main_col:
        return []

    toc_items: list[tuple[str, str]] = []

    if "css-k1l4fw" in (body_row.get("class") or []):
        classes = list(dict.fromkeys([*(body_row.get("class") or []), "internal-article-layout"]))
        body_row["class"] = classes

        white_panel = body_row.select_one(".internal-article-content")
        if not white_panel:
            white_panel = soup.new_tag("div", attrs={"class": "internal-article-content"})
            main_col.replace_with(white_panel)
            white_panel.append(main_col)

        remove_duplicate_title(main_col, page_title_text)

        toc_wrap = body_row.select_one(".internal-article-toc")
        if not toc_wrap:
            toc_wrap = soup.new_tag("div", attrs={"class": "internal-article-toc"})
            if toc_col:
                toc_col.replace_with(toc_wrap)
                toc_wrap.append(toc_col)
            else:
                body_row.append(toc_wrap)
        elif toc_col and toc_col not in toc_wrap.descendants:
            toc_wrap.append(toc_col)
        if not toc_col:
            ensure_generated_toc(toc_wrap, main_col)
        flatten_article_accordions(content_host)
        mark_intro_text(main_col)
        toc_items = fix_toc_wrap(toc_wrap) or toc_nav_items(collect_toc_entries(main_col))
        return toc_items

    layout_row = content_host.select_one(".internal-article-layout")
    if not layout_row:
        layout_row = soup.new_tag("div", attrs={"class": "internal-article-layout"})
        header_wrap = content_host.select_one(".internal-main-header")
        if header_wrap:
            header_wrap.insert_after(layout_row)
        else:
            content_host.append(layout_row)

    white_panel = layout_row.select_one(".internal-article-content")
    if not white_panel:
        white_panel = soup.new_tag("div", attrs={"class": "internal-article-content"})
        layout_row.append(white_panel)

    toc_wrap = layout_row.select_one(".internal-article-toc")
    if not toc_wrap:
        toc_wrap = soup.new_tag("div", attrs={"class": "internal-article-toc"})
        layout_row.append(toc_wrap)

    remove_duplicate_title(main_col, page_title_text)

    if main_col not in white_panel.descendants:
        white_panel.append(main_col.extract())

    if toc_col and toc_col not in toc_wrap.descendants:
        toc_wrap.append(toc_col.extract())
    else:
        ensure_generated_toc(toc_wrap, main_col)

    flatten_article_accordions(content_host)
    mark_intro_text(main_col)
    toc_items = fix_toc_wrap(toc_wrap) or toc_nav_items(collect_toc_entries(main_col))
    return toc_items


def set_html_ready(soup: BeautifulSoup) -> None:
    html = soup.find("html")
    if not html:
        return
    classes = [c for c in (html.get("class") or []) if c not in ("internal-layout-pending",)]
    if "internal-layout-active" not in classes:
        classes.append("internal-layout-active")
    if "internal-layout-ready" not in classes:
        classes.append("internal-layout-ready")
    html["class"] = classes


def is_layout_already_baked(soup: BeautifulSoup, main: Tag, path: str, standalone: bool) -> bool:
    baked = main.get("data-internal-layout-baked")
    if normalize_path(baked or "") != normalize_path(path):
        return False
    if standalone:
        return bool(
            soup.select_one("h1.internal-page-title")
            and soup.select_one(".internal-main-header")
            and soup.select_one(".internal-article-layout")
            and soup.select_one(".internal-article-content")
        )
    shell = soup.select_one(".internal-page-shell")
    if not shell or not soup.select_one(".internal-main"):
        return False
    for child in shell.children:
        if isinstance(child, Tag) and "internal-article-layout" in (child.get("class") or []):
            return False
    return True


def ensure_about_shell_class(soup: BeautifulSoup, path: str) -> bool:
    if path != "/about/":
        return False
    shell = soup.select_one(".internal-page-shell")
    if not shell:
        return False
    classes = list(shell.get("class") or [])
    if "internal-page-shell--about" in classes:
        return False
    classes.append("internal-page-shell--about")
    shell["class"] = classes
    return True


def repair_about_page_custom_links(soup: BeautifulSoup) -> bool:
    """Restore about-page partner/social/intro links flattened by inline link normalizer."""
    changed = False
    if not soup.select_one(".about-partner-btn__name"):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "update_about_page",
            Path(__file__).resolve().parent / "update-about-page.py",
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.rebuild_partners_section(soup)
            mod.rebuild_social_buttons(soup)
            changed = True

    intro = soup.select_one(".about-page__intro .mantine-172zsy7")
    if intro:
        link = intro.find(
            "a",
            class_=lambda value: value and INLINE_EXTERNAL_LINK_CLASS in (value or []),
        )
        if link:
            href = link.get("href") or "https://pryncyp.com"
            text = extract_inline_link_text(link)
            new = soup.new_tag("a", href=href, target="_blank")
            new.string = text
            link.replace_with(new)
            changed = True
    return changed


def bake_page(html_path: Path, tree: dict, force: bool = False) -> bool:
    path = path_from_file(html_path)
    if path == "/":
        return False

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    main = soup.select_one("main.css-yp9swi") or soup.select_one("main")
    if not main:
        return False

    standalone = path in STANDALONE_PAGES
    category = None if standalone else find_category(tree, path)
    if not category and not standalone:
        return False

    if not force and is_layout_already_baked(soup, main, path, standalone):
        content_host = soup.select_one(".internal-main")
        if content_host:
            main_col = content_host.select_one(
                ".internal-article-content .css-7nll2u, .css-7nll2u"
            )
            toc_wrap = content_host.select_one(".internal-article-toc")
            if main_col and toc_wrap:
                ensure_generated_toc(toc_wrap, main_col)
                fix_toc_wrap(toc_wrap)
            if main_col:
                mark_intro_text(main_col)
            sync_baked_mobile_toc(content_host)
        if path == "/privacy-policy/":
            upsert_privacy_page_title(soup)
            if content_host:
                finalize_privacy_layout(content_host, soup)
        apply_heading_normalization(soup)
        normalize_legal_basis_blocks(soup)
        normalize_audience_switch(soup, path)
        normalize_additional_sources_sections(soup)
        normalize_section_document_blocks(soup)
        normalize_section_documents_h4_headings(soup)
        if path == "/about/":
            ensure_about_shell_class(soup, path)
            repair_about_page_custom_links(soup)
        normalize_inline_article_links(soup)
        normalize_external_link_icons(soup)
        normalize_inline_doc_link_icons(soup)
        normalize_document_download_blocks(soup)
        repair_header_foreigners_links(soup)
        repair_article_card_sections(soup)
        repair_dash_bullet_lists(soup)
        repair_recommendation_callouts(soup)
        if content_host:
            main_col = content_host.select_one(
                ".internal-article-content .css-7nll2u, .css-7nll2u"
            )
            toc_wrap = content_host.select_one(".internal-article-toc")
            if main_col and toc_wrap:
                ensure_generated_toc(toc_wrap, main_col)
                fix_toc_wrap(toc_wrap)
                sync_baked_mobile_toc(content_host)
        ensure_article_updated_label(soup, path)
        set_html_ready(soup)
        html_path.write_text(
            linkify_email_addresses(normalize_typographic_quotes(str(soup))),
            encoding="utf-8",
        )
        return True

    unwrap_baked_layout(main, standalone)
    hide_stage_interlinks(soup)
    data = load_next_data(soup)
    title = standalone_page_title(main, soup, data) if standalone else page_title(soup, data)
    if path == "/privacy-policy/":
        title = privacy_page_title(main)

    if standalone:
        section = (
            main.select_one("section.css-1napgkq")
            or main.select_one("section.css-1m99gl8")
            or main.select_one("section.css-t97qev")
            or main.select_one("section")
        )

        shell = main.select_one(".internal-page-shell")
        if not shell:
            shell = soup.new_tag(
                "div",
                attrs={"class": "internal-page-shell internal-page-shell--standalone"},
            )
            if section and section.parent is main:
                for child in list(section.children):
                    if isinstance(child, Tag):
                        shell.append(child.extract())
                section.decompose()
            else:
                for child in list(main.children):
                    if isinstance(child, Tag):
                        shell.append(child.extract())
            main.append(shell)

        if path == "/download/":
            shell_classes = list(shell.get("class") or [])
            if "internal-page-shell--download" not in shell_classes:
                shell_classes.append("internal-page-shell--download")
                shell["class"] = shell_classes

        if path == "/privacy-policy/":
            shell_classes = list(shell.get("class") or [])
            if "internal-page-shell--privacy" not in shell_classes:
                shell_classes.append("internal-page-shell--privacy")
                shell["class"] = shell_classes

        if path == "/about/":
            shell_classes = list(shell.get("class") or [])
            if "internal-page-shell--about" not in shell_classes:
                shell_classes.append("internal-page-shell--about")
                shell["class"] = shell_classes

        content_host = shell.select_one(".internal-main")
        if not content_host:
            content_host = soup.new_tag("div", attrs={"class": "internal-main"})
            for child in list(shell.children):
                if isinstance(child, Tag):
                    content_host.append(child.extract())
            shell.append(content_host)

        if path == "/privacy-policy/":
            prepare_privacy_standalone_layout(content_host, soup)

        toc_items = restructure_article(soup, content_host, title, None, True)
        remove_stage_step_badges(content_host)
        main_col = content_host.select_one(".css-7nll2u")
        if main_col and path in ABOUT_STYLE_PAGES:
            if restructure_about_sections(main_col, soup):
                toc_wrap = content_host.select_one(".internal-article-toc")
                if toc_wrap:
                    ensure_generated_toc(toc_wrap, main_col)
                    toc_items = toc_nav_items(collect_toc_entries(main_col))
            else:
                sections_wrap = main_col.select_one(".mantine-1jhay8j")
                if sections_wrap and repair_about_faq_order(sections_wrap):
                    toc_wrap = content_host.select_one(".internal-article-toc")
                    if toc_wrap:
                        ensure_generated_toc(toc_wrap, main_col)
                        toc_items = toc_nav_items(collect_toc_entries(main_col))
        if main_col:
            remove_duplicate_title(main_col, title)

        header_html = (
            f'<div class="internal-breadcrumbs-row internal-breadcrumbs-row--standalone">'
            f"{mobile_toc_toggle_markup(toc_items)}</div>"
            f'<h1 class="internal-page-title">{escape(title)}</h1>'
        )
        header_wrap = content_host.select_one(".internal-main-header")
        if not header_wrap:
            header_wrap = soup.new_tag("div", attrs={"class": "internal-main-header"})
            content_host.insert(0, header_wrap)
        header_wrap.clear()
        header_wrap.append(BeautifulSoup(header_html, "html.parser"))
        remove_orphan_toc_columns(content_host)
        sync_baked_mobile_toc(content_host)
        main["data-internal-layout-baked"] = path
        main["data-internal-layout"] = path
        if path == "/privacy-policy/" and soup.title:
            soup.title.string = title
        apply_heading_normalization(soup)
        if path == "/privacy-policy/":
            finalize_privacy_layout(content_host, soup, title)
        normalize_document_download_blocks(soup)
        repair_article_card_sections(soup)
        repair_dash_bullet_lists(soup)
        set_html_ready(soup)
        html_path.write_text(
            linkify_email_addresses(normalize_typographic_quotes(str(soup))),
            encoding="utf-8",
        )
        return True

    trail_nodes = find_trail(category.get("children") or [], path) or []
    breadcrumb_trail = build_breadcrumb_trail(category, path)
    cards = resolve_cards(category, path, trail_nodes, soup)
    hub_page = bool(cards)

    shell = main.select_one(".internal-page-shell")
    if not shell:
        shell = soup.new_tag("div", attrs={"class": "internal-page-shell"})
        for child in list(main.children):
            if isinstance(child, Tag):
                shell.append(child.extract())
        main.append(shell)

    content_host = shell.select_one(".internal-main")
    if not content_host:
        content_host = soup.new_tag("div", attrs={"class": "internal-main"})
        shell.append(content_host)

    repair_shell_layout(shell)

    sidebar = shell.select_one(".internal-sidebar")
    sidebar_markup = BeautifulSoup(sidebar_html(category, path), "html.parser")
    if sidebar:
        sidebar.replace_with(sidebar_markup)
    else:
        shell.insert(0, sidebar_markup)

    if hub_page:
        for child in list(shell.children):
            if isinstance(child, Tag) and "internal-sidebar" not in (child.get("class") or []):
                if child is not content_host:
                    child.decompose()
        for extra in shell.select("section"):
            extra.decompose()
        header_html = (
            breadcrumbs_row_html(breadcrumb_trail, [])
            + f'<h1 class="internal-page-title">{escape(title)}</h1>'
            + strip_html_cards(cards)
            + injured_chatbot_promo_html(path)
        )
        content_host.clear()
        content_host.append(BeautifulSoup(header_html, "html.parser"))
    else:
        section = (
            shell.select_one("section.css-1napgkq")
            or shell.select_one("section.css-1m99gl8")
            or shell.select_one("section.css-t97qev")
            or shell.select_one("section")
        )
        if section and section not in content_host.descendants:
            content_host.append(section.extract())

        toc_items: list[tuple[str, str]] = []
        restructure_article(soup, content_host, title, breadcrumb_trail, False)
        toc_wrap = content_host.select_one(".internal-article-toc")
        if toc_wrap:
            toc_items = fix_toc_wrap(toc_wrap)
        if not toc_items:
            main_col = content_host.select_one(".css-7nll2u")
            if main_col:
                toc_items = toc_nav_items(collect_toc_entries(main_col))

        header_html = (
            breadcrumbs_row_html(breadcrumb_trail, toc_items)
            + f'<h1 class="internal-page-title">{escape(title)}</h1>'
        )
        header_wrap = content_host.select_one(".internal-main-header")
        if not header_wrap:
            header_wrap = soup.new_tag("div", attrs={"class": "internal-main-header"})
            content_host.insert(0, header_wrap)
        header_wrap.clear()
        header_wrap.append(BeautifulSoup(header_html, "html.parser"))
        remove_duplicate_toc_sections(content_host)
        remove_orphan_toc_columns(content_host)
        sync_baked_mobile_toc(content_host)

    main["data-internal-layout-baked"] = path
    main["data-internal-layout"] = path
    apply_heading_normalization(soup)
    normalize_legal_basis_blocks(soup)
    normalize_audience_switch(soup, path)
    normalize_additional_sources_sections(soup)
    normalize_section_document_blocks(soup)
    normalize_section_documents_h4_headings(soup)
    if path == "/about/":
        ensure_about_shell_class(soup, path)
        repair_about_page_custom_links(soup)
    normalize_inline_article_links(soup)
    normalize_external_link_icons(soup)
    normalize_inline_doc_link_icons(soup)
    normalize_document_download_blocks(soup)
    repair_header_foreigners_links(soup)
    repair_article_card_sections(soup)
    repair_dash_bullet_lists(soup)
    repair_recommendation_callouts(soup)
    content_host = soup.select_one(".internal-main")
    if content_host:
        main_col = content_host.select_one(
            ".internal-article-content .css-7nll2u, .css-7nll2u"
        )
        toc_wrap = content_host.select_one(".internal-article-toc")
        if main_col and toc_wrap:
            ensure_generated_toc(toc_wrap, main_col)
            fix_toc_wrap(toc_wrap)
            sync_baked_mobile_toc(content_host)
    ensure_article_updated_label(soup, path)
    set_html_ready(soup)
    html_path.write_text(
        linkify_email_addresses(normalize_typographic_quotes(str(soup))),
        encoding="utf-8",
    )
    return True


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Bake internal page layout into HTML.")
    parser.add_argument("--path", default="", help="Bake one page or directory only")
    parser.add_argument("--force", action="store_true", help="Re-bake even if already baked")
    args = parser.parse_args()

    tree = load_tree()
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
        files = sorted(p for p in ROOT.rglob("*.html") if p.resolve() != (ROOT / "index.html").resolve())

    baked = skipped = 0
    for html_path in files:
        if bake_page(html_path, tree, force=args.force):
            baked += 1
        else:
            skipped += 1
    print(f"Baked layout: {baked}, skipped: {skipped}")
    persist_file_size_cache_if_needed()


if __name__ == "__main__":
    main()
