#!/usr/bin/env python3
"""Inject internal page layout assets on all HTML pages except the homepage."""

from __future__ import annotations

from pathlib import Path

import re

ROOT = Path(__file__).resolve().parent.parent
CSS_TAG = '<link rel="stylesheet" href="/css/internal-layout.css?v=110"/>'
CRITICAL_BLOCK = (
    '  <style id="internal-layout-critical">'
    "html.internal-layout-active main.css-yp9swi{visibility:visible}"
    "</style>\n"
    "  <script>"
    'document.documentElement.classList.add("internal-layout-active","internal-layout-ready");'
    "</script>"
)
JS_TAG = '<script src="/js/internal-layout.js?v=61"></script>'
PATCH_RUNTIME_TAG = '<script src="/js/patch-runtime.js?v=3"></script>'

OLD_CRITICAL_RE = re.compile(
    r'<style id="internal-layout-critical">.*?</style>\s*'
    r'<script>document\.documentElement\.classList\.add\("internal-layout-active","internal-layout-(?:pending|ready)"\);.*?</script>\s*',
    re.DOTALL,
)
BROKEN_READY_CRITICAL_RE = re.compile(
    r'<style id="internal-layout-critical">html\.internal-layout-ready main\.css-yp9swi\{visibility:hidden\}.*?</style>\s*'
    r'<script>document\.documentElement\.classList\.add\("internal-layout-active","internal-layout-ready"\);</script>\s*',
    re.DOTALL,
)


def is_homepage(path: Path) -> bool:
    return path.resolve() == (ROOT / "index.html").resolve()


def upsert_critical_block(text: str) -> tuple[str, bool]:
    if OLD_CRITICAL_RE.search(text):
        return OLD_CRITICAL_RE.sub(CRITICAL_BLOCK, text, count=1), True
    if BROKEN_READY_CRITICAL_RE.search(text):
        return BROKEN_READY_CRITICAL_RE.sub(CRITICAL_BLOCK, text, count=1), True
    if "internal-layout-critical" in text and "visibility:hidden" in text:
        new_text = re.sub(
            r'<style id="internal-layout-critical">.*?</style>',
            '<style id="internal-layout-critical">'
            "html.internal-layout-active main.css-yp9swi{visibility:visible}"
            "</style>",
            text,
            count=1,
            flags=re.DOTALL,
        )
        if new_text != text:
            return new_text, True
    if "internal-layout-critical" in text:
        return text, False
    if "internal-layout.css" in text:
        return text.replace(CSS_TAG + "\n", CSS_TAG + "\n" + CRITICAL_BLOCK + "\n", 1), True
    return text, False


def main() -> None:
    css_added = js_added = critical_added = updated = 0
    for path in sorted(ROOT.rglob("*.html")):
        if is_homepage(path):
            continue

        text = path.read_text(encoding="utf-8")
        changed = False

        new_text = re.sub(
            r'href="/css/internal-layout\.css\?v=\d+"',
            'href="/css/internal-layout.css?v=110"',
            text,
        )
        if new_text != text:
            text = new_text
            changed = True
            updated += 1

        new_text = re.sub(
            r'src="/js/internal-layout\.js\?v=\d+"',
            'src="/js/internal-layout.js?v=61"',
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

        if "internal-layout.css" not in text and "</head>" in text:
            text = text.replace("</head>", f"  {CSS_TAG}\n{CRITICAL_BLOCK}\n</head>", 1)
            css_added += 1
            critical_added += 1
            changed = True
        else:
            new_text, critical_changed = upsert_critical_block(text)
            if critical_changed:
                text = new_text
                critical_added += 1
                changed = True

        if "internal-layout-pending" in text:
            text = text.replace("internal-layout-pending", "internal-layout-ready")
            text = re.sub(r"\sinternal-layout-ready\sinternal-layout-ready", " internal-layout-ready", text)
            changed = True

        if '<html lang="uk">' in text and 'class="internal-layout-active' not in text:
            text = text.replace(
                '<html lang="uk">',
                '<html lang="uk" class="internal-layout-active internal-layout-ready">',
                1,
            )
            changed = True

        if "internal-layout.js" not in text and "</body>" in text:
            text = text.replace("</body>", f"{JS_TAG}</body>", 1)
            js_added += 1
            changed = True

        if changed:
            path.write_text(text, encoding="utf-8")

    print(
        f"CSS added: {css_added}, critical: {critical_added}, JS added: {js_added}, "
        f"version bumps: {updated}"
    )


if __name__ == "__main__":
    main()
