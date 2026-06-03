#!/usr/bin/env python3
"""Repair internal pages where .internal-article-layout is orphaned under .internal-page-shell."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "generate_internal_layout",
    ROOT / "scripts" / "generate-internal-layout.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
repair_shell_layout = _mod.repair_shell_layout


def shell_is_broken(shell: Tag) -> bool:
    content_host = shell.select_one(".internal-main")
    if not content_host:
        return False
    for child in shell.children:
        if isinstance(child, Tag) and "internal-article-layout" in (child.get("class") or []):
            return child not in content_host.descendants
    return False


def repair_page(html_path: Path) -> bool:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    shell = soup.select_one(".internal-page-shell")
    if not shell or not shell_is_broken(shell):
        return False
    if not repair_shell_layout(shell):
        return False
    html_path.write_text(str(soup), encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair orphaned internal-article-layout in page shell.")
    parser.add_argument("--path", default="", help="Repair one page or directory only")
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

    repaired = skipped = 0
    for html_path in files:
        if repair_page(html_path):
            repaired += 1
        else:
            skipped += 1

    print(f"Repaired: {repaired}, skipped: {skipped}")


if __name__ == "__main__":
    main()
