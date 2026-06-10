#!/usr/bin/env python3
"""Import VLK guide docx into injured-military/vlk/index.html."""

from __future__ import annotations

import re
import shutil
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path
from urllib.parse import unquote, urlparse

EXTERNAL_LINK_ARROW_ICON = "/img/Arrow%20small%2045.svg"
EXTERNAL_LINK_ICON_SIZE = "16"
LEGAL_BASIS_ICON = (
    f'<img class="internal-article-legal-basis__icon" src="{EXTERNAL_LINK_ARROW_ICON}" alt="" '
    f'width="{EXTERNAL_LINK_ICON_SIZE}" height="{EXTERNAL_LINK_ICON_SIZE}" '
    'aria-hidden="true" decoding="async" loading="lazy"/>'
)

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DOCX_PATH = Path("/Users/tskyt/Downloads/vlk_guide (1).docx")
PAGE_PATH = ROOT / "injured-military" / "vlk" / "index.html"
IMG_DIR = ROOT / "img" / "vlk"
GENERATOR = ROOT / "scripts" / "generate-internal-layout.py"

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"

H2_CLASS = (
    "mantine-Text-root mantine-Title-root css-1yyhngn mantine-1iwx6kr internal-section-h2"
)
H3_CLASS = "mantine-Text-root mantine-Title-root mantine-pzgqay internal-section-h3"
H4_CLASS = "mantine-Text-root mantine-Title-root mantine-pzgqay internal-section-h4"
P_CLASS = "mantine-Text-root mantine-172zsy7"
DOWNLOAD_HOSTS = (
    "storage.googleapis.com",
    "drive.google.com",
    "docs.google.com",
    "view.officeapps.live.com",
    "turbota.mil.gov.ua",
)

# office viewer -> direct file
OFFICE_VIEWER_RE = re.compile(
    r"https://view\.officeapps\.live\.com/op/view\.aspx\?src=(.+)",
    re.I,
)


def build_legal_basis_html(href: str, title: str) -> str:
    return (
        '<aside class="internal-article-legal-basis" aria-label="Нормативна основа">'
        '<p class="internal-article-legal-basis__label">Що регулює</p>'
        '<p class="internal-article-legal-basis__doc">'
        f'<a class="internal-article-legal-basis__link" href="{escape(href, quote=True)}" '
        'target="_blank" rel="noopener noreferrer">'
        f'<span class="internal-article-legal-basis__link-text">{escape(title)}</span>'
        f"{LEGAL_BASIS_ICON}"
        '<span class="internal-article-legal-basis__sr-only"> (відкривається в новій вкладці)</span>'
        "</a></p></aside>"
    )


def is_legal_basis_chunks(chunks: list[dict]) -> bool:
    text = "".join(chunk.get("text", "") for chunk in chunks)
    if "Що регулює" not in text:
        return False
    links = [chunk for chunk in chunks if chunk.get("href")]
    return len(links) == 1 and not is_download_href(links[0]["href"])


def slug_id(title: str) -> str:
    value = title.strip().replace(" ", "_")
    value = value.replace("«", "").replace("»", "")
    return value.rstrip(":?")


def load_numbering(z: zipfile.ZipFile) -> dict[tuple[str, str], str]:
    mapping: dict[tuple[str, str], str] = {}
    try:
        root = ET.fromstring(z.read("word/numbering.xml"))
    except KeyError:
        return mapping
    abs_map: dict[str, str] = {}
    for abstract in root.findall(W + "abstractNum"):
        abs_id = abstract.get(W + "abstractNumId")
        lvl0 = abstract.find(W + "lvl")
        if abs_id is None or lvl0 is None:
            continue
        num_fmt = lvl0.find(W + "numFmt")
        if num_fmt is not None:
            abs_map[abs_id] = num_fmt.get(W + "val") or "bullet"
    for num in root.findall(W + "num"):
        num_id = num.get(W + "numId")
        abs_ref = num.find(W + "abstractNumId")
        if num_id is None or abs_ref is None:
            continue
        abs_id = abs_ref.get(W + "val")
        if abs_id in abs_map:
            mapping[(num_id, "0")] = abs_map[abs_id]
    return mapping


