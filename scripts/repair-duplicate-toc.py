#!/usr/bin/env python3
"""Remove leftover mobile TOC sections duplicated at the bottom of article pages."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "generate_internal_layout",
    ROOT / "scripts" / "generate-internal-layout.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
remove_duplicate_toc_sections = _mod.remove_duplicate_toc_sections
remove_orphan_toc_columns = _mod.remove_orphan_toc_columns


def repair_file(path: Path) -> bool:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    changed = False
    for content_host in soup.select(".internal-main"):
        if remove_duplicate_toc_sections(content_host):
            changed = True
        if remove_orphan_toc_columns(content_host):
            changed = True
    if changed:
        path.write_text(str(soup), encoding="utf-8")
    return changed


def main() -> None:
    repaired = 0
    for path in sorted(ROOT.rglob("*.html")):
        if repair_file(path):
            repaired += 1
    print(f"Repaired: {repaired}")


if __name__ == "__main__":
    main()
