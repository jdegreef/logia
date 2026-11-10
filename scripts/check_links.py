"""Check the built site's own links: every href and src that points inside
logia.faith must reach a page or file in site/, and every #fragment on a
page must name an id on the page it points to.

    python3 scripts/check_links.py          # after scripts/build_site.py

Links to other sites are not fetched (the build has no network), and
fragments that the page's script handles (#v12, #v12-calvin on a chapter)
are accepted when the page is a chapter.
"""

import html.parser
import os
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
HOST = "logia.faith"
# Fragments web/reader.js reads on a chapter page: a verse, and a verse with a work.
SCRIPT_FRAGMENTS = re.compile(r"^v\d+(-[a-z0-9-]+)?$")
CHAPTER = re.compile(r"^/[a-z0-9]{3}/\d+/$")


class Page(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.ids = [], set()
        self.skip = 0  # inside <script> or <template>

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("name"):
            self.ids.add(a["name"])
        for key in ("href", "src"):
            if a.get(key) and not (tag == "link" and a.get("rel") in ("preconnect", "dns-prefetch")):
                self.links.append(a[key])


def target(path):
    """The file in site/ a site path is served from, or None."""
    rel = unquote(path).lstrip("/")
    full = os.path.join(SITE, rel)
    if path.endswith("/"):
        full = os.path.join(full, "index.html")
    if os.path.isfile(full):
        return full
    if os.path.isfile(os.path.join(full, "index.html")):
        return os.path.join(full, "index.html")
    return None


def main():
    if not os.path.isdir(SITE):
        sys.exit("site/ is missing: run scripts/build_site.py first")
    pages = {}
    for dirpath, _dirs, files in os.walk(SITE):
        for name in files:
            if name.endswith(".html"):
                full = os.path.join(dirpath, name)
                p = Page()
                with open(full, encoding="utf-8") as f:
                    p.feed(f.read())
                pages[full] = p
    missing, bad_fragments = {}, {}
    for full, p in pages.items():
        here = "/" + os.path.relpath(os.path.dirname(full), SITE).replace(os.sep, "/").strip(".") + "/"
        here = re.sub(r"/+", "/", here)
        for link in p.links:
            u = urlsplit(link)
            if u.scheme in ("mailto", "tel", "javascript", "data") or (u.netloc and u.netloc != HOST):
                continue
            path = u.path
            if not path:
                path = here
            elif not path.startswith("/"):
                trail = "/" if path.endswith("/") else ""
                path = os.path.normpath(os.path.join(here, path)).replace(os.sep, "/") + trail
            dest = target(path)
            if dest is None:
                missing.setdefault(path, set()).add(here)
                continue
            frag = unquote(u.fragment)
            if frag and dest in pages and frag not in pages[dest].ids:
                if CHAPTER.match(path) and SCRIPT_FRAGMENTS.match(frag):
                    continue
                bad_fragments.setdefault(f"{path}#{frag}", set()).add(here)
    for title, found in (("Links to pages or files that do not exist", missing),
                         ("Links to a #fragment that is not on the page", bad_fragments)):
        if found:
            print(f"{title}: {len(found)}")
            for link, where in sorted(found.items())[:40]:
                print(f"  {link}  (from {len(where)} page{'s' if len(where) > 1 else ''}, e.g. {sorted(where)[0]})")
    total = sum(len(p.links) for p in pages.values())
    print(f"{len(pages)} pages, {total} links checked: "
          f"{len(missing)} missing, {len(bad_fragments)} broken fragments")
    sys.exit(1 if missing or bad_fragments else 0)


if __name__ == "__main__":
    main()