def runs_from_paragraph(p: ET.Element, relmap: dict[str, str]) -> list[dict]:
    chunks: list[dict] = []
    for child in p:
        tag = child.tag.split("}")[-1]
        if tag == "r":
            text = "".join((x.text or "") for x in child.findall(W + "t"))
            if not text:
                continue
            r_pr = child.find(W + "rPr")
            chunks.append(
                {
                    "text": text,
                    "bold": r_pr is not None and r_pr.find(W + "b") is not None,
                    "italic": r_pr is not None and r_pr.find(W + "i") is not None,
                }
            )
        elif tag == "hyperlink":
            rid = child.get(R + "id")
            text = "".join((x.text or "") for x in child.findall(".//" + W + "t"))
            if text:
                chunks.append({"text": text, "href": relmap.get(rid or "", "")})
    return chunks


def paragraph_meta(p: ET.Element) -> tuple[str | None, int | None, str | None]:
    p_pr = p.find(W + "pPr")
    if p_pr is None:
        return None, None, None
    style = None
    p_style = p_pr.find(W + "pStyle")
    if p_style is not None:
        style = p_style.get(W + "val")
    list_level = None
    list_num_id = None
    num_pr = p_pr.find(W + "numPr")
    if num_pr is not None:
        ilvl = num_pr.find(W + "ilvl")
        num_id = num_pr.find(W + "numId")
        list_level = int(ilvl.get(W + "val")) if ilvl is not None else 0
        list_num_id = num_id.get(W + "val") if num_id is not None else None
    return style, list_level, list_num_id


def images_from_paragraph(p: ET.Element, relmap: dict[str, str]) -> list[str]:
    targets: list[str] = []
    for blip in p.findall(".//" + A + "blip"):
        embed = blip.get(R + "embed")
        if embed and relmap.get(embed):
            targets.append(relmap[embed])
    return targets


def chunks_to_html(chunks: list[dict]) -> str:
    parts: list[str] = []
    for chunk in chunks:
        text = escape(chunk.get("text", ""))
        if not text:
            continue
        href = chunk.get("href", "")
        if href:
            href = normalize_href(href)
            parts.append(f'<a href="{escape(href, quote=True)}" target="_blank">{text}</a>')
        elif chunk.get("bold"):
            parts.append(f"<b>{text}</b>")
        elif chunk.get("italic"):
            parts.append(f"<i>{text}</i>")
        else:
            parts.append(text)
    return "".join(parts)


def normalize_href(href: str) -> str:
    match = OFFICE_VIEWER_RE.match(href)
    if match:
        return unquote(match.group(1))
    return href


def is_download_href(href: str) -> bool:
    if not href:
        return False
    host = urlparse(href).netloc.lower()
    if any(host.endswith(item) or host == item for item in DOWNLOAD_HOSTS):
        return True
    return href.lower().endswith((".docx", ".pdf", ".doc"))


def download_label(text: str, href: str) -> str:
    text = text.strip()
    if text:
        return text
    name = Path(urlparse(href).path).name
    return unquote(name).replace("_", " ").rsplit(".", 1)[0]


def split_bold_prefix(chunks: list[dict]) -> tuple[list[dict], list[dict] | None]:
    if not chunks:
        return chunks, None
    prefix: list[dict] = []
    rest: list[dict] = []
    seen_non_bold = False
    for chunk in chunks:
        if not seen_non_bold and chunk.get("bold") and "href" not in chunk:
            prefix.append(chunk)
        else:
            seen_non_bold = True
            rest.append(chunk)
    if not prefix or not rest:
        return chunks, None
    prefix_text = "".join(c["text"] for c in prefix)
    rest_text = "".join(c["text"] for c in rest)
    if rest_text.startswith(prefix_text):
        trimmed = rest_text[len(prefix_text) :]
        if trimmed and trimmed[0].isalpha():
            new_rest = [{"text": trimmed}]
            new_rest.extend(rest[1:])
            return prefix, new_rest
    return chunks, None


