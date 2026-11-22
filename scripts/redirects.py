"""The book redirects in render.yaml: /john/3/16/, /JHN/3/16/ and
/1-corinthians/13/ go (301) to /jhn/3/16/ and /1co/13/.

People and answer engines build an address from a reference ("John 3:16")
and fetch it; Render serves a page that exists before any rule, so these
only catch addresses that would otherwise be 404s. The names are the
books' English names and the long forms in scripture.NAMES, never typed
here. The rules sit between two marker lines at the end of render.yaml.

    python3 scripts/redirects.py           rewrite them
    python3 scripts/redirects.py --check   fail if render.yaml is stale
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scripture  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BEGIN = "    # BEGIN book redirects (scripts/redirects.py writes these; don't edit by hand)\n"
END = "    # END book redirects\n"
# Top-level paths of the site that a book name must never take over.
RESERVED = {"about", "ai", "api", "comm", "commentators", "creeds", "data", "differ", "downloads", "explore",
            "feeds", "fonts", "glossary", "icons", "linker", "new", "offline", "open-data", "panel", "plans",
            "quiz", "random", "read", "readings", "review", "saved", "search", "sheets", "signed-in", "topics",
            "translators", "votd", "widget", "works"}


# Pages that were indexed at an address the site no longer builds: Genesis
# 18:1–50:26 was one passage until the Open Word Bible gave Genesis 19–50
# their headings.
MOVED = {"/gen/18/1-50.26/": "/gen/18/"}


def slugs(name):
    """'1 Corinthians' -> ['1-corinthians', '1corinthians']; 'John' -> ['john']."""
    low = re.sub(r"[^a-z0-9 ]", "", name.lower()).split()
    return sorted({"-".join(low), "".join(low)})


def sources():
    """{source path segment: book code}, in the books' order."""
    out = {}
    for code, name in scripture.BOOK_NAMES.items():
        if code not in scripture._BOOKS:
            continue
        names = {name} | {w for w in scripture.NAMES.get(code, "").split() if len(w) > 4}
        for words, codes in scripture.NUMBERED.items():
            if code in codes:
                n = codes.index(code) + 1
                names |= {f"{n} {w}" for w in words.split() if len(w) > 4}
        segs = {code} | {s for nm in names for s in slugs(nm)}
        for s in sorted(segs):
            if s != code.lower() and s not in RESERVED and s not in out:
                out[s] = code
    return out


def block():
    rows = "".join(f"      - type: redirect\n        source: /{s}/*\n        destination: /{c.lower()}/*\n"
                   for s, c in sources().items())
    rows += "".join(f"      - type: redirect\n        source: {a}\n        destination: {b}\n"
                    for a, b in MOVED.items())
    return BEGIN + "    routes:\n" + rows + END


def main():
    path = ROOT / "render.yaml"
    text = path.read_text(encoding="utf-8")
    if BEGIN in text:
        head, rest = text.split(BEGIN, 1)
        tail = rest.split(END, 1)[1]
    else:
        head, tail = text if text.endswith("\n") else text + "\n", ""
    new = head + block() + tail
    if "--check" in sys.argv:
        if new != text:
            sys.exit("render.yaml: the book redirects are stale; run python3 scripts/redirects.py")
        print(f"render.yaml book redirects OK ({len(sources())} rules)")
        return
    path.write_text(new, encoding="utf-8")
    print(f"render.yaml: {len(sources())} book redirects")


if __name__ == "__main__":
    main()
