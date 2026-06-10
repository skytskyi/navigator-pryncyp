#!/usr/bin/env python3
"""Create search/index.html results page."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parent.parent
ABOUT_PATH = ROOT / "about" / "index.html"
SEARCH_PATH = ROOT / "search" / "index.html"

PAGE_TITLE = "Пошук"
SEARCH_MARKUP = """
<div class="site-search-page">
  <form class="site-search-page__form app-search-form" role="search" action="/search/" method="get">
    <input type="search" class="site-search-page__input app-search-form__input" name="q" placeholder="Пошук за темою або послугою" aria-label="Пошук за темою або послугою" autocomplete="off"/>
    <span class="app-search-form__divider" aria-hidden="true"></span>
    <button type="submit" class="site-search-page__submit app-search-form__submit">
      <img class="app-search-form__submit-icon" src="/img/search.svg" width="20" height="20" alt="" aria-hidden="true"/>
      <span class="app-search-form__submit-label">Шукати</span>
    </button>
  </form>
  <p class="site-search-page__meta is-hidden" data-site-search-meta></p>
  <div class="site-search-page__tabs is-hidden" data-site-search-tabs role="tablist" aria-label="Фільтр результатів пошуку"></div>
  <div class="site-search-page__results" data-site-search-results></div>
</div>
"""


def upsert_assets(soup: BeautifulSoup) -> None:
    css_href = "/css/site-search.css?v=8"
    app_css_href = "/css/app-search.css?v=2"
    js_href = "/js/site-search.js?v=6"

    existing_css = soup.select_one('link[href*="site-search.css"]')
    if existing_css:
        existing_css["href"] = css_href
    else:
        internal_css = soup.select_one('link[href*="internal-layout.css"]')
        tag = BeautifulSoup(f'<link href="{css_href}" rel="stylesheet"/>', "html.parser")
        if internal_css:
            internal_css.insert_after(tag)
        elif soup.head:
            soup.head.append(tag)

    existing_app_css = soup.select_one('link[href*="app-search.css"]')
    if existing_app_css:
        existing_app_css["href"] = app_css_href
    else:
        site_css = soup.select_one('link[href*="site-search.css"]')
        tag = BeautifulSoup(f'<link href="{app_css_href}" rel="stylesheet"/>', "html.parser")
        if site_css:
            site_css.insert_after(tag)
        elif soup.head:
            soup.head.append(tag)

    existing_js = soup.select_one('script[src*="site-search.js"]')
    if existing_js:
        existing_js["src"] = js_href
    else:
        internal_js = soup.select_one('script[src*="internal-layout.js"]')
        tag = BeautifulSoup(f'<script src="{js_href}"></script>', "html.parser")
        if internal_js:
            internal_js.insert_after(tag)
        elif soup.body:
            soup.body.append(tag)


def set_metadata(soup: BeautifulSoup) -> None:
    path = "/search/"
    if soup.title:
        soup.title.string = PAGE_TITLE

    for meta in soup.find_all("meta"):
        prop = meta.get("property") or meta.get("name") or ""
        if prop in ("og:title", "twitter:title"):
            meta["content"] = PAGE_TITLE
        if prop == "og:url":
            meta["content"] = f"https://navigator.pryncyp.org{path.rstrip('/')}"

    h1 = soup.select_one(".internal-page-title")
    if h1:
        h1.clear()
        h1.append(PAGE_TITLE)

    main = soup.select_one("main")
    if main:
        main["data-internal-layout"] = path
        main["data-internal-layout-baked"] = path

    shell = soup.select_one(".internal-page-shell")
    if shell:
        classes = list(shell.get("class") or [])
        for extra in ("internal-page-shell--search", "internal-page-shell--standalone"):
            if extra not in classes:
                classes.append(extra)
        shell["class"] = classes

    for toc in soup.select(
        ".internal-article-toc, .internal-toc-toggle-wrap, .internal-toc-dropdown"
    ):
        toc.decompose()


def replace_main_content(soup: BeautifulSoup) -> None:
    main_col = soup.select_one(".internal-article-content .css-7nll2u") or soup.select_one(
        ".css-7nll2u"
    )
    if not main_col:
        raise SystemExit("Main column not found")

    for child in list(main_col.children):
        if isinstance(child, Tag):
            child.decompose()

    main_col.append(BeautifulSoup(SEARCH_MARKUP, "html.parser"))


def main() -> None:
    if not ABOUT_PATH.exists():
        raise SystemExit(f"Missing template: {ABOUT_PATH}")

    soup = BeautifulSoup(ABOUT_PATH.read_text(encoding="utf-8"), "html.parser")
    upsert_assets(soup)
    set_metadata(soup)
    replace_main_content(soup)

    SEARCH_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEARCH_PATH.write_text(str(soup), encoding="utf-8")
    print(f"Created {SEARCH_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