def parse_docx(path: Path) -> list[dict]:
    items: list[dict] = []
    with zipfile.ZipFile(path) as z:
        doc = ET.fromstring(z.read("word/document.xml"))
        rels = ET.fromstring(z.read("word/_rels/document.xml.rels"))
        relmap = {r.get("Id"): r.get("Target") for r in rels.findall(PKG + "Relationship")}
        numbering = load_numbering(z)
        media_cache: dict[str, str] = {}

        def export_image(target: str) -> str:
            if target in media_cache:
                return media_cache[target]
            idx = len(media_cache) + 1
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                static = ROOT / "img" / f"vlk_{idx}{ext}"
                if static.exists():
                    media_cache[target] = f"/img/vlk_{idx}{ext}"
                    return media_cache[target]
            blob_path = target if target.startswith("word/") else f"word/{target}"
            data = z.read(blob_path)
            ext = Path(target).suffix.lower() or ".png"
            filename = f"vlk-guide-{idx}{ext}"
            IMG_DIR.mkdir(parents=True, exist_ok=True)
            out = IMG_DIR / filename
            out.write_bytes(data)
            media_cache[target] = f"/img/vlk/{filename}"
            return media_cache[target]

        body = doc.find(W + "body")
        for child in list(body):
            tag = child.tag.split("}")[-1]
            if tag == "p":
                style, list_level, list_num_id = paragraph_meta(child)
                chunks = runs_from_paragraph(child, relmap)
                text = "".join(c.get("text", "") for c in chunks).strip()
                images = images_from_paragraph(child, relmap)
                list_type = None
                if list_num_id is not None:
                    list_type = numbering.get((list_num_id, "0"), "bullet")
                if images:
                    for target in images:
                        items.append(
                            {
                                "type": "image",
                                "src": export_image(target),
                                "alt": "",
                            }
                        )
                if text or style:
                    prefix, rest = split_bold_prefix(chunks)
                    items.append(
                        {
                            "type": "paragraph",
                            "style": style,
                            "text": text,
                            "chunks": chunks,
                            "prefix": prefix if rest else None,
                            "rest": rest,
                            "list_level": list_level,
                            "list_type": list_type,
                        }
                    )
            elif tag == "tbl":
                continue
    return items


