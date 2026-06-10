#!/usr/bin/env python3
"""Assign accessible card palette colors in site-nav-tree.json."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TREE_PATH = ROOT / "data" / "site-nav-tree.json"

CARD_PALETTE = (
    "#686F4E",
    "#61523A",
    "#503334",
    "#47515A",
    "#434A3A",
    "#383C3B",
    "#37332E",
    "#151D23",
    "#2B3A62",
)


def assign_colors(nodes: list[dict]) -> None:
    for index, node in enumerate(nodes):
        node["color"] = CARD_PALETTE[index % len(CARD_PALETTE)]
        children = node.get("children") or []
        if children:
            assign_colors(children)


def main() -> None:
    tree = json.loads(TREE_PATH.read_text(encoding="utf-8"))
    for category in tree.get("categories", []):
        children = category.get("children") or []
        if children:
            assign_colors(children)
    TREE_PATH.write_text(
        json.dumps(tree, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Updated card colors in {TREE_PATH.name}")


if __name__ == "__main__":
    main()
