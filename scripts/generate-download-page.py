#!/usr/bin/env python3
"""Create download/index.html and QR code asset."""

from __future__ import annotations

from pathlib import Path

import qrcode
from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parent.parent
ABOUT_PATH = ROOT / "about" / "index.html"
DOWNLOAD_PATH = ROOT / "download" / "index.html"
QR_PATH = ROOT / "img" / "download-app-qr.png"

APP_STORE_URL = (
    "https://apps.apple.com/ua/app/"
    "%D0%BF%D1%80%D0%B0%D0%B2%D0%BE%D0%B2%D0%B8%D0%B9-%D0%BD%D0%B0%D0%B2%D1%96%D0%B3%D0%B0%D1%82%D0%BE%D1%80/id6477533766?l=uk"
)
GOOGLE_PLAY_URL = "https://play.google.com/store/apps/details?id=com.legalnavigatormobile"
TELEGRAM_URL = "https://t.me/pryncyp_bot"

PAGE_TITLE = "Завантажуйте Правовий навігатор"
CARD_LEAD = (
    "Мобільний застосунок і чат-бот від команди «Принцип» — ваш помічник "
    "у юридичних питаннях під час служби, поранення та після повернення додому."
)
QR_CAPTION = "Скануйте QR-код, щоб<br>завантажити Правовий навігатор"


def generate_qr_image() -> None:
    QR_PATH.parent.mkdir(parents=True, exist_ok=True)
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(APP_STORE_URL)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(QR_PATH)


def download_card_markup() -> str:
    return f"""
<div class="download-page-wrap">
  <div class="download-page-card">
    <div class="download-page-card__content">
      <p class="css-tualuh download-page-card__lead">{CARD_LEAD}</p>
      <div class="download-page-card__stores">
        <a class="download-store-btn download-store-btn--store" href="{APP_STORE_URL}" target="_blank" rel="noopener noreferrer">
          <span class="download-store-btn__icon"><img src="/img/app_store.svg" alt="" width="24" height="24"/></span>
          App Store
        </a>
        <a class="download-store-btn download-store-btn--store" href="{GOOGLE_PLAY_URL}" target="_blank" rel="noopener noreferrer">
          <span class="download-store-btn__icon"><img src="/img/google_play.svg" alt="" width="24" height="24"/></span>
          Google Play
        </a>
        <a class="download-store-btn download-store-btn--telegram" href="{TELEGRAM_URL}" target="_blank" rel="noopener noreferrer">
          <span class="download-store-btn__icon"><img src="/img/telegram.svg" alt="" width="24" height="24"/></span>
          Чат-бот для поранених
        </a>
      </div>
    </div>
    <div class="download-page-card__qr">
      <div class="download-page-card__qr-group">
        <div class="download-page-card__qr-box">
          <img src="/img/download-app-qr.png" alt="QR-код для завантаження застосунку в App Store" width="240" height="240"/>
        </div>
        <p class="css-tualuh download-page-card__qr-caption">{QR_CAPTION}</p>
      </div>
    </div>
  </div>
</div>
"""


def upsert_download_css(soup: BeautifulSoup) -> None:
    href = "/css/download-page.css?v=20"
    existing = soup.select_one('link[href*="download-page.css"]')
    if existing:
        existing["href"] = href
        return
    link_tag = f'<link href="{href}" rel="stylesheet"/>'
    internal_css = soup.select_one('link[href*="internal-layout.css"]')
    if internal_css:
        internal_css.insert_after(BeautifulSoup(link_tag, "html.parser"))
    elif soup.head:
        soup.head.append(BeautifulSoup(link_tag, "html.parser"))


def set_metadata(soup: BeautifulSoup) -> None:
    path = "/download/"
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
        if main.has_attr("data-internal-layout-baked"):
            del main["data-internal-layout-baked"]
        html = soup.find("html")
        if html and html.get("data-header-layout-baked"):
            pass
        else:
            main.attrs.pop("data-internal-layout-baked", None)

    shell = soup.select_one(".internal-page-shell")
    if shell:
        classes = list(shell.get("class") or [])
        if "internal-page-shell--download" not in classes:
            classes.append("internal-page-shell--download")
        shell["class"] = classes


def replace_main_content(soup: BeautifulSoup) -> None:
    main_col = soup.select_one(".internal-article-content .css-7nll2u") or soup.select_one(
        ".css-7nll2u"
    )
    if not main_col:
        raise SystemExit("Main column not found")

    for child in list(main_col.children):
        if isinstance(child, Tag):
            child.decompose()

    main_col.append(BeautifulSoup(download_card_markup(), "html.parser"))

    for toc in soup.select(".internal-article-toc, .internal-toc-toggle-wrap, .internal-toc-dropdown"):
        toc.decompose()


def main() -> None:
    if not ABOUT_PATH.exists():
        raise SystemExit(f"Missing template: {ABOUT_PATH}")

    generate_qr_image()

    soup = BeautifulSoup(ABOUT_PATH.read_text(encoding="utf-8"), "html.parser")
    upsert_download_css(soup)
    set_metadata(soup)
    replace_main_content(soup)

    DOWNLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_PATH.write_text(str(soup), encoding="utf-8")
    print(f"Created {DOWNLOAD_PATH.relative_to(ROOT)}")
    print(f"Created {QR_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
