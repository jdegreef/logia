"""The page-weight budget: on a sample of pages, what a first visit downloads
before it can draw (the page's HTML and the stylesheets and scripts it names
on Logia itself, each gzipped as the server sends it) must stay under a
budget, so that a change that makes a page slow shows up in CI.

    python3 scripts/build_site.py
    python3 scripts/page_weight.py

Fonts, images and what a page fetches later (a chapter's commentary, the
search index) are not counted. It exits 1 when a page is over its budget.
"""
import gzip
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
# Page: most kilobytes (gzipped) it may take, about a fifth over its weight
# when the budget was set (November 2026).
BUDGETS = {"/": 190, "/jhn/": 180, "/jhn/3/": 215, "/jhn/3/16/": 195, "/commentators/calvin/": 225, "/search/": 160}


def gz(path):
    with open(path, "rb") as f:
        return len(gzip.compress(f.read(), 6))


def weight(page):
    """(total bytes, [(file, bytes)]) for a page and what it names."""
    html = os.path.join(SITE, page.lstrip("/"), "index.html")
    text = open(html, encoding="utf-8").read()
    parts = [(page, gz(html))]
    names = re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="(/[^"]+)"', text)
    names += re.findall(r'<script[^>]+src="(/[^"]+)"', text)
    for name in dict.fromkeys(n.split("?")[0] for n in names):
        path = os.path.join(SITE, name.lstrip("/"))
        if os.path.isfile(path):
            parts.append((name, gz(path)))
    return sum(n for _f, n in parts), parts


def main():
    over = 0
    for page, budget in BUDGETS.items():
        total, parts = weight(page)
        ok = total <= budget * 1024
        over += not ok
        detail = ", ".join(f"{f} {n / 1024:.0f}" for f, n in sorted(parts, key=lambda p: -p[1])[:4])
        print(f"{'ok  ' if ok else 'OVER'} {page}: {total / 1024:.0f} kB of {budget} kB ({detail})")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
