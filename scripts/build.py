#!/usr/bin/env python3
"""
DevShop static site generator.

Parses the community-maintained free-for-dev markdown list into structured
data and renders a fast, SEO-friendly static site:

  dist/
    index.html                  home: search, filters, categories
    category/<slug>/index.html  one pre-rendered page per category
    service/<slug>/index.html   one pre-rendered page per service
    api/services.json           public JSON API (all services)
    api/categories.json         public JSON API (category index)
    sitemap.xml, robots.txt, manifest.webmanifest, sw.js, 404.html

Standard library only. Usage:
    SITE_URL=https://user.github.io/DevShop python3 scripts/build.py
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "source" / "free-for-dev.md"
STATIC = ROOT / "static"
DIST = ROOT / "dist"

SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")
BASE = urlparse(SITE_URL).path.rstrip("/")  # e.g. "/DevShop" on GitHub Pages
SITE_NAME = "DevShop"
TAGLINE = "Every free developer tier, on one shelf."
SITE_DESC = (
    "DevShop is a searchable directory of {n}+ SaaS, PaaS, IaaS and API services "
    "with genuinely free tiers for developers: hosting, databases, CI/CD, "
    "monitoring, auth, email, AI and more."
)
REPO_URL = os.environ.get("REPO_URL", "https://github.com/jrnoorbaloch/DevShop")
UPSTREAM = "https://github.com/ripienaar/free-for-dev"
TODAY = dt.date.today().isoformat()

# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
ITEM_RE = re.compile(r"^  [*-] \[(?P<name>[^\]]+)\]\((?P<url>[^)\s]+)\)\s*(?:[-–—:]\s*)?(?P<desc>.*)$")
SECTION_RE = re.compile(r"^## (?P<title>.+?)\s*$")

TAG_RULES = [
    ("No credit card", re.compile(r"no credit card|without (?:a |any )?credit card|no cc\b|no card required", re.I)),
    ("Open source", re.compile(r"open[- ]source", re.I)),
    ("Unlimited", re.compile(r"\bunlimited\b", re.I)),
    ("Forever free", re.compile(r"forever|always[- ]free|free forever|lifetime", re.I)),
    ("AI / ML", re.compile(r"\bAI\b|\bLLMs?\b|\bGPT|machine learning|\bML\b|inference|embedding", re.I)),
    ("API", re.compile(r"\bAPIs?\b")),
    ("Students", re.compile(r"student|education", re.I)),
    ("EU / GDPR", re.compile(r"\bEU\b|GDPR|europe", re.I)),
    ("Self-host option", re.compile(r"self[- ]host", re.I)),
    ("Teams", re.compile(r"\bteam(s)?\b|collaborat", re.I)),
]

CATEGORY_ICONS = {
    "cloud": "☁️", "repo": "📦", "api": "🔌", "data": "🗄️", "ml": "🧠", "ai": "🤖",
    "team": "👥", "cms": "📝", "code": "💻", "ci": "🚀", "test": "🧪", "security": "🔐",
    "auth": "🔑", "mobile": "📱", "messag": "💬", "log": "📜", "translat": "🌍",
    "monitor": "📈", "crash": "💥", "search": "🔎", "education": "🎓", "email": "✉️",
    "feature": "🚩", "font": "🔤", "form": "🧾", "cdn": "🛡️", "paas": "🧩", "baas": "🧱",
    "low-code": "🧰", "hosting": "🌐", "dns": "🧭", "domain": "🏷️", "iaas": "🖥️",
    "tunnel": "🚇", "issue": "🐞", "storage": "💾", "design": "🎨", "map": "🗺️",
    "package": "📦", "ide": "⌨️", "analytic": "📊", "session": "🎥", "phone": "☎️",
    "payment": "💳", "docker": "🐳", "blog": "✍️", "comment": "🗨️", "screenshot": "📸",
    "flutter": "🦋", "privacy": "🕶️", "misc": "🧺", "remote": "🖱️", "other": "🎁",
    "management": "🗂️",
}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "item"


def icon_for(title: str) -> str:
    t = title.lower()
    for key, icon in (("low-code", "🧰"), ("maps", "🗺️"), ("phone", "☎️"), ("mobile number", "☎️"), ("screenshot", "📸")):
        if key in t:
            return icon
    for key, icon in CATEGORY_ICONS.items():
        if re.search(r"\b" + re.escape(key), t):
            return icon
    return "🛒"


def md_inline(text: str) -> str:
    """Tiny, safe inline-markdown renderer: links, `code`, **bold**."""
    out, pos = [], 0
    token = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|(https?://[^\s)]+)")
    for m in token.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        if m.group(1):
            href = m.group(2)
            if href.startswith(("http://", "https://")):
                out.append(f'<a href="{html.escape(href)}" rel="noopener nofollow" target="_blank">{html.escape(m.group(1))}</a>')
            else:
                out.append(html.escape(m.group(1)))
        elif m.group(3):
            out.append(f"<code>{html.escape(m.group(3))}</code>")
        elif m.group(4):
            out.append(f"<strong>{html.escape(m.group(4))}</strong>")
        else:
            u = m.group(5).rstrip(".,;")
            out.append(f'<a href="{html.escape(u)}" rel="noopener nofollow" target="_blank">{html.escape(u)}</a>')
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def md_plain(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return re.sub(r"[`*]", "", text).strip()


def parse(md: str):
    categories, services = [], []
    current_cat, current = None, None
    started = False
    used_slugs: dict[str, int] = {}

    for raw in md.splitlines():
        line = raw.rstrip()
        sec = SECTION_RE.match(line)
        if sec:
            title = sec.group("title").strip()
            started = True
            current = None
            cslug = slugify(title)
            current_cat = {"slug": cslug, "name": title, "icon": icon_for(title), "count": 0}
            categories.append(current_cat)
            continue
        if not started or current_cat is None:
            continue
        m = ITEM_RE.match(line)
        if m:
            name = m.group("name").strip()
            url = m.group("url").strip()
            desc_md = m.group("desc").strip()
            base_slug = slugify(name)
            n = used_slugs.get(base_slug, 0)
            used_slugs[base_slug] = n + 1
            slug = base_slug if n == 0 else f"{base_slug}-{n + 1}"
            current = {
                "id": len(services) + 1,
                "slug": slug,
                "name": name,
                "url": url,
                "domain": (urlparse(url).hostname or "").removeprefix("www."),
                "category": current_cat["slug"],
                "categoryName": current_cat["name"],
                "description": md_plain(desc_md),
                "descriptionHtml": md_inline(desc_md),
                "details": [],
            }
            services.append(current)
            current_cat["count"] += 1
            continue
        # Nested bullet → detail of the previous top-level service
        nested = re.match(r"^\s{3,}[*-]\s+(.*)$", line)
        if nested and current is not None:
            current["details"].append(nested.group(1).strip())
            continue
        if not line.strip() or line.startswith("**["):
            continue

    for s in services:
        if not s["description"] and s["details"]:
            parts = [md_plain(d).split(" - ")[0].strip() for d in s["details"][:6]]
            parts = [p for p in parts if p and not p.lower().startswith("full")][:5]
            s["description"] = "Free tier includes " + ", ".join(parts) + " and more."
            s["descriptionHtml"] = html.escape(s["description"])
        details_html = [md_inline(d) for d in s["details"]]
        haystack = " ".join([s["description"], *s["details"]])
        s["tags"] = [label for label, rx in TAG_RULES if rx.search(haystack)]
        s["detailsHtml"] = details_html
        s["details"] = [md_plain(d) for d in s["details"]]

    categories = [c for c in categories if c["count"] > 0]
    return categories, services


# --------------------------------------------------------------------------- #
# HTML helpers
# --------------------------------------------------------------------------- #
def u(path: str = "/") -> str:
    """Site-relative URL honoring the base path (GitHub Pages project sites)."""
    return f"{BASE}{path}"


def abs_url(path: str = "/") -> str:
    return f"{SITE_URL}{path}"


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def truncate(s: str, n: int = 155) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def layout(*, title: str, description: str, path: str, body: str, jsonld: list | None = None,
           page_type: str = "website", extra_head: str = "", body_attrs: str = "") -> str:
    canonical = abs_url(path)
    ld = "".join(
        f'<script type="application/ld+json">{json.dumps(obj, ensure_ascii=False)}</script>'
        for obj in (jsonld or [])
    )
    return f"""<!doctype html>