class HtmlBuilder:
    def __init__(self) -> None:
        self.cards: list[dict] = []
        self.current: dict | None = None
        self.pending_downloads: list[tuple[str, str]] = []
        self.list_stack: list[dict] = []

    def _ensure_card(self, section_id: str, title: str, heading: str) -> None:
        if self.current and self.current.get("id") == section_id:
            return
        self._close_lists()
        self._flush_downloads()
        self.current = {"id": section_id, "title": title, "heading": heading, "parts": []}
        self.cards.append(self.current)

    def _add_part(self, html: str) -> None:
        if self.current is None:
            intro = next((c for c in self.cards if c.get("intro")), None)
            if intro is None:
                intro = {"intro": True, "parts": []}
                self.cards.insert(0, intro)
            intro["parts"].append(html)
        else:
            self.current["parts"].append(html)

    def _close_lists(self) -> None:
        while self.list_stack:
            level = self.list_stack.pop()
            self._add_part("</" + level["tag"] + ">")

    def _open_list(self, list_type: str | None, level: int) -> None:
        tag = "ol" if list_type == "decimal" else "ul"
        class_name = (
            "internal-article-numbered-list"
            if tag == "ol"
            else "internal-article-list"
        )
        while self.list_stack and self.list_stack[-1]["level"] > level:
            closed = self.list_stack.pop()
            self._add_part("</" + closed["tag"] + ">")
        if self.list_stack and self.list_stack[-1]["level"] == level:
            return
        while self.list_stack and self.list_stack[-1]["level"] < level:
            # Should not happen often; close until matching
            closed = self.list_stack.pop()
            self._add_part("</" + closed["tag"] + ">")
        self.list_stack.append({"level": level, "tag": tag})
        self._add_part(f'<{tag} class="{class_name}">')

    def _is_additional_sources_card(self) -> bool:
        return bool(
            self.current
            and (self.current.get("id") or "").startswith("Додаткові_джерела")
        )

    def _add_source_link(self, link_chunk: dict) -> None:
        href = normalize_href(link_chunk["href"])
        label = (link_chunk.get("text") or "").strip() or download_label(
            link_chunk.get("text", ""), href
        )
        self._close_lists()
        if not self.list_stack:
            self._open_list("bullet", 0)
        self._add_part(
            f'<li><a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">'
            f"{escape(label)}</a></li>"
        )

    def _flush_downloads(self) -> None:
        if not self.pending_downloads:
            return
        if self._is_additional_sources_card():
            if not self.list_stack:
                self._open_list("bullet", 0)
            for label, href in self.pending_downloads:
                self._add_part(
                    f'<li><a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">'
                    f"{escape(label)}</a></li>"
                )
            self.pending_downloads.clear()
            return
        blocks = []
        for label, href in self.pending_downloads:
            blocks.append(
                '<a class="css-uex5rt" download="" href="'
                + escape(href, quote=True)
                + '" target="_blank"><div class="css-1h5x3dy mantine-1qq82n7"><p class="css-enb2gh">'
                + escape(label)
                + '</p><img alt="file-icon" decoding="async" loading="lazy" src="/img/download_24dp.svg" style="color:transparent"/></div></a>'
            )
        self._add_part('<div class="mantine-1fv3ct">' + "".join(blocks) + "</div>")
        self.pending_downloads.clear()

    def add_heading(self, level: int, title: str) -> None:
        if not title.strip():
            return
        if level == 2:
            self._ensure_card(slug_id(title), title, "h2")
            display_title = title.rstrip(":?").strip()
            self._add_part(
                f'<h2 class="{H2_CLASS}">{escape(display_title)}</h2>'
            )
        elif level == 3:
            self._flush_downloads()
            self._close_lists()
            self._add_part(f'<h3 class="{H3_CLASS}">{escape(title)}</h3>')
        elif level == 4:
            self._flush_downloads()
            self._close_lists()
            self._add_part(f'<h4 class="{H4_CLASS}">{escape(title)}</h4>')

    def add_paragraph_item(self, item: dict) -> None:
        if item.get("prefix") and item.get("rest"):
            prefix_html = chunks_to_html(item["prefix"])
            self._add_part(f'<div class="{P_CLASS}"><b>{prefix_html}</b></div>')
            rest_item = dict(item)
            rest_item["chunks"] = item["rest"]
            rest_item["text"] = "".join(c.get("text", "") for c in item["rest"]).strip()
            self.add_paragraph_item(rest_item)
            return

        chunks = item.get("chunks") or []
        links = [c for c in chunks if c.get("href")]
        if is_legal_basis_chunks(chunks):
            href = links[0]["href"]
            title = links[0]["text"].strip()
            intro = next((c for c in self.cards if c.get("intro")), None)
            if intro is None:
                intro = {"intro": True, "legal_basis": True, "parts": []}
                self.cards.insert(0, intro)
            intro["legal_basis"] = True
            self._add_part(build_legal_basis_html(href, title))
            return
        if len(links) == 1 and len(chunks) <= 2 and is_download_href(links[0]["href"]):
            if self._is_additional_sources_card():
                self._add_source_link(links[0])
                return
            href = normalize_href(links[0]["href"])
            label = download_label(links[0]["text"], href)
            self.pending_downloads.append((label, href))
            return

        if item.get("list_level") is not None:
            self._open_list(item.get("list_type"), item["list_level"])
            html = chunks_to_html(chunks)
            self._add_part(f"<li>{html}</li>")
            return

        self._close_lists()
        html = chunks_to_html(chunks)
        if not html:
            return
        self._add_part(f'<div class="{P_CLASS}">{html}</div>')

    def add_image(self, src: str, alt: str) -> None:
        self._close_lists()
        self._flush_downloads()
        label = escape(f"Відкрити зображення: {alt}")
        self._add_part(
            '<figure class="internal-article-figure">'
            f'<button type="button" class="internal-article-figure__trigger" aria-label="{label}">'
            f'<img alt="{escape(alt)}" decoding="async" loading="lazy" src="{escape(src, quote=True)}"/>'
            "</button></figure>"
        )

    def render(self) -> str:
        self._close_lists()
        self._flush_downloads()
        chunks: list[str] = []
        for card in self.cards:
            if card.get("intro"):
                if card["parts"]:
                    chunks.append('<div class="mantine-1fr50if">')
                    if card.get("legal_basis"):
                        chunks.append("".join(card["parts"]))
                    else:
                        chunks.append(
                            '<div class="css-sdnfq3 mantine-1hdrj7p internal-article-intro-card">'
                        )
                        chunks.append("".join(card["parts"]))
                        chunks.append("</div>")
                    chunks.append("</div>")
                continue
            section_id = card["id"]
            chunks.append('<div class="mantine-1fr50if">')
            chunks.append(
                f'<div class="css-sdnfq3 mantine-1620ffq" id="{escape(section_id, quote=True)}">'
            )
            chunks.append("".join(card["parts"]))
            chunks.append("</div></div>")
        return '<div class="css-64gglc mantine-1fr50if">' + "".join(chunks) + "</div>"


