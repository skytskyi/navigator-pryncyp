#!/usr/bin/env python3
"""Generate site navigation tree JSON from exported HTML pages."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "site-nav-tree.json"

CATEGORIES = [
    {
        "id": "serviceman",
        "label": "Військові",
        "href": "/serviceman/",
        "roots": ["serviceman"],
    },
    {
        "id": "injured",
        "label": "Поранені",
        "href": "/injured/",
        "roots": ["injured", "injured-military", "ingured-mia"],
    },
    {
        "id": "veterans",
        "label": "Ветерани",
        "href": "/veterans/",
        "roots": ["veterans"],
    },
    {
        "id": "pow",
        "label": "Звільнені з полону",
        "href": "/pow/",
        "roots": ["pow"],
    },
    {
        "id": "family",
        "label": "Родини військових та ветеранів",
        "href": "/family/",
        "roots": ["family"],
    },
]

TITLE_SUFFIX = " | Правовий навігатор"
GRAPHQL_URL = "https://api.navigator.pryncyp.org/graphql"
SUBSTAGES_QUERY = """
query ($slug: String!) {
  stages(filters: { Stage_Slug: { eq: $slug } }) {
    data {
      attributes {
        substages {
          data {
            attributes {
              Substage_Slug
              Substage_Title
              Substage_Color
              Substage_Icon { data { attributes { url } } }
            }
          }
        }
      }
    }
  }
}
"""


def load_next_data(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.DOTALL
    )
    if not match:
        return None
    return json.loads(match.group(1))


def title_from_html(path: Path, data: dict | None) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"<title>([^<]+)</title>", text)
    title = match.group(1).replace(TITLE_SUFFIX, "") if match else path.parent.name
    if not data:
        return title

    pp = data.get("props", {}).get("pageProps", {})
    api = pp.get("apiData", {})

    if "userRoles" in api:
        role = api["userRoles"]["data"][0]["attributes"]
        seo = role.get("SEO_Block") or {}
        return seo.get("Title") or role.get("Role_Title") or title

    if "stages" in api and api["stages"]["data"]:
        stage = api["stages"]["data"][0]["attributes"]
        return stage.get("Stage_Title") or title

    if "substages" in api and api["substages"]["data"]:
        sub = api["substages"]["data"][0]["attributes"]
        return sub.get("Substage_Title") or title

    return title


def graphql_request(query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables})
    try:
        proc = subprocess.run(
            [
                "curl",
                "-sS",
                "-X",
                "POST",
                GRAPHQL_URL,
                "-H",
                "Content-Type: application/json",
                "-H",
                "Accept: application/json",
                "-d",
                body,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return json.loads(proc.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError) as exc:
        raise urllib.error.URLError(str(exc)) from exc


def fetch_substages_from_api(stage_slug: str) -> dict[str, dict]:
    try:
        payload = graphql_request(SUBSTAGES_QUERY, {"slug": stage_slug})
    except urllib.error.URLError as exc:
        print(f"Warning: GraphQL request failed for stage {stage_slug}: {exc}")
        return {}

    stages = (payload.get("data") or {}).get("stages", {}).get("data") or []
    if not stages:
        return {}

    substages = stages[0]["attributes"].get("substages", {}).get("data") or []
    by_slug: dict[str, dict] = {}
    for item in substages:
        attrs = item["attributes"]
        slug = attrs.get("Substage_Slug")
        if not slug:
            continue
        by_slug[slug] = {
            "label": attrs.get("Substage_Title"),
            "color": attrs.get("Substage_Color"),
            "icon": icon_url(attrs, "Substage_Icon"),
        }
    return by_slug


def stage_slug_from_href(href: str) -> str:
    parts = href.strip("/").split("/")
    return parts[-1] if parts else ""


def substage_slug_from_child(href: str, parent_href: str) -> str:
    base = parent_href if parent_href.endswith("/") else parent_href + "/"
    if not href.startswith(base):
        return ""
    remainder = href[len(base) :].strip("/")
    return remainder.split("/")[0] if remainder else ""


def merge_substages_into_children(node: dict, substages: dict[str, dict]) -> None:
    base = node["href"] if node["href"].endswith("/") else node["href"] + "/"
    for child in node.get("children") or []:
        slug = substage_slug_from_child(child["href"], base)
        meta = substages.get(slug)
        if not meta:
            continue
        if not child.get("color") and meta.get("color"):
            child["color"] = meta["color"]
        if not child.get("icon") and meta.get("icon"):
            child["icon"] = meta["icon"]


def enrich_node_children_from_api(node: dict) -> None:
    children = node.get("children") or []
    if not children:
        return
    if all(child.get("icon") and child.get("color") for child in children):
        return
    slug = stage_slug_from_href(node["href"])
    if not slug:
        return
    substages = fetch_substages_from_api(slug)
    if substages:
        merge_substages_into_children(node, substages)


def walk_tree_nodes(nodes: list[dict]) -> None:
    for node in nodes:
        enrich_node_children_from_api(node)
        walk_tree_nodes(node.get("children") or [])


def enrich_tree_from_api(tree: dict) -> int:
    updated = 0
    for category in tree.get("categories") or []:
        before = json.dumps(category, ensure_ascii=False)
        walk_tree_nodes(category.get("children") or [])
        if json.dumps(category, ensure_ascii=False) != before:
            updated += 1
    return updated


def icon_url(attrs: dict, key: str) -> str | None:
    block = attrs.get(key)
    if not block:
        return None
    try:
        return block["data"]["attributes"]["url"]
    except (KeyError, TypeError):
        return None


def node_from_stage(attrs: dict, base_href: str) -> dict:
    slug = attrs["Stage_Slug"]
    href = f"{base_href}{slug}/"
    children: list[dict] = []

    substages = attrs.get("substages", {}).get("data") or []
    for item in substages:
        sub_attrs = item["attributes"]
        sub_slug = sub_attrs["Substage_Slug"]
        children.append(
            {
                "label": sub_attrs["Substage_Title"],
                "href": f"{href}{sub_slug}/",
                "color": sub_attrs.get("Substage_Color"),
                "icon": icon_url(sub_attrs, "Substage_Icon"),
                "children": [],
            }
        )

    nested = attrs.get("stages", {}).get("data") or []
    for item in nested:
        nested_attrs = item["attributes"]
        children.append(node_from_stage(nested_attrs, href))

    node = {
        "label": attrs["Stage_Title"],
        "href": href,
        "color": attrs.get("Stage_Color"),
        "icon": icon_url(attrs, "Stage_Icon"),
        "children": children,
    }
    return enrich_node_from_page(node)


def substages_from_stage(stage: dict, base: str) -> list[dict]:
    children: list[dict] = []
    for item in stage.get("substages", {}).get("data") or []:
        sub = item["attributes"]
        children.append(
            {
                "label": sub["Substage_Title"],
                "href": f"{base}{sub['Substage_Slug']}/",
                "color": sub.get("Substage_Color"),
                "icon": icon_url(sub, "Substage_Icon"),
                "children": [],
            }
        )
    return children


def enrich_node_from_page(node: dict) -> dict:
    rel = node["href"].strip("/")
    page = ROOT / rel / "index.html"
    if not page.exists():
        return node

    data = load_next_data(page)
    if not data:
        return node

    api = data["props"]["pageProps"].get("apiData", {})
    if "stages" not in api or not api["stages"]["data"]:
        return node

    stage = api["stages"]["data"][0]["attributes"]
    base = node["href"] if node["href"].endswith("/") else node["href"] + "/"
    substages = substages_from_stage(stage, base)

    if node.get("children") and substages:
        by_slug = {
            substage_slug_from_child(sub["href"], base): sub for sub in substages
        }
        merge_substages_into_children(node, by_slug)
    elif substages:
        node["children"] = substages
        if not node.get("color"):
            node["color"] = stage.get("Stage_Color")
        if not node.get("icon"):
            node["icon"] = icon_url(stage, "Stage_Icon")

    return node


def role_children(path: Path, role_slug: str) -> list[dict]:
    index = path / role_slug / "index.html"
    if not index.exists():
        return []

    data = load_next_data(index)
    if not data:
        return []

    api = data["props"]["pageProps"]["apiData"]
    role = api["userRoles"]["data"][0]["attributes"]
    stages = role.get("stages", {}).get("data") or []
    base = f"/{role_slug}/"
    return [node_from_stage(item["attributes"], base) for item in stages]


def injured_children() -> list[dict]:
    children: list[dict] = []

    for slug, label in (
        ("injured-military", "Поранені із системи МОУ"),
        ("ingured-mia", "Поранені із системи МВС"),
    ):
        index = ROOT / slug / "index.html"
        data = load_next_data(index)
        color = None
        icon = None
        stage_children: list[dict] = []
        if data:
            role = data["props"]["pageProps"]["apiData"]["userRoles"]["data"][0][
                "attributes"
            ]
            color = role.get("Role_Color")
            icon = icon_url(role, "Role_Icon")
            stages = role.get("stages", {}).get("data") or []
            stage_children = [
                node_from_stage(item["attributes"], f"/{slug}/") for item in stages
            ]

        children.append(
            {
                "label": label,
                "href": f"/{slug}/",
                "color": color,
                "icon": icon,
                "children": stage_children,
            }
        )

    return children


def build_category(category: dict) -> dict:
    cat_id = category["id"]
    if cat_id == "injured":
        children = injured_children()
    else:
        children = role_children(ROOT, category["roots"][0])

    return {
        "id": cat_id,
        "label": category["label"],
        "href": category["href"],
        "children": children,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--enrich-api-only",
        action="store_true",
        help="Load existing site-nav-tree.json and merge substage icon/color from GraphQL",
    )
    args = parser.parse_args()

    if args.enrich_api_only:
        if not OUT.exists():
            raise SystemExit(f"Missing {OUT}")
        tree = json.loads(OUT.read_text(encoding="utf-8"))
        updated = enrich_tree_from_api(tree)
        OUT.write_text(
            json.dumps(tree, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Enriched {OUT} from GraphQL ({updated} categories touched)")
        return

    tree = {"categories": [build_category(cat) for cat in CATEGORIES]}
    enrich_tree_from_api(tree)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(tree, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