<html lang="en" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta name="theme-color" content="#0b0d10" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#f7f5ef" media="(prefers-color-scheme: light)">
<meta name="color-scheme" content="dark light">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:type" content="{page_type}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(abs_url('/assets/og.png'))}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="twitter:image" content="{esc(abs_url('/assets/og.png'))}">
<link rel="icon" href="{u('/assets/favicon.svg')}" type="image/svg+xml">
<link rel="apple-touch-icon" href="{u('/assets/icon-192.png')}">
<link rel="manifest" href="{u('/manifest.webmanifest')}">
<link rel="search" type="application/opensearchdescription+xml" title="DevShop" href="{u('/opensearch.xml')}">
<link rel="stylesheet" href="{u('/assets/style.css')}?v={BUILD_ID}">
<script>try{{var t=localStorage.getItem('ds-theme');if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
{extra_head}{ld}
</head>
<body {body_attrs}>
<a class="skip" href="#main">Skip to content</a>
<header class="topbar">
  <a class="brand" href="{u('/')}" aria-label="DevShop home">
    <span class="brand-mark" aria-hidden="true">$0</span><span class="brand-name">Dev<b>Shop</b></span>
  </a>
  <nav class="topnav" aria-label="Primary">
    <a href="{u('/#categories')}">Categories</a>
    <a href="{u('/#browse')}" data-saved-link>Saved <span class="saved-count" data-saved-count>0</span></a>
    <a href="{u('/api/services.json')}">API</a>
    <a href="{esc(REPO_URL)}" rel="noopener">GitHub</a>
  </nav>
  <button class="icon-btn" id="theme-toggle" type="button" aria-label="Toggle colour theme" title="Toggle theme">
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M12 3a9 9 0 1 0 9 9c0-.46-.04-.92-.1-1.36a5.39 5.39 0 0 1-4.4 2.26 5.4 5.4 0 0 1-3.14-9.8c-.44-.06-.9-.1-1.36-.1z"/></svg>
  </button>
</header>
<main id="main">
{body}
</main>
<footer class="footer">
  <div class="footer-inner">
    <p><strong>DevShop</strong> — {esc(TAGLINE)}</p>
    <p class="muted">Data from the community list <a href="{UPSTREAM}" rel="noopener">free-for-dev</a>
    (1600+ contributors), synced automatically. Free tiers change often — always confirm on the provider's pricing page.</p>
    <p class="muted"><a href="{u('/sitemap.xml')}">Sitemap</a> · <a href="{u('/api/services.json')}">JSON API</a> · <a href="{esc(REPO_URL)}">Source</a> · Updated {TODAY}</p>
  </div>
</footer>
<script src="{u('/assets/app.js')}?v={BUILD_ID}" defer></script>
</body>
</html>"""


def service_card(s: dict, *, heading: str = "h3") -> str:
    tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in s["tags"][:4])
    return f"""<article class="card" data-id="{s['id']}">
  <div class="card-head">
    <img class="fav" loading="lazy" decoding="async" width="28" height="28" alt="" src="https://icons.duckduckgo.com/ip3/{esc(s['domain'])}.ico" onerror="this.style.visibility='hidden'">
    <{heading} class="card-title"><a href="{u('/service/' + s['slug'] + '/')}">{esc(s['name'])}</a></{heading}>
    <span class="price" aria-label="Free tier">$0</span>
  </div>
  <p class="card-desc">{s['descriptionHtml'] or esc('Free tier available.')}</p>
  <div class="card-foot">
    <a class="chip cat" href="{u('/category/' + s['category'] + '/')}">{esc(s['categoryName'])}</a>{tags}
  </div>
  <div class="card-actions">
    <a class="btn btn-primary" href="{esc(s['url'])}" target="_blank" rel="noopener nofollow">Visit ↗</a>
    <button class="btn save-btn" type="button" data-save="{s['id']}" aria-pressed="false">☆ Save</button>
  </div>
</article>"""


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def page_home(categories, services):
    cat_grid = "".join(
        f'<a class="cat-tile" href="{u("/category/" + c["slug"] + "/")}" data-cat="{c["slug"]}">'
        f'<span class="cat-icon" aria-hidden="true">{c["icon"]}</span>'
        f'<span class="cat-name">{esc(c["name"])}</span><span class="cat-count">{c["count"]}</span></a>'
        for c in categories
    )
    tag_counts = {}
    for s in services:
        for t in s["tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    tag_opts = "".join(
        f'<button type="button" class="chip filter-tag" data-tag="{esc(t)}" aria-pressed="false">{esc(t)} <small>{n}</small></button>'
        for t, n in sorted(tag_counts.items(), key=lambda kv: -kv[1])
    )
    cat_opts = "".join(f'<option value="{c["slug"]}">{esc(c["name"])} ({c["count"]})</option>' for c in categories)
    popular = [c for c in categories if c["slug"] in (
        "major-cloud-providers", "web-hosting", "managed-data-services", "ci-and-cd",
        "authentication-authorization-and-user-management", "email", "generative-ai", "monitoring")]
    popular_links = " ".join(f'<a href="{u("/category/" + c["slug"] + "/")}">{esc(c["name"])}</a>' for c in popular)
    desc = SITE_DESC.format(n=len(services) // 100 * 100)

    body = f"""
<section class="hero">
  <p class="eyebrow">{len(services):,} services · {len(categories)} categories · always $0 to start</p>
  <h1>Every free developer tier,<br><span class="hl">on one shelf.</span></h1>
  <p class="lead">Find free hosting, databases, CI/CD, auth, email, monitoring and AI APIs in seconds.
  Search, filter, save your picks, and ship without a credit card.</p>
  <form class="search" role="search" action="{u('/')}" onsubmit="return false">
    <label class="sr-only" for="q">Search free services</label>
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="currentColor" d="M10 4a6 6 0 1 0 3.87 10.59l4.27 4.27 1.41-1.41-4.27-4.27A6 6 0 0 0 10 4zm0 2a4 4 0 1 1 0 8 4 4 0 0 1 0-8z"/></svg>
    <input id="q" name="q" type="search" autocomplete="off" spellcheck="false"
      placeholder="Try “postgres”, “no credit card”, “email api”…" aria-describedby="search-hint">
    <kbd id="search-hint" title="Press / to search">/</kbd>
  </form>
  <p class="popular">Popular: {popular_links}</p>
</section>

<section id="browse" class="browse" aria-label="Browse services">
  <div class="toolbar">
    <div class="toolbar-row">
      <label class="sr-only" for="cat">Category</label>
      <select id="cat"><option value="">All categories</option>{cat_opts}</select>
      <label class="sr-only" for="sort">Sort</label>
      <select id="sort">
        <option value="relevance">Sort: Relevance</option>
        <option value="az">Sort: A → Z</option>
        <option value="za">Sort: Z → A</option>
        <option value="category">Sort: Category</option>
      </select>
      <button type="button" class="chip" id="saved-only" aria-pressed="false">★ Saved only</button>
      <button type="button" class="chip" id="random-btn" title="Open a random service">🎲 Surprise me</button>
      <button type="button" class="chip" id="view-toggle" aria-pressed="false" title="Toggle compact list view">☰ Compact</button>
    </div>
    <div class="toolbar-row tags" role="group" aria-label="Filter by feature">{tag_opts}</div>
    <p class="result-meta" aria-live="polite"><span id="result-count">{len(services):,}</span> services <button type="button" class="link-btn" id="clear-filters" hidden>Clear filters</button>
      <button type="button" class="link-btn" id="export-saved" hidden>Export saved (.md)</button>
      <button type="button" class="link-btn" id="share-view">Copy link to this view</button></p>
  </div>
  <div id="results" class="grid" data-mode="app">
    {''.join(service_card(s) for s in services[:24])}
  </div>
  <div id="sentinel" aria-hidden="true"></div>
  <noscript><p>JavaScript is off — browse by <a href="#categories">category</a> instead.</p></noscript>
</section>

<section id="categories" class="categories">
  <h2>Browse by category</h2>
  <div class="cat-grid">{cat_grid}</div>
</section>

<section class="faq">
  <h2>Frequently asked questions</h2>
  <details><summary>What counts as a “free tier” on DevShop?</summary>
  <p>Only as-a-service offerings with a real free tier — not a short trial. Time-limited tiers must last at least 12 months. Self-hosted software is not listed.</p></details>
  <details><summary>Where does the data come from?</summary>
  <p>DevShop is built on top of the community-maintained <a href="{UPSTREAM}">free-for-dev</a> list and re-syncs it automatically every week, then adds search, tags, per-service pages and a JSON API.</p></details>
  <details><summary>Is there an API?</summary>
  <p>Yes. The whole catalogue is available as static JSON at <a href="{u('/api/services.json')}"><code>/api/services.json</code></a> and <a href="{u('/api/categories.json')}"><code>/api/categories.json</code></a>. No key needed.</p></details>
  <details><summary>Does it work offline?</summary>
  <p>Yes — DevShop is a Progressive Web App. Install it from your browser and your saved services stay available offline.</p></details>
</section>
"""
    faq_ld = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": "What counts as a free tier on DevShop?",
             "acceptedAnswer": {"@type": "Answer", "text": "Only as-a-service offerings with a real free tier, not a short trial. Time-limited tiers must last at least 12 months."}},
            {"@type": "Question", "name": "Where does the data come from?",
             "acceptedAnswer": {"@type": "Answer", "text": "DevShop is built on the community-maintained free-for-dev list and re-syncs it weekly."}},
            {"@type": "Question", "name": "Is there an API?",
             "acceptedAnswer": {"@type": "Answer", "text": "Yes, the catalogue is available as static JSON at /api/services.json."}},
        ],
    }
    site_ld = {
        "@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": abs_url("/"),
        "description": desc,
        "potentialAction": {"@type": "SearchAction", "target": abs_url("/?q={search_term_string}"),
                            "query-input": "required name=search_term_string"},
    }
    org_ld = {"@context": "https://schema.org", "@type": "Organization", "name": SITE_NAME,
              "url": abs_url("/"), "logo": abs_url("/assets/icon-512.png"), "sameAs": [REPO_URL]}
    return layout(
        title=f"DevShop — {len(services):,}+ Free Tiers for Developers (Hosting, DB, CI/CD, AI)",
        description=truncate(desc, 160), path="/", body=body, jsonld=[site_ld, org_ld, faq_ld],
        body_attrs='data-page="home"',
    )


def page_category(cat, categories, services):
    items = [s for s in services if s["category"] == cat["slug"]]
    idx = categories.index(cat)
    prev_c = categories[idx - 1] if idx > 0 else None
    next_c = categories[idx + 1] if idx + 1 < len(categories) else None
    names = ", ".join(s["name"] for s in items[:6])
    desc = truncate(f"{len(items)} {cat['name']} services with free tiers for developers, including {names}. Compare limits and start free.", 160)
    pager = '<nav class="pager" aria-label="Categories">'
    if prev_c:
        pager += f'<a href="{u("/category/" + prev_c["slug"] + "/")}">← {esc(prev_c["name"])}</a>'
    pager += "<span></span>"
    if next_c:
        pager += f'<a href="{u("/category/" + next_c["slug"] + "/")}">{esc(next_c["name"])} →</a>'
    pager += "</nav>"
    body = f"""
<nav class="crumbs" aria-label="Breadcrumb"><a href="{u('/')}">DevShop</a> <span>/</span> <a href="{u('/#categories')}">Categories</a> <span>/</span> <span aria-current="page">{esc(cat['name'])}</span></nav>
<section class="page-head">
  <p class="eyebrow">{cat['icon']} Category · {len(items)} services</p>
  <h1>Free {esc(cat['name'])} services for developers</h1>
  <p class="lead">Hand-picked {esc(cat['name'].lower())} tools with genuine free tiers. Filter below, save the ones you like, then hit Visit.</p>
  <form class="search search-sm" role="search" onsubmit="return false">
    <label class="sr-only" for="q">Filter {esc(cat['name'])}</label>
    <input id="q" type="search" autocomplete="off" placeholder="Filter {len(items)} services…">
  </form>
</section>
<section class="browse">
  <p class="result-meta" aria-live="polite"><span id="result-count">{len(items)}</span> services</p>
  <div id="results" class="grid" data-mode="static">
    {''.join(service_card(s, heading='h2') for s in items)}
  </div>
  {pager}
</section>"""
    ld = [
        {"@context": "https://schema.org", "@type": "CollectionPage", "name": f"Free {cat['name']} services",
         "url": abs_url(f"/category/{cat['slug']}/"), "description": desc,
         "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": [
             {"@type": "ListItem", "position": i + 1, "url": abs_url(f"/service/{s['slug']}/"), "name": s["name"]}
             for i, s in enumerate(items)]}},
        breadcrumbs([("DevShop", "/"), (cat["name"], f"/category/{cat['slug']}/")]),
    ]
    return layout(title=f"{len(items)} Free {cat['name']} Services for Developers | DevShop",
                  description=desc, path=f"/category/{cat['slug']}/", body=body, jsonld=ld,
                  body_attrs=f'data-page="category" data-cat="{cat["slug"]}"')


def breadcrumbs(trail):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": name, "item": abs_url(path)}
        for i, (name, path) in enumerate(trail)]}


def page_service(s, services, cat):
    related = [x for x in services if x["category"] == s["category"] and x["id"] != s["id"]]
    # Prefer related services sharing tags, then neighbours alphabetically
    related.sort(key=lambda x: (-len(set(x["tags"]) & set(s["tags"])), abs(x["id"] - s["id"])))
    related = related[:6]
    details = ""
    if s["detailsHtml"]:
        details = "<h2>What's included in the free tier</h2><ul class='details'>" + "".join(
            f"<li>{d}</li>" for d in s["detailsHtml"]) + "</ul>"
    tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in s["tags"])
    desc = truncate(f"{s['name']} free tier: {s['description'] or 'free plan for developers'}", 160)
    body = f"""
<nav class="crumbs" aria-label="Breadcrumb"><a href="{u('/')}">DevShop</a> <span>/</span> <a href="{u('/category/' + cat['slug'] + '/')}">{esc(cat['name'])}</a> <span>/</span> <span aria-current="page">{esc(s['name'])}</span></nav>
<article class="service" data-id="{s['id']}">
  <header class="service-head">
    <img class="fav fav-lg" width="56" height="56" alt="" src="https://icons.duckduckgo.com/ip3/{esc(s['domain'])}.ico" onerror="this.style.visibility='hidden'">
    <div>
      <p class="eyebrow">{cat['icon']} {esc(cat['name'])}</p>
      <h1>{esc(s['name'])} <span class="muted">free tier</span></h1>
      <p class="domain">{esc(s['domain'])}</p>
    </div>
    <span class="price price-lg">$0</span>
  </header>
  <p class="lead">{s['descriptionHtml'] or 'Free tier available for developers.'}</p>
  {details}
  <div class="tags-row">{tags}</div>
  <div class="card-actions">
    <a class="btn btn-primary btn-lg" href="{esc(s['url'])}" target="_blank" rel="noopener nofollow">Visit {esc(s['name'])} ↗</a>
    <button class="btn btn-lg save-btn" type="button" data-save="{s['id']}" aria-pressed="false">☆ Save</button>
    <button class="btn btn-lg" type="button" data-share>Share</button>
  </div>
  <p class="note">Free tiers change. Last synced {TODAY} — confirm current limits on the provider's pricing page.
  Something wrong? <a href="{UPSTREAM}/edit/master/README.md">Suggest a fix upstream</a>.</p>
</article>
<section class="related">
  <h2>Alternatives to {esc(s['name'])} in {esc(cat['name'])}</h2>
  <div class="grid">{''.join(service_card(r) for r in related)}</div>
  <p><a class="btn" href="{u('/category/' + cat['slug'] + '/')}">See all {cat['count']} {esc(cat['name'])} services →</a></p>
</section>"""
    ld = [
        {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": s["name"],
         "url": s["url"], "applicationCategory": "DeveloperApplication", "operatingSystem": "Web",
         "description": s["description"] or f"{s['name']} free tier",
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD", "description": "Free tier"}},
        breadcrumbs([("DevShop", "/"), (cat["name"], f"/category/{cat['slug']}/"),
                     (s["name"], f"/service/{s['slug']}/")]),
    ]
    return layout(title=f"{s['name']} Free Tier — Limits & Alternatives | DevShop", description=desc,
                  path=f"/service/{s['slug']}/", body=body, jsonld=ld, page_type="article",
                  body_attrs='data-page="service"')


def page_404():
    body = f"""<section class="page-head center"><p class="price price-lg">404</p>
<h1>This shelf is empty.</h1><p class="lead">The page you're looking for isn't here — but {len(SERVICES):,} free services are.</p>
<p><a class="btn btn-primary btn-lg" href="{u('/')}">Back to the shop</a></p></section>"""
    html_ = layout(title="Not found | DevShop", description="Page not found.", path="/404.html", body=body)
    return html_.replace('content="index,follow,max-image-preview:large"', 'content="noindex"')


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main():
    global BUILD_ID, SERVICES
    md = SOURCE.read_text(encoding="utf-8")
    categories, services = parse(md)
    SERVICES = services
    BUILD_ID = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M")
    if len(services) < 500:
        sys.exit(f"Parse sanity check failed: only {len(services)} services found")

    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(STATIC, DIST)

    # Public JSON API
    api_services = [{k: s[k] for k in ("id", "slug", "name", "url", "domain", "category", "categoryName",
                                       "description", "details", "tags")} for s in services]
    meta = {"generated": TODAY, "count": len(services), "source": UPSTREAM, "site": abs_url("/")}
    write(DIST / "api/services.json", json.dumps({**meta, "services": api_services}, ensure_ascii=False))
    write(DIST / "api/categories.json", json.dumps({**meta, "categories": categories}, ensure_ascii=False, indent=1))
    # Compact client index (home page app)
    client = [[s["id"], s["slug"], s["name"], s["url"], s["domain"], s["category"], s["descriptionHtml"],
               s["tags"], s["description"]] for s in services]
    write(DIST / "assets/index.json", json.dumps(
        {"c": {c["slug"]: c["name"] for c in categories}, "s": client}, ensure_ascii=False, separators=(",", ":")))

    write(DIST / "index.html", page_home(categories, services))
    for c in categories:
        write(DIST / f"category/{c['slug']}/index.html", page_category(c, categories, services))
    cat_by_slug = {c["slug"]: c for c in categories}
    for s in services:
        write(DIST / f"service/{s['slug']}/index.html", page_service(s, services, cat_by_slug[s["category"]]))
    write(DIST / "404.html", page_404())

    # sitemap / robots / manifest / opensearch
    urls = [("/", "1.0", "daily")] + [(f"/category/{c['slug']}/", "0.8", "weekly") for c in categories] + \
           [(f"/service/{s['slug']}/", "0.6", "weekly") for s in services]
    write(DIST / "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(
              f"  <url><loc>{esc(abs_url(p))}</loc><lastmod>{TODAY}</lastmod><changefreq>{f}</changefreq><priority>{pr}</priority></url>\n"
              for p, pr, f in urls) + "</urlset>\n")
    write(DIST / "robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {abs_url('/sitemap.xml')}\n")
    write(DIST / "manifest.webmanifest", json.dumps({
        "name": "DevShop — Free tiers for developers", "short_name": "DevShop",
        "description": TAGLINE, "start_url": u("/"), "scope": u("/"), "display": "standalone",
        "background_color": "#0b0d10", "theme_color": "#0b0d10",
        "icons": [{"src": u("/assets/icon-192.png"), "sizes": "192x192", "type": "image/png"},
                  {"src": u("/assets/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}],
    }, indent=1))
    write(DIST / "opensearch.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>DevShop</ShortName><Description>Search free developer tiers</Description>
  <Url type="text/html" template="{esc(abs_url('/'))}?q={{searchTerms}}"/>
  <Image height="64" width="64" type="image/png">{esc(abs_url('/assets/icon-192.png'))}</Image>
</OpenSearchDescription>""")
    sw = (STATIC / "sw.js").read_text().replace("__BASE__", BASE).replace("__BUILD__", BUILD_ID)
    write(DIST / "sw.js", sw)
    (DIST / ".nojekyll").write_text("")

    print(f"Built {len(services)} services in {len(categories)} categories → {DIST} (base='{BASE}')")


BUILD_ID = "dev"
SERVICES: list = []

if __name__ == "__main__":
    main()
