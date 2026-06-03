#!/usr/bin/env python3
"""Split about/index.html into about (intro + partners) and faq (abbrev + FAQ sections)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parent.parent
ABOUT_PATH = ROOT / "about" / "index.html"
FAQ_PATH = ROOT / "faq" / "index.html"

PARTNERS_ID = "Наші_партнери"
FAQ_SECTION_IDS = {
    "Скорочення_та_абревіатури",
    "Чи_надаєте_ви_індивідуальні_консультації?",
    "Чи_можу_я_бути_впевнений_в_актуальності_інформації_на_сайті?",
    "Де_мені_взяти_зразки_документів?",
    "Як_я_можу_долучитися_до_команди?",
    "Якщо_я_готую_матеріал_для_медіа_про_шлях_пораненого,_чи_даєте_ви_коментарі?",
}


def main_col(soup: BeautifulSoup) -> Tag | None:
    return soup.select_one(".internal-article-content .css-7nll2u") or soup.select_one(
        ".css-7nll2u"
    )


def is_intro_card(node: Tag) -> bool:
    classes = set(node.get("class") or [])
    return "internal-article-intro-card" in classes or (
        node.name == "div"
        and "css-sdnfq3" in classes
        and node.select_one(".css-tualuh")
        and "Правовий навігатор" in node.get_text()
    )


def is_mobile_toc(node: Tag) -> bool:
    classes = set(node.get("class") or [])
    return "css-1sctyhq" in classes


def is_faq_header(node: Tag) -> bool:
    classes = set(node.get("class") or [])
    return "mantine-vgkn1f" in classes


def is_faq_section(node: Tag) -> bool:
    if node.name != "div":
        return False
    classes = set(node.get("class") or [])
    if "mantine-wnhdd8" not in classes:
        return False
    section_id = node.get("id") or ""
    return section_id in FAQ_SECTION_IDS


def is_partners_section(node: Tag) -> bool:
    if node.name != "div":
        return False
    classes = set(node.get("class") or [])
    if "mantine-wnhdd8" not in classes:
        return False
    return (node.get("id") or "") == PARTNERS_ID


def classify_main_col_children(main: Tag) -> dict[str, list[Tag]]:
    groups: dict[str, list[Tag]] = {
        "intro": [],
        "mobile_toc": [],
        "faq_header": [],
        "faq_sections": [],
        "partners": [],
        "other": [],
    }
    for child in list(main.children):
        if not isinstance(child, Tag):
            continue
        if is_intro_card(child):
            groups["intro"].append(child)
        elif is_mobile_toc(child):
            groups["mobile_toc"].append(child)
        elif is_faq_header(child):
            groups["faq_header"].append(child)
        elif is_faq_section(child):
            groups["faq_sections"].append(child)
        elif is_partners_section(child):
            groups["partners"].append(child)
        else:
            groups["other"].append(child)
    return groups


def clear_main_col(main: Tag) -> None:
    for child in list(main.children):
        if isinstance(child, Tag):
            child.decompose()


def append_nodes(main: Tag, nodes: list[Tag]) -> None:
    for node in nodes:
        main.append(node)


def set_page_metadata(soup: BeautifulSoup, title: str, path: str) -> None:
    if soup.title:
        soup.title.string = title
    for meta in soup.find_all("meta"):
        prop = meta.get("property") or meta.get("name") or ""
        if prop in ("og:title", "twitter:title"):
            meta["content"] = title
        if prop == "og:url" and path != "/about/":
            meta["content"] = f"https://navigator.pryncyp.org{path.rstrip('/')}"
    h1 = soup.select_one("h1.internal-page-title")
    if h1:
        h1.clear()
        h1.append(title)
    main = soup.select_one("main")
    if main:
        main["data-internal-layout"] = path
        if main.has_attr("data-internal-layout-baked"):
            main["data-internal-layout-baked"] = path


def toc_entries_for_nodes(nodes: list[Tag]) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for node in nodes:
        if is_faq_header(node) or is_mobile_toc(node):
            continue
        section_id = node.get("id") or ""
        if not section_id:
            continue
        heading = node.select_one("h2, h3")
        title = heading.get_text(strip=True) if heading else section_id.replace("_", " ")
        entries.append((f"#{quote(section_id, safe='')}", title))
    return entries


def rebuild_toc_lists(soup: BeautifulSoup, entries: list[tuple[str, str]]) -> None:
    item_html = lambda href, title: (
        f'<li class="mantine-List-item"><div class="internal-toc-item-text">'
        f'<a class="css-16clbz5" href="{href}">{title}</a></div></li>'
    )
    desktop_item_html = lambda href, title: (
        f'<li class="mantine-List-item mantine-riob0u" data-with-icon="true">'
        f'<div class="___ref-itemWrapper mantine-iwg4hh mantine-List-itemWrapper">'
        f'<span class="mantine-uezznj mantine-List-itemIcon">'
        f'<div class="mantine-ThemeIcon-root mantine-1tnkqq"></div></span>'
        f'<span><div class="internal-toc-item-text mantine-12e74aa">'
        f'<a class="css-16clbz5" href="{href}">{title}</a>'
        f"</div></span></div></li>"
    )

    mobile_list = soup.select_one(".internal-toc-dropdown ul.mantine-List-root")
    if mobile_list:
        mobile_list.clear()
        for href, title in entries:
            mobile_list.append(BeautifulSoup(item_html(href, title), "html.parser"))

    desktop_list = soup.select_one(".internal-article-toc ul.mantine-List-root")
    if desktop_list:
        desktop_list.clear()
        for href, title in entries:
            desktop_list.append(BeautifulSoup(desktop_item_html(href, title), "html.parser"))


def split_pages() -> None:
    about_html = ABOUT_PATH.read_text(encoding="utf-8")
    about_soup = BeautifulSoup(about_html, "html.parser")
    about_main = main_col(about_soup)
    if not about_main:
        raise SystemExit("Could not find main column in about/index.html")

    groups = classify_main_col_children(about_main)
    if not groups["intro"] or not groups["partners"]:
        raise SystemExit("about/index.html is missing intro or partners section")

    faq_order = (
        groups["mobile_toc"]
        + groups["faq_header"]
        + groups["faq_sections"][1:]
        + groups["faq_sections"][:1]
    )
    if len(groups["faq_sections"]) < 6:
        raise SystemExit(
            f"Expected 6 FAQ sections (abbrev + 5 Q&A), found {len(groups['faq_sections'])}"
        )

    faq_html = "".join(str(node) for node in faq_order)
    for node in faq_order:
        node.decompose()

    set_page_metadata(about_soup, "Про нас", "/about/")
    about_entries = toc_entries_for_nodes(groups["partners"])
    rebuild_toc_lists(about_soup, about_entries)

    faq_soup = BeautifulSoup(about_html, "html.parser")
    faq_main = main_col(faq_soup)
    if not faq_main:
        raise SystemExit("Could not find main column for faq page")

    clear_main_col(faq_main)
    faq_fragment = BeautifulSoup(faq_html, "html.parser")
    faq_nodes: list[Tag] = []
    for child in list(faq_fragment.children):
        if isinstance(child, Tag):
            faq_main.append(child)
            faq_nodes.append(child)

    set_page_metadata(faq_soup, "FAQ", "/faq/")
    faq_entries = toc_entries_for_nodes(faq_nodes)
    rebuild_toc_lists(faq_soup, faq_entries)

    FAQ_PATH.parent.mkdir(parents=True, exist_ok=True)
    ABOUT_PATH.write_text(str(about_soup), encoding="utf-8")
    FAQ_PATH.write_text(str(faq_soup), encoding="utf-8")
    print(f"Updated {ABOUT_PATH.relative_to(ROOT)} (intro + partners)")
    print(f"Created {FAQ_PATH.relative_to(ROOT)} (abbrev + FAQ)")


if __name__ == "__main__":
    split_pages()
