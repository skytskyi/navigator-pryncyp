#!/usr/bin/env python3
"""Bake header logos and category nav into static HTML."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parent.parent

CATEGORY_LABEL = "Категорії правового навігатора:"
FOREIGNERS_LABEL = "🌍 For Foreigners"
NAVIGATOR_LOGO = "/img/Logo_navigator.png"
PRYNCYP_LOGO = "/img/Logo_pryncyp.png"
PRYNCYP_URL = "https://www.pryncyp.org/"

CATEGORIES = [
    {
        "id": "serviceman",
        "label": "Військові",
        "href": "/serviceman/",
        "prefixes": ["/serviceman"],
    },
    {
        "id": "injured",
        "label": "Поранені",
        "href": "/injured/",
        "prefixes": ["/injured", "/injured-military", "/ingured-mia"],
    },
    {
        "id": "veterans",
        "label": "Ветерани",
        "href": "/veterans/",
        "prefixes": ["/veterans"],
    },
    {
        "id": "pow",
        "label": "Звільнені з полону",
        "href": "/pow/",
        "prefixes": ["/pow"],
    },
    {
        "id": "family",
        "label": "Родини військових та ветеранів",
        "href": "/family/",
        "prefixes": ["/family"],
    },
]

DIVIDER_STYLE = (
    "width:1px;height:30px;background-color:#D9D9D9;"
    "flex-shrink:0;display:block;align-self:center;"
)
LOGOS_STYLE = "display:flex !important;align-items:center;gap:12px;flex-shrink:0;"


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


def get_active_category(path: str) -> dict | None:
    for category in CATEGORIES:
        for prefix in category["prefixes"]:
            if path.startswith(prefix):
                return category
    return None


def logos_markup() -> str:
    return (
        f'<div class="site-header-logos" style="{LOGOS_STYLE}">'
        f'<a href="/">'
        f'<img alt="Правовий навігатор" width="132" height="30" decoding="async" '
        f'fetchpriority="high" loading="eager" '
        f'style="height:30px;width:auto;display:block !important" src="{NAVIGATOR_LOGO}"/>'
        f"</a>"
        '<span aria-hidden="true" style="width:1px;height:30px;background-color:#D9D9D9;'
        'flex-shrink:0;display:block"></span>'
        f'<a href="{PRYNCYP_URL}" target="_blank" rel="noopener noreferrer">'
        f'<img alt="Принцип" width="132" height="30" decoding="async" '
        f'fetchpriority="high" loading="eager" '
        f'style="height:30px;width:auto;display:block !important" src="{PRYNCYP_LOGO}"/>'
        f"</a>"
        "</div>"
    )


def normalize_logo_imgs(soup: BeautifulSoup) -> None:
    for img in soup.select(".site-header-logos img"):
        img["loading"] = "eager"
        img["fetchpriority"] = "high"
        img["decoding"] = "async"
        if not img.get("width"):
            img["width"] = "132"
        if not img.get("height"):
            img["height"] = "30"
        style = img.get("style") or ""
        if "display:block" not in style.replace(" ", ""):
            img["style"] = "height:30px;width:auto;display:block !important"


def category_nav_markup(active_id: str) -> str:
    links = []
    for category in CATEGORIES:
        class_name = "category-nav__link"
        if category["id"] == active_id:
            class_name += " category-nav__link--active"
        links.append(
            f'<a class="{class_name}" href="{category["href"]}">{category["label"]}</a>'
        )
    return (
        f'<div class="category-nav-chrome">'
        f'<nav class="category-nav" aria-label="{CATEGORY_LABEL}">'
        f'<p class="category-nav__label">{CATEGORY_LABEL}</p>'
        f'<div class="category-nav__inner">'
        f'<div class="category-nav__links">{"".join(links)}</div>'
        f"</div></nav></div>"
    )


def is_old_logo_img(img: Tag) -> bool:
    src = img.get("src") or ""
    alt = img.get("alt") or ""
    return alt == "logo" or bool(re.search(r"logo\.b15c3320|/_next/static/media/logo", src))


def is_our_logos_block(node: Tag | None) -> bool:
    if not node or "site-header-logos" not in (node.get("class") or []):
        return False
    nav = node.select_one('img[alt="Правовий навігатор"]')
    pry = node.select_one('img[alt="Принцип"]')
    if not nav or not pry:
        return False
    nav_src = nav.get("src") or ""
    pry_src = pry.get("src") or ""
    return NAVIGATOR_LOGO in nav_src and PRYNCYP_LOGO in pry_src


def inject_logos(header_bar: Tag, soup: BeautifulSoup) -> None:
    existing = header_bar.select_one(".site-header-logos")
    if is_our_logos_block(existing):
        existing["style"] = LOGOS_STYLE
        return

    if existing:
        existing.decompose()

    old_anchor = None
    for img in header_bar.select("img"):
        if is_old_logo_img(img):
            old_anchor = img.find_parent("a")
            break

    block = BeautifulSoup(logos_markup(), "html.parser")
    logos = block.find("div", class_="site-header-logos")
    if not logos:
        return

    if old_anchor:
        old_anchor.replace_with(logos)
    else:
        header_bar.insert(0, logos)


def remove_search(header: Tag) -> None:
    for img in header.select('img[alt="search"]'):
        box = img.find_parent(class_=lambda value: value and "mantine-6bln36" in value)
        if box:
            box.decompose()
    for el in header.select(".mantine-us64po"):
        el.decompose()


def remove_navigator_menu(header: Tag) -> None:
    for el in header.select(".mantine-c1sy14, .mantine-ykctob"):
        text = el.get_text(strip=True)
        if text not in ("Чат-бот", "Навігатор"):
            continue
        trigger = el.find_parent(attrs={"aria-haspopup": "menu"})
        if not trigger:
            continue
        wrap = trigger.find_parent(class_=lambda value: value and "mantine-1xkg0b8" in value)
        if wrap and wrap.parent and "mantine-1xkg0b8" in (wrap.parent.get("class") or []):
            wrap.parent.decompose()
            continue
        if wrap:
            wrap.decompose()
            continue
        trigger.decompose()


def update_foreigners_link(header: Tag) -> None:
    for link in header.select('a[href*="foreigners.navigator"]'):
        classes = list(link.get("class") or [])
        if "css-bho8e5" not in classes:
            classes.append("css-bho8e5")
        if "css-clvzh3" in classes:
            classes = [c for c in classes if c != "css-clvzh3"]
        link["class"] = classes
        for svg in link.select("svg"):
            svg.decompose()
        label = link.select_one(".mantine-Text-root") or link.select_one(
            ".mantine-1uguyhf > div:last-child"
        )
        if label is not None and label.get_text(strip=True) != FOREIGNERS_LABEL:
            label.clear()
            label.append(FOREIGNERS_LABEL)


def fix_dividers(header: Tag) -> None:
    for el in header.select('.site-header-logos > span[aria-hidden="true"]'):
        el["style"] = DIVIDER_STYLE
    for el in header.select(".css-1qav3gh"):
        el["style"] = DIVIDER_STYLE


def normalize_header_bar(header_bar: Tag) -> None:
    classes = list(header_bar.get("class") or [])
    if "mantine-ahbyky" in classes and "mantine-sel6jv" not in classes:
        classes.append("mantine-sel6jv")
        header_bar["class"] = classes


def inject_header_search_link(header: Tag, soup: BeautifulSoup) -> bool:
    """Insert «Пошук» link after «Перелік документів», before «Завантажити»."""
    nav_cluster = header.select_one(".css-zfqabr")
    if not nav_cluster:
        return False

    documents = nav_cluster.select_one('a[href="/documents/"]')
    if not documents:
        return False

    changed = False
    search = nav_cluster.select_one('a.header-search-btn[href="/search/"]')
    old_button = nav_cluster.select_one("button.header-search-btn[data-site-search-open]")

    if old_button and not search:
        old_button.name = "a"
        if "type" in old_button.attrs:
            del old_button["type"]
        for attr in ("aria-expanded", "aria-controls", "data-site-search-open"):
            if attr in old_button.attrs:
                del old_button[attr]
        old_button["href"] = "/search/"
        search = old_button
        changed = True
    elif old_button and search:
        old_button.decompose()
        changed = True

    if not search:
        search = soup.new_tag("a", href="/search/")
        search["class"] = ["header-search-btn"]
        icon = soup.new_tag("img", src="/img/search.svg", alt="", width="18", height="18")
        icon["aria-hidden"] = "true"
        span = soup.new_tag("span")
        span.string = "Пошук"
        search.append(icon)
        search.append(span)
        documents.insert_after(search)
        changed = True

    download = nav_cluster.select_one('a.header-download-btn[href="/download/"]')
    if download and download.find_previous_sibling() is not search:
        search.insert_after(download.extract())
        changed = True

    return changed


def replace_store_icons_with_download(header: Tag, soup: BeautifulSoup) -> bool:
    """Remove store icon cluster and place «Завантажити» after «Перелік документів»."""
    nav_cluster = header.select_one(".css-zfqabr")
    if not nav_cluster:
        return False

    changed = False

    for wrap in list(nav_cluster.select(".mantine-3k8ssu")):
        if wrap.select(
            'a[href*="apps.apple.com"], a[href*="play.google.com"], a[href*="pryncyp_bot"]'
        ):
            wrap.decompose()
            changed = True

    for link in list(
        nav_cluster.select(
            'a[href*="apps.apple.com"], a[href*="play.google.com"], a[href*="pryncyp_bot"]'
        )
    ):
        link.decompose()
        changed = True

    documents = nav_cluster.select_one('a[href="/documents/"]')
    if not documents:
        return changed

    download = nav_cluster.select_one('a.header-download-btn[href="/download/"]')
    if download:
        search = nav_cluster.select_one('a.header-search-btn[href="/search/"]')
        anchor = search if search else documents
        if download.find_previous_sibling() is not anchor:
            anchor.insert_after(download.extract())
            changed = True
        return changed

    btn = soup.new_tag("a", href="/download/")
    btn["class"] = ["header-download-btn"]
    btn.string = "Завантажити"
    search = nav_cluster.select_one('a.header-search-btn[href="/search/"]')
    if search:
        search.insert_after(btn)
    else:
        documents.insert_after(btn)
    return True


def inject_faq_nav_link(header: Tag, soup: BeautifulSoup) -> bool:
    nav_cluster = header.select_one(".css-zfqabr")
    if not nav_cluster:
        return False
    if nav_cluster.select_one('a[href="/faq/"]'):
        return False
    about_link = nav_cluster.select_one('a[href="/about/"]')
    if not about_link:
        return False
    faq_link = soup.new_tag("a", href="/faq/")
    faq_link["class"] = ["css-bho8e5"]
    faq_link.string = "FAQ"
    about_link.insert_after(faq_link)
    return True


def clean_nav_cluster(nav_cluster: Tag) -> bool:
    """Remove stray <style> nodes from the desktop nav flex row."""
    changed = False
    for node in list(nav_cluster.children):
        if isinstance(node, Tag) and node.name == "style":
            node.decompose()
            changed = True
    return changed


def repair_header_nav_bar(header_bar: Tag) -> bool:
    nav_cluster = header_bar.select_one(".css-zfqabr")
    if not nav_cluster:
        return False

    orphans = []
    past_cluster = False
    for child in list(header_bar.children):
        if child is nav_cluster:
            past_cluster = True
            continue
        if past_cluster:
            orphans.append(child)

    if not orphans:
        return False

    for node in orphans:
        nav_cluster.append(node.extract())

    clean_nav_cluster(nav_cluster)
    return True


def header_nav_is_broken(header_bar: Tag) -> bool:
    nav_cluster = header_bar.select_one(".css-zfqabr")
    if not nav_cluster:
        return False

    past_cluster = False
    for child in header_bar.children:
        if child is nav_cluster:
            past_cluster = True
            continue
        if past_cluster and isinstance(child, Tag):
            return True
    return False


def remove_persist_script(soup: BeautifulSoup) -> None:
    for script in soup.find_all("script", src=True):
        src = script.get("src") or ""
        if "header-persist.js" in src:
            script.decompose()


def sync_category_nav(soup: BeautifulSoup, path: str) -> None:
    header = soup.select_one("header.css-9r8uj3") or soup.select_one("header")
    if not header:
        return

    for chrome in soup.select(".category-nav-chrome"):
        chrome.decompose()
    for nav in soup.select(".category-nav"):
        nav.decompose()

    if path == "/":
        return

    active = get_active_category(path)
    if not active:
        return

    chrome = BeautifulSoup(category_nav_markup(active["id"]), "html.parser").select_one(
        ".category-nav-chrome"
    )
    if chrome:
        header.insert_after(chrome)


def is_header_already_baked(soup: BeautifulSoup, path: str) -> bool:
    html = soup.find("html")
    if not html or html.get("data-header-layout-baked") != "1":
        return False

    header_bar = soup.select_one("header .css-1bgjytp")
    if not header_bar or not is_our_logos_block(header_bar.select_one(".site-header-logos")):
        return False

    if soup.select('header img[alt="search"]') or soup.select("header .mantine-us64po"):
        return False

    if header_bar and header_nav_is_broken(header_bar):
        return False

    nav_cluster = soup.select_one("header .css-zfqabr")
    if nav_cluster and any(
        isinstance(child, Tag) and child.name == "style" for child in nav_cluster.children
    ):
        return False

    nav_cluster = soup.select_one("header .css-zfqabr")
    if nav_cluster and nav_cluster.select_one('a[href="/documents/"]'):
        if not nav_cluster.select_one('a.header-search-btn[href="/search/"]'):
            return False

    active = get_active_category(path) if path != "/" else None
    nav = soup.select_one(".category-nav")
    if active and not nav:
        return False
    if not active and nav:
        return False

    if active and nav:
        active_link = nav.select_one(".category-nav__link--active")
        if not active_link or normalize_path(active_link.get("href") or "") != normalize_path(
            active["href"]
        ):
            return False
    return True


def bake_page(html_path: Path, force: bool = False) -> bool:
    path = path_from_file(html_path)
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")

    header = soup.select_one("header.css-9r8uj3") or soup.select_one("header")
    if not header:
        return False

    if not force and is_header_already_baked(soup, path):
        normalize_logo_imgs(soup)
        inject_faq_nav_link(header, soup)
        inject_header_search_link(header, soup)
        replace_store_icons_with_download(header, soup)
        nav_cluster = header.select_one(".css-zfqabr")
        if nav_cluster:
            clean_nav_cluster(nav_cluster)
        remove_persist_script(soup)
        html_path.write_text(str(soup), encoding="utf-8")
        return True

    header_bar = header.select_one(".css-1bgjytp")
    if not header_bar:
        return False

    inject_logos(header_bar, soup)
    normalize_logo_imgs(soup)
    remove_search(header)
    remove_navigator_menu(header)
    update_foreigners_link(header)
    fix_dividers(header)
    normalize_header_bar(header_bar)
    repair_header_nav_bar(header_bar)
    inject_faq_nav_link(header, soup)
    inject_header_search_link(header, soup)
    replace_store_icons_with_download(header, soup)
    nav_cluster = header.select_one(".css-zfqabr")
    if nav_cluster:
        clean_nav_cluster(nav_cluster)
    sync_category_nav(soup, path)
    remove_persist_script(soup)

    html = soup.find("html")
    if html is not None:
        html["data-header-layout-baked"] = "1"

    html_path.write_text(str(soup), encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Bake header layout into HTML.")
    parser.add_argument("--path", default="", help="Bake one page or directory only")
    parser.add_argument("--force", action="store_true", help="Re-bake even if already baked")
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

    baked = skipped = 0
    for html_path in files:
        if bake_page(html_path, force=args.force):
            baked += 1
        else:
            skipped += 1

    print(f"Baked header: {baked}, skipped: {skipped}")


if __name__ == "__main__":
    main()
