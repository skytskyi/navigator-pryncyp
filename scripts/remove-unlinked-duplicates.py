#!/usr/bin/env python3
"""Remove HTML pages with no inbound links from other HTML files.

Warning: Do not use on this site while flat *.html and */index.html coexist.
Internal links target *.html; */index.html enables directory URLs (/page/).
Removing index.html breaks paths like /serviceman/main-documents/.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

ROOT = Path(__file__).resolve().parent.parent

LINK_ATTRS = re.compile(r'(?:href|src|srcSet)=(["\'])(.*?)\1', re.IGNORECASE)

# Never delete the site entry point even if analysis changes.
KEEP_ALWAYS = {"index.html"}


def resolve_link(from_file: Path, href: str, files: dict[str, Path]) -> str | None:
    href = href.split("#")[0].split("?")[0].strip()
    if not href or href.startswith(("http://", "https://", "mailto:", "tel:", "javascript:", "data:")):
        return None

    from_rel = from_file.relative_to(ROOT).as_posix()
    from_dir = str(Path(from_rel).parent)
    if from_dir == ".":
        from_dir = ""

    base_url = f"http://x/{from_dir}/" if from_dir else "http://x/"
    joined = urljoin(base_url, href)
    path = unquote(urlparse(joined).path).lstrip("/")
    if not path or path.endswith("/"):
        path = f"{path}index.html" if path else "index.html"

    candidate_path = Path(path)
    candidates: list[str] = []
    if candidate_path.suffix == ".html":
        candidates.append(candidate_path.as_posix())
    else:
        candidates.append((candidate_path / "index.html").as_posix())
        candidates.append(f"{candidate_path.as_posix()}.html")

    for candidate in candidates:
        if candidate in files:
            return candidate
    return None


def build_inbound(files: dict[str, Path]) -> dict[str, set[str]]:
    inbound: dict[str, set[str]] = {key: set() for key in files}
    for rel, path in files.items():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in LINK_ATTRS.finditer(text):
            value = match.group(2)
            for part in value.split(","):
                part = part.strip().split(" ")[0]
                target = resolve_link(path, part, files)
                if target and target != rel:
                    inbound[target].add(rel)
    return inbound


def find_unlinked(files: dict[str, Path]) -> list[str]:
    inbound = build_inbound(files)
    return sorted(
        rel
        for rel, refs in inbound.items()
        if not refs and rel not in KEEP_ALWAYS
    )


def remove_empty_dirs() -> int:
    removed = 0
    for path in sorted(ROOT.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and path != ROOT and not any(path.iterdir()):
            path.rmdir()
            removed += 1
    return removed


def main() -> None:
    files = {p.relative_to(ROOT).as_posix(): p for p in ROOT.rglob("*.html")}
    unlinked = find_unlinked(files)

    if not unlinked:
        print("No unlinked HTML files found.")
        return

    for rel in unlinked:
        target = ROOT / rel
        target.unlink()
        print(f"Deleted {rel}")

    empty_dirs = remove_empty_dirs()
    print(f"Done: removed {len(unlinked)} file(s), {empty_dirs} empty director(ies).")


if __name__ == "__main__":
    main()
