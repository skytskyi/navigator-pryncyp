#!/usr/bin/env python3
"""Update about page title, intro layout, and social link buttons."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parent.parent
ABOUT_PATH = ROOT / "about" / "index.html"
PAGE_TITLE = "Про нас"
ABOUT_CSS = '<link href="/css/about-page.css?v=6" rel="stylesheet"/>'

SOCIAL_LINKS = (
    ("https://www.facebook.com/pryncypua", "Facebook", "/img/facebook.svg"),
    ("https://www.instagram.com/pryncyp.ua", "Instagram", "/img/instagram.svg"),
    ("https://twitter.com/Pryncyp_UA", "X", "/img/x.svg"),
)
PARTNERS = (
    ("https://fedoriv.com/", "fedoriv agency", "Стратегія, брендинг та планування"),
    ("https://www.hotburo.com/", "hot büro", "Розробка Навігатора та дизайн першого релізу"),
    ("https://buildapps.pro/uk", "BuildApps", "Розробка Навігатора та дизайн другої ітерації"),
    (
        "https://opentech.softserveinc.com/",
        "OpenTech SoftServe",
        "Дизайн третьої ітерації",
    ),
)
PARTNER_ICON = "/img/Arrow_45.svg"
DOWNLOAD_CSS = '<link href="/css/download-page.css?v=21" rel="stylesheet"/>'


def upsert_about_css(soup: BeautifulSoup) -> None:
    existing = soup.select_one('link[href*="about-page.css"]')
    if existing:
        existing["href"] = "/css/about-page.css?v=6"
    else:
        internal_css = soup.select_one('link[href*="internal-layout.css"]')
        tag = BeautifulSoup(ABOUT_CSS, "html.parser")
        if internal_css:
            internal_css.insert_after(tag)
        elif soup.head:
            soup.head.append(tag)

    download_css = soup.select_one('link[href*="download-page.css"]')
    if download_css:
        download_css["href"] = "/css/download-page.css?v=21"
    else:
        about_css = soup.select_one('link[href*="about-page.css"]')
        tag = BeautifulSoup(DOWNLOAD_CSS, "html.parser")
        if about_css:
            about_css.insert_after(tag)
        elif soup.head:
            soup.head.append(tag)


def set_metadata(soup: BeautifulSoup) -> None:
    if soup.title:
        soup.title.string = PAGE_TITLE

    for meta in soup.find_all("meta"):
        prop = meta.get("property") or meta.get("name") or ""
        if prop in ("og:title", "twitter:title"):
            meta["content"] = PAGE_TITLE

    h1 = soup.select_one(".internal-page-title")
    if h1:
        h1.clear()
        h1.append(PAGE_TITLE)

    shell = soup.select_one(".internal-page-shell")
    if shell:
        classes = list(shell.get("class") or [])
        if "internal-page-shell--about" not in classes:
            classes.append("internal-page-shell--about")
        shell["class"] = classes


def build_social_buttons(soup: BeautifulSoup) -> Tag:
    wrap = soup.new_tag("div", attrs={"class": "about-page__social"})
    label = soup.new_tag("p", attrs={"class": "about-page__social-label"})
    label.string = "Приєднуйтесь до нас у соцмережах:"
    wrap.append(label)

    buttons = soup.new_tag(
        "div",
        attrs={"class": "about-page__social-buttons download-page-card__stores"},
    )
    for href, label_text, icon in SOCIAL_LINKS:
        link = soup.new_tag(
            "a",
            href=href,
            target="_blank",
            rel="noopener noreferrer",
            **{"class": "download-store-btn download-store-btn--social"},
        )
        icon_wrap = soup.new_tag("span", attrs={"class": "download-store-btn__icon"})
        img = soup.new_tag("img", src=icon, alt="", width="24", height="24")
        icon_wrap.append(img)
        link.append(icon_wrap)
        link.append(label_text)
        buttons.append(link)
    wrap.append(buttons)
    return wrap


def copy_element_children(source: Tag, target: Tag) -> None:
    for child in list(source.children):
        if isinstance(child, NavigableString):
            text = str(child)
            if text.strip():
                target.append(NavigableString(text))
        elif isinstance(child, Tag):
            target.append(child.extract())


def make_body_text_block(soup: BeautifulSoup, source: Tag | None, fallback_text: str = "") -> Tag:
    block = soup.new_tag("div", attrs={"class": "mantine-Text-root mantine-172zsy7"})
    if source is not None:
        copy_element_children(source, block)
    elif fallback_text:
        block.append(fallback_text)
    return block


def find_lead_source(main_col: Tag) -> Tag | None:
    lead = main_col.select_one(":scope > p.about-page__lead")
    if lead:
        return lead

    intro = main_col.select_one(".about-page__intro")
    if intro:
        text_block = intro.select_one(".mantine-Text-root.mantine-172zsy7")
        if text_block and "Правовий навігатор створено" in text_block.get_text(" ", strip=True):
            return text_block

    for paragraph in main_col.find_all(["p", "div"], recursive=True):
        text = paragraph.get_text(" ", strip=True)
        if text.startswith("Правовий навігатор створено"):
            return paragraph
    return None


def find_thank_you_source(container: Tag) -> Tag | None:
    for paragraph in container.find_all("p", recursive=True):
        if paragraph.get_text(strip=True) == "Дякуємо вам за службу!":
            return paragraph
    return None


def restructure_intro(soup: BeautifulSoup) -> None:
    main_col = soup.select_one(".css-7nll2u")
    if not main_col:
        raise SystemExit("Main column not found on about page")

    old_intro = main_col.select_one(".about-page__intro")
    old_follow = main_col.select_one(".about-page__follow") or main_col.select_one(
        ".internal-article-intro-card"
    )
    old_lead = main_col.select_one(":scope > p.about-page__lead")

    lead_source = find_lead_source(main_col)
    if not lead_source:
        raise SystemExit("Lead paragraph not found on about page")

    thank_source = None
    social = None
    if old_intro:
        thank_source = find_thank_you_source(old_intro)
        social = old_intro.select_one(".about-page__social")
    if old_follow:
        thank_source = thank_source or find_thank_you_source(old_follow)
        social = social or old_follow.select_one(".about-page__social")

    if old_intro:
        insert_before = old_intro
    elif old_lead:
        insert_before = old_lead
    elif old_follow:
        insert_before = old_follow
    else:
        insert_before = main_col.select_one(".mantine-wnhdd8")

    intro = soup.new_tag(
        "div",
        attrs={"class": "about-page__intro css-sdnfq3 mantine-1hdrj7p"},
    )
    intro.append(make_body_text_block(soup, lead_source))
    intro.append(
        make_body_text_block(
            soup,
            thank_source,
            "Дякуємо вам за службу!",
        )
    )

    if social:
        social.extract()
        intro.append(social)
    else:
        intro.append(build_social_buttons(soup))

    if insert_before:
        insert_before.insert_before(intro)
    else:
        main_col.append(intro)

    if old_intro:
        old_intro.decompose()
    if old_follow:
        old_follow.decompose()
    if old_lead:
        old_lead.decompose()


def build_partner_button(soup: BeautifulSoup, href: str, name: str, description: str) -> Tag:
    link = soup.new_tag(
        "a",
        href=href,
        target="_blank",
        rel="noopener noreferrer",
        **{"class": "about-partner-btn"},
    )
    content = soup.new_tag("span", attrs={"class": "about-partner-btn__content"})
    title = soup.new_tag("span", attrs={"class": "about-partner-btn__name"})
    title.string = name
    desc = soup.new_tag("span", attrs={"class": "about-partner-btn__desc"})
    desc.string = description
    content.append(title)
    content.append(desc)

    icon_wrap = soup.new_tag("span", attrs={"class": "about-partner-btn__icon"})
    icon = soup.new_tag("img", src=PARTNER_ICON, alt="", width="24", height="24")
    icon_wrap.append(icon)

    link.append(content)
    link.append(icon_wrap)
    return link


def build_partners_list(soup: BeautifulSoup) -> Tag:
    wrap = soup.new_tag("div", attrs={"class": "about-partners-list"})
    for href, name, description in PARTNERS:
        wrap.append(build_partner_button(soup, href, name, description))
    return wrap


def rebuild_partners_section(soup: BeautifulSoup) -> None:
    partners_block = soup.select_one(".mantine-wnhdd8")
    if not partners_block:
        return

    list_wrap = partners_block.select_one(".mantine-10usrlv")
    if not list_wrap:
        return

    list_wrap.clear()
    list_wrap.append(build_partners_list(soup))


def rebuild_social_buttons(soup: BeautifulSoup) -> None:
    intro = soup.select_one(".about-page__intro")
    if not intro:
        return
    existing = intro.select_one(".about-page__social")
    new_social = build_social_buttons(soup)
    if existing:
        existing.replace_with(new_social)
    else:
        intro.append(new_social)


def main() -> None:
    if not ABOUT_PATH.exists():
        raise SystemExit(f"Missing {ABOUT_PATH}")

    soup = BeautifulSoup(ABOUT_PATH.read_text(encoding="utf-8"), "html.parser")
    upsert_about_css(soup)
    set_metadata(soup)
    if soup.select_one(".about-page__intro"):
        rebuild_social_buttons(soup)
    else:
        restructure_intro(soup)
    rebuild_partners_section(soup)
    ABOUT_PATH.write_text(str(soup), encoding="utf-8")
    print(f"Updated {ABOUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