def replace_article_html(page_path: Path, article_html: str) -> None:
    soup = BeautifulSoup(page_path.read_text(encoding="utf-8"), "html.parser")
    toc_wrap = soup.select_one(".internal-article-toc")
    if toc_wrap:
        toc_wrap.clear()
    dropdown = soup.select_one(".internal-toc-dropdown .mantine-List-root")
    if dropdown:
        dropdown.clear()
    host = soup.select_one(".internal-article-content .css-7nll2u")
    if not host:
        raise RuntimeError("Article host not found")
    wrapper = soup.select_one(".internal-article-content .mantine-wfw6r2")
    if not wrapper:
        raise RuntimeError("Article wrapper not found")
    inner = wrapper.select_one(".mantine-vdx6qn")
    if not inner:
        raise RuntimeError("Article inner not found")

    legacy_menu = inner.select_one(".css-1sctyhq")
    new_content = BeautifulSoup(article_html, "html.parser")
    inner.clear()
    if legacy_menu:
        inner.append(legacy_menu)
    inner.append(new_content)
    page_path.write_text(str(soup), encoding="utf-8")


def main() -> None:
    if not DOCX_PATH.exists():
        raise SystemExit(f"Docx not found: {DOCX_PATH}")

    items = parse_docx(DOCX_PATH)
    builder = HtmlBuilder()

    heading_map = {"Heading1": 1, "Heading2": 2, "Heading3": 3, "Heading4": 4}
    for item in items:
        if item["type"] == "image":
            alt = "Алгоритм ВЛК" if "vlk_1" in item["src"] or "vlk-guide-1" in item["src"] else "Схема ВЛК"
            builder.add_image(item["src"], alt)
            continue
        style = item.get("style")
        if style in heading_map and style != "Heading1":
            builder.add_heading(heading_map[style], item.get("text", ""))
            continue
        if style == "Heading1":
            continue
        builder.add_paragraph_item(item)

    article_html = builder.render()
    replace_article_html(PAGE_PATH, article_html)

    subprocess.run(
        ["python3", str(GENERATOR), "--path", "injured-military/vlk", "--force"],
        cwd=ROOT,
        check=True,
    )
    print(f"Updated {PAGE_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
