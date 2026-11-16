#!/usr/bin/env python3
"""Search the DevShop catalogue of free developer tiers.

Tries the live API first, then falls back to the bundled snapshot.
Standard library only.

  find_free_tiers.py "postgres" --limit 10
  find_free_tiers.py "email" --tag "No credit card" --json
  find_free_tiers.py --category web-hosting
  find_free_tiers.py --list-categories
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

API = "https://jrnoorbaloch.github.io/DevShop/api/services.json"
SITE = "https://jrnoorbaloch.github.io/DevShop"
SNAPSHOT = Path(__file__).resolve().parent.parent / "data" / "services.json"


def load(offline: bool) -> tuple[list[dict], str]:
    if not offline:
        try:
            with urllib.request.urlopen(API, timeout=8) as r:
                return json.load(r)["services"], "live"
        except Exception:
            pass
    with open(SNAPSHOT, encoding="utf-8") as f:
        data = json.load(f)
    return data["services"], f"snapshot {data.get('generated', '')}".strip()


def score(s: dict, terms: list[str]) -> int:
    name = s["name"].lower()
    text = " ".join([s["name"], s["domain"], s["categoryName"], s["description"], *s["details"], *s["tags"]]).lower()
    total = 0
    for t in terms:
        if name == t:
            total += 30
        elif name.startswith(t):
            total += 15
        elif t in name:
            total += 8
        elif t in text:
            total += 2
        else:
            return -1
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="*", help="search words (all must match)")
    ap.add_argument("--category", "-c", help="category slug, e.g. web-hosting")
    ap.add_argument("--tag", "-t", action="append", default=[], help="require tag (repeatable)")
    ap.add_argument("--limit", "-n", type=int, default=12)
    ap.add_argument("--json", action="store_true", help="output JSON")
    ap.add_argument("--offline", action="store_true", help="use bundled snapshot only")
    ap.add_argument("--list-categories", action="store_true")
    a = ap.parse_args()

    services, source = load(a.offline)

    if a.list_categories:
        counts: dict[tuple[str, str], int] = {}
        for s in services:
            k = (s["category"], s["categoryName"])
            counts[k] = counts.get(k, 0) + 1
        for (slug, name), n in counts.items():
            print(f"{slug:55} {n:4}  {name}")
        return 0

    terms = [t.lower() for t in " ".join(a.query).split()]
    tags = {t.lower() for t in a.tag}
    hits = []
    for s in services:
        if a.category and s["category"] != a.category:
            continue
        if tags and not tags <= {t.lower() for t in s["tags"]}:
            continue
        sc = score(s, terms) if terms else 0
        if sc >= 0:
            hits.append((sc, s))
    hits.sort(key=lambda x: (-x[0], x[1]["name"].lower()))
    hits = hits[: a.limit]

    if a.json:
        print(json.dumps([{**s, "devshop": f"{SITE}/service/{s['slug']}/"} for _, s in hits], ensure_ascii=False, indent=1))
        return 0
    print(f"# {len(hits)} result(s) · source: {source}\n")
    for _, s in hits:
        tag_str = f"  [{', '.join(s['tags'])}]" if s["tags"] else ""
        print(f"- {s['name']} — {s['url']}  ({s['categoryName']}){tag_str}")
        print(f"  {s['description']}")
        for d in s["details"][:6]:
            print(f"    · {d}")
        print(f"  DevShop: {SITE}/service/{s['slug']}/")
    if not hits:
        print("No matches. Try fewer words, or --list-categories.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
