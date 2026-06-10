#!/usr/bin/env python3
"""Inject header logo assets and anti-flicker critical CSS on all HTML pages."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_TAG = '<link rel="stylesheet" href="/css/header-logos.css?v=23"/>'
GLOBAL_CSS_TAG = '<link rel="stylesheet" href="/css/site-global.css?v=4"/>'
MOBILE_CSS_TAG = '<link rel="stylesheet" href="/css/mobile-menu.css?v=40"/>'
HEADER_CRITICAL_STYLE = (
    '  <style id="header-critical">'
    "header .css-1bgjytp.mantine-ahbyky,header .css-1bgjytp.mantine-sel6jv{background:#fff!important;opacity:1!important}"
    "header .site-header-logos{display:flex!important;align-items:center;gap:12px;flex-shrink:0;min-height:30px;min-width:280px}"
    "header .site-header-logos img{display:block!important;height:30px!important;width:auto!important;max-width:none!important}"
    "header img[alt=logo],header a:has(>img[alt=logo]){display:none!important}"
    "header .mantine-6bln36,header img[alt=search],header .mantine-us64po{display:none!important}"
    ".mantine-Drawer-body .mantine-6bln36,.mantine-Drawer-body img[alt=search],.mantine-Drawer-body .mantine-us64po{display:none!important}"
    "header .mantine-1xkg0b8:has([aria-haspopup=menu] .mantine-c1sy14),"
    "header [aria-haspopup=menu]:has(.mantine-c1sy14){display:none!important}"
    "</style>"
)
LOGO_PRELOAD = (
    '  <link rel="preload" as="image" href="/img/Logo_navigator.png"/>'
    '  <link rel="preload" as="image" href="/img/Logo_pryncyp.png"/>'
)
PERSIST_SCRIPT = '<script src="/js/header-persist.js?v=2"></script>'
PATCH_RUNTIME_HEAD = '<script src="/js/patch-runtime.js?v=5"></script>'
JS_TAG = '<script src="/js/header-logos.js?v=17"></script>'
MOBILE_JS_TAG = '<script src="/js/mobile-menu.js?v=31"></script>'
BODY_PERSIST_RE = re.compile(r"<body>", re.IGNORECASE)


def upsert_header_critical(text: str) -> tuple[str, bool]:
    changed = False
    if re.search(r'<style id="header-critical">', text):
        new_text = re.sub(
            r'<style id="header-critical">.*?</style>',
            HEADER_CRITICAL_STYLE.strip(),
            text,
            count=1,
            flags=re.S,
        )
        if new_text != text:
            text = new_text
            changed = True
    elif "header-logos.css" in text:
        text = re.sub(
            r'(<link rel="stylesheet" href="/css/header-logos\.css\?v=\d+"/>)\n?',
            r"\1\n" + HEADER_CRITICAL_STYLE + "\n",
            text,
            count=1,
        )
        changed = True
    elif "</head>" in text:
        text = text.replace(
            "</head>",
            f"  {CSS_TAG}\n{HEADER_CRITICAL_STYLE}\n{PATCH_RUNTIME_HEAD}\n</head>",
            1,
        )
        changed = True

    text = re.sub(
        r'  <script>document\.documentElement\.classList\.add\("header-pending"\);.*?</script>\n?',
        "",
        text,
        flags=re.S,
    )
    if "header-pending" in text and "header-critical" in text:
        changed = True

    return text, changed


def upsert_logo_preload(text: str) -> tuple[str, bool]:
    if 'href="/img/Logo_navigator.png"' in text:
        return text, False
    if "</head>" not in text:
        return text, False
    return text.replace("</head>", LOGO_PRELOAD + "\n</head>", 1), True


def strip_search_overlay_assets(text: str) -> tuple[str, bool]:
    changed = False
    new_text, count = re.subn(
        r'\s*<link[^>]+href="/css/site-search-overlay\.css\?v=\d+"[^>]*/>\n?',
        "\n",
        text,
        flags=re.I,
    )
    if count:
        text = new_text
        changed = True

    new_text, count = re.subn(
        r'<script src="/js/site-search-overlay\.js\?v=\d+"></script>',
        "",
        text,
    )
    if count:
        text = new_text
        changed = True

    return text, changed


def upsert_global_css(text: str) -> tuple[str, bool]:
    if "site-global.css" in text:
        new_text = re.sub(
            r'href="/css/site-global\.css\?v=\d+"',
            'href="/css/site-global.css?v=4"',
            text,
        )
        return new_text, new_text != text

    link_patterns = (
        r'(<link href="/css/header-logos\.css\?v=\d+" rel="stylesheet"/>)\n?',
        r'(<link rel="stylesheet" href="/css/header-logos\.css\?v=\d+"/>)\n?',
        r'(<link href="/css/mobile-menu\.css\?v=\d+" rel="stylesheet"/>)\n?',
        r'(<link rel="stylesheet" href="/css/mobile-menu\.css\?v=\d+"/>)\n?',
    )
    for pattern in link_patterns:
        new_text, count = re.subn(
            pattern,
            GLOBAL_CSS_TAG + "\n  " + r"\1\n",
            text,
            count=1,
        )
        if count:
            return new_text, True

    if "</head>" in text:
        return text.replace("</head>", f"  {GLOBAL_CSS_TAG}\n</head>", 1), True

    return text, False


def upsert_mobile_assets(text: str) -> tuple[str, bool]:
    changed = False

    if "mobile-menu.css" not in text:
        if "header-logos.css" in text:
            text = re.sub(
                r'(<link rel="stylesheet" href="/css/header-logos\.css\?v=\d+"/>)\n?',
                r"\1\n  " + MOBILE_CSS_TAG + "\n",
                text,
                count=1,
            )
            changed = True
        elif "</head>" in text:
            text = text.replace("</head>", f"  {MOBILE_CSS_TAG}\n</head>", 1)
            changed = True
    else:
        new_text = re.sub(
            r'href="/css/mobile-menu\.css\?v=\d+"',
            'href="/css/mobile-menu.css?v=40"',
            text,
        )
        if new_text != text:
            text = new_text
            changed = True

    if "mobile-menu.js" not in text and "</body>" in text:
        if "header-logos.js" in text:
            text = re.sub(
                r'(<script src="/js/header-logos\.js\?v=\d+"></script>)',
                r"\1" + MOBILE_JS_TAG,
                text,
                count=1,
            )
        else:
            text = text.replace("</body>", MOBILE_JS_TAG + "</body>", 1)
        changed = True
    else:
        new_text = re.sub(
            r'src="/js/mobile-menu\.js\?v=\d+"',
            'src="/js/mobile-menu.js?v=31"',
            text,
        )
        if new_text != text:
            text = new_text
            changed = True

    return text, changed


def strip_body_persist(text: str) -> tuple[str, bool]:
    new_text, count = re.subn(
        r'<script src="/js/header-persist\.js\?v=\d+"></script>',
        "",
        text,
    )
    return new_text, count > 0


def upsert_body_persist(text: str) -> tuple[str, bool]:
    text, removed = strip_body_persist(text)
    return text, removed


def main() -> None:
    css_added = critical_updated = 0
    persist_removed = runtime_moved = js_added = mobile_added = global_added = overlay_removed = updated = 0
    for path in sorted(ROOT.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        changed = False

        new_text = re.sub(
            r'href="/css/header-logos\.css\?v=\d+"',
            'href="/css/header-logos.css?v=23"',
            text,
        )
        if new_text != text:
            text = new_text
            changed = True
            updated += 1

        new_text = re.sub(
            r'src="/js/header-logos\.js\?v=\d+"',
            'src="/js/header-logos.js?v=17"',
            text,
        )
        if new_text != text:
            text = new_text
            changed = True

        new_text = re.sub(
            r'src="/js/patch-runtime\.js\?v=\d+"',
            'src="/js/patch-runtime.js?v=5"',
            text,
        )
        if new_text != text:
            text = new_text
            changed = True

        text, critical_changed = upsert_header_critical(text)
        if critical_changed:
            critical_updated += 1
            changed = True

        text, preload_changed = upsert_logo_preload(text)
        if preload_changed:
            changed = True

        text, persist_changed = upsert_body_persist(text)
        if persist_changed:
            persist_removed += 1
            changed = True

        text, overlay_changed = strip_search_overlay_assets(text)
        if overlay_changed:
            overlay_removed += 1
            changed = True

        text, global_changed = upsert_global_css(text)
        if global_changed:
            global_added += 1
            changed = True

        text, mobile_changed = upsert_mobile_assets(text)
        if mobile_changed:
            mobile_added += 1
            changed = True

        if "header-logos.css" not in text and "</head>" in text:
            text = text.replace("</head>", f"  {CSS_TAG}\n</head>", 1)
            css_added += 1
            changed = True

        head_end = text.find("</head>")
        head_chunk = text[:head_end] if head_end != -1 else text
        body_chunk = text[head_end:] if head_end != -1 else ""
        if "patch-runtime.js" not in head_chunk:
            if "patch-runtime.js" in body_chunk:
                body_tag = re.search(
                    r'<script src="/js/patch-runtime\.js\?v=\d+"></script>',
                    body_chunk,
                )
                if body_tag:
                    body_chunk = body_chunk.replace(body_tag.group(0), "", 1)
                    text = head_chunk + PATCH_RUNTIME_HEAD + "\n" + body_chunk
                    runtime_moved += 1
                    changed = True
            elif "</head>" in text:
                text = text.replace("</head>", PATCH_RUNTIME_HEAD + "\n</head>", 1)
                runtime_moved += 1
                changed = True

        if "header-logos.js" not in text and "</body>" in text:
            text = text.replace("</body>", f"{JS_TAG}</body>", 1)
            js_added += 1
            changed = True

        if changed:
            path.write_text(text, encoding="utf-8")

    print(
        f"CSS added: {css_added}, critical updated: {critical_updated}, "
        f"persist removed: {persist_removed}, runtime moved: {runtime_moved}, "
        f"JS added: {js_added}, overlay removed: {overlay_removed}, "
        f"global css: {global_added}, mobile assets: {mobile_added}, version bumps: {updated}"
    )


if __name__ == "__main__":
    main()
