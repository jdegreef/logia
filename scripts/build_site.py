"""Build the Logia site into site/.

    python3 scripts/build_site.py

Reads the library (library/authors, works, comments, corrections, citations,
quotations, texts), the Bible
text (bible/owb), the interface text (i18n/en.json) and web/, and writes a
static site:

    /                        home
    /read/                   every book, by testament, with its chapters
    /<book>/                 a book: its chapters and who comments on it
    /<book>/<chapter>/       the reader: Bible text and the commentary panel
    /<book>/<chapter>/<verse>/  a verse with commentary: every voice on it in full
    /commentators/           every commentator, by era
    /commentators/<author>/  one commentator: biography, works, comments
    /works/<work>/           one commentary: edition, rights, every excerpt
    /works/<work>/<n>/       a whole homily or tractate (library/texts)
    /about/                  what Logia is and how its text is checked

The look, the header, footer and settings menu follow openwordbible.org:
web/style.css and the fonts are the Open Word Bible's own, and web/site.js
is taken from its site script. web/logia.css adds Logia's own parts.
"""
import csv
import datetime
import functools
import glob
import hashlib
import html
import io
import json
import os
import re
import shutil
from collections import Counter
import subprocess
from urllib.parse import quote

import scripture

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
WEB = os.path.join(ROOT, "web")
LANG = "en"
SITE_URL = "https://logia.faith"
# Accounts are Open Word Bible's: its API keeps them, and its site signs
# readers in (web/account.js). LOGIA_API_URL / LOGIA_OWB_URL point a local
# build at a local API and site.
OWB_SITE = os.environ.get("LOGIA_OWB_URL", "https://openwordbible.org").rstrip("/")
API_URL = os.environ.get("LOGIA_API_URL", "https://api.openwordbible.org").rstrip("/")
GITHUB_URL = "https://github.com/jdegreef/logia"
# The Lent the reading plan gives dates for (/<book>/lent/).
LENT_YEAR = 2027
ERAS = ["Early church", "Middle Ages", "Reformation", "Puritans and the 1700s", "The 1800s"]
OT_BOOKS = 39

# The settings menu, as on openwordbible.org: the colour mode, then the
# display settings, then Logia's own. A choice is kept as logia-<name> and
# applied as data-<name> on <html> (web/site.js); the default removes both.
COLOUR_MODES = (("auto", "#faf6ef", "#16130f"), ("light", "#faf6ef", "#3f3d9a"), ("sepia", "#f4ecd8", "#3f3d9a"),
                ("dark", "#16130f", "#9c9af2"), ("night", "#000000", "#e0b45c"), ("contrast", "#ffffff", "#000000"))
DISPLAY_PREFS = (("size", "m", ("s", "m", "l", "xl")),
                 ("font", "serif", ("serif", "sans", "readable")),
                 ("leading", "normal", ("compact", "normal", "spacious")),
                 ("motion", "auto", ("auto", "reduce")),
                 ("level", "B", ("L", "B", "R")),
                 *(("gender", "inclusive", ("inclusive", "traditional")),
                   ("christos", "christ", ("christ", "messiah")),
                   ("divine_name", "lord", ("lord", "yahweh")),
                   ("deity_pronoun", "upper", ("lower", "upper")),
                   ("units", "modern", ("modern", "original"))),
                 ("excerpt", "preview", ("preview", "full")))
# The Open Word Bible's reader settings: wording it writes both ways in the
# text, {{gender:all people|men}}, its default first (owb/markup.py). A
# choice's place among its values is the option it shows, so the values keep
# the spans' order; pronouns for God show capitalised (the second) by default.
# web/reader.js picks the options; the page's plain text uses the defaults.
WORDING = ("gender", "christos", "divine_name", "deity_pronoun", "units")
SPAN = re.compile(r"\{\{([a-z_]+):([^{}]*)\}\}")
LINE = re.compile(r" ?\\q ?")


# A reader who chose another level or wording sees it from the first paint:
# their choice is on <html> before anything is drawn (BOOT_SCRIPT), so the
# page's plain text, written at the defaults, waits for web/reader.js. If the
# script never runs, it shows after a moment anyway.
TEXT_WAITS = ("html:is(" + ",".join(f"[data-{name}]" for name, _d, _v in DISPLAY_PREFS if name in ("level", *WORDING))
              + ") .cx-text:not(.cx-ready){visibility:hidden;animation:cx-reveal 0s 1.5s forwards}"
              "@keyframes cx-reveal{to{visibility:visible}}")


def default_wording(text):
    """Text at the default reader settings, on one line (poetry's line breaks read as spaces)."""
    defaults = {name: values.index(default) for name, default, values in DISPLAY_PREFS if name in WORDING}

    def choose(m):
        options = m[2].split("|")
        i = defaults.get(m[1], 0)
        return options[i] if i < len(options) else options[0]

    return LINE.sub(" ", SPAN.sub(choose, text or ""))
LEADING_GAPS = {"compact": 5, "normal": 7, "spacious": 9}

# Applies saved settings before the first paint, so a page never flashes the
# default colours or text size. Mirrors web/site.js.
BOOT_SCRIPT = ("try{var d=document.documentElement,t=localStorage.getItem('logia-theme');"
               "if(['auto','light','sepia','dark','night','contrast'].indexOf(t)>=0)d.setAttribute('data-theme',t);"
               "var p={" + ",".join(f"{name}:{[v for v in values if v != default]!r}"
                                   for name, default, values in DISPLAY_PREFS) + "};"
               "for(var k in p){var v=localStorage.getItem('logia-'+k);"
               "if(p[k].indexOf(v)>=0)d.setAttribute('data-'+k,v)}"
               # Signed in (web/account.js): the header's "Sign in" stays hidden.
               "if(localStorage.getItem('logia.account'))d.classList.add('signed-in')}catch(e){}")

ICONS = {
    "home": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/>',
    "book": '<path d="M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.2a6.5 6.5 0 0 1 3.5 5.8"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7"/>',
    "code": '<path d="m8 8-5 4 5 4M16 8l5 4-5 4M14 4l-4 16"/>',
    "chevron": '<path d="m6 9 6 6 6-6"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "back": '<path d="M19 12H5M11 6l-6 6 6 6"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "close": '<path d="M6 6l12 12M18 6 6 18"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
}
GEAR = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 '
        '1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 '
        '1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 '
        '4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 '
        '1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06'
        '.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>')

# Logia's mark: the Open Word Bible's open book, on a gold tile, with three
# lines of comment written on its right-hand page: Scripture and its
# commentary. web/logia.css colours it from the mode's gold.
MARK_INNER = ('<rect width="64" height="64" rx="14" fill="#9a6a1c"/>'
              '<path d="M28 20C23 17 17 16.2 11 17v28c6-.8 12 0 17 3zM32 20c5-3 11-3.8 17-3v28c-6-.8-12 0-17 3z" fill="#faf6ef"/>'
              '<path class="lines" d="M36 25h9M36 30.5h9M36 36h6" fill="none" stroke="#9a6a1c" stroke-width="2.6" '
              'stroke-linecap="round"/>')
MARK = f'<svg class="mark" width="32" height="32" viewBox="0 0 64 64" aria-hidden="true">{MARK_INNER}</svg>'
FAVICON = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">{MARK_INNER}</svg>\n'


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


CATALOG = load(os.path.join(ROOT, "i18n", f"{LANG}.json"))


def t(key, **values):
    """Interface text from i18n/<lang>.json by dotted key, with {name} filled."""
    node = CATALOG
    for part in key.split("."):
        node = node[part]
    return node.format(**values) if values else node


def e(text):
    return html.escape(str(text), quote=True)


def icon(name, size=18, cls="icon"):
    return (f'<svg class="{cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def ref_parts(ref):
    book, chapter, verse = ref.split(".")
    return book, int(chapter), int(verse)


def chapter_url(book, chapter):
    return f"/{book.lower()}/{chapter}/"


def short_name(author):
    """"Chrysostom", "Augustine", "Aquinas": what the panel's summary calls them."""
    special = {"augustine": "Augustine", "aquinas": "Aquinas", "chrysostom": "Chrysostom"}
    return special.get(author["id"], author["name"].split(" ")[-1])


def short_edition(edition):
    m = re.match(r"^[^;(]+", edition)
    s = (m[0] if m else edition).strip().rstrip(",.")
    return s if len(s) <= 90 else re.sub(r"\s+\S*$", "", s[:88]) + "…"


def snippet(text, words=34):
    """The first words of an excerpt, cut at a word, for lists that link to it."""
    first = text.split("\n\n")[0].split()
    return " ".join(first[:words]) + ("…" if len(first) > words else "")


SENTENCE_END = re.compile(r"[.?!][\"”’)]*\s+(?=[A-Z“\"‘(\[])|\n\s*\n")


def cite_snippet(text, at, length):
    """The sentence a citation sits in, copied from the excerpt as it reads
    (cut at about 220 characters on either side, marked with …)."""
    lo, hi = max(0, at - 220), min(len(text), at + length + 220)
    ends = [m.end() for m in SENTENCE_END.finditer(text, lo, at)]
    s = ends[-1] if ends else lo
    if not ends and s > 0:
        s = text.find(" ", s) + 1
    m = SENTENCE_END.search(text, at + length, hi)
    e_ = m.start() + 1 if m else hi
    if not m and e_ < len(text):
        e_ = text.rfind(" ", at + length, e_)
    piece = " ".join(text[s:e_].split())
    if len(piece) < 60 and len(ends) > 1:
        # A bare reference such as "(Gen. i. 1.)" says nothing alone: take
        # the sentence before it as well.
        s = ends[-2]
        piece = " ".join(text[s:e_].split())
    return ("… " if s > 0 and not ends else "") + piece + (" …" if not m and e_ < len(text) else "")


def plural(word):
    return word[:-1] + "ies" if word.endswith("y") else word + "s"


def locus_label(work, locus):
    """'4.1' in Chrysostom -> 'Homily 4, section 1'."""
    names = [n if i == 0 else n.lower() for i, n in enumerate(work["divisions"])]
    return ", ".join(f"{name} {n}" for name, n in zip(names, locus.split(".")))


# --- The library --------------------------------------------------------------

class Library:
    def __init__(self):
        self.authors = {a["id"]: a for a in (load(p) for p in glob.glob(os.path.join(ROOT, "library", "authors", "*.json")))}
        self.works = {w["id"]: w for w in (load(p) for p in glob.glob(os.path.join(ROOT, "library", "works", "*.json")))}
        self.books = load(os.path.join(ROOT, "bible", "owb", "books.json"))
        self.fixes = {}
        for p in glob.glob(os.path.join(ROOT, "library", "corrections", "*.json")):
            c = load(p)
            self.fixes[c["work"]] = [(x["from"], x["to"]) for x in c["corrections"]]
        urls = {(f["work"], os.path.basename(f["path"])): f["url"]
                for f in load(os.path.join(ROOT, "sources", "manifest.json"))["files"]}
        self.urls = urls
        # Scripture each excerpt cites, and the Catena's quotations traced to
        # the Fathers' passages (scripts/find_refs.py); rejected ones are left out.
        cites, quotes, quoted_in = {}, {}, {}
        for p in sorted(glob.glob(os.path.join(ROOT, "library", "citations", "*", "*.json"))):
            for c in load(p)["citations"]:
                if c["status"] != "rejected":
                    cites.setdefault(c["in"], []).append(c)
        for p in sorted(glob.glob(os.path.join(ROOT, "library", "quotations", "*", "*.json"))):
            for q in load(p)["quotations"]:
                if q["status"] != "rejected":
                    quotes.setdefault(q["in"], []).append(q)
                    if q["excerpt"]:
                        quoted_in.setdefault(q["excerpt"], []).append(q)
        self.comments = []
        for p in sorted(glob.glob(os.path.join(ROOT, "library", "comments", "*", "*.json"))):
            data = load(p)
            work = data["work"]
            for entry in data["entries"]:
                text = entry["text"]
                for a, b in self.fixes.get(work, []):
                    text = text.replace(a, b)
                self.comments.append({**entry, "work": work, "text": text,
                                      "source_url": urls.get((work, entry["sources"][0]), self.works[work]["full_text_url"]),
                                      "cites": cites.get(entry["id"], []), "quotes": quotes.get(entry["id"], []),
                                      "quoted_in": quoted_in.get(entry["id"], [])})
        self.by_id = {c["id"]: c for c in self.comments}
        # (work, book, chapter) of each page under /works/<work>/<book>/<chapter>/.
        self.work_chapter_pages = {(c["work"], *ref_parts(c["start"])[:2]) for c in self.comments}
        # Whole homilies and tractates (scripts/extract_texts.py), in order,
        # and where each excerpt begins in one.
        self.texts = {}
        for p in glob.glob(os.path.join(ROOT, "library", "texts", "*", "*.json")):
            x = load(p)
            self.texts.setdefault(x["work"], []).append(x)
        self.in_full = {}
        for wid, ts in self.texts.items():
            ts.sort(key=lambda x: int(x["locus"]))
            for x in ts:
                for para in x["paragraphs"]:
                    for cid in para["excerpts"]:
                        self.in_full.setdefault(cid, f"/works/{wid}/{x['locus']}/#{para['id']}")
        # The chapters whose Bible text is imported, in canonical order.
        order = list(self.books)
        self.chapters = sorted(
            (tuple(os.path.basename(p)[:-5].split(".")) for p in glob.glob(os.path.join(ROOT, "bible", "owb", "en", "*.json"))),
            key=lambda bc: (order.index(bc[0]), int(bc[1])))
        self.chapters = [(b, int(c)) for b, c in self.chapters]

    def bible(self, book, chapter):
        return load(os.path.join(ROOT, "bible", "owb", "en", f"{book}.{chapter}.json"))

    def chapter_title(self, book, chapter):
        """The heading a chapter opens with ("Jesus and Nicodemus"), at the default wording."""
        return chapter_title(book, chapter)

    def author_of(self, work_id):
        return self.authors[self.works[work_id]["author"]]

    def excerpts_on_verse(self):
        """{(book, chapter, verse): how many excerpts in Logia start there}."""
        if not hasattr(self, "_on_verse"):
            self._on_verse = Counter(ref_parts(c["start"]) for c in self.comments)
        return self._on_verse

    def ordered_works(self, ids=None):
        ids = self.works if ids is None else ids
        return sorted(ids, key=lambda w: (ERAS.index(self.author_of(w)["era"]), self.author_of(w)["died"], w))

    def ordered_authors(self):
        return sorted(self.authors.values(), key=lambda a: (ERAS.index(a["era"]), a["died"]))

    def in_chapter(self, book, chapter, last_verse):
        """{work: [entries clipped to this chapter as verse numbers]}, each
        with what the reader shows beside it: the Scripture it cites, the
        Fathers it quotes or that quote it, and its place in a whole text."""
        out = {}
        for c in self.comments:
            sb, sc, sv = ref_parts(c["start"])
            eb, ec, ev = ref_parts(c["end"])
            if sb != book or not (sc <= chapter <= ec):
                continue
            out.setdefault(c["work"], []).append({
                "id": c["id"], "start": sv if sc == chapter else 1, "end": ev if ec == chapter else last_verse,
                "heading": c["heading"], "excerpt": c["text"], "source_url": c["source_url"],
                "locus": c.get("locus"), "cites": self.cites_for(c), "quotes": self.quote_rows(c),
                "quotedIn": self.quoted_in_rows(c), "inFull": self.in_full.get(c["id"]),
                "words": len(c["text"].split()), "speakers": catena_speakers(c["work"], c["text"])})
        return out

    # --- Links between texts (docs/references.md) ---

    def verse_link(self, ref, card=None):
        """Where to read a verse: on Logia if its chapter is here, else on the
        Open Word Bible, which has no deuterocanonical books (None)."""
        book, chapter, verse = scripture.parse(ref)
        if (book, chapter) in self.chapters:
            return chapter_url(book, chapter) + f"#v{verse}" + (f"-{card}" if card else "")
        if book in scripture.DEUTEROCANON or card:
            return None
        return OWB_SITE + chapter_url(book, chapter)

    def cites_for(self, c):
        return [{"at": x["at"], "text": x["text"], "label": scripture.label(x["start"], x["end"]),
                 "href": self.verse_link(x["start"]), "status": x["status"]} for x in c["cites"]]

    def quote_rows(self, c):
        """A catena excerpt's quotations, traced to the quoted works."""
        out = []
        for q in c["quotes"]:
            w, a = self.works[q["work"]], self.author_of(q["work"])
            held = self.by_id.get(q["excerpt"])
            url = self.urls.get((q["work"], q["source"]), w["full_text_url"]) + (f"#{q['para']}" if q["para"] else "")
            out.append({"label": q["label"], "author": a["name"], "where": locus_label(w, q["locus"]),
                        "exact": bool(q["para"]), "url": url, "status": q["status"],
                        "href": self.verse_link(held["start"], held["work"]) if held else None,
                        "ref": scripture.label(held["start"], held["end"]) if held else None})
        return out

    def quoted_in_rows(self, c):
        """The catena excerpts that quote this excerpt's passage."""
        out = []
        for q in c["quoted_in"]:
            cat = self.by_id[q["in"]]
            w, a = self.works[cat["work"]], self.author_of(cat["work"])
            out.append({"author": a["name"], "title": w["title"].split(":")[0], "status": q["status"],
                        "ref": scripture.label(cat["start"], cat["end"]),
                        "href": self.verse_link(cat["start"], cat["work"])})
        return out

    def whole_on(self, ref):
        """The whole homilies and tractates that expound a verse (the work's
        second structure, by verse): each with where the verse begins in it,
        the first paragraph marked with that verse, or the text's top when
        only its heading's range covers it."""
        out = []
        b, ch, v = scripture.parse(ref)
        for wid in self.ordered_works(self.texts):
            w, a = self.works[wid], self.author_of(wid)
            for x in self.texts[wid]:
                sb, sc, sv = scripture.parse(x["verses"]["start"])
                _, ec, ev = scripture.parse(x["verses"]["end"])
                if sb != b or not (sc, sv) <= (ch, v) <= (ec, ev):
                    continue
                para = next((p for p in x["paragraphs"] if p["verse"] == ref), None)
                where = locus_label(w, para["locus"] if para and para["locus"].split(".")[-1] != "1" else x["locus"])
                out.append({"author": a["name"], "short": short_name(a), "work_id": wid, "where": where,
                            "href": f"/works/{wid}/{x['locus']}/" + (f"#{para['id']}" if para else "")})
        return out

    def cited_by(self, book, chapter, verses):
        """{verse: [excerpts anywhere in the library that cite it while
        commenting on another verse]}."""
        first, last = verses[0], verses[-1]
        out = {str(v): [] for v in verses}
        for c in self.comments:
            cb, cc, cv = ref_parts(c["start"])
            _, ec, ev = ref_parts(c["end"])
            for x in c["cites"]:
                b, ch, v = scripture.parse(x["start"])
                _, ch2, v2 = scripture.parse(x["end"])
                if b != book or not (ch <= chapter <= ch2):
                    continue
                for verse in range(v if ch == chapter else first, (v2 if ch2 == chapter else last) + 1):
                    rows = out.get(str(verse))
                    if rows is None or (cb == book and (cc, cv) <= (chapter, verse) <= (ec, ev)):
                        continue                 # not in this chapter, or already on the verse
                    if any(r["id"] == c["id"] for r in rows):
                        continue
                    a = self.author_of(c["work"])
                    rows.append({"id": c["id"], "author": a["name"], "author_dates": a["dates"],
                                 "tradition": a["tradition"], "era": a["era"], "died": a["died"],
                                 "ref": scripture.label(c["start"], c["end"]),
                                 "href": self.verse_link(c["start"], c["work"]) or self.works[c["work"]]["full_text_url"],
                                 "text": x["text"], "snippet": cite_snippet(c["text"], x["at"], len(x["text"]))})
        for rows in out.values():
            rows.sort(key=lambda r: (ERAS.index(r["era"]), r["died"]))
        return out

    def comments_in(self, book, chapter):
        """The excerpts on a chapter of a book."""
        return self.by_chapter.get((book, chapter), [])

    @functools.cached_property
    def by_chapter(self):
        out = {}
        for c in self.comments:
            sb, sc, _ = ref_parts(c["start"])
            _, ec, _ = ref_parts(c["end"])
            for ch in range(sc, ec + 1):
                out.setdefault((sb, ch), []).append(c)
        return out

    @functools.cached_property
    def voices_on(self):
        """{(book, chapter, verse): [works commenting on it]}, in the reader's order."""
        out = {}
        for c in self.comments:
            sb, sc, sv = ref_parts(c["start"])
            _, ec, ev = ref_parts(c["end"])
            if sc != ec:
                continue
            for v in range(sv, ev + 1):
                ws = out.setdefault((sb, sc, v), [])
                if c["work"] not in ws:
                    ws.append(c["work"])
        return {k: self.ordered_works(ws) for k, ws in out.items()}

    def verse_pages(self, book, chapter):
        """The verses of a chapter that have a page of their own: those with commentary."""
        return sorted(v for b, c, v in self.voices_on if (b, c) == (book, chapter))

    def verses(self, book, chapter):
        """The verse numbers of a chapter, as the Open Word Bible has them."""
        return chapter_verses(book, chapter)

    def plain(self, book, chapter):
        """{verse: its plain Balanced text} for a chapter."""
        return chapter_plain(book, chapter)

    def related(self, book, chapter, bible):
        """{verse: [verses it cross-references that have commentary]} for the
        verses no one in the library comments on: each with its text and the
        first words of one voice on it, copied as the excerpt reads."""
        out = {}
        for v, refs in bible["crossrefs"].items():
            if (book, chapter, int(v)) in self.voices_on:
                continue
            rows = []
            for x in refs:
                p = x.split(".")
                if len(p) < 3:
                    continue
                key = (p[0], int(p[1]), int(p[2].split("-")[0]))
                works = self.voices_on.get(key)
                if not works or (key[0], key[1]) not in self.chapters:
                    continue
                ref = f"{key[0]}.{key[1]}.{key[2]}"
                exact = [c for c in self.comments if c["start"] == ref and c["work"] == works[-1]]
                c = exact[0] if exact else next(c for c in self.comments if c["work"] == works[-1]
                                                and ref_parts(c["start"])[:2] == key[:2]
                                                and ref_parts(c["start"])[2] <= key[2] <= ref_parts(c["end"])[2])
                a = self.author_of(c["work"])
                rows.append({"ref": scripture.label(ref), "href": chapter_url(key[0], key[1]) + f"#v{key[2]}",
                             "n": len(works), "text": self.plain(key[0], key[1]).get(key[2], ""),
                             "author": a["name"], "era": a["era"], "snippet": snippet(c["text"], 30)})
                if len(rows) == 2:
                    break
            if rows:
                out[v] = rows
        return out

    def coverage(self):
        """{(book, chapter): (number of works, [verses with commentary])}."""
        return self._coverage

    @functools.cached_property
    def _coverage(self):
        # Every page's menus read it, so it is worked out once.
        cov = {}
        for c in self.comments:
            sb, sc, sv = ref_parts(c["start"])
            _, ec, ev = ref_parts(c["end"])
            for ch in range(sc, ec + 1):
                works, verses = cov.setdefault((sb, ch), (set(), set()))
                works.add(c["work"])
                verses.update(range(sv if ch == sc else 1, (ev if ch == ec else 999) + 1))
        return {k: (len(w), sorted(v)) for k, (w, v) in cov.items()}


@functools.lru_cache(maxsize=None)
def chapter_title(book, chapter):
    bible = load(os.path.join(ROOT, "bible", "owb", "en", f"{book}.{chapter}.json"))
    return default_wording(next((r["heading"] for r in bible["records"] if r["heading"]), ""))


@functools.lru_cache(maxsize=None)
def chapter_plain(book, chapter):
    return plain_verses(load(os.path.join(ROOT, "bible", "owb", "en", f"{book}.{chapter}.json")))


@functools.lru_cache(maxsize=None)
def chapter_verses(book, chapter):
    return tuple(load(os.path.join(ROOT, "bible", "owb", "en", f"{book}.{chapter}.json"))["verses"])


def span_text(verses):
    return f"{verses[0]}–{verses[-1]}" if verses else ""


# --- Page frame: header, settings menu, footer --------------------------------

def prefs_menu():
    def option(value, default, face, name):
        on = value == default
        return (f'<button type="button" role="radio" aria-checked="{"true" if on else "false"}" '
                f'tabindex="{0 if on else -1}" data-value="{value}">{face}{e(name)}'
                f'<span class="check" aria-hidden="true">&#10003;</span></button>')

    def group(pref, default, options):
        return (f'<p class="prefs-label" id="prefs-{pref}">{e(t("prefs." + pref))}</p>'
                f'<div role="radiogroup" aria-labelledby="prefs-{pref}" data-pref="{pref}" data-default="{default}">'
                + "".join(option(v, default, face, name) for v, face, name in options) + "</div>")

    def sample(pref, value):
        if pref in ("motion", "level", "excerpt", *WORDING):
            return ""
        if pref == "leading":
            gap = LEADING_GAPS[value]
            lines = "".join(f'<line x1="2" x2="{24 if i < 2 else 16}" y1="{y}" y2="{y}"/>'
                            for i, y in enumerate((13 - gap, 13, 13 + gap)))
            inner = ('<svg width="26" height="26" viewBox="0 0 26 26" fill="none" stroke="currentColor" '
                     f'stroke-width="2" stroke-linecap="round" aria-hidden="true">{lines}</svg>')
        else:
            inner = "Aa"
        return f'<span class="sample" aria-hidden="true">{inner}</span>'

    theme = group("theme", "light", [
        (v, f'<span class="swatch" style="--sw-bg:{bg};--sw-accent:{accent}" aria-hidden="true"></span>', t("theme." + v))
        for v, bg, accent in COLOUR_MODES])
    rows = [group(pref, default, [(v, sample(pref, v), t(f"{pref}.{v}")) for v in values])
            for pref, default, values in DISPLAY_PREFS]
    label = e(t("prefs.display"))
    return ('<div class="prefs"><button type="button" class="tool-btn prefs-btn" aria-expanded="false" '
            f'aria-controls="colour-menu" aria-label="{label}" title="{label}">{GEAR}</button>'
            f'<div id="colour-menu" class="prefs-menu" role="group" aria-label="{label}" hidden>'
            + theme + "".join(rows) + "</div></div>")


def nav_menus(lib):
    def row(href, title, note="", ico=None, ext=False, current=False):
        lead = f'<span class="dd-ico">{icon(ico)}</span>' if ico else ""
        note = f'<span class="dd-note">{e(note)}</span>' if note else ""
        rel = ' rel="noopener"' if ext else ""
        return (f'<a class="dd-item" href="{href}"{rel}>{lead}'
                f'<span class="dd-text"><span class="dd-title">{e(title)}</span>{note}</span></a>')

    def all_link(href, label):
        return f'<a class="dd-all" href="{href}">{e(label)} {icon("arrow", 16)}</a>'

    cov = lib.coverage()
    rows = []
    for code in lib.books:
        done = sum(1 for (b, _c) in cov if b == code)
        if done:
            rows.append(f'<a class="dd-item dd-book" href="/{code.lower()}/" data-book="{code.lower()}">'
                        f'<span class="dd-title">{e(lib.books[code]["en"])}</span>'
                        f'<span class="dd-count" aria-hidden="true">{done}/{lib.books[code]["chapters"]}</span></a>')
    read = (f'<div class="dd-testaments"><div class="dd-col" style="--cols: 1"><p class="dd-head">{e(t("nav.with_commentary"))}</p>'
            f'<div class="dd-books">{"".join(rows)}</div></div></div>'
            f'<div class="dd-alls">{all_link("/read/", t("nav.all_books"))}</div>')
    cols = []
    for era in ERAS:
        authors = [a for a in lib.ordered_authors() if a["era"] == era]
        if authors:
            cols.append(f'<div class="dd-col"><p class="dd-head">{e(t("eras." + era))}</p>'
                        + "".join(row(f'/commentators/{a["id"]}/', a["name"], a["dates"]) for a in authors) + "</div>")
    people = (f'<div class="dd-cols" style="--cols: {min(len(cols), 3)}">{"".join(cols)}</div>'
              f'{all_link("/commentators/", t("nav.all_commentators"))}')
    about = "".join((
        row("/about/", t("nav.about_logia"), t("nav.about_logia_note"), "info"),
        row("/about/#checked", t("nav.checked"), t("nav.checked_note"), "check"),
        row(OWB_SITE + "/", t("nav.owb"), t("nav.owb_note"), "book", ext=True),
        row(GITHUB_URL, t("nav.source"), t("nav.source_note"), "code", ext=True)))
    return (("read", t("nav.read"), "book", "/read/", read, "dd-read"),
            ("commentators", t("nav.commentators"), "users", "/commentators/", people, "dd-wide"),
            ("about", t("nav.about"), "info", "/about/", about, "dd-about"))


def account_menu(path):
    """Signed out, "Sign in", leading to Open Word Bible's /handoff/ and back
    to this page; signed in, the reader's initial, opening their name, Saved,
    their account on Open Word Bible and signing out. web/account.js runs it."""
    href = f"{OWB_SITE}/handoff/?site=logia&to={quote(path, safe='')}"
    label = e(t("account.your_account"))
    return (
        '<div class="account-menu">'
        f'<a class="sign-in-btn" href="{e(href)}" data-login title="{e(t("account.sign_in_title"))}">{icon("user")}<span>{e(t("account.sign_in"))}</span></a>'
        f'<button type="button" class="tool-btn avatar-btn" aria-expanded="false" aria-controls="account-pop" '
        f'aria-label="{label}" title="{label}" hidden><span class="account-initial"></span></button>'
        f'<div class="account-pop" id="account-pop" role="group" aria-label="{label}" hidden>'
        '<p class="who"><strong class="who-name"></strong><span class="who-email"></span></p>'
        f'<a class="pop-item" href="/saved/">{e(t("account.saved"))}</a>'
        f'<a class="pop-item" href="{OWB_SITE}/account/" rel="noopener">{e(t("account.account_page"))}</a>'
        f'<button type="button" class="pop-item sign-out">{e(t("account.sign_out"))}</button>'
        '</div></div>')


def site_header(lib, current, path):
    home_on = current == "/"
    items = [f'<li><a class="nav-link" href="/"{" aria-current=page" if home_on else ""}>'
             f'{icon("home")}<span>{e(t("nav.home"))}</span></a></li>']
    for key, label, ico, href, panel, cls in nav_menus(lib):
        if path:
            panel = panel.replace(f'class="dd-item" href="{path}"', f'class="dd-item" href="{path}" aria-current="page"')
            book = re.match(r"/([a-z0-9]{3})/", path)
            if book:
                panel = panel.replace(f'data-book="{book[1]}"', f'data-book="{book[1]}" aria-current="true"')
        items.append(
            f'<li class="nav-item"><button type="button" class="nav-link nav-trigger{" active" if current == href else ""}" '
            f'aria-expanded="false" aria-controls="dd-{key}">{icon(ico)}<span>{e(label)}</span>'
            f'{icon("chevron", 15, "icon caret")}</button><div class="dropdown {cls}" id="dd-{key}" hidden>{panel}</div></li>')
    menu = e(t("nav.menu"))
    return f"""<header class="site"><div class="wrap bar">
<a class="brand" href="/"{" aria-current=page" if home_on else ""}>{MARK}<span class="brand-name">Logia</span></a>
<nav class="primary" id="site-nav" aria-label="{e(t("nav.main"))}"><ul class="nav-list">{"".join(items)}</ul></nav>
<div class="tools">
{account_menu(path)}
{prefs_menu()}
<button type="button" class="tool-btn menu-btn" aria-expanded="false" aria-controls="site-nav" aria-label="{menu}">{icon("menu", 22)}{icon("close", 22)}</button>
</div>
</div></header>"""


def site_footer(lib):
    cov = lib.coverage()

    # How much of each testament has commentary: the books that have some,
    # each with its chapters done, and a bar of books out of the testament's.
    codes = list(lib.books)
    tiers = []
    for key, part in (("old", codes[:OT_BOOKS]), ("new", codes[OT_BOOKS:])):
        started = [c for c in part if any(b == c for b, _c in cov)]
        chips = "".join(
            f'<li><a class="book-chip" href="/{c.lower()}/">{e(lib.books[c]["en"])} '
            f'<span class="lg-chip-n">{e(t("footer.chapters_done", n=sum(1 for b, _c in cov if b == c), total=lib.books[c]["chapters"]))}</span></a></li>'
            for c in started) or f'<li class="lg-quiet">{e(t("footer.none_yet"))}</li>'
        tiers.append(f'<section class="testament" aria-labelledby="foot-{key}"><div class="testament-head">'
                     f'<h3 id="foot-{key}">{e(t("testaments." + key))}</h3>'
                     f'<span>{e(t("footer.books_done", n=len(started), total=len(part)))}</span></div>'
                     f'<span class="lg-meter" aria-hidden="true"><span style="width:{100 * len(started) / len(part):.1f}%"></span></span>'
                     f'<ul class="book-chips">{chips}</ul></section>')

    def links(pairs):
        return "".join(f'<li><a href="{href}"{" rel=noopener" if href.startswith("http") else ""}>{e(label)}</a></li>'
                       for href, label in pairs)

    read = [("/read/", t("nav.all_books"))] + [(f"/{b.lower()}/", lib.books[b]["en"])
                                               for b in dict.fromkeys(b for b, _c in sorted(cov))][:4]
    people = [("/commentators/", t("nav.all_commentators"))]
    project = [("/about/", t("nav.about_logia")), ("/about/#checked", t("nav.checked")),
               (OWB_SITE + "/", t("nav.owb")), (GITHUB_URL, t("nav.source")),
               (GITHUB_URL + "/issues/new", t("footer.report"))]
    return f"""<footer class="site"><div class="wrap">
<div class="foot-top"><div class="foot-about">
<a class="brand" href="/">{MARK}<span class="brand-name">Logia</span></a>
<p>{e(t("site.tagline"))}</p>
<p class="foot-licence"><span class="pill">{e(t("site.licence_pill"))}</span> {e(t("site.licence"))}</p>
</div>
<nav class="foot-books" aria-labelledby="foot-read"><h2 id="foot-read">{e(t("footer.books_with"))}</h2>
<div class="testaments">{"".join(tiers)}</div>
<p class="lg-quiet lg-foot-note">{e(t("footer.every_book"))} <a href="/read/">{e(t("footer.all_books"))}</a></p></nav></div>
<div class="foot-grid">
<nav aria-labelledby="foot-r"><h2 id="foot-r">{e(t("footer.read"))}</h2><ul>{links(read)}</ul></nav>
<nav aria-labelledby="foot-c"><h2 id="foot-c">{e(t("footer.commentators"))}</h2><ul>{links(people)}</ul>
<p class="lg-foot-names">{" · ".join(f'<a href="/commentators/{a["id"]}/">{e(short_name(a))}</a>' for a in lib.ordered_authors())}</p></nav>
<nav aria-labelledby="foot-p"><h2 id="foot-p">{e(t("footer.project"))}</h2><ul>{links(project)}</ul></nav>
</div>
<div class="foot-base"><p class="foot-review">{e(t("footer.review"))}</p><p>{e(t("footer.licences"))}</p></div>
</div></footer>"""


# --- style.css, trimmed -------------------------------------------------------
# web/style.css is the Open Word Bible's whole stylesheet (171 KB), kept as it
# is so it can be refreshed from there. The site publishes only the rules
# whose classes and ids Logia uses. Every class and id Logia writes appears
# whole somewhere in this script or in web/*.js, so a rule is kept when each
# of its selector's classes and ids is a word of those files. Element,
# attribute and @-rules other than @media/@supports are kept as they are.

def css_blocks(css):
    """Top-level (prelude, body) pairs; body is None for a statement such as @import."""
    out, i, n = [], 0, len(css)
    while i < n:
        j = i
        while j < n and css[j] not in "{;":
            j += 1
        if j >= n:
            break
        if css[j] == ";":
            out.append((css[i:j].strip(), None))
            i = j + 1
            continue
        depth, k = 1, j + 1
        while depth:
            depth += {"{": 1, "}": -1}.get(css[k], 0)
            k += 1
        out.append((css[i:j].strip(), css[j + 1:k - 1]))
        i = k
    return out


def trim_css(css, used):
    """css without the rules whose selectors name a class or id not in used."""
    def wanted(selector):
        bare = re.sub(r"\[[^\]]*\]", "", selector)   # [href="#main"] names no id
        names = re.findall(r"\.(-?[_a-zA-Z][\w-]*)", bare) + re.findall(r"#([_a-zA-Z][\w-]*)", bare)
        return all(x in used for x in names)

    def walk(text):
        out = []
        for prelude, body in css_blocks(text):
            if body is None:
                out.append(prelude + ";")
            elif prelude.startswith(("@media", "@supports")):
                inner = walk(body)
                if inner:
                    out.append(prelude + "{" + inner + "}")
            elif prelude.startswith("@"):
                out.append(prelude + "{" + body + "}")
            else:
                selectors = [x.strip() for x in prelude.split(",") if wanted(x)]
                if selectors:
                    out.append(",".join(selectors) + "{" + body.strip() + "}")
        return "\n".join(out)

    return walk(re.sub(r"/\*.*?\*/", "", css, flags=re.S)) + "\n"


@functools.lru_cache(maxsize=None)
def published(name):
    """A web/ file as the site publishes it."""
    with open(os.path.join(WEB, name), encoding="utf-8") as f:
        text = f.read()
    if name != "style.css":
        return text
    used = set()
    for path in [__file__] + glob.glob(os.path.join(WEB, "*.js")):
        with open(path, encoding="utf-8") as f:
            used.update(re.findall(r"[\w-]+", f.read()))
    return trim_css(text, used)


def asset(name):
    """A file in web/ by an address that changes when its contents do
    (/style.css?v=1a2b3c4d5e), so browsers may keep it for a year
    (render.yaml) and still see each new version at once."""
    return digest_url(f"/{name}", published(name))


def digest_url(path, text):
    return f"{path}?v={hashlib.sha256(text.encode()).hexdigest()[:10]}"


def page(lib, title, body, path, current="", description="", scripts=(), noindex=False, canonical=True,
         preload=(), head_title=None, ld=()):
    """A whole page. head_title, when given, is the <title> and og:title in
    place of "<title> · Logia"; ld is schema.org data for search engines."""
    full = head_title or (f"{title} · Logia" if title != "Logia" else "Logia")
    description = description or t("site.description")
    own = e(SITE_URL + path)
    js = "".join(f'\n<script src="{asset(s)}" defer></script>' for s in ("site.js", "account.js", "logia.js") + tuple(scripts))
    account_text = json.dumps(CATALOG["account"]["ui"], ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="{LANG}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full)}</title>
<meta name="description" content="{e(description)}">
{f'<link rel="canonical" href="{own}">' if canonical else ""}
<meta property="og:site_name" content="Logia">
<meta property="og:type" content="website">{f'{chr(10)}<meta property="og:url" content="{own}">' if canonical else ""}
<meta property="og:title" content="{e(full)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:image" content="{SITE_URL}/card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(t("site.card_alt"))}">
<meta name="twitter:card" content="summary_large_image">{'<meta name="robots" content="noindex">' if noindex else ""}{json_ld(ld)}
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta name="logia-api" content="{API_URL}">
<meta name="logia-owb" content="{OWB_SITE}">
<meta name="theme-color" content="#f4eee3" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#2a241c" media="(prefers-color-scheme: dark)">
<script>{BOOT_SCRIPT}</script>
<style>{TEXT_WAITS}</style>
<link rel="preload" href="/fonts/hanken-grotesk-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/fonts/gentium-book-plus-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
{"".join(f'<link rel="preload" href="{u}" as="fetch" crossorigin>{chr(10)}' for u in preload)}<link rel="stylesheet" href="{asset("style.css")}">
<link rel="stylesheet" href="{asset("logia.css")}">{js}
</head>
<body>
<a class="skip" href="#main">{e(t("site.skip"))}</a>
{site_header(lib, current, path)}
<main class="wrap" id="main" tabindex="-1">
{body}
</main>
{site_footer(lib)}
<script type="application/json" id="account-text">{account_text}</script>
</body>
</html>
"""


def json_ld(items):
    """schema.org data, one <script type="application/ld+json"> for the page."""
    if not items:
        return ""
    data = items[0] if len(items) == 1 else {"@context": "https://schema.org", "@graph": [
        {k: v for k, v in x.items() if k != "@context"} for x in items]}
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'\n<script type="application/ld+json">{text}</script>'


def breadcrumbs(*crumbs):
    """schema.org BreadcrumbList from (name, path) pairs, Home first."""
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": name, "item": SITE_URL + path}
        for i, (name, path) in enumerate((("Logia", "/"), *crumbs))]}


# --- The passage search (web/logia.js) --------------------------------------

# Short forms readers type that the commentaries' printed abbreviations
# (scripture.NAMES) don't cover.
TYPED = {"jn": "JHN", "mt": "MAT", "mk": "MRK", "lk": "LUK", "ps": "PSA", "pss": "PSA", "gn": "GEN", "ex": "EXO",
         "rm": "ROM", "sg": "SNG", "song": "SNG", "song of solomon": "SNG", "qoh": "ECC", "jas": "JAS", "phil": "PHP",
         "php": "PHP", "1jn": "1JN", "2jn": "2JN", "3jn": "3JN"}


@functools.lru_cache(maxsize=None)
def search_json(lib):
    """What the search box needs: every book's names and abbreviations, its
    chapters, and the commentators."""
    aliases = {}
    for code, b in lib.books.items():
        aliases[code.lower()] = code
        aliases[b["en"].lower()] = code
        aliases[b["en"].lower().replace(" ", "")] = code
    for code, names in scripture.NAMES.items():
        for n in names.split():
            aliases.setdefault(n.lower(), code)
    for names, codes in scripture.NUMBERED.items():
        for i, code in enumerate(codes, 1):
            for n in names.split():
                aliases.setdefault(f"{i} {n.lower()}", code)
                aliases.setdefault(f"{i}{n.lower()}", code)
    aliases.update({k: v for k, v in TYPED.items() if k not in aliases})
    data = {"aliases": aliases, "names": {k: v["en"] for k, v in lib.books.items()},
            "chapters": {k: v["chapters"] for k, v in lib.books.items()},
            "people": [[a["name"], f'/commentators/{a["id"]}/', a["dates"]] for a in lib.ordered_authors()],
            "ui": CATALOG["search"]["ui"]}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def search_box(lib, sid, cls="hero-search", key_hint=False):
    """A search box that goes to a verse, a book or a commentator (key_hint:
    show that "/" focuses it)."""
    return (f'<form class="lg-search {cls}" role="search" action="/read/" autocomplete="off">'
            f'<span class="hero-search-ico" aria-hidden="true">{SEARCH_ICON}</span>'
            f'<input type="search" name="q" id="{sid}" placeholder="{e(t("search.placeholder"))}" aria-label="{e(t("search.label"))}" '
            f'role="combobox" aria-expanded="false" aria-controls="{sid}-list" aria-autocomplete="list">'
            + (f'<kbd class="lg-kbd" title="{e(t("search.key_hint"))}">/</kbd>' if key_hint else "")
            + f'<button type="submit" class="button">{e(t("search.go"))}</button>'
            f'<ul class="lg-sugg" id="{sid}-list" role="listbox" aria-label="{e(t("search.label"))}" hidden></ul></form>'
            f'<script type="application/json" id="search-data">{search_json(lib)}</script>')


SEARCH_ICON = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
               'stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>')


# --- Pages --------------------------------------------------------------------

# The verses the home page's card offers, one tab each (a book without
# commentary yet is left out), and the eras of the three voices shown on
# each: the earliest, the Reformation and the latest, then any other era
# where a verse has fewer.
HOME_VERSES = ("JHN.3.16", "MAT.5.3", "ROM.8.28")
HOME_ERAS = ("Early church", "Reformation", "The 1800s")
# Well-known passages the home page offers as a way in, by chapter.
HOME_PASSAGES = (("JHN", 1), ("JHN", 3), ("JHN", 6), ("JHN", 10), ("JHN", 11), ("JHN", 14), ("JHN", 17), ("JHN", 20))
# The hero's "Try" row: verses (one from each book), a chapter and a commentator.
HOME_TRY = ("JHN.1.1", "MAT.5.3", "ROM.8.28")
HOME_TRY_CHAPTER = ("ROM", 8)
HOME_TRY_AUTHOR = "chrysostom"
# The motto's verse: Romans 3:2, where Paul's word for "oracles" is logia.
HOME_MOTTO = "ROM.3.2"
# For Christmas, beside the Christmas Day Gospel (library/occasions.json):
# Matthew's account of the birth, by its passages ((chapter, verse) start, end).
HOME_CHRISTMAS_MAT = (((1, 18), (1, 25)),)


def home_voices(lib, ref):
    """Up to three works on a verse, by HOME_ERAS first, then the other eras
    in order, and each one's first excerpt on that verse alone."""
    on = [c for c in lib.comments if c["start"] == c["end"] == ref]
    works = lib.ordered_works({c["work"] for c in on})
    picked = []
    for era in HOME_ERAS + tuple(x for x in ERAS if x not in HOME_ERAS):
        for wid in works:
            if len(picked) < 3 and wid not in picked and lib.author_of(wid)["era"] == era:
                picked.append(wid)
                break
    picked.sort(key=lambda w: (ERAS.index(lib.author_of(w)["era"]), works.index(w)))
    return on, works, [(w, min((c for c in on if c["work"] == w), key=lambda c: c["id"])) for w in picked]


def home_verse_panel(lib, ref, pid):
    """One verse on the home card: its text, three voices whose first words
    open in place to their whole first paragraph, and the initials of every
    voice on it."""
    book, chapter, verse = ref_parts(ref)
    text = plain_verses(lib.bible(book, chapter)).get(verse, "")
    on, works, shown = home_voices(lib, ref)
    voices = []
    for wid, c in shown:
        a = lib.author_of(wid)
        paras = [p for p in c["text"].split("\n\n") if p.strip()]
        lead = paras[1] if len(paras) > 1 and len(paras[0].split()) < 30 else paras[0]
        short = snippet(lead, 26)
        # Opened, a voice shows up to 120 words of its paragraph, then links to the rest.
        body = (f'<details class="lg-vv-more"><summary><span class="lg-vv-text">{e(short)}</span> '
                f'<span class="lg-vv-open">{e(t("home.keep_reading"))}</span></summary>'
                f'<p class="lg-vv-text lg-vv-full">{e(snippet(lead, 120))}</p>'
                f'<p class="lg-vv-src"><a href="{excerpt_href(lib, c)}">{e(t("home.read_whole", name=short_name(a)))} {icon("arrow", 13)}</a></p></details>'
                if short != lead else f'<p class="lg-vv-text">{e(lead)}</p>')
        voices.append(f'<li><p class="lg-vv-who"><a href="/commentators/{a["id"]}/"><b>{e(a["name"])}</b></a> '
                      f'<span>{e(t("eras." + a["era"]))} · {e(a["dates"])}</span></p>{body}</li>')
    href = chapter_url(book, chapter) + f"#v{verse}"
    label = f'{lib.books[book]["en"]} {chapter}:{verse}'
    shown_ids = {w for w, _c in shown}
    authors = list(dict.fromkeys(lib.author_of(w)["id"] for w in works))
    faces = "".join(
        f'<a class="lg-face lg-era-{ERAS.index(a["era"])}{"" if any(lib.author_of(w)["id"] == a["id"] for w in shown_ids) else " lg-face-more"}" '
        f'href="/commentators/{a["id"]}/" title="{e(a["name"])}">{e(name_initials(a))}</a>'
        for a in (lib.authors[x] for x in authors))
    return (f'<div class="lg-votd-panel" id="{pid}" role="tabpanel" aria-labelledby="{pid}-tab">'
            f'<blockquote><p class="votd-text">{e(text)}</p></blockquote>'
            f'<footer><a class="votd-ref" href="{href}">{e(label)}</a></footer>'
            f'<ul class="lg-vv">{"".join(voices)}</ul>'
            f'<p class="lg-vv-all"><span class="lg-faces" aria-hidden="true">{faces}</span>'
            f'<a class="votd-why" href="{href}">{e(t("home.all_voices", n=len(authors), ref=label))} {icon("arrow", 15)}</a></p></div>')


def home_verse(lib):
    """The home page's card: a verse from each book with commentary, as tabs,
    each with a few words from three voices on it, copied from their
    excerpts as they read (a first paragraph that only repeats the verse is
    passed over)."""
    refs = [r for r in HOME_VERSES if (ref_parts(r)[0], ref_parts(r)[1]) in lib.chapters
            and any(c["start"] == c["end"] == r for c in lib.comments)]
    if not refs:
        return ""
    ids = [f'hv-{r.split(".")[0].lower()}' for r in refs]
    tabs = ""
    if len(refs) > 1:
        tabs = ('<div class="lg-tabs lg-votd-tabs" role="tablist" hidden aria-label="' + e(t("home.verse_voices")) + '">'
                + "".join(f'<button type="button" role="tab" id="{i}-tab" aria-controls="{i}" aria-selected="{"true" if not n else "false"}">'
                          f'{e(lib.books[ref_parts(r)[0]]["en"])} {ref_parts(r)[1]}:{ref_parts(r)[2]}</button>'
                          for n, (r, i) in enumerate(zip(refs, ids)))
                + "</div>")
    panels = "".join(home_verse_panel(lib, r, i) for r, i in zip(refs, ids))
    return (f'<section class="votd lg-votd" aria-labelledby="h-votd"><p class="eyebrow" id="h-votd">{e(t("home.verse_voices"))}</p>'
            f'{tabs}{panels}</section>')


def home_doors(lib):
    """Three ways in by purpose, each to a page that already exists."""
    doors = (("preach", "/readings/"), ("study", "/jhn/study/"), ("devotion", "/jhn/lent/"))
    items = "".join(f'<li><a class="lg-door" href="{href}"><b>{e(t(f"home.doors.{k}"))}</b>'
                    f'<span>{e(t(f"home.doors.{k}_text"))}</span>'
                    f'<span class="lg-door-go">{e(t(f"home.doors.{k}_go"))} {icon("arrow", 14)}</span></a></li>'
                    for k, href in doors)
    return (f'<section class="lg-block lg-doors" aria-labelledby="h-doors"><h2 id="h-doors">{e(t("home.doors.heading"))}</h2>'
            f'<ul>{items}</ul></section>')


def home_hero(lib, cov):
    """The first screen: the motto, the headline, the voices by name, the
    search, ways to try it, the books to start in, and what Logia promises."""
    mb, mc, mv = ref_parts(HOME_MOTTO)
    motto = e(t("home.verse"))
    if (mb, mc) in cov:
        motto = f'<a href="{chapter_url(mb, mc)}#v{mv}" title="{e(t("home.motto_title"))}">{motto}</a>'
    names = " ".join(f'<a class="lg-era-{ERAS.index(a["era"])}" href="/commentators/{a["id"]}/">{e(short_name(a))}</a>'
                     for a in lib.ordered_authors())
    # Try: the season first, then a verse from each book, a chapter, a commentator.
    xmas = next(((b, st, en) for oid, b, st, en, _v in occasions(lib) if oid == "christmas"), None)
    season = [(t("home.christmas", ref=passage_ref(lib, *xmas)), t("occasions.christmas.path"))] if xmas else []
    for (sc, sv), (ec, ev) in HOME_CHRISTMAS_MAT:
        if ("MAT", sc) in cov:
            season.append((t("home.christmas", ref=passage_ref(lib, "MAT", (sc, sv), (ec, ev))), passage_url("MAT", (sc, sv), (ec, ev))))
    chips = [f'<a class="lg-season" href="{e(h)}">{e(x)}</a>' for x, h in season]
    for r in HOME_TRY:
        b, c, v = ref_parts(r)
        if (b, c) in cov:
            chips.append(f'<a href="{chapter_url(b, c)}#v{v}">{e(lib.books[b]["en"])} {c}:{v}</a>')
    if HOME_TRY_CHAPTER in cov:
        b, c = HOME_TRY_CHAPTER
        chips.append(f'<a href="{chapter_url(b, c)}">{e(lib.books[b]["en"])} {c} <i>{e(t("home.kind_chapter"))}</i></a>')
    if HOME_TRY_AUTHOR in lib.authors:
        a = lib.authors[HOME_TRY_AUTHOR]
        chips.append(f'<a href="/commentators/{a["id"]}/">{e(short_name(a))} <i>{e(t("home.kind_commentator"))}</i></a>')
    # The books with commentary, each with how many voices it has.
    books = ""
    for book in dict.fromkeys(b for b, _c in sorted(cov, key=lambda bc: lib.chapters.index(bc))):
        n = len({lib.author_of(c["work"])["id"] for c in lib.comments if c["start"].split(".")[0] == book})
        first = min(c for b, c in cov if b == book)
        books += (f'<a class="button ghost" href="{chapter_url(book, first)}">{e(lib.books[book]["en"])} '
                  f'<span>{e(t("home.n_voices", n=n))}</span></a>')
    trust = "".join(f'<li><a href="{h}">{e(t("home.trust." + k))}</a></li>'
                    for k, h in (("free", "/about/"), ("public", "/about/"), ("copied", "/about/"), ("data", "/open-data/")))
    return f"""
<section class="hero lg-hero">
<p class="eyebrow lg-motto">{motto}</p>
<h1>{e(t("home.title"))}</h1>
<p class="hero-sub">{e(t("home.lead"))}</p>
<p class="lg-names">{names}</p>
{search_box(lib, "home-q", key_hint=True)}
<p class="hero-try lg-try"><span>{e(t("search.try"))}</span> {" ".join(chips)}</p>
<p class="lg-books"><span>{e(t("home.start_in"))}</span> <a class="button" href="/" data-resume="{e(t("home.resume"))}" hidden></a>{books}
<a class="lg-books-all" href="/read/">{e(t("home.browse"))} {icon("arrow", 14)}</a></p>
<ul class="lg-trust">{trust}</ul>
</section>"""


def home_page(lib):
    cov = lib.coverage()
    # Start reading: each book with commentary as a strip of its chapters,
    # then a few well-known passages by their titles.
    strips = ""
    for book in dict.fromkeys(b for b, _c in sorted(cov, key=lambda bc: lib.chapters.index(bc))):
        strips += (f'<div class="lg-strip"><a class="lg-strip-book" href="/{book.lower()}/">{e(lib.books[book]["en"])}</a>'
                   f'<div class="chap-pills">{chapter_pills(lib, book, cov)}</div></div>')
    famous = "".join(
        f'<li><a class="lg-card" href="{chapter_url(b, c)}"><span class="lg-card-ref">{e(lib.books[b]["en"])} {c}</span>'
        f'<b>{e(lib.chapter_title(b, c))}</b></a></li>'
        for b, c in HOME_PASSAGES if (b, c) in cov)
    cards = (f'{strips}<h3 class="label lg-famous-h">{e(t("home.famous"))}</h3><ul class="lg-cards lg-famous">{famous}</ul>'
             if famous else strips)
    voices = ""
    for era in ERAS:
        people = [a for a in lib.ordered_authors() if a["era"] == era]
        if people:
            voices += (f'<section><h3 class="label">{e(t("eras." + era))}</h3><ul class="lg-people">'
                       + "".join(f'<li><a href="/commentators/{a["id"]}/"><b>{e(a["name"])}</b> '
                                 f'<span>{e(a["dates"])}</span></a></li>' for a in people) + "</ul></section>")
    body = f"""{home_hero(lib, cov)}
{home_verse(lib)}
{home_doors(lib)}
<section class="lg-block" aria-labelledby="h-read"><h2 id="h-read">{e(t("home.read_heading"))}</h2>
<p class="lg-quiet">{e(t("home.read_note"))}</p>{cards}</section>
<section class="lg-block" aria-labelledby="h-voices"><h2 id="h-voices">{e(t("home.voices_heading"))}</h2>
<div class="lg-eras">{voices}</div>
<p><a class="lg-more" href="/commentators/">{e(t("home.all_commentators"))} {icon("arrow", 15)}</a></p></section>
<section class="lg-block" aria-labelledby="h-how"><h2 id="h-how">{e(t("home.how_heading"))}</h2>
<div class="lg-cols">
<div><h3>{e(t("home.how_copied"))}</h3><p>{e(t("home.how_copied_text"))}</p></div>
<div><h3>{e(t("home.how_owb"))}</h3><p>{e(t("home.how_owb_text"))}</p></div>
<div><h3>{e(t("home.how_langs"))}</h3><p>{e(t("home.how_langs_text"))}</p></div>
</div></section>"""
    website = {"@context": "https://schema.org", "@type": "WebSite", "name": "Logia", "url": SITE_URL + "/",
               "description": t("site.description"), "inLanguage": LANG}
    return page(lib, "Logia", body, "/", current="/", head_title=t("site.home_title"), ld=(website,))


def chapter_pills(lib, book, cov, current=None):
    have = {c for b, c in lib.chapters if b == book}
    out = []
    for n in range(1, lib.books[book]["chapters"] + 1):
        label = f'{lib.books[book]["en"]} {n}'
        if n in have:
            commented = (book, n) in cov
            note = t("read.has_commentary") if commented else t("read.text_only_chapter")
            out.append(f'<a class="chap{" lg-has" if commented else " part"}" href="{chapter_url(book, n)}"'
                       f'{" aria-current=page" if n == current else ""} title="{e(label + ": " + note)}">{n}</a>')
        else:
            out.append(f'<span class="chap none" title="{e(label)}">{n}</span>')
    return "".join(out)


# The parts of the canon the Read page groups the books in: (key, first book, last book).
CANON_SECTIONS = (("pentateuch", "GEN", "DEU"), ("history", "JOS", "EST"), ("wisdom", "JOB", "SNG"),
                  ("major_prophets", "ISA", "DAN"), ("minor_prophets", "HOS", "MAL"), ("gospels", "MAT", "ACT"),
                  ("paul", "ROM", "PHM"), ("letters", "HEB", "REV"))


def canon_section(lib, code):
    """The CANON_SECTIONS key a book is in."""
    codes = list(lib.books)
    i = codes.index(code)
    return next(k for k, a, b in CANON_SECTIONS if codes.index(a) <= i <= codes.index(b))


def read_page(lib):
    """Every book, by testament and part of the canon: a compact grid of
    names, each opening to its chapters (gold where there is commentary).
    Books with commentary start open."""
    cov = lib.coverage()
    have = {b for b, _c in lib.chapters}
    codes = list(lib.books)
    commented = [c for c in codes if any(b == c for b, _c in cov)]
    parts = []
    for key, part in (("old", codes[:OT_BOOKS]), ("new", codes[OT_BOOKS:])):
        sections = []
        for sec, a, b in CANON_SECTIONS:
            books = [c for c in codes[codes.index(a):codes.index(b) + 1] if c in part and c in have]
            if not books:
                continue
            tiles = []
            for code in books:
                name, total = lib.books[code]["en"], lib.books[code]["chapters"]
                done = sum(1 for (bk, _c) in cov if bk == code)
                badge = (f'<span class="lg-badge">{e(t("read.commentary_short", n=done, total=total))}</span>' if done
                         else f'<span class="lg-quiet">{e(t("read.chapters", n=total))}</span>')
                tiles.append(
                    f'<li class="lg-bk{" lg-bk-has" if done else ""}"><details id="{code.lower()}"{" open" if done else ""}>'
                    f'<summary><span class="lg-bk-name">{e(name)}</span>{badge}{icon("chevron", 16, "icon lg-caret")}</summary>'
                    f'<div class="lg-bk-open"><div class="chap-pills">{chapter_pills(lib, code, cov)}</div>'
                    f'<p><a class="book-page-link" href="/{code.lower()}/">{e(t("read.book_page", book=name))}&nbsp;&rarr;</a></p>'
                    f'</div></details></li>')
            sections.append(f'<section class="lg-canon" aria-labelledby="sec-{sec}"><h3 class="label" id="sec-{sec}">'
                            f'{e(t("canon." + sec))}</h3><ul class="lg-books">{"".join(tiles)}</ul></section>')
        parts.append(f'<section class="lg-block lg-testament" id="{"ot" if key == "old" else "nt"}" aria-labelledby="h-{key}">'
                     f'<h2 id="h-{key}">{e(t("testaments." + key))}</h2>{"".join(sections)}</section>')
    coming = ""
    for key, part in (("old", codes[:OT_BOOKS]), ("new", codes[OT_BOOKS:])):
        names = [f'<li><span class="book-chip none">{e(lib.books[c]["en"])}</span></li>' for c in part if c not in have]
        if names:
            coming += (f'<section class="testament"><div class="testament-head"><h3>{e(t("testaments." + key))}</h3>'
                       f'<span>{len(names)}</span></div><ul class="book-chips">{"".join(names)}</ul></section>')
    if coming:
        coming = (f'<section class="lg-block lg-coming" aria-labelledby="h-coming"><h2 id="h-coming">{e(t("read.coming"))}</h2>'
                  f'<p class="lg-quiet">{e(t("read.coming_note"))}</p><div class="testaments">{coming}</div></section>')
    so_far = ", ".join(lib.books[c]["en"] for c in commented) or "—"
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("read.title"))}</p>
<h1>{e(t("read.heading"))}</h1><p class="dek">{e(t("read.dek", books=so_far))}</p></header>
<div class="lg-read-tools">{search_box(lib, "read-q", "hero-search lg-read-search")}
<nav class="lg-jump" aria-label="{e(t("read.jump"))}"><a href="#ot">{e(t("testaments.old"))}</a><a href="#nt">{e(t("testaments.new"))}</a></nav></div>
<ul class="lg-legend" aria-label="{e(t("read.legend"))}"><li><span class="chap lg-has" aria-hidden="true">3</span>{e(t("read.has_commentary_key"))}</li>
<li><span class="chap part" aria-hidden="true">3</span>{e(t("read.text_only_key"))}</li>
<li><span class="chap part lg-read" aria-hidden="true">3</span>{e(t("read.read_key"))}</li></ul>
<div class="book-index">{"".join(parts)}</div>
{coming}"""
    return page(lib, t("read.title"), body, "/read/", current="/read/")


def book_page(lib, book):
    """A book's contents: each chapter by its title, how many verses it has
    and how many commentaries, and who comments on the book."""
    cov = lib.coverage()
    name = lib.books[book]["en"]
    total = lib.books[book]["chapters"]
    have = [c for b, c in lib.chapters if b == book]
    done = sum(1 for (b, _c) in cov if b == book)
    rows = []
    for c in have:
        verses = len(lib.plain(book, c))
        n = cov[(book, c)][0] if (book, c) in cov else 0
        badge = (f'<span class="lg-badge" title="{e(t("book.chapter_card_one" if n == 1 else "book.chapter_card", n=n, span=span_text(cov[(book, c)][1])))}">'
                 f'{e(t("book.commentaries_one" if n == 1 else "book.commentaries", n=n))}</span>' if n else "")
        rows.append(f'<li><a href="{chapter_url(book, c)}"><span class="lg-toc-n">{c}</span>'
                    f'<span class="lg-toc-title">{e(lib.chapter_title(book, c) or f"{name} {c}")}</span>{badge}'
                    f'<span class="lg-quiet">{e(t("book.verses", n=verses))}</span></a></li>')
    works = {c["work"] for c in lib.comments if c["start"].startswith(book + ".")}
    people = "".join(
        f'<li><a href="/works/{w}/"><b>{e(lib.author_of(w)["name"])}</b> <span>{e(lib.works[w]["title"])}</span></a></li>'
        for w in lib.ordered_works(works))
    who = (f'<section class="lg-block"><h2>{e(t("book.commentators", book=name))}</h2><ul class="lg-people lg-wide">{people}</ul></section>'
           if people else "")
    plist = passage_list(lib, book)
    passages = (f'<section class="lg-block" id="passages"><h2>{e(t("passage.list_title"))}</h2>'
                f'<p class="lg-quiet">{e(t("passage.list_note", book=name))} <a href="/{book.lower()}/most-discussed/">{e(t("most.heading", book=name))}</a> · <a href="/{book.lower()}/lent/">{e(t("plan.heading", book=name, n=40))}</a> · <a href="/{book.lower()}/scripture-cited/">{e(t("cited.heading", book=name))}</a>{guide_links(book)}{" · " + collection_links(lib, book) if collection_links(lib, book) else ""}</p><ul class="lg-people lg-wide">{plist}</ul></section>'
                if plist else "")
    codes = list(lib.books)
    testament = "old" if codes.index(book) < OT_BOOKS else "new"
    start = f'<p class="actions"><a class="button" href="{chapter_url(book, have[0])}">{e(t("book.start", book=name, chapter=have[0]))}</a></p>' if have else ""
    body = f"""
<header class="page-head"><p class="eyebrow"><a href="/read/">{e(t("read.title"))}</a> · <a href="/read/#{"ot" if testament == "old" else "nt"}">{e(t("testaments." + testament))}</a> · {e(t("canon." + canon_section(lib, book)))}</p>
<h1>{e(name)}</h1><p class="dek">{e(t("book.dek", n=total, done=done))}</p>{start}</header>
<section class="lg-block"><h2>{e(t("book.chapters"))}</h2><ol class="lg-toc">{"".join(rows)}</ol></section>
{passages}{who}"""
    return page(lib, name, body, f"/{book.lower()}/", current="/read/", noindex=not indexed(lib, f"/{book.lower()}/"),
                ld=(breadcrumbs((t("read.title"), "/read/"), (name, f"/{book.lower()}/")),))


# What the panel's Greek/Hebrew words and translation notes tabs show is most
# of a chapter's data (Psalm 119: 550 KB of 690 KB), and most readers never
# open them, so it is a file of its own, /panel/<BOOK>.<chapter>.json,
# fetched by web/reader.js when one is opened. The page keeps the counts
# the tabs show.
PANEL_FIELDS = ("source", "gloss", "decisions")


def panel_file(bible):
    """The words and notes of a chapter, and the page's slimmer records."""
    panel = {"words": bible["words"],
             "records": {r["id"]: {k: r[k] for k in PANEL_FIELDS} for r in bible["records"]}}
    records = [{**{k: v for k, v in r.items() if k not in PANEL_FIELDS and k != "status"}, "notes": len(r["decisions"])}
               for r in bible["records"]]
    return json.dumps(panel, ensure_ascii=False, separators=(",", ":")), records


# The commentary's text is most of a chapter page that has any (John 1:
# 815 KB of 860 KB), so it is a file of its own too, /comm/<BOOK>.<chapter>.json,
# preloaded from the page's head so it downloads beside the page while the
# Bible text is shown. The page keeps an index of who comments on which
# verses and how many words: enough for the timeline, the summary, the gold
# line beside the text and the brackets for passages.
INDEX_FIELDS = ("work_id", "author", "short_name", "era", "died")


def comm_file(commentaries, cited_by):
    """The commentary file's text (None when there is nothing in it), and the page's index."""
    index = [{**{k: w[k] for k in INDEX_FIELDS},
              "entries": [{"start": x["start"], "end": x["end"], "words": x["words"]} for x in w["entries"]]}
             for w in commentaries]
    if not commentaries and not any(cited_by.values()):
        return None, index
    return json.dumps({"commentaries": commentaries, "citedBy": cited_by},
                      ensure_ascii=False, separators=(",", ":")), index


def plain_verses(bible):
    """{verse: its Balanced text at the default wording}, as the reader shows it."""
    verses = {}
    for r in bible["records"]:
        # A verse of two sentences is in two records: keep a space between them.
        for v in dict.fromkeys(p[0] for p in r["pieces"]):
            if v in verses:
                verses[v] += " "
        for p in r["pieces"]:
            verses[p[0]] = verses.get(p[0], "") + default_wording(p[1])
    return {v: " ".join(x.split()) for v, x in verses.items()}


def verse_gaps(lib, book, chapter, verses, commentaries):
    """{verse after a gap: a note}, for the verses the Open Word Bible leaves
    out because its Greek text does (John 5:4, 7:53-8:11, Acts 8:37...),
    naming the commentators who comment on them, linked to where they do."""
    have = set(verses)
    runs, run = [], []
    for v in range(1, verses[-1] + 1):
        if v in have:
            if run:
                runs.append((run[0], run[-1], v))
            run = []
        else:
            run.append(v)
    out = {}
    for a, b, after in runs:
        text = t("chapter.gap_one", v=a) if a == b else t("chapter.gap_range", a=a, b=b)
        links = []
        for c in commentaries:
            hit = next((x for x in c["entries"] if x["start"] <= b and x["end"] >= a), None)
            if hit:
                orig = lib.by_id[hit["id"]]
                ob, oc, _v = ref_parts(orig["start"])
                links.append(f'<a href="{work_chapter_url(c["work_id"], ob, oc)}#{e(hit["id"])}">{e(c["short_name"] or c["author"])}</a>')
        ref = f"{chapter}:{a}" + (f"–{b}" if b != a else "")
        more = (f' {e(t("chapter.gap_comm", verses=ref))} ' + " · ".join(links)) if links else ""
        out[str(after)] = f'<p class="lg-gap" id="gap-{a}" data-a="{a}" data-b="{b}"><b>{e(ref)}</b> {e(text)}{more}</p>'
    return out


def chapter_page(lib, book, chapter, all_chapters):
    """The reader page, and the texts of its panel and commentary files."""
    bible = lib.bible(book, chapter)
    name = lib.books[book]["en"]
    last = bible["verses"][-1]
    by_work = lib.in_chapter(book, chapter, last)
    commentaries = []
    for wid in lib.ordered_works(by_work):
        w, a = lib.works[wid], lib.author_of(wid)
        commentaries.append({
            "work_id": wid, "author": a["name"], "short_name": short_name(a), "author_dates": a["dates"],
            "tradition": a["tradition"], "era": a["era"], "died": a["died"], "title": w["title"],
            "edition_short": short_edition(w["edition"]), "author_url": f'/commentators/{a["id"]}/',
            "divisions": w["divisions"],
            "work_url": f"/works/{wid}/", "entries": sorted(by_work[wid], key=lambda x: (x["start"], x["end"]))})
    ui = dict(CATALOG["reader"])
    ui["eras"] = CATALOG["eras"]
    ui["fathers"] = CATALOG["catena"]["names"]
    ui["levels"] = CATALOG["level"]
    hebrew = bible["source"] == "hbo"
    if hebrew:
        # Old Testament chapters read from the Hebrew: a string with an _hbo
        # variant uses it there ("Tap a Hebrew word...").
        ui.update({k[:-4]: v for k, v in CATALOG["reader"].items() if k.endswith("_hbo")})
    panel, records = panel_file(bible)
    comm, index = comm_file(commentaries, lib.cited_by(book, chapter, bible["verses"]))
    comm_url = digest_url(f"/comm/{book}.{chapter}.json", comm) if comm else None
    text_data = {k: v for k, v in bible.items() if k not in ("records", "words")}
    data = {**text_data, "records": records, "wordCounts": {v: len(ws) for v, ws in bible["words"].items()},
            "panel": digest_url(f"/panel/{book}.{chapter}.json", panel),
            "comm": comm_url, "bookName": name, "commentaries": index, "ui": ui, "eras": ERAS,
            "wording": {name: list(values) for name, _d, values in DISPLAY_PREFS if name in WORDING},
            "wholeTexts": {str(v): lib.whole_on(f"{book}.{chapter}.{v}") for v in bible["verses"]},
            "related": lib.related(book, chapter, bible),
            "books": {k: v["en"] for k, v in lib.books.items()}}
    gaps = verse_gaps(lib, book, chapter, bible["verses"], commentaries)
    data["gaps"] = gaps
    heading = lib.chapter_title(book, chapter) or f"{name} {chapter}"
    # The text as plain Balanced verses, for search engines and readers
    # without JavaScript; web/reader.js replaces it.
    verses = plain_verses(bible)
    plain = " ".join(gaps.get(str(v), "") + f'<span class="cx-verse"><span class="cx-vn">{v}</span>{e(verses[v])}</span>'
                     for v in sorted(verses))
    i = all_chapters.index((book, chapter))
    turns = []
    if i > 0:
        pb, pc = all_chapters[i - 1]
        turns.append(f'<a rel="prev" href="{chapter_url(pb, pc)}">&larr; {e(lib.books[pb]["en"])} {pc}</a>')
    else:
        turns.append("<span></span>")
    if i + 1 < len(all_chapters):
        nb, nc = all_chapters[i + 1]
        turns.append(f'<a rel="next" href="{chapter_url(nb, nc)}">{e(lib.books[nb]["en"])} {nc} &rarr;</a>')
    levels = "".join(
        f'<button type="button" id="lv-{lv}" data-level="{lv}" aria-pressed="{"true" if lv == "B" else "false"}">'
        f'{e(t("level." + lv))}</button>' for lv in ("L", "B", "R"))
    works_credit = "; ".join(
        f'{e(c["author"])}, <a href="{e(lib.works[c["work_id"]]["full_text_url"])}" rel="noopener"><i>{e(c["title"])}</i></a>'
        for c in commentaries)
    credits = f'<p class="cx-credits">{t("chapter.credits", works=works_credit)}</p>' if commentaries else ""
    # Each commentary's own page for this chapter: its excerpts as text in the
    # page, read straight through, for readers and search engines alike.
    in_order = [(c, work_chapter_url(c["work_id"], book, chapter)) for c in commentaries
                if (c["work_id"], book, chapter) in lib.work_chapter_pages]
    in_order = (f'<nav class="lg-in-order" aria-label="{e(t("chapter.in_order", chapter=f"{name} {chapter}"))}">'
                f'<p>{e(t("chapter.in_order", chapter=f"{name} {chapter}"))} '
                + " · ".join(f'<a href="{href}">{e(c["short_name"] or c["author"])}</a>' for c, href in in_order)
                + "</p></nav>") if in_order else ""
    owb_link = f'<a href="{OWB_SITE}{chapter_url(book, chapter)}" rel="noopener">Open Word Bible</a>'
    first_ref = f"{name} {chapter}:{bible['verses'][0]}"
    # Short tab names, so all four fit the panel; the full name is the tooltip.
    def tab_name(k, short=""):
        return t("chapter.tab_" + k + short + ("_hbo" if hebrew and k == "words" else ""))
    tabs = "".join(
        f'<button role="tab" id="tab-{k}" data-tab="{k}" aria-selected="{"true" if k == "comm" else "false"}" title="{e(tab_name(k))}">'
        f'{e(tab_name(k, "_short"))}<span class="cx-n" id="n-{k}"></span></button>'
        for k in ("comm", "words", "notes", "xref"))
    picks = "".join(
        f'<li><a href="{chapter_url(book, n)}"{" aria-current=page" if n == chapter else ""}><b>{n}</b>'
        f'<span>{e(lib.chapter_title(book, n))}</span></a></li>'
        for b, n in all_chapters if b == book)
    bar_prev = (f'<a rel="prev" href="{chapter_url(*all_chapters[i - 1])}" aria-label="{e(t("chapter.previous"))}">&lsaquo; '
                f'<span>{e(lib.books[all_chapters[i - 1][0]]["en"])} {all_chapters[i - 1][1]}</span></a>' if i > 0 else "<span></span>")
    bar_next = (f'<a rel="next" href="{chapter_url(*all_chapters[i + 1])}" aria-label="{e(t("chapter.next"))}">'
                f'<span>{e(lib.books[all_chapters[i + 1][0]]["en"])} {all_chapters[i + 1][1]}</span> &rsaquo;</a>'
                if i + 1 < len(all_chapters) else "<span></span>")
    body = f"""
<div class="cx-bar" id="cx-bar" hidden><div class="wrap cx-bar-in">{bar_prev}
<details class="cx-pick"><summary><b>{e(name)} {chapter}</b> <span>{e(heading)}</span>{icon("chevron", 15, "icon lg-caret")}</summary>
<ol class="cx-pick-list">{picks}</ol></details>{bar_next}</div><span class="cx-progress" id="cx-progress"></span></div>
<div class="cx-layout">
<article class="cx-passage">
<p class="cx-eyebrow"><a href="/{book.lower()}/">{e(name)}</a> · {e(t("chapter.eyebrow", chapter=chapter))}</p>
<h1>{e(heading)}</h1>
<p class="cx-sub">{e(t("chapter.pick" + ("" if commentaries else "_none") + ("_hbo" if hebrew else "")))}</p>
<div class="cx-levels" role="group" aria-label="{e(t("chapter.level_label"))}">{levels}</div>
<div class="cx-text" id="text">{plain}</div>
<p class="cx-hint">{t("chapter.owb_hint", link=owb_link)}</p>
{in_order}
<nav class="cx-turns" aria-label="{e(t("chapter.previous"))} / {e(t("chapter.next"))}">{"".join(turns)}</nav>
</article>
<aside class="cx-panel" id="panel" aria-label="{e(t("chapter.panel_label"))}">
<button type="button" class="cx-grab" id="grab" aria-label="{e(t("chapter.toggle_panel"))}"></button>
<div class="cx-ph">
<div class="cx-ph-ref"><h2 class="cx-ref" id="ref">{e(first_ref)}</h2>
<div class="cx-nav"><button type="button" id="prev" aria-label="{e(t("chapter.prev_verse"))}">&#8249;</button>
<button type="button" id="next" aria-label="{e(t("chapter.next_verse"))}">&#8250;</button></div></div>
<div class="cx-ph-text" id="ph-text"></div>
<div class="cx-summary" id="summary" aria-live="polite"></div>
<a class="cx-vpage" id="vpage" hidden></a>
<div class="cx-rail" id="rail" aria-label="{e(t("chapter.rail_label"))}"></div>
<div class="cx-tabs" role="tablist">{tabs}</div>
</div>
<div class="cx-pb" id="pb"></div>
</aside>
</div>
<dialog class="cx-compare" id="compare" aria-labelledby="compare-ref">
<div class="cx-compare-head"><h2 id="compare-ref"></h2>
<button type="button" class="cx-compare-close" data-close aria-label="{e(t("reader.close"))}">{icon("close", 20)}</button></div>
<p class="cx-compare-text" id="compare-text"></p>
<div class="cx-picks" id="compare-picks"></div>
<div class="cx-cols" id="compare-cols"></div>
</dialog>
{credits}
{chapter_verse_nav(lib, book, chapter, lib.verse_pages(book, chapter))}{chapter_passages(lib, book, chapter)}
<script type="application/json" id="chapter-data">{json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")}</script>"""
    n = len(commentaries)
    description = (t("chapter.description", book=name, chapter=chapter, n=n) if n
                   else t("chapter.description_none", book=name, chapter=chapter))
    crumbs = breadcrumbs((t("read.title"), "/read/"), (name, f"/{book.lower()}/"), (f"{name} {chapter}", chapter_url(book, chapter)))
    names = [c["short_name"] or c["author"] for c in commentaries]
    names = ", ".join(names[:3]) if len(names) <= 3 else t("chapter.head_more", names=", ".join(names[:3]), n=len(names) - 3)
    head_title = t("chapter.head_title", book=name, chapter=chapter, names=names) if commentaries else None
    # A chapter with no commentary is only the Bible text, which
    # openwordbible.org publishes: it stays readable, out of search (indexed()).
    return page(lib, f"{name} {chapter}", body, chapter_url(book, chapter), current="/read/", ld=(crumbs,), head_title=head_title,
                description=description, noindex=not indexed(lib, chapter_url(book, chapter)), scripts=("reader.js",), preload=(comm_url,) if comm_url else ()), panel, comm


# --- Verse pages --------------------------------------------------------------
#
# /<book>/<chapter>/<verse>/: one verse and everything Logia holds on it,
# written into the page so it reads without JavaScript and search engines
# and answer engines can read it whole. An excerpt on a range of verses is
# printed in full on the page of the verse it begins at; the other verses of
# the range show its first words and link there, so each excerpt's text has
# one page.

def verse_url(book, chapter, verse):
    return f"/{book.lower()}/{chapter}/{verse}/"


def name_list(names):
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + t("verse.and") + names[-1]


def verse_href(lib, ref):
    """Where a verse reference leads from a verse page: its own page when it
    has one, else its verse in the chapter reader (or the Open Word Bible)."""
    b, ch, v = scripture.parse(ref)
    if (b, ch, v) in lib.voices_on:
        return verse_url(b, ch, v)
    return lib.verse_link(ref)


def verse_html(lib, text, cites):
    """An excerpt's paragraphs, with the Scripture it cites linked."""
    h, pos = [], 0
    for c in sorted(cites, key=lambda c: c["at"]):
        if c["at"] < pos:
            continue
        href = verse_href(lib, c["start"])
        words = e(text[c["at"]:c["at"] + len(c["text"])])
        label = e(scripture.label(c["start"], c["end"]))
        h.append(e(text[pos:c["at"]]))
        h.append(f'<a class="lg-cite" href="{e(href)}" title="{label}">{words}</a>' if href
                 else f'<span class="lg-cite" title="{label}">{words}</span>')
        pos = c["at"] + len(c["text"])
    h.append(e(text[pos:]))
    return "".join(f"<p>{p.strip()}</p>" for p in re.split(r"\n\s*\n", "".join(h)) if p.strip())


def verse_ref(lib, book, chapter, v, ev=None):
    return f'{lib.books[book]["en"]} {chapter}:{v}' + (f"–{ev}" if ev and ev != v else "")


def verse_voices(lib, book, chapter, verse):
    """[(work, [excerpts on the verse])], in the reader's order of works."""
    by_work = {}
    for c in lib.comments_in(book, chapter):
        _, _, sv = ref_parts(c["start"])
        _, _, ev = ref_parts(c["end"])
        if sv <= verse <= ev:
            by_work.setdefault(c["work"], []).append(c)
    return [(w, sorted(by_work[w], key=order_key)) for w in lib.ordered_works(by_work)]


def verse_excerpt(lib, c, book, chapter, verse):
    w = lib.works[c["work"]]
    _, _, sv = ref_parts(c["start"])
    _, _, ev = ref_parts(c["end"])
    on = f'<p class="lg-ref">{e(t("verse.on_range", ref=verse_ref(lib, book, chapter, sv, ev)))}</p>' if ev != sv else ""
    heading = f'<p class="lg-lemma">{e(c["heading"])}</p>' if c["heading"] else ""
    if sv != verse:
        # Printed in full where it begins.
        start = verse_ref(lib, book, chapter, sv)
        return (f'<article class="lg-excerpt lg-vx">{on}<p class="lg-quiet">{e(t("verse.continues", ref=start))}</p>'
                f'<div class="lg-text"><p>{e(snippet(c["text"], 40))}</p></div>'
                f'<p class="lg-vx-links"><a href="{verse_url(book, chapter, sv)}#{e(c["id"])}">'
                f'{e(t("verse.read_full", ref=start))}</a></p></article>')
    links = [f'<a href="{e(c["source_url"])}" rel="noopener">{e(t("verse.source"))}</a>']
    if lib.in_full.get(c["id"]):
        links.append(f'<a href="{lib.in_full[c["id"]]}">{e(t("verse.in_whole", division=w["divisions"][0].lower()))}</a>')
    links.append(f'<a href="{chapter_url(book, chapter)}#v{sv}-{c["work"]}">{e(t("verse.in_reader"))}</a>')
    more = []
    for q in lib.quote_rows(c):
        label = e(t("verse.quotes", author=q["author"], where=q["where"]))
        more.append(f'<li><a href="{e(q["href"])}">{label}</a></li>' if q["href"]
                    else f'<li><a href="{e(q["url"])}" rel="noopener">{label}</a></li>')
    for q in lib.quoted_in_rows(c):
        label = e(t("verse.quoted_by", name=q["author"], title=q["title"], ref=q["ref"]))
        more.append(f'<li><a href="{e(q["href"])}">{label}</a></li>' if q["href"] else f"<li>{label}</li>")
    locus = f' {e(locus_label(w, c["locus"]))}.' if c.get("locus") else ""
    return (f'<article class="lg-excerpt lg-vx" id="{e(c["id"])}">{on}{heading}'
            f'<div class="lg-text">{verse_html(lib, c["text"], c["cites"])}</div>'
            + (f'<ul class="lg-vx-more">{"".join(more)}</ul>' if more else "")
            + f'<p class="lg-vx-links lg-quiet">{e(t("verse.from", edition=short_edition(w["edition"])))}{locus} '
            f'{" · ".join(links)}</p></article>')


def verse_words(bible, verse):
    words = bible["words"].get(str(verse), [])
    if not words:
        return ""
    lang = "hbo" if bible["source"] == "hbo" else "grc"
    rows = "".join(
        f'<tr><td class="cx-gk" lang="{"arc" if w.get("lang") == "A" else lang}"{" dir=rtl" if lang == "hbo" else ""}>{e(w["text"])}'
        + (f'<br><i class="lg-quiet">{e(w["transliteration"])}</i>' if w.get("transliteration") else "")
        + f'</td><td class="cx-gk" lang="{lang}"{" dir=rtl" if lang == "hbo" else ""}>{e(w["lemma"])}</td>'
        f'<td>{e(w["gloss"])}</td><td class="lg-quiet">{e(w.get("parse", ""))}</td></tr>'
        for w in words)
    head = "".join(f"<th>{e(t('verse.col_' + k))}</th>" for k in ("word", "lemma", "gloss", "grammar"))
    return (f'<section class="lg-block" id="words"><h2>{e(t("verse.words_hbo" if lang == "hbo" else "verse.words"))}</h2>'
            f'<div class="lg-table-wrap"><table class="lg-words"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p class="lg-quiet">{e(t("verse.words_note"))}</p></section>')


def verse_notes(bible, verse, ref):
    """The Open Word Bible's decisions on the sentences the verse is in: its
    meaning decisions, and its wording at the Balanced level."""
    out = []
    for r in bible["records"]:
        if verse not in r["verses"]:
            continue
        decs = [d for d in r["decisions"] if d["layer"] == "meaning" or "B" in (d["levels"] or [])]
        notes = "".join(
            f'<div class="cx-note"><h3>{e(default_wording(d["choice"]))} <span class="cx-tag">'
            f'{e(CATALOG["reader"]["categories"].get(d["category"], d["category"]))}</span>'
            + (f'<span class="cx-tag">{e(t("verse.uncertain"))}</span>' if d["uncertain"] else "") + "</h3>"
            + (f'<p class="cx-alt">{e(t("verse.not_"))} {" · ".join(e(default_wording(a)) for a in d["alternatives"])}</p>'
               if d["alternatives"] else "")
            + f'<p>{e(default_wording(d["reason"]))}</p></div>' for d in decs)
        out.append(f'<p class="lg-quiet">{e(t("verse.word_for_word"))} {e(r["gloss"])}</p>{notes}')
    if not out:
        return ""
    return f'<section class="lg-block" id="notes"><h2>{e(t("verse.notes", ref=ref))}</h2>{"".join(out)}</section>'


def verse_xrefs(lib, bible, verse):
    rows = []
    for x in bible["crossrefs"].get(str(verse), []):
        p = x.split(".")
        if len(p) < 3 or p[0] not in lib.books:
            continue
        ch, a = int(p[1]), int(p[2].split("-")[0])
        label = f'{lib.books[p[0]]["en"]} {p[1]}:{p[2]}'
        text = chapter_plain(p[0], ch).get(a, "") if (p[0], ch) in lib.chapters else ""
        href = verse_url(p[0], ch, a) if (p[0], ch, a) in lib.voices_on else chapter_url(p[0], ch) + f"#v{a}"
        rows.append(f'<li><a href="{href}"><b>{e(label)}</b></a> <span>{e(text)}</span></li>')
    if not rows:
        return ""
    return (f'<section class="lg-block" id="xrefs"><h2>{e(t("verse.xrefs"))}</h2><ul class="lg-xrefs">{"".join(rows)}</ul>'
            f'<p class="lg-quiet">{e(t("verse.xref_credit"))}</p></section>')


def breadcrumbs_ld(items):
    return json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": name, "item": SITE_URL + path}
        for i, (name, path) in enumerate(items)]}, ensure_ascii=False).replace("</", "<\\/")


def person_ld(author):
    """schema.org Person for a commentator: their page, dates and tradition."""
    out = {"@context": "https://schema.org", "@type": "Person", "name": author["name"],
           "url": SITE_URL + f'/commentators/{author["id"]}/', "deathDate": f'{author["died"]:04d}'}
    if not author["dates"].lstrip().startswith("c."):      # "c. 347-407": the birth year is a guess
        out["birthDate"] = f"{born(author):04d}"
    return out


def work_ld(lib, wid):
    """schema.org Book for a commentary: the edition Logia copies from."""
    w = lib.works[wid]
    return {"@type": "Book", "name": w["title"], "url": SITE_URL + f"/works/{wid}/", "bookEdition": w["edition"],
            "datePublished": str(w["published"]), "inLanguage": LANG, "sameAs": w["full_text_url"],
            "author": {"@type": "Person", "name": lib.author_of(wid)["name"]}}


def verse_ld(lib, ref, path, voices, verse):
    """schema.org data for a verse page: each excerpt printed on it in full
    as a Quotation, by its commentator, from its edition."""
    parts = []
    for wid, cs in voices:
        a = lib.author_of(wid)
        creator = {k: v for k, v in person_ld(a).items() if k != "@context"}
        for c in cs:
            if ref_parts(c["start"])[2] != verse:
                continue                    # printed in full on the verse it begins at
            parts.append({"@type": "Quotation", "url": SITE_URL + path + "#" + c["id"],
                          "text": opening_words(c, 60), "creator": creator, "isPartOf": work_ld(lib, wid),
                          "isBasedOn": c["source_url"], "about": ref})
    return {"@context": "https://schema.org", "@type": "WebPage", "name": ref, "url": SITE_URL + path,
            "inLanguage": LANG, "isAccessibleForFree": True, "hasPart": parts}


def verse_page(lib, book, chapter, verse, bible, pages_here, cited_by):
    """A verse's page. cited_by is lib.cited_by for its whole chapter."""
    name = lib.books[book]["en"]
    ref = verse_ref(lib, book, chapter, verse)
    plain = chapter_plain(book, chapter)
    text = plain.get(verse, "")
    note = ""
    if text:
        verse_html = f'<blockquote class="lg-vtext"><p>{e(text)}</p></blockquote>'
    else:
        # A verse the Open Word Bible's Greek text leaves out (John 5:4, 8:1-11):
        # say so, as the chapter page does, over the whole run it belongs to.
        a = b = verse
        while a > 1 and not plain.get(a - 1):
            a -= 1
        while b + 1 <= max(plain, default=0) and not plain.get(b + 1):
            b += 1
        note = t("chapter.gap_one", v=a) if a == b else t("chapter.gap_range", a=a, b=b)
        verse_html = f'<p class="lg-gap">{e(note)}</p>'
    voices = verse_voices(lib, book, chapter, verse)
    authors = [lib.author_of(w) for w, _cs in voices]
    names = [short_name(a) for a in authors]
    if len(authors) == 1:
        lead = t("verse.lead_one", name=authors[0]["name"], dates=authors[0]["dates"], ref=ref)
    else:
        lead = t("verse.lead", n=len(authors), ref=ref, first=authors[0]["name"], first_dates=authors[0]["dates"],
                 last=authors[-1]["name"], last_dates=authors[-1]["dates"], names=name_list(names))
    sections, toc = [], []
    for (wid, cs), a in zip(voices, authors):
        w = lib.works[wid]
        meta = (f'<p class="lg-vmeta"><a href="/commentators/{a["id"]}/">{e(a["name"])}</a> ({e(a["dates"])}) · '
                f'{e(a["tradition"])} · <a href="{work_chapter_url(wid, book, chapter)}"><i>{e(w["title"])}</i></a></p>')
        sections.append(f'<section class="lg-voice" id="{wid}"><h3>{e(t("verse.question", name=short_name(a), ref=ref))}</h3>'
                        f'{meta}{"".join(verse_excerpt(lib, c, book, chapter, verse) for c in cs)}</section>')
        toc.append(f'<a href="#{wid}">{e(short_name(a))}</a>')
    cited = cited_by.get(str(verse), [])
    cited_html = ""
    if cited:
        rows = "".join(f'<li><p class="lg-ex-ref"><a href="{e(r["href"])}"><b>{e(r["author"])}</b> · {e(r["ref"])}</a></p>'
                       f'<div><p>{e(r["snippet"])}</p></div></li>' for r in cited)
        cited_html = (f'<section class="lg-block" id="cited"><h2>{e(t("verse.cited_by"))}</h2>'
                      f'<p class="lg-quiet">{e(t("verse.cited_by_note", ref=ref))}</p><ul class="lg-excerpts">{rows}</ul></section>')
    whole = lib.whole_on(f"{book}.{chapter}.{verse}")
    whole_html = ""
    if whole:
        rows = "".join(f'<li><a href="{e(x["href"])}"><b>{e(x["author"])}</b> <span>{e(x["where"])}</span></a></li>' for x in whole)
        whole_html = (f'<section class="lg-block" id="whole"><h2>{e(t("verse.whole_texts", ref=ref))}</h2>'
                      f'<ul class="lg-people lg-wide">{rows}</ul></section>')
    i = pages_here.index(verse)
    turns = [f'<a rel="prev" href="{verse_url(book, chapter, pages_here[i - 1])}">&larr; {e(verse_ref(lib, book, chapter, pages_here[i - 1]))}</a>'
             if i else "<span></span>",
             f'<a rel="next" href="{verse_url(book, chapter, pages_here[i + 1])}">{e(verse_ref(lib, book, chapter, pages_here[i + 1]))} &rarr;</a>'
             if i + 1 < len(pages_here) else "<span></span>"]
    owb_link = f'<a href="{OWB_SITE}{chapter_url(book, chapter)}" rel="noopener">Open Word Bible</a>'
    chapter_name = f"{name} {chapter}"
    crumbs = breadcrumbs((name, f"/{book.lower()}/"), (chapter_name, chapter_url(book, chapter)),
                         (ref, verse_url(book, chapter, verse)))
    body = f"""
<article class="lg-verse">
<header class="page-head"><p class="eyebrow"><a href="/{book.lower()}/">{e(name)}</a> · <a href="{chapter_url(book, chapter)}">{e(t("chapter.eyebrow", chapter=chapter))}</a> · {e(lib.chapter_title(book, chapter))}</p>
<h1>{e(ref)}</h1>
{verse_html}
<p class="lg-quiet">{t("verse.bible_credit", link=owb_link)}</p>
<p class="dek lg-vlead">{e(lead)}</p>
<nav class="lg-chbar" aria-label="{e(t("verse.contents"))}">{"".join(toc)}</nav></header>
<section class="lg-block" id="voices"><h2>{e(t("verse.voices"))}</h2>{"".join(sections)}</section>
{cited_html}{whole_html}{verse_words(bible, verse)}{verse_notes(bible, verse, ref)}{verse_xrefs(lib, bible, verse)}
<p class="lg-block"><a class="lg-more" href="{chapter_url(book, chapter)}#v{verse}">{e(t("verse.open_chapter", chapter=chapter_name))} {icon("arrow", 15)}</a></p>
<nav class="lg-turns" aria-label="{e(t("verse.previous"))} / {e(t("verse.next"))}">{"".join(turns)}</nav>
</article>"""
    # Up to four names fit a title; "and 1 more" would be longer than the name.
    shown = names if len(names) <= 4 else names[:3]
    title_names = name_list(shown) if len(names) <= 4 else t("verse.title_more", names=", ".join(shown), n=len(names) - 3)
    description = (t("verse.description", ref=ref, text=snippet(text, 16), names=name_list(names)) if text
                   else t("verse.description_gap", ref=ref, names=name_list(names)))
    return page(lib, t("verse.title", ref=ref, names=title_names), body, verse_url(book, chapter, verse),
                current="/read/", description=description,
                ld=(verse_ld(lib, ref, verse_url(book, chapter, verse), voices, verse), crumbs))


def chapter_verse_nav(lib, book, chapter, verses):
    """The links from a chapter page to its verse pages: there for search
    engines and readers without JavaScript, and a contents for everyone."""
    if not verses:
        return ""
    links = "".join(f'<a href="{verse_url(book, chapter, v)}">{v}</a>' for v in verses)
    return (f'<nav class="lg-block lg-vnav" aria-labelledby="by-verse"><h2 id="by-verse">{e(t("chapter.by_verse"))}</h2>'
            f'<p class="lg-quiet">{e(t("chapter.by_verse_note"))}</p><div class="lg-chbar">{links}</div></nav>')


# --- Passage pages (/<book>/<chapter>/<a>-<b>/) -------------------------------
#
# A passage is a section of the Open Word Bible under one of its headings
# ("The wedding at Cana", John 2:1-12): what people search for by name. Its
# page is a contents of every excerpt on it, each opening with its first
# words and linking to the verse page where it is printed in full, so each
# excerpt's text still lives on one page.

@functools.lru_cache(maxsize=None)
def book_sections(book, chapters):
    """[(heading, (chapter, verse), (chapter, verse))] for a book, from its
    headings: each runs to the verse before the next heading, or to the next
    heading's verse when that heading falls inside a verse (John 12:36b)."""
    heads = []
    for c in range(1, chapters + 1):
        path = os.path.join(ROOT, "bible", "owb", "en", f"{book}.{c}.json")
        if not os.path.exists(path):
            continue
        for r in load(path)["records"]:
            if r["heading"]:
                _b, rc, rv, part = r["id"].split(".")
                key = (int(rc), int(rv), part)
                if key not in [h[0] for h in heads]:
                    heads.append((key, default_wording(r["heading"])))
    heads.sort()
    out = []
    for i, ((c, v, _p), heading) in enumerate(heads):
        if i + 1 < len(heads):
            nc, nv, npart = heads[i + 1][0]
            if npart != "s1":
                end = (nc, nv)
            elif nv > 1:
                end = (nc, nv - 1)
            else:
                end = (nc - 1, max(chapter_verses(book, nc - 1)))
        else:
            end = (chapters, max(chapter_verses(book, chapters)))
        out.append((heading, (c, v), end))
    return tuple(out)


def passage_url(book, start, end):
    (c, v), (ec, ev) = start, end
    tail = f"{ev}" if ec == c else f"{ec}.{ev}"
    return f"/{book.lower()}/{c}/{v}-{tail}/"


def passage_ref(lib, book, start, end):
    (c, v), (ec, ev) = start, end
    name = lib.books[book]["en"]
    return f"{name} {c}:{v}–{ev}" if ec == c else f"{name} {c}:{v}–{ec}:{ev}"


def in_passage(lib, book, start, end):
    """[(work, [excerpts])] on a passage, in the reader's order of works and
    each work's own order: every excerpt that begins in it, and one that
    began before it and runs into it."""
    lo, hi = start, end
    by_work, seen = {}, set()
    for ch in range(start[0], end[0] + 1):
        for c in lib.comments_in(book, ch):
            _, sc, sv = ref_parts(c["start"])
            _, ec, ev = ref_parts(c["end"])
            if (sc, sv) <= hi and (ec, ev) >= lo and c["id"] not in seen:
                seen.add(c["id"])
                by_work.setdefault(c["work"], []).append(c)
    return [(w, sorted(by_work[w], key=order_key)) for w in lib.ordered_works(by_work)]


def passages_with_commentary(lib, book):
    """The sections of a book that have commentary, with their excerpts."""
    out = []
    for heading, start, end in book_sections(book, lib.books[book]["chapters"]):
        voices = in_passage(lib, book, start, end)
        if voices:
            out.append((heading, start, end, voices))
    return out


def excerpt_href(lib, c):
    """Where an excerpt is printed in full: its verse page, or its place on
    its work's chapter page when it has none (one that crosses a chapter)."""
    b, ch, v = ref_parts(c["start"])
    if (b, ch, v) in lib.voices_on and c["work"] in lib.voices_on[(b, ch, v)] and ref_parts(c["end"])[1] == ch:
        return f'{verse_url(b, ch, v)}#{c["id"]}'
    return f'{work_chapter_url(c["work"], b, ch)}#{c["id"]}'


def occasion_text(occasion, field, **values):
    """An occasion's own wording for field, or the shared one, which names it."""
    own = CATALOG
    for part in (occasion + "." + field).split("."):
        own = own.get(part) if isinstance(own, dict) else None
    return own.format(**values) if own else t("occasions." + field, name=t(occasion + ".name"), **values)


def occasions(lib):
    """[(id, book, start, end, voices)] for each reading in library/occasions.json, in the church year's order."""
    out = []
    for o in load(os.path.join(ROOT, "library", "occasions.json"))["occasions"]:
        book, sc, sv = ref_parts(o["start"])
        _b, ec, ev = ref_parts(o["end"])
        out.append((o["id"], book, (sc, sv), (ec, ev), in_passage(lib, book, (sc, sv), (ec, ev))))
    return out


def readings_page(lib):
    """/readings/: the days of the church year whose Gospel Logia has a page for."""
    rows = []
    for oid, book, start, end, voices in occasions(lib):
        key = f"occasions.{oid}"
        n = sum(len(cs) for _w, cs in voices)
        rows.append(f'<li><a href="{e(t(key + ".path"))}"><b>{e(t(key + ".name"))}</b> '
                    f'<span>{e(passage_ref(lib, book, start, end))} · {e(t(key + ".season"))} · {e(t("passage.n_excerpts", n=n))}</span></a>'
                    f'<p class="lg-quiet">{e(t(key + ".read"))}</p></li>')
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("occasions.eyebrow"))}</p>
<h1>{e(t("occasions.index_heading"))}</h1><p class="dek">{e(t("occasions.index_dek"))}</p></header>
<section class="lg-block"><ul class="lg-people lg-wide lg-readings">{"".join(rows)}</ul>
<p class="lg-quiet">{e(t("occasions.index_note"))}</p>
<p><a class="lg-more" href="/jhn/lent/">{e(t("plan.heading", book=lib.books["JHN"]["en"], n=40))} {icon("arrow", 15)}</a></p></section>"""
    return page(lib, t("occasions.index_heading"), body, "/readings/", current="/read/",
                description=t("occasions.index_description"),
                ld=(breadcrumbs((t("occasions.eyebrow"), "/readings/")),))


def passage_page(lib, book, heading, start, end, voices, occasion=None):
    """A passage's page: its Bible text, then each commentator's excerpts on
    it, opening with their first words. occasion, when given, is the key in
    i18n/en.json of a reading the page is built for ("occasions.christmas")."""
    name = lib.books[book]["en"]
    ref = passage_ref(lib, book, start, end)
    authors = [lib.author_of(w) for w, _cs in voices]
    names = [short_name(a) for a in authors]
    n = sum(len(cs) for _w, cs in voices)
    lines = []
    for ch in range(start[0], end[0] + 1):
        plain = chapter_plain(book, ch)
        lo = start[1] if ch == start[0] else 1
        hi = end[1] if ch == end[0] else max(chapter_verses(book, ch))
        for v in range(lo, hi + 1):
            if plain.get(v):
                num = (f'<a href="{verse_url(book, ch, v)}">{v if ch == start[0] else f"{ch}:{v}"}</a>'
                       if (book, ch, v) in lib.voices_on else str(v))
                lines.append(f'<sup>{num}</sup> {e(plain[v])}')
    text_html = (f'<blockquote class="lg-vtext lg-ptext"><p>{" ".join(lines)}</p></blockquote>' if lines
                 else f'<p class="lg-gap">{e(t("passage.not_in_text", ref=ref))}</p>')
    sections, toc = [], []
    for (wid, cs), a in zip(voices, authors):
        w = lib.works[wid]
        rows = []
        for c in cs:
            b, sc, sv = ref_parts(c["start"])
            _, ec, ev = ref_parts(c["end"])
            on = verse_ref(lib, b, sc, sv) if (sc, sv) == (ec, ev) else scripture.label(c["start"], c["end"])
            head = f' <span class="lg-quiet">{e(c["heading"])}</span>' if c["heading"] else ""
            rows.append(f'<li><p class="lg-ex-ref"><a href="{excerpt_href(lib, c)}"><b>{e(on)}</b></a>{head}</p>'
                        f'<div><p>{e(snippet(c["text"], 40))}</p></div></li>')
        meta = (f'<p class="lg-vmeta"><a href="/commentators/{a["id"]}/">{e(a["name"])}</a> ({e(a["dates"])}) · '
                f'{e(a["tradition"])} · <i>{e(w["title"])}</i> · {e(t("passage.n_excerpts", n=len(cs)) if len(cs) != 1 else t("passage.one_excerpt"))}</p>')
        sections.append(f'<section class="lg-voice" id="{wid}"><h3>{e(t("verse.question", name=short_name(a), ref=ref))}</h3>'
                        f'{meta}<ul class="lg-excerpts">{"".join(rows)}</ul></section>')
        toc.append(f'<a href="#{wid}">{e(short_name(a))}</a>')
    lead = t("passage.lead", n=n, ref=ref, k=len(authors), first=authors[0]["name"], first_dates=authors[0]["dates"],
             last=authors[-1]["name"], last_dates=authors[-1]["dates"]) if len(authors) > 1 else \
        t("passage.lead_one", n=n, ref=ref, name=authors[0]["name"], dates=authors[0]["dates"])
    title = f"{heading} ({ref})"
    path = passage_url(book, start, end)
    eyebrow = (f'<a href="/{book.lower()}/">{e(name)}</a> · <a href="{chapter_url(book, start[0])}">'
               f'{e(t("chapter.eyebrow", chapter=start[0]))}</a> · <a href="/{book.lower()}/#passages">{e(t("passage.eyebrow"))}</a>')
    intro = ""
    if occasion:
        path = t(occasion + ".path")
        title = occasion_text(occasion, "heading", ref=ref)
        eyebrow = (f'<a href="/readings/">{e(t("occasions.eyebrow"))}</a> · {e(t(occasion + ".season"))}')
        intro = f'<p class="dek">{e(t(occasion + ".intro", ref=ref))}</p>'
    crumbs = ([("Logia", "/"), (t("occasions.eyebrow"), "/readings/"), (title, path)] if occasion
              else [("Logia", "/"), (name, f"/{book.lower()}/"), (heading, path)])
    shown = names[:3]
    title_names = name_list(shown) if len(names) <= 3 else t("verse.title_more", names=", ".join(shown), n=len(names) - 3)
    head_title = (occasion_text(occasion, "title", ref=ref, names=title_names) if occasion
                  else t("passage.title", heading=heading, ref=ref, names=title_names)) + " · Logia"
    description = (occasion_text(occasion, "description", ref=ref, n=n, names=name_list(names)) if occasion
                   else t("passage.description", heading=heading, ref=ref, n=n, names=name_list(names)))
    body = f"""
<article class="lg-verse lg-passage">
<header class="page-head"><p class="eyebrow">{eyebrow}</p>
<h1>{e(title)}</h1>{intro}
{text_html}
<p class="lg-quiet">{t("verse.bible_credit", link=f'<a href="{OWB_SITE}{chapter_url(book, start[0])}" rel="noopener">Open Word Bible</a>')}</p>
<p class="dek lg-vlead">{e(lead)}</p>
<nav class="lg-chbar" aria-label="{e(t("verse.contents"))}">{"".join(toc)}</nav></header>
<section class="lg-block" id="voices"><h2>{e(t("verse.voices"))}</h2>
<p class="lg-quiet">{e(t("passage.how"))}</p>{"".join(sections)}</section>
<p class="lg-block"><a class="lg-more" href="{chapter_url(book, start[0])}#v{start[1]}">{e(t("verse.open_chapter", chapter=f"{name} {start[0]}"))} {icon("arrow", 15)}</a></p>
</article>
<script type="application/ld+json">{breadcrumbs_ld(crumbs)}</script>"""
    return page(lib, title, body, path, current="/read/", description=description, head_title=head_title)


def passage_list(lib, book, chapter=None):
    """The passages of a book (or one chapter) with commentary, as links."""
    rows = []
    for heading, start, end, voices in passages_with_commentary(lib, book):
        if chapter is not None and not (start[0] <= chapter <= end[0]):
            continue
        n = sum(len(cs) for _w, cs in voices)
        rows.append(f'<li><a href="{passage_url(book, start, end)}"><b>{e(heading)}</b> '
                    f'<span>{e(passage_ref(lib, book, start, end))} · {e(t("passage.n_voices", n=len(voices)) if len(voices) != 1 else t("passage.one_voice"))} · '
                    f'{e(t("passage.n_excerpts", n=n))}</span></a></li>')
    return "".join(rows)


def chapter_passages(lib, book, chapter):
    rows = passage_list(lib, book, chapter)
    return (f'<nav class="lg-block lg-vnav" aria-labelledby="passages"><h2 id="passages">{e(t("passage.in_chapter"))}</h2>'
            f'<ul class="lg-people lg-wide">{rows}</ul></nav>' if rows else "")


# The timeline's span (AD), and the eras drawn behind it: (era, from, to).
TIMELINE = (300, 1950)
ERA_SPANS = (("Early church", 300, 600), ("Middle Ages", 600, 1500), ("Reformation", 1500, 1650),
             ("Puritans and the 1700s", 1650, 1800), ("The 1800s", 1800, 1950))


def born(author):
    """The year an author was born, from their dates ("c. 347-407" -> 347)."""
    m = re.search(r"(\d{3,4})\s*[-–]", author["dates"])
    return int(m[1]) if m else author["died"] - 60


def timeline(lib):
    """Each commentator's lifetime as a bar on one line of centuries, over
    the eras, each bar linking to their page."""
    lo, hi = TIMELINE
    pos = lambda y: (y - lo) / (hi - lo) * 100  # noqa: E731
    bands = "".join(f'<span class="lg-tl-band" style="left:{pos(a):.2f}%;width:{pos(b) - pos(a):.2f}%">'
                    f'<span>{e(t("eras." + era))}</span></span>' for era, a, b in ERA_SPANS)
    ticks = "".join(f'<span class="lg-tl-tick" style="left:{pos(y):.2f}%">{y}</span>' for y in range(400, hi, 300))
    rows = []
    for a in lib.ordered_authors():
        b, d = born(a), a["died"]
        flip = pos(d) > 62
        rows.append(f'<li class="lg-tl-row"><a class="lg-tl-life lg-era-{ERAS.index(a["era"])}{" lg-tl-flip" if flip else ""}" '
                    f'href="/commentators/{a["id"]}/" style="left:{pos(b):.2f}%;width:{max(pos(d) - pos(b), .6):.2f}%">'
                    f'<span class="lg-tl-name"><b>{e(a["name"])}</b> {e(a["dates"])}</span></a></li>')
    return (f'<figure class="lg-tl" aria-labelledby="tl-cap"><div class="lg-tl-scroll"><div class="lg-tl-in">'
            f'<div class="lg-tl-bands" aria-hidden="true">{bands}</div><ol class="lg-tl-rows">{"".join(rows)}</ol>'
            f'<div class="lg-tl-axis" aria-hidden="true">{ticks}</div></div></div>'
            f'<figcaption class="lg-quiet" id="tl-cap">{e(t("commentators.timeline_note", a=lo, b=hi))}</figcaption></figure>')


def name_initials(a):
    """"JC" for John Chrysostom: the first and last capitals of a name."""
    caps = "".join(w[0] for w in a["name"].replace(".", " ").split() if w[0].isupper())
    return caps[0] + caps[-1] if len(caps) > 1 else caps


def commentators_page(lib):
    # Each commentator as a card in one grid: their initials in their era's
    # colour, dates and tradition, the first words of their first excerpt,
    # the language they wrote in, and how much of each book they cover.
    verses = {}
    for c in lib.comments:
        b, ch, v = ref_parts(c["start"])
        _, ech, ev = ref_parts(c["end"])
        for x in lib.verses(b, ch):
            if v <= x and (ech != ch or x <= ev):
                verses.setdefault(lib.works[c["work"]]["author"], {}).setdefault(b, set()).add((ch, x))
    book_verses = {b: sum(len(lib.verses(b, ch)) for bb, ch in lib.chapters if bb == b) for b, _c in lib.coverage()}
    cards = []
    for a in lib.ordered_authors():
        mine = sorted((c for c in lib.comments if lib.works[c["work"]]["author"] == a["id"]), key=order_key)
        works = lib.ordered_works({c["work"] for c in mine})
        first = mine[0] if mine else None
        quote = ""
        if first:
            paras = [p for p in first["text"].split("\n\n") if p.strip()]
            lead = paras[1] if len(paras) > 1 and len(paras[0].split()) < 30 else paras[0]
            quote = (f'<p class="lg-pq">“{e(snippet(lead, 22))}” '
                     f'<span>{e(t("commentators.on", ref=scripture.label(first["start"], first["end"])))}</span></p>')
        cov = "".join(
            f'<span class="lg-cov"><span class="lg-meter"><span style="width:{100 * len(vs) / book_verses[b]:.0f}%"></span></span>'
            f'{e(t("commentators.coverage", book=lib.books[b]["en"], n=len(vs), total=book_verses[b]))}</span>'
            for b, vs in verses.get(a["id"], {}).items())
        langs = " · ".join(dict.fromkeys(lib.works[w]["original_language"] for w in works))
        initials = name_initials(a)
        cards.append(
            f'<li><a class="lg-person lg-era-{ERAS.index(a["era"])}" href="/commentators/{a["id"]}/">'
            f'<span class="lg-mono" aria-hidden="true">{e(initials)}</span>'
            f'<span><span class="lg-era-name">{e(t("eras." + a["era"]))}</span><b>{e(a["name"])}</b>'
            f'<span class="lg-dates">{e(a["dates"])} · {e(a["tradition"])}</span>{quote}'
            f'<span class="lg-meta">{e(t("commentators.wrote_in", lang=langs))}</span>{cov}</span></a></li>')
    sections = f'<section class="lg-block"><ul class="lg-grid lg-people-grid">{"".join(cards)}</ul></section>'
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("commentators.title"))}</p>
<h1>{e(t("commentators.heading"))}</h1><p class="dek">{e(t("commentators.dek"))}</p></header>
{timeline(lib)}
<p class="lg-era-links">{e(t("era.by_era"))} {era_links(lib)}</p>
{sections}"""
    return page(lib, t("commentators.title"), body, "/commentators/", current="/commentators/")


def reading_minutes(text):
    """Minutes to read an excerpt aloud or slowly, at about 200 words a minute."""
    return max(1, round(len(text.split()) / 200))


def excerpt_list(lib, comments, show_work=False):
    """Excerpts grouped by chapter, each chapter closed but the first, with a
    bar of the chapters above them, each shaded by how much is said on it:
    one row per verse or range, the verse as the Open Word Bible has it, the
    excerpt's first words, where it sits in its work, and links to read it."""
    out, rows = [], {}
    for c in comments:
        b, ch, v = ref_parts(c["start"])
        _, ech, ev = ref_parts(c["end"])
        rows.setdefault((b, ch), {}).setdefault((v, ech, ev, c["work"] if show_work else ""), []).append(c)
    words = {k: sum(len(c["text"].split()) for cs in g.values() for c in cs) for k, g in rows.items()}
    most = max(words.values(), default=1)
    several = len({x for x, _y in rows}) > 1
    bar = "".join(f'<a href="#ch-{b.lower()}-{ch}" style="--depth:{8 + 32 * words[(b, ch)] / most:.0f}%" '
                  f'title="{e(t("commentators.chapter_words", chapter=lib.books[b]["en"] + f" {ch}", n=f"{words[(b, ch)]:,}"))}">'
                  f'{e(lib.books[b]["en"]) + " " if several else ""}{ch}</a>'
                  for b, ch in rows)
    out.append(f'<nav class="lg-chbar lg-chbar-depth" aria-label="{e(t("commentators.chapters"))}">{bar}</nav>')
    for n, ((b, ch), group) in enumerate(rows.items()):
        name = f'{lib.books[b]["en"]} {ch}'
        passages = sum(len(cs) for cs in group.values())
        works = {c["work"] for cs in group.values() for c in cs}
        whole = (f'<p class="lg-chlink"><a href="{work_chapter_url(next(iter(works)), b, ch)}">'
                 f'{e(t("commentators.in_order", chapter=name))} {icon("arrow", 15)}</a></p>' if len(works) == 1 else "")
        out.append(f'<details class="lg-ch" id="ch-{b.lower()}-{ch}"{" open" if n == 0 else ""}><summary><b>{e(name)}</b>'
                   f'<span class="lg-quiet">{e(t("commentators.passages", n=passages))}</span>{icon("chevron", 16, "icon lg-caret")}</summary>'
                   f'{whole}<ul class="lg-excerpts">')
        plain = lib.plain(b, ch)
        for (v, ech, ev, work), cs in group.items():
            ref = f"{ch}:{v}" + (f"–{ev}" if (ech, ev) != (ch, v) else "") if ech == ch else f"{ch}:{v}–{ech}:{ev}"
            more = f'<span class="lg-quiet">{e(t("commentators.passages", n=len(cs)))}</span>' if len(cs) > 1 else ""
            title = f'<span class="lg-quiet">{e(lib.works[work]["title"])}</span>' if work else ""
            c = cs[0]
            h = c["heading"]
            lead = re.sub(r"^\s*\d+\.\s*", "", c["text"]).lower()
            lemma = f'<i>{e(h)}</i> ' if h and not lead.startswith(h.lower().strip(" .")) else ""
            verse = snippet(plain.get(v, ""), 24)
            verse = (f'<p class="lg-ex-verse">{e(verse)}{" …" if (ech, ev) != (ch, v) and not verse.endswith("…") else ""}</p>'
                     if verse else "")
            w = lib.works[c["work"]]
            meta = [e(locus_label(w, c["locus"]))] if c.get("locus") else []
            meta.append(e(t("commentators.minutes", n=reading_minutes(c["text"]))))
            if lib.in_full.get(c["id"]):
                meta.append(f'<a href="{lib.in_full[c["id"]]}">{e(t("commentators.from_here", division=w["divisions"][0].lower()))}</a>')
            else:
                meta.append(f'<a href="{excerpt_href(lib, c)}">{e(t("commentators.read_it"))}</a>')
            last = ev if ech == ch else max(lib.verses(b, ch))
            out.append(f'<li data-from="{v}" data-to="{last}"><p class="lg-ex-ref"><a href="{chapter_url(b, ch)}#v{v}" '
                       f'title="{e(lib.books[b]["en"])} {e(ref)}"><b>{e(ref)}</b></a>{more}</p>'
                       f'<div>{title}{verse}<p>{lemma}{e(snippet(c["text"]))}</p>'
                       f'<p class="lg-ex-meta">{" · ".join(meta)}</p></div></li>')
        out.append("</ul></details>")
    return "".join(out)


def order_key(c):
    b, ch, v = ref_parts(c["start"])
    return (b, ch, v, c["id"])


def missing_verses(lib, author, book, covered):
    """The verses of a book a commentator has no comment on, as linked runs
    ("1:5, 2:3–4"), folded away under their count."""
    missing = [(ch, v) for bb, ch in sorted(lib.chapters) if bb == book for v in lib.verses(bb, ch) if (ch, v) not in covered]
    if not missing:
        return ""
    runs = []
    for ch, v in missing:
        if runs and runs[-1][0] == ch and runs[-1][2] + 1 == v:
            runs[-1][2] = v
        else:
            runs.append([ch, v, v])
    links = ", ".join(f'<a href="{chapter_url(book, ch)}#v{a}">{ch}:{a}{f"–{z}" if z != a else ""}</a>' for ch, a, z in runs)
    return (f'<details class="lg-missing"><summary>{e(t("commentators.missing", name=short_name(author), n=len(missing)))}</summary>'
            f'<p>{e(lib.books[book]["en"])} {links}</p></details>')


def author_covered(lib, comments):
    """{book: {(chapter, verse)}} that the excerpts comment on."""
    covered = {}
    for c in comments:
        b, ch, v = ref_parts(c["start"])
        _, ech, ev = ref_parts(c["end"])
        covered.setdefault(b, set()).update((ch, x) for x in lib.verses(b, ch) if v <= x and (ech != ch or x <= ev))
    return covered


def coverage_map(lib, author, book, covered):
    """A book as rows of chapters and squares of verses, the verses with no
    comment left open, and the list of them beneath."""
    rows = []
    for bb, ch in lib.chapters:
        if bb != book:
            continue
        cells = "".join('<i></i>' if (ch, v) in covered else
                        f'<i class="lg-nc" title="{e(lib.books[book]["en"])} {ch}:{v}"></i>' for v in lib.verses(book, ch))
        rows.append(f'<li><a href="#ch-{book.lower()}-{ch}">{ch}</a><span>{cells}</span></li>')
    return (f'<div class="lg-cov-map"><h3 class="label">{e(t("commentators.map", book=lib.books[book]["en"]))}</h3>'
            f'<ol>{"".join(rows)}</ol>{missing_verses(lib, author, book, covered)}</div>')


def start_here(lib, comments, n=3):
    """The author's excerpts on the verses the most works in Logia comment
    on, one a chapter, the Catena's quotations and length breaking ties."""
    seen, out = set(), []
    for c in sorted(comments, key=lambda c: (-len(lib.voices_on.get(ref_parts(c["start"]), [])),
                                             -len(c["quoted_in"]), -len(c["text"].split()), order_key(c))):
        b, ch, _v = ref_parts(c["start"])
        if (b, ch) in seen:
            continue
        seen.add((b, ch))
        out.append(c)
        if len(out) == n:
            break
    return sorted(out, key=order_key)


def count_bars(rows, top):
    """Rows of (label html, n) as bars against top."""
    return "".join(f'<li><span>{label}</span><span class="lg-hbar"><span style="width:{100 * n / top:.1f}%"></span></span>'
                   f'<span class="lg-quiet">{n:,}</span></li>' for label, n in rows)


def author_page(lib, author):
    works = lib.ordered_works([w for w, x in lib.works.items() if x["author"] == author["id"]])
    comments = sorted((c for c in lib.comments if c["work"] in works), key=order_key)
    name, short = author["name"], short_name(author)
    bio = "".join(f"<p>{e(p)}</p>" for p in author["bio"].split("\n\n"))
    draft = f'<p><span class="lg-pill lg-pill-draft">{e(t("commentators.bio_draft"))}</span></p>' if author["bio_status"] == "ai_draft" else ""
    langs = " · ".join(dict.fromkeys(lib.works[w]["original_language"] for w in works))
    covered = author_covered(lib, comments)
    totals = {b: sum(len(lib.verses(b, ch)) for bb, ch in lib.chapters if bb == b) for b in covered}
    # The facts beside the biography: when they lived, their tradition, the
    # language they wrote in, their works here and how much they cover.
    facts = [(t("commentators.lived"), author["dates"]), (t("commentators.era"), t("eras." + author["era"])),
             (t("commentators.tradition"), author["tradition"]), (t("work.original"), langs)]
    for w in works:
        x = lib.works[w]
        facts.append((t("commentators.work"), f'<a href="/works/{w}/"><i>{e(x["title"])}</i></a>'
                      + (f'<span class="lg-quiet">{e(short_edition(x["edition"]))}</span>' if x["edition"] else "")))
    for b, vs in covered.items():
        facts.append((t("commentators.covers"), f'<span class="lg-meter"><span style="width:{100 * len(vs) / totals[b]:.0f}%"></span></span>'
                      + e(t("commentators.coverage", book=lib.books[b]["en"], n=len(vs), total=totals[b]))))
    dl = "".join(f"<div><dt>{e(k)}</dt><dd>{v if k in (t('commentators.work'), t('commentators.covers')) else e(v)}</dd></div>"
                 for k, v in facts)
    # The same facts in a line under the name, for a phone, where the card
    # falls below the biography.
    wholes = [w for w in works if lib.texts.get(w)]
    chips = [langs] + [t("commentators.in_full", n=len(lib.texts[w]), divisions=plural(lib.works[w]["divisions"][0]).lower(),
                         book=lib.books[lib.texts[w][0]["verses"]["start"].split(".")[0]]["en"]) for w in wholes]
    chips += [t("commentators.coverage", book=lib.books[b]["en"], n=len(vs), total=totals[b]) for b, vs in covered.items()]
    chips = "".join(f'<li>{e(x)}</li>' for x in chips)

    # Start here: three passages to read first.
    starts = "".join(
        f'<li><a href="{excerpt_href(lib, c)}"><b>{e(scripture.label(c["start"], c["end"]))}</b>'
        f'<span class="lg-start-text">{e(snippet(c["text"], 30))}</span>'
        f'<span class="lg-quiet">{e(locus_label(lib.works[c["work"]], c["locus"]) if c.get("locus") else lib.works[c["work"]]["title"])}</span></a></li>'
        for c in start_here(lib, comments))
    start = (f'<section class="lg-block lg-start"><h2>{e(t("commentators.start_here"))}</h2>'
             f'<p class="lg-quiet">{e(t("commentators.start_note", name=short))}</p><ul>{starts}</ul></section>' if starts else "")

    # Verse by verse, or each homily whole; a box that goes to a verse.
    books_here = list(covered)
    first = comments[0] if comments else None
    example = (f'{lib.books[books_here[-1]]["en"]} ' if len(books_here) > 1 else "") + "3:16"
    names = {b: [lib.books[b]["en"].lower(), b.lower()] for b in books_here}
    jump = (f'<form class="lg-goto" data-books="{e(json.dumps(names))}" data-none="{e(t("commentators.jump_none", name=short))}">'
            f'<label for="jump-{author["id"]}">{e(t("commentators.jump_label"))}</label>'
            f'<input id="jump-{author["id"]}" type="text" inputmode="text" autocomplete="off" placeholder="{e(example)}" '
            f'aria-describedby="jump-{author["id"]}-hint">'
            f'<button type="submit" class="button ghost">{e(t("commentators.jump_go"))}</button>'
            f'<span class="lg-quiet" id="jump-{author["id"]}-hint" role="status">{e(t("commentators.jump_hint", example=example))}</span></form>'
            if first else "")
    by_verse = excerpt_list(lib, comments, show_work=len(works) > 1)
    if wholes:
        division = lib.works[wholes[0]]["divisions"][0].lower()
        lists = "".join((f'<h3 class="label">{e(lib.works[w]["title"])}</h3>' if len(wholes) > 1 else "")
                        + f'<ul class="lg-wholes">{wholes_list(lib, w)}</ul>' for w in wholes)
        aid = author["id"]
        tabs = (f'<div class="lg-tabs" role="tablist" hidden>'
                f'<button type="button" role="tab" id="tab-{aid}-v" aria-controls="by-verse" aria-selected="true">{e(t("commentators.by_verse"))}</button>'
                f'<button type="button" role="tab" id="tab-{aid}-w" aria-controls="by-whole" aria-selected="false">'
                f'{e(t("commentators.by_division", division=division))}</button></div>')
        says = (f'{tabs}<div id="by-verse" role="tabpanel" aria-labelledby="tab-{aid}-v">{jump}{by_verse}</div>'
                f'<div id="by-whole" role="tabpanel" aria-labelledby="tab-{aid}-w">'
                f'<h3 class="lg-tab-title">{e(t("commentators.by_division", division=division))}</h3>'
                f'<p class="lg-quiet">{e(t("commentators.whole_note", division=division))}</p>{lists}</div>')
    else:
        says = jump + by_verse

    # The shape of the work: what it covers, the Scripture it cites, where it
    # says the most.
    maps = "".join(coverage_map(lib, author, b, vs) for b, vs in covered.items())
    cited = {}
    for c in comments:
        here = c["start"].split(".")[0]
        for x in c["cites"]:
            b = x["start"].split(".")[0]
            if b != here and b in lib.books:
                cited[b] = cited.get(b, 0) + 1
    top_cited = sorted(cited.items(), key=lambda kv: (-kv[1], list(lib.books).index(kv[0])))[:6]
    cites = (f'<div><h3 class="label">{e(t("commentators.cited", name=short))}</h3><ul class="lg-pbars">'
             + count_bars([(e(lib.books[b]["en"]), n) for b, n in top_cited], top_cited[0][1])
             + f'</ul><p class="lg-quiet">{e(t("commentators.cited_note"))}</p></div>' if top_cited else "")
    longest = sorted(comments, key=lambda c: (-len(c["text"].split()), order_key(c)))[:5]
    longest = "".join(f'<li><a href="{excerpt_href(lib, c)}"><b>{e(scripture.label(c["start"], c["end"]))}</b>'
                      f'<span>{e(snippet(c["text"], 12))}</span></a>'
                      f'<span class="lg-quiet">{e(t("commentators.words", n=f"{len(c['text'].split()):,}"))}</span></li>' for c in longest)
    shape = (f'<section class="lg-block" id="shape"><h2>{e(t("commentators.shape"))}</h2>'
             f'<p class="lg-quiet">{e(t("commentators.map_note"))}</p><div class="lg-cov-maps">{maps}</div>'
             f'<div class="lg-shape">{cites}<div><h3 class="label">{e(t("commentators.longest", name=short))}</h3>'
             f'<ol class="lg-longest">{longest}</ol></div></div></section>' if comments else "")

    # Read alongside: who comments on the same verses, and how often the
    # Catena quotes them.
    mine = {k for k, ws in lib.voices_on.items() if any(w in works for w in ws)}
    others = []
    for a in lib.ordered_authors():
        if a["id"] == author["id"]:
            continue
        n = sum(1 for k in mine if any(lib.works[w]["author"] == a["id"] for w in lib.voices_on[k]))
        if n:
            others.append((f'<a href="/commentators/{a["id"]}/">{e(a["name"])}</a>', n))
    others.sort(key=lambda r: -r[1])
    quoted = sum(1 for c in lib.comments for q in c["quotes"] if q["work"] in works)
    catena = (f'<p class="lg-catq"><b>{quoted:,}</b> <span>{e(t("commentators.catena"))} '
              f'<a href="/works/catena/fathers/">{e(t("commentators.catena_link"))}</a></span></p>' if quoted and "catena" in lib.works else "")
    alongside = (f'<section class="lg-block" id="alongside"><h2>{e(t("commentators.alongside"))}</h2>'
                 f'<p class="lg-quiet">{e(t("commentators.alongside_note", name=short))}</p>'
                 f'<ul class="lg-pbars lg-bars-gold">{count_bars(others, len(mine))}</ul>{catena}</section>' if others else "")

    # About the text: each work's edition, rights and citation.
    about = "".join(
        f'<div class="lg-about-work"><h3><a href="/works/{w}/"><i>{e(lib.works[w]["title"])}</i></a></h3>'
        f'<p>{e(lib.works[w]["translation"] or lib.works[w]["edition"])}</p>'
        f'<p class="lg-pills">{rights_pills(lib.works[w])}</p>{cite_box(author, lib.works[w])}'
        f'<p class="lg-about-links"><a href="{e(lib.works[w]["full_text_url"])}" rel="noopener">{e(t("commentators.full_text"))} ↗</a> · '
        f'<a href="/open-data/">{e(t("commentators.open_data"))}</a></p></div>' for w in works)
    about = f'<section class="lg-block" id="about-text"><h2>{e(t("commentators.about_text"))}</h2><div class="lg-about-works">{about}</div></section>'

    era = ERAS.index(author["era"])
    body = f"""
<div class="lg-profile lg-era-{era}">
<div class="lg-profile-main"><header class="page-head lg-person-head"><span class="lg-mono" aria-hidden="true">{e(name_initials(author))}</span><div>
<p class="eyebrow"><a href="/commentators/">{e(t("commentators.title"))}</a> · <a href="{era_url(author["era"])}">{e(t("eras." + author["era"]))}</a></p>
<h1>{e(name)}</h1><p class="dek">{e(author["dates"])} · {e(author["tradition"])}</p><ul class="lg-chips">{chips}</ul></div></header>
<section class="prose lg-bio">{bio}{draft}</section></div>
<dl class="lg-facts-card">{dl}</dl></div>
{start}
<section class="lg-block" id="says"><h2>{e(t("commentators.comments_on", name=name))}</h2>{says}</section>
{shape}{alongside}{about}"""
    books = " · ".join(lib.books[b]["en"] for b in covered)
    person = {"@context": "https://schema.org", "@type": "Person", "name": name,
              "url": SITE_URL + f'/commentators/{author["id"]}/', "description": author["bio"].split("\n\n")[0],
              "deathDate": f'{author["died"]:04d}'}
    if not author["dates"].lstrip().startswith("c."):
        person["birthDate"] = f"{born(author):04d}"
    crumbs = breadcrumbs((t("commentators.title"), "/commentators/"), (name, f'/commentators/{author["id"]}/'))
    return page(lib, name, body, f'/commentators/{author["id"]}/', current="/commentators/",
                head_title=t("commentators.head_title", name=name, books=books) if books else None,
                ld=(person, crumbs),
                description=author["bio"].split("\n\n")[0])


def rights_pills(w):
    """A work's rights, said plainly: its status in the US and worldwide as pills."""
    r = w["rights"]
    us = r["basis"].lower().startswith("public domain")
    world = r["worldwide"].lower().startswith("public domain")
    return (f'<span class="lg-pill {"lg-pill-ok" if us else "lg-pill-draft"}">{e(t("work.rights_us" if us else "work.rights_us_check"))}</span> '
            f'<span class="lg-pill {"lg-pill-ok" if world else "lg-pill-draft"}">'
            f'{e(t("work.rights_world" if world else "work.rights_world_check"))}</span>')


def cite_box(a, w):
    """The edition as a citation gives it (up to its first note in brackets
    or after a semicolon, which name the scan or the series), with a copy button."""
    edition = re.match(r"^[^;(]+", w["edition"])[0].strip().rstrip(",.")
    citation = t("work.citation", name=a["name"], title=w["title"], edition=edition)
    return (f'<div class="lg-cite-box"><p class="label">{e(t("work.cite"))}</p><p class="lg-cite-text">{e(citation)}</p>'
            f'<button type="button" class="button ghost lg-copy" data-copy="{e(citation)}" data-done="{e(t("work.cite_copied"))}">'
            f'{e(t("work.cite_copy"))}</button></div>')


def wholes_list(lib, wid):
    """A work's whole homilies or tractates, in order, each with its opening."""
    w = lib.works[wid]
    return "".join(f'<li><a href="/works/{wid}/{x["locus"]}/"><b>{e(locus_label(w, x["locus"]))}</b></a>'
                   f'<span class="lg-quiet">{e(text_lead(x))}</span></li>' for x in lib.texts.get(wid, []))


def work_start_here(lib, comments, n=3):
    """A work's first excerpt on each of the n verses (one a chapter) that
    the most works in Logia comment on, then the most excerpts in all."""
    total = lib.excerpts_on_verse()
    seen, out = set(), []
    for c in sorted(comments, key=lambda c: (-len(lib.voices_on.get(ref_parts(c["start"]), [])),
                                             -total[ref_parts(c["start"])], order_key(c))):
        b, ch, _v = ref_parts(c["start"])
        if (b, ch) not in seen:
            seen.add((b, ch))
            out.append(c)
        if len(out) == n:
            break
    return sorted(out, key=order_key)


def voices_line(lib, c):
    """How many works in Logia comment on an excerpt's first verse."""
    n = len(lib.voices_on.get(ref_parts(c["start"]), []))
    return t("work.start_voices_one" if n == 1 else "work.start_voices", n=n)


def work_page(lib, wid):
    w, a = lib.works[wid], lib.author_of(wid)
    comments = sorted((c for c in lib.comments if c["work"] == wid), key=order_key)
    source = (t("work.source_scan", n=len(lib.fixes.get(wid, []))) if w["source_kind"] == "scan"
              else t("work.source_digital"))
    facts = [(t("work.original"), w["original_language"]), (t("work.edition"), w["edition"])]
    if w["translation"]:
        facts.append((t("work.translation"), w["translation"]))
    facts += [(t("work.published"), str(w["published"])), (t("work.source"), source),
              (t("work.in_logia"), t("work.excerpts", n=len(comments)))]
    dl = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in facts)
    r = w["rights"]
    dl += (f'<dt>{e(t("work.rights"))}</dt><dd><span class="lg-pills">{rights_pills(w)}</span>'
           f'<span class="lg-quiet lg-rights-note">{e(r["basis"])}; {e(r["worldwide"])}</span></dd>')
    cite = cite_box(a, w)
    # Start here: three passages to read first, on the verses the most works discuss.
    starts = "".join(
        f'<li><a href="{excerpt_href(lib, c)}"><b>{e(scripture.label(c["start"], c["end"]))}</b>'
        f'<span class="lg-start-text">{e(snippet(c["text"], 30))}</span>'
        f'<span class="lg-quiet">{e(voices_line(lib, c))}</span></a></li>'
        for c in work_start_here(lib, comments))
    start = (f'<section class="lg-block lg-start lg-work-start"><h2>{e(t("work.start_here"))}</h2>'
             f'<p class="lg-quiet">{e(t("work.start_note"))}</p><ul>{starts}</ul></section>' if starts else "")
    contents = work_contents(lib, wid, comments)
    texts = lib.texts.get(wid, [])
    whole = ""
    if texts:
        items = wholes_list(lib, wid)
        verses = []
        for x in texts:
            b, c, a1 = scripture.parse(x["verses"]["start"])
            _, _, a2 = scripture.parse(x["verses"]["end"])
            verses += [f"{b}.{c}.{v}" for v in range(a1, a2 + 1) if f"{b}.{c}.{v}" not in verses]
        by_verse = "".join(
            f'<li><a href="{e(lib.verse_link(ref) or "")}"><b>{e(scripture.label(ref))}</b></a><span>'
            + " · ".join(f'<a href="{e(r["href"])}">{e(r["where"])}</a>' for r in lib.whole_on(ref) if r["work_id"] == wid)
            + "</span></li>" for ref in verses)
        whole = (f'<section class="lg-block" id="whole"><h2>{e(t("work.straight_through"))}</h2>'
                 f'<p class="lg-quiet">{e(t("work.straight_through_note", divisions=plural(w["divisions"][0]).lower()))}</p>'
                 f'<div class="lg-structures"><div><h3 class="label">{e(t("work.by_division", division=w["divisions"][0].lower()))}</h3>'
                 f'<ul class="lg-wholes">{items}</ul></div>'
                 f'<div><h3 class="label">{e(t("work.by_verse"))}</h3><p class="lg-quiet">{e(t("work.by_verse_note"))}</p>'
                 f'<ul class="lg-wholes lg-by-verse">{by_verse}</ul></div></div></section>')
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("work.eyebrow"))} · {e(t("eras." + a["era"]))}</p>
<h1>{e(w["title"])}</h1><p class="dek">{t("work.by", name=f'<a href="/commentators/{a["id"]}/">{e(a["name"])}</a>')} ({e(a["dates"])})</p>
<p class="actions"><a class="button ghost" href="{e(w["full_text_url"])}" rel="noopener">{e(t("work.full_text"))} ↗</a>{f' <a class="button ghost" href="/works/{wid}/fathers/">{e(t("catena.heading"))}</a>' if wid == "catena" else ""}</p></header>
{start}
<section class="lg-record" aria-label="{e(t("work.record"))}"><dl class="lg-facts">{dl}</dl>{cite}</section>
{whole}
<section class="lg-block" id="contents"><h2>{e(t("work.front_to_back"))}</h2><p class="lg-quiet">{e(t("work.front_to_back_note"))}</p>
<ol class="lg-contents">{contents}</ol></section>"""
    return page(lib, w["title"], body, f"/works/{wid}/", current="/commentators/",
                description=f'{a["name"]}, {w["title"]}: {len(comments)} excerpts in Logia.')


def work_chapters(comments):
    """{(book, chapter): [excerpts]} in canonical order, for a work's excerpts sorted by order_key."""
    out = {}
    for c in comments:
        b, ch, _v = ref_parts(c["start"])
        out.setdefault((b, ch), []).append(c)
    return out


def work_chapter_url(wid, book, chapter):
    return f"/works/{wid}/{book.lower()}/{chapter}/"


def work_contents(lib, wid, comments, current=None):
    """A work's chapters, each linking to its page with how many excerpts it has."""
    return "".join(
        f'<li><a href="{work_chapter_url(wid, b, ch)}"{" aria-current=page" if (b, ch) == current else ""}>'
        f'<span>{e(lib.books[b]["en"])} {ch}</span><span class="lg-quiet">{e(t("work.excerpts", n=len(cs)))}</span></a></li>'
        for (b, ch), cs in work_chapters(comments).items())


def work_chapter_page(lib, wid, book, chapter, comments):
    """One chapter of a work: its excerpts in order, beside the work's contents."""
    w, a = lib.works[wid], lib.author_of(wid)
    chapters = list(work_chapters(comments))
    here = work_chapters(comments)[(book, chapter)]
    name = f'{lib.books[book]["en"]} {chapter}'
    full = []
    text = lib.plain(book, chapter)
    shown = None
    for c in here:
        b, ch, v = ref_parts(c["start"])
        _, ech, ev = ref_parts(c["end"])
        ref = f"{lib.books[b]['en']} {ch}:{v}" + (f"–{ev}" if (ech, ev) != (ch, v) else "")
        heading = f'<p class="lg-lemma">{e(c["heading"])}</p>' if c["heading"] else ""
        paras = "".join(f"<p>{e(p.strip())}</p>" for p in c["text"].split("\n\n"))
        # The verse being commented on, in the margin, once for a run of
        # excerpts on the same verses (at most three verses of it).
        side, label = "", ""
        if (v, ech, ev) != shown:
            shown = (v, ech, ev)
            last = min(ev if ech == ch else max(text), v + 2)
            words = " ".join(f'<sup>{x}</sup>{e(text[x])}' for x in range(v, last + 1) if x in text)
            more = " …" if last < (ev if ech == ch else max(text)) else ""
            side = (f'<aside class="lg-side"><p class="label">{e(ref)} · {e(t("work.bible_text"))}</p>'
                    f'<p class="lg-side-text">{words}{more}</p></aside>') if words else ""
            label = (f'<p class="lg-ref"><a href="{chapter_url(b, ch)}#v{v}" '
                     f'title="{e(t("work.open_verse", ref=ref))}">{e(ref)}</a></p>')
        full.append(f'<article class="lg-excerpt lg-excerpt-side" id="{e(c["id"])}">{label}{heading}<div class="lg-text">{paras}</div>{side}</article>')
    i = chapters.index((book, chapter))
    turns = [f'<a rel="prev" href="{work_chapter_url(wid, *chapters[i - 1])}">&larr; {e(lib.books[chapters[i - 1][0]]["en"])} {chapters[i - 1][1]}</a>'
             if i else "<span></span>",
             f'<a rel="next" href="{work_chapter_url(wid, *chapters[i + 1])}">{e(lib.books[chapters[i + 1][0]]["en"])} {chapters[i + 1][1]} &rarr;</a>'
             if i + 1 < len(chapters) else "<span></span>"]
    body = f"""
<div class="lg-work-layout">
<nav class="lg-work-toc" aria-labelledby="toc-h"><p class="label" id="toc-h"><a href="/works/{wid}/#contents">{e(t("work.contents"))}</a></p>
<ol class="lg-contents">{work_contents(lib, wid, comments, (book, chapter))}</ol></nav>
<article class="lg-work-main">
<header class="page-head"><p class="eyebrow"><a href="/commentators/{a["id"]}/">{e(a["name"])}</a> · <a href="/works/{wid}/">{e(w["title"])}</a></p>
<h1>{e(name)}</h1><p class="dek">{e(t("work.chapter_dek", n=len(here), name=name))}</p></header>
<div class="lg-book lg-book-side">{"".join(full)}</div>
<nav class="lg-turns" aria-label="{e(w["title"])}">{"".join(turns)}</nav>
</article></div>"""
    return page(lib, f'{a["name"]} on {name}', body, work_chapter_url(wid, book, chapter), current="/commentators/",
                description=t("work.chapter_description", name=a["name"], title=w["title"], chapter=name, n=len(here)))


def text_lead(x):
    """The short headings under a homily's title: "John i. 1", "Chapter I. 1–5"."""
    out = []
    for p in x["paragraphs"][1:3]:
        if len(p["text"]) >= 60 or p["excerpts"]:
            break
        out.append(p["text"])
    return " · ".join(out)


def linked_html(lib, text, cites):
    """Text with the Scripture it cites made into links."""
    h, pos = [], 0
    for c in sorted(cites, key=lambda c: c["at"]):
        if c["at"] < pos:
            continue
        href = lib.verse_link(c["start"])
        words = e(text[c["at"]:c["at"] + len(c["text"])])
        label = e(scripture.label(c["start"], c["end"]))
        h.append(e(text[pos:c["at"]]))
        h.append(f'<a class="lg-cite" href="{e(href)}" title="{label}">{words}</a>' if href
                 else f'<span class="lg-cite" title="{label}">{words}</span>')
        pos = c["at"] + len(c["text"])
    return "".join(h) + e(text[pos:])


def text_page(lib, wid, x):
    """A whole homily or tractate, paragraph by paragraph, marking the
    passages Logia sets beside a verse and those the Catena quotes."""
    w, a = lib.works[wid], lib.author_of(wid)
    name = locus_label(w, x["locus"])
    lead = text_lead(x)
    paras = x["paragraphs"][1 + (lead.count(" · ") + 1 if lead else 0):]
    quoted = {}
    for c in lib.comments:
        for q in c["quotes"]:
            if q["work"] == wid and q["para"]:
                quoted.setdefault(q["para"], []).append(q)
    body, section = [], None
    for n, p in enumerate(paras):
        sec = p["locus"].split(".")[-1] if p["locus"] else None
        if sec != section:
            if section is not None:
                body.append("</section>")
            body.append(f'<section class="lg-section" id="s{sec}">')
            section = sec
        if p["verse"] and p["verse"] != (paras[n - 1]["verse"] if n else None):
            href = lib.verse_link(p["verse"])
            label = e(scripture.label(p["verse"]))
            body.append('<p class="lg-verse">' + (f'<a href="{e(href)}">{label}</a>' if href else label) + "</p>")
        head = len(p["text"]) < 60 and not p["cites"] and not re.search(r"[.?!”]$", p["text"])
        cls = " ".join(k for k, on in (("lg-head", head), ("lg-held", p["excerpts"])) if on)
        body.append(f'<p id="{e(p["id"])}"' + (f' class="{cls}"' if cls else "") + f'>{linked_html(lib, p["text"], p["cites"])}</p>')
        marks = []
        after = paras[n + 1]["excerpts"] if n + 1 < len(paras) else []
        for cid in (cid for cid in p["excerpts"] if cid not in after):     # once, under its last paragraph
            c = lib.by_id[cid]
            href = lib.verse_link(c["start"], wid)
            if href:
                marks.append(f'<a href="{e(href)}">{e(t("text.in_logia", ref=scripture.label(c["start"], c["end"])))}</a>')
        for q in quoted.get(p["id"], []):
            cat = lib.by_id[q["in"]]
            href = lib.verse_link(cat["start"], cat["work"])
            ref = e(scripture.label(cat["start"], cat["end"]))
            link = f'<a href="{e(href)}">{ref}</a>' if href else ref
            note = "" if q["status"] == "reviewed" else " " + e(t("reader.unchecked"))
            marks.append(f'<span>{t("text.quoted", name=e(lib.author_of(cat["work"])["name"]), title="<i>" + e(lib.works[cat["work"]]["title"].split(":")[0]) + "</i>", ref=link)}{note}</span>')
        if marks:
            body.append(f'<div class="lg-marks">{"".join(marks)}</div>')
    if section is not None:
        body.append("</section>")
    siblings = lib.texts[wid]
    i = siblings.index(x)
    turns = [f'<a rel="prev" href="/works/{wid}/{siblings[i - 1]["locus"]}/">&larr; {e(locus_label(w, siblings[i - 1]["locus"]))}</a>'
             if i else "<span></span>",
             f'<a rel="next" href="/works/{wid}/{siblings[i + 1]["locus"]}/">{e(locus_label(w, siblings[i + 1]["locus"]))} &rarr;</a>'
             if i + 1 < len(siblings) else "<span></span>"]
    html_body = f"""
<header class="page-head"><p class="eyebrow"><a href="/works/{wid}/">{e(w["title"])}</a> · {e(scripture.label(x["verses"]["start"], x["verses"]["end"]))}</p>
<h1>{e(name)}</h1><p class="dek">{e(lead)}</p>
<p class="actions"><a class="button ghost" href="/commentators/{a["id"]}/">{e(a["name"])}</a>
<a class="button ghost" href="{e(x["url"])}" rel="noopener">{e(t("text.on_ccel"))} ↗</a></p></header>
<div class="lg-whole">{"".join(body)}</div>
<nav class="lg-turns" aria-label="{e(w["title"])}">{"".join(turns)}</nav>
<p class="lg-quiet lg-whole-note">{e(t("text.note", edition=w["edition"]))}</p>"""
    return page(lib, f'{a["name"]}, {name}', html_body, f"/works/{wid}/{x['locus']}/", current="/commentators/",
                description=t("text.description", name=a["name"], title=w["title"], where=name))


def signed_in_page(lib):
    """Where Open Word Bible sends a reader back with a single-use code
    (#code=...&to=...); web/account.js trades it for a token and goes on."""
    body = f"""
<section class="auth" id="signed-in"><div class="auth-card auth-message">
{MARK}
<h1>{e(t("account.signed_in_title"))}</h1>
<p class="auth-dek">{e(t("account.signed_in_dek"))}</p>
<p id="signed-in-status" role="status"></p>
<p><a class="button" id="signed-in-retry" href="{OWB_SITE}/handoff/?site=logia&amp;to=%2F" hidden>{e(t("account.try_again"))}</a></p>
</div></section>"""
    return page(lib, t("account.signed_in_title"), body, "/signed-in/", description=t("account.signed_in_dek"),
                noindex=True)


def saved_page(lib):
    """The reader's saved comments; web/account.js fills it in. Signed out,
    it shows what saving does, with an excerpt as it would be kept."""
    sample = ""
    on = sorted((c for c in lib.comments if c["start"] == c["end"] == HOME_VERSES[0]), key=lambda c: (lib.ordered_works().index(c["work"]), c["id"]))
    calvin = [c for c in on if c["work"] == "calvin"] or on
    if calvin:
        c = calvin[0]
        a = lib.author_of(c["work"])
        sample = (f'<div class="lg-saved lg-saved-sample" aria-hidden="true"><p class="lg-saved-who"><b>{e(a["name"])}</b> '
                  f'{e(t("commentators.on", ref=scripture.label(c["start"])))}</p><p class="lg-saved-text">{e(snippet(c["text"], 26))}</p></div>')
    href = f"{OWB_SITE}/handoff/?site=logia&to={quote('/saved/', safe='')}"
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("account.saved_title"))}</p>
<h1>{e(t("account.saved_heading"))}</h1><p class="dek">{e(t("account.saved_dek"))}</p></header>
<section id="saved-page"><p class="lg-quiet" id="saved-note" role="status"></p><ul class="lg-saved-list" id="saved-list"></ul>
<div class="lg-saved-empty" id="saved-empty" hidden>{sample}
<h2>{e(t("account.saved_empty_title"))}</h2><p>{e(t("account.saved_empty_text"))}</p>
<p class="actions"><a class="button" href="{e(href)}" data-login>{icon("user")} {e(t("account.saved_empty_sign_in"))}</a>
<a class="button ghost" href="/jhn/3/#v16">{e(t("account.saved_empty_try"))}</a></p></div></section>"""
    return page(lib, t("account.saved_title"), body, "/saved/", noindex=True)


def not_found_page(lib):
    """Served by Render for any address with no page (/404.html). It can be
    served at any depth, so every link on it is absolute; signing in from it
    returns to the home page."""
    body = f"""
<section class="auth lg-not-found"><div class="auth-card auth-message">
{MARK}
<h1>{e(t("not_found.heading"))}</h1>
<p class="lg-guess" id="nf-guess" data-text="{e(t("not_found.guess"))}" hidden></p>
<p class="auth-dek">{e(t("not_found.dek"))}</p>
{search_box(lib, "nf-q", "hero-search lg-nf-search")}
<p class="hero-try lg-nf-try">{e(t("search.try"))} <a href="/jhn/1/#v1">John 1:1</a> <a href="/jhn/3/#v16">John 3:16</a> <a href="/jhn/14/#v6">John 14:6</a></p>
<p class="lg-not-found-links"><a class="button" href="/">{e(t("not_found.home"))}</a>
<a class="button ghost" href="/read/">{e(t("not_found.read"))}</a></p>
</div></section>"""
    return page(lib, t("not_found.title"), body, "/", description=t("not_found.dek"), noindex=True, canonical=False)


def chapter_file(lib, book, chapter):
    """A chapter's commentary as JSON, for the Saved page (/data/<BOOK>.<chapter>.json)."""
    bible = lib.bible(book, chapter)
    by_work = lib.in_chapter(book, chapter, bible["verses"][-1])
    return {"book": book, "chapter": chapter, "bookName": lib.books[book]["en"], "commentaries": [
        {"work_id": w, "author": lib.author_of(w)["name"], "title": lib.works[w]["title"],
         "entries": [{"start": x["start"], "end": x["end"], "excerpt": x["excerpt"]} for x in by_work[w]]}
        for w in lib.ordered_works(by_work)]}


# The About page's real examples, read from the library: one excerpt
# followed through the checks, the verse the name comes from, and a
# correction from each of four scans (work, the scan's reading).
ABOUT_EXAMPLE = "ryle.JHN.1.1.1"
ABOUT_NAME_VERSE = "ROM.3.2"
ABOUT_FIXES = (("ryle", "Let ns"), ("westcott", "which twos eternally"), ("bengel-romans", "of one mail"), ("godet-romans", "Bomans"))
ABOUT_RECENT = 3


def day_label(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {t('plan.months')[d.month - 1]} {d.year}"


def manifest_files():
    return load(os.path.join(ROOT, "sources", "manifest.json"))["files"]


def works_added():
    """{work: the day its record was first committed}, from the git history.
    Empty where there is none to read (a shallow clone), and the page then
    leaves the list out."""
    try:
        shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT, capture_output=True,
                                 text=True, timeout=30).stdout.strip()
        if shallow != "false":
            return {}
        out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%ad", "--date=short", "--name-only", "--",
                              "library/works/"], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    added, day = {}, None
    for line in out.splitlines():
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", line):
            day = line
        elif line.startswith("library/works/") and line.endswith(".json") and day:
            added[os.path.basename(line)[:-5]] = day   # oldest last, so the first commit wins
    return added


def about_stats(lib):
    """The library's size: excerpts, commentators, works, books and scan fixes."""
    books = [lib.books[b]["en"] for b in lib.books if any(x == b for x, _c in lib.coverage())]
    items = ((f"{len(lib.comments):,}", t("about.stats.excerpts")), (str(len(lib.authors)), t("about.stats.commentators")),
             (str(len(lib.works)), t("about.stats.works")), (str(len(books)), t("about.stats.books", books=name_list(books))),
             (f"{sum(len(v) for v in lib.fixes.values()):,}", t("about.stats.fixes")))
    return '<ul class="lg-ab-stats">' + "".join(f"<li><b>{n}</b><span>{e(label)}</span></li>" for n, label in items) + "</ul>"


def about_example(lib):
    """A verse and the opening of one commentator's excerpt on it, as copied."""
    c = lib.by_id.get(ABOUT_EXAMPLE)
    if not c:
        return ""
    book, chapter, verse = ref_parts(c["start"])
    a, w = lib.author_of(c["work"]), lib.works[c["work"]]
    ref = f'{lib.books[book]["en"]} {chapter}:{verse}'
    text = plain_verses(lib.bible(book, chapter)).get(verse, "")
    lead = next(p for p in c["text"].split("\n\n") if p.strip())
    n = len({x["work"] for x in lib.comments if x["start"] <= c["start"] <= x["end"] and ref_parts(x["start"])[0] == book})
    href = chapter_url(book, chapter) + f"#v{verse}"
    return (f'<figure class="lg-ab-example"><p class="eyebrow">{e(t("about.example_label"))}</p>'
            f'<blockquote class="lg-ab-verse"><p>{e(text)}</p><footer><a href="{href}">{e(ref)}</a></footer></blockquote>'
            f'<div class="lg-ab-voice"><p class="lg-ab-who"><a href="/commentators/{a["id"]}/"><b>{e(a["name"])}</b></a> '
            f'<span>{e(a["tradition"])} · {e(a["dates"])}</span></p>'
            f'<p class="lg-ab-excerpt">{e(snippet(lead, 60))}</p>'
            f'<p class="lg-quiet"><i>{e(t("about.example_from", title=w["title"], year=w["published"]))}</i> '
            f'<a href="{excerpt_href(lib, c)}">{e(t("about.example_whole"))}</a></p></div>'
            f'<p><a class="lg-more" href="{href}">{e(t("about.example_more", ref=ref, n=n))} {icon("arrow", 15)}</a></p></figure>')


def about_name(lib):
    """Where the name comes from, with the verse as the Open Word Bible reads it."""
    book, chapter, verse = ref_parts(ABOUT_NAME_VERSE)
    text = plain_verses(lib.bible(book, chapter)).get(verse, "") if (book, chapter) in lib.chapters else ""
    href = lib.verse_link(ABOUT_NAME_VERSE)
    note = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", e(t("about.name_note")))
    verse_html = (f'<p class="lg-ab-name-verse">{e(text)} <a href="{href}">{e(lib.books[book]["en"])} {chapter}:{verse}</a></p>'
                  if text and href else "")
    more = (f'<p><a class="lg-more" href="{href}">{e(t("about.name_more"))} {icon("arrow", 15)}</a></p>'
            if href and href.startswith("/") else "")
    return (f'<aside class="lg-ab-name"><p class="eyebrow">{e(t("about.name_label"))}</p>'
            f'<p class="lg-ab-name-words"><i>{e(t("about.name_words"))}</i></p>{verse_html}<p>{note}</p>{more}</aside>')


def about_voices(lib):
    """The commentators on one line of centuries, and their traditions."""
    traditions = "".join(f'<span class="lg-pill lg-pill-ok">{e(x)}</span>'
                         for x in dict.fromkeys(a["tradition"] for a in lib.ordered_authors()))
    return (f'<p>{e(t("about.voices"))}</p>{timeline(lib)}'
            f'<p class="label lg-ab-label">{e(t("about.traditions"))}</p>'
            f'<p class="lg-pills">{traditions}</p>')


def about_library(lib):
    """Each book with commentary: how many works, how many of its verses, and
    the works fetched most recently."""
    cov = lib.coverage()
    rows = []
    for book in lib.books:
        chapters = [c for b, c in cov if b == book]
        if not chapters:
            continue
        works = {c["work"] for c in lib.comments if ref_parts(c["start"])[0] == book}
        done = sum(len(set(cov[(book, c)][1]) & set(chapter_verses(book, c))) for c in chapters)
        total = sum(len(chapter_verses(b, c)) for b, c in lib.chapters if b == book)
        rows.append(f'<tr><td><a href="/{book.lower()}/">{e(lib.books[book]["en"])}</a></td><td>{len(works)}</td>'
                    f'<td>{e(t("about.library_count", n=f"{done:,}", total=f"{total:,}"))}</td></tr>')
    table = (f'<div class="lg-table-wrap"><table class="lg-words lg-ab-books"><thead><tr><th>{e(t("about.library_book"))}</th>'
             f'<th>{e(t("about.library_works"))}</th><th>{e(t("about.library_verses"))}</th></tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table></div>')
    added = works_added()
    recent = sorted((w for w in added if w in lib.works), key=lambda w: (added[w], w), reverse=True)[:ABOUT_RECENT]
    if not recent:
        return table
    items = "".join(f'<li><a href="/works/{w}/"><b>{e(lib.author_of(w)["name"])}</b> '
                    f'<span>{e(t("about.recent_row", title=lib.works[w]["title"], year=lib.works[w]["published"]))}</span></a>'
                    f'<span class="lg-quiet">{e(day_label(added[w]))}</span></li>' for w in recent)
    return f'{table}<h3>{e(t("about.recent"))}</h3><ul class="lg-ab-recent">{items}</ul>'


def about_trail(lib):
    """The five steps, each shown for one real excerpt: its edition, the file
    it was copied from, how it was checked, a correction in it and its verse."""
    c = lib.by_id.get(ABOUT_EXAMPLE)
    titles = t("about.steps")
    if not c:
        return "".join(f'<li><b>{e(a)}</b><span>{e(b)}</span></li>' for a, b in titles)
    w = lib.works[c["work"]]
    book, chapter, verse = ref_parts(c["start"])
    ref = f'{lib.books[book]["en"]} {chapter}:{verse}'
    src = c["sources"][0]
    rec = next((f for f in manifest_files() if f["work"] == c["work"] and os.path.basename(f["path"]) == src), None)
    with open(os.path.join(ROOT, "library", "comments", c["work"], f"{book}.json"), encoding="utf-8") as f:
        raw = next(x["text"] for x in json.load(f)["entries"] if x["id"] == c["id"])
    fix = next(((a, b) for a, b in lib.fixes.get(c["work"], []) if a.strip() and a in raw), None)
    saved = (t("about.trail_saved", file=rec["path"], date=day_label(rec["retrieved"])) if rec else "")
    examples = (t("about.trail_edition", edition=short_edition(w["edition"])),
                saved,
                t("about.trail_scan") if w.get("source_kind") == "scan" else t("about.trail_digital"),
                t("about.trail_fix", a=fix[0], b=fix[1]) if fix else t("about.trail_nofix"),
                t("about.trail_placed", ref=ref))
    links = (w["full_text_url"], f'{GITHUB_URL}/blob/main/{rec["path"]}' if rec else "", "", "",
             chapter_url(book, chapter) + f"#v{verse}")
    steps = "".join(
        f'<li><b>{e(a)}</b><span>{e(b)}</span>'
        + (f'<a class="lg-ab-eg" href="{e(link)}">{e(x)}</a>' if link else f'<span class="lg-ab-eg">{e(x)}</span>') + '</li>'
        for (a, b), x, link in zip(titles, examples, links))
    return steps, t("about.trail_title", name=lib.author_of(c["work"])["name"], ref=ref)


def checking_figure(lib):
    """How an excerpt reaches Logia, step by step for one real excerpt, then
    real correction pairs from four scans as the build applies them."""
    trail = about_trail(lib)
    steps, title = trail if isinstance(trail, tuple) else (trail, "")
    rows = []
    for work, wrong in ABOUT_FIXES:
        right = dict(lib.fixes.get(work, [])).get(wrong)
        if right and work in lib.works:
            name = f'{short_name(lib.author_of(work))}, {lib.books[ref_parts(next(c["start"] for c in lib.comments if c["work"] == work))[0]]["en"]}'
            rows.append(f'<tr><td><a href="/works/{work}/">{e(name)}</a></td><td><del>{e(wrong)}</del></td>'
                        f'<td><ins>{e(right)}</ins></td><td>{len(lib.fixes[work]):,}</td></tr>')
    fixes = ""
    if rows:
        fixes = (f'<h3>{e(t("about.fixes_title"))}</h3><div class="lg-table-wrap"><table class="lg-words lg-ab-fixes"><thead><tr>'
                 f'<th>{e(t("about.fixes_work"))}</th><th>{e(t("about.fixes_scan"))}</th><th>{e(t("about.fixes_page"))}</th>'
                 f'<th>{e(t("about.fixes_n"))}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
                 f'<p><a class="lg-more" href="{GITHUB_URL}/tree/main/library/corrections" rel="noopener">{e(t("about.fixes_all"))} ↗</a></p>')
    total = sum(len(v) for v in lib.fixes.values())
    cap = f'<p class="label lg-ab-label">{e(title)}</p>' if title else ""
    return (f'<figure class="lg-steps-fig">{cap}<ol class="lg-steps">{steps}</ol>'
            f'<figcaption class="lg-quiet">{e(t("about.steps_note", n=f"{len(lib.comments):,}", fixes=f"{total:,}"))}</figcaption></figure>'
            f'{fixes}<details class="lg-ab-details"><summary>{e(t("about.details"))}</summary><p>{e(t("about.details_text"))}</p></details>')


def about_open():
    tiles = "".join(f'<li><b>{e(a)}</b><span class="lg-pill lg-pill-ok">{e(b)}</span><span>{e(c)}</span></li>'
                    for a, b, c in t("about.open"))
    return (f'<ul class="lg-ab-tiles">{tiles}</ul><p class="lg-quiet">{e(t("about.open_note"))}</p>'
            f'<p class="lg-ab-actions"><a class="button" href="/open-data/">{e(t("open_data.about_link"))}</a> '
            f'<a class="button ghost" href="{GITHUB_URL}" rel="noopener">{e(t("about.github"))} ↗</a></p>')


def about_cite():
    citation = t("about.citation", url=SITE_URL + "/")
    return (f'<p>{e(t("about.cite"))}</p><div class="lg-cite-box"><p class="lg-cite-text">{e(citation)}</p>'
            f'<button type="button" class="button ghost lg-copy" data-copy="{e(citation)}" data-done="{e(t("work.cite_copied"))}">'
            f'{e(t("work.cite_copy"))}</button></div><p class="lg-quiet">{e(t("about.cite_note"))}</p>')


def about_help():
    items = "".join(f'<li><a href="{GITHUB_URL}/issues/new?template={e(tpl)}" rel="noopener"><b>{e(a)} ↗</b><span>{e(b)}</span></a></li>'
                    for a, b, tpl in t("about.help_items"))
    return f'<p>{e(t("about.help"))}</p><ul class="lg-ab-tiles lg-ab-help">{items}</ul>'


def about_thanks(lib):
    """The sites Logia's texts were copied from, with the works from each,
    read from sources/manifest.json; then the Bible text and Sefaria."""
    hosts = {}
    for f in manifest_files():
        if f["work"] in lib.works:
            host = f["url"].split("/")[2]
            hosts.setdefault(host, {}).setdefault(lib.works[f["work"]]["author"], f["work"])
    names = t("about.hosts")
    rows = []
    for host, by in hosts.items():
        kinds = {lib.works[w].get("source_kind") for w in by.values()}
        who = name_list([short_name(a) for a in lib.ordered_authors() if a["id"] in by])
        key = "about.thanks_scans" if kinds == {"scan"} else "about.thanks_texts"
        rows.append(f'<tr><td><a href="https://{e(host)}/" rel="noopener">{e(names.get(host, host))}</a></td><td>{e(t(key, works=who))}</td></tr>')
    for (name, what), url in ((t("about.thanks_owb"), OWB_SITE + "/"), (t("about.thanks_sefaria"), "https://www.sefaria.org/")):
        rows.append(f'<tr><td><a href="{e(url)}" rel="noopener">{e(name)}</a></td><td>{e(what)}</td></tr>')
    return (f'<p>{e(t("about.thanks"))}</p><div class="lg-table-wrap"><table class="lg-words lg-ab-thanks"><tbody>'
            f'{"".join(rows)}</tbody></table></div>')


def about_questions():
    return "".join(f'<details class="lg-ab-details"><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in t("about.questions"))


def about_page(lib):
    sections = (("what", "".join(f"<p>{e(p)}</p>" for p in t("about.what")) + about_example(lib) + about_name(lib)),
                ("voices", about_voices(lib)),
                ("library", about_library(lib)),
                ("checked", f'<p>{e(t("about.checked"))}</p>' + checking_figure(lib)),
                ("bible", "".join(f"<p>{e(p)}</p>" for p in t("about.bible"))),
                ("languages", "".join(f"<p>{e(p)}</p>" for p in t("about.languages"))),
                ("open", about_open()),
                ("cite", about_cite()),
                ("help", about_help()),
                ("thanks", about_thanks(lib)),
                ("questions", about_questions()))
    toc = "".join(f'<li><a href="#{k}">{e(t("about.h." + k))}</a></li>' for k, _ in sections)
    parts = "".join(f'<section class="lg-ab-sec" id="{k}"><h2>{e(t("about.h." + k))}</h2>{html_}</section>' for k, html_ in sections)
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("about.title"))}</p>
<h1>{e(t("about.heading"))}</h1><p class="dek">{e(t("about.dek"))}</p>{about_stats(lib)}</header>
<nav class="lg-ab-toc" aria-label="{e(t("about.toc"))}"><p class="label">{e(t("about.toc"))}</p><ul>{toc}</ul></nav>
<div class="prose lg-ab">{parts}</div>"""
    return page(lib, t("about.title"), body, "/about/", current="/about/")


# --- Collections (/<book>/<id>/): passages that belong together -------------
#
# A collection is a set of verses or passages readers look for together,
# such as the "I am" sayings, listed in library/collections.json. Its page
# shows each one's text and, for each commentator, the opening words of
# their first excerpt on it, linked to where it is printed in full.

def collections(lib):
    return load(os.path.join(ROOT, "library", "collections.json"))["collections"]


def collection_page(lib, col):
    key = f'collections.{col["id"]}'
    book = col["book"]
    name = lib.books[book]["en"]
    path = f'/{book.lower()}/{col["id"]}/'
    blocks, toc, total = [], [], 0
    for i, item in enumerate(col["items"], 1):
        _b, sc, sv = ref_parts(item["start"])
        _b, ec, ev = ref_parts(item["end"])
        voices = in_passage(lib, book, (sc, sv), (ec, ev))
        n = sum(len(cs) for _w, cs in voices)
        total += n
        single = (sc, sv) == (ec, ev)
        ref = verse_ref(lib, book, sc, sv) if single else passage_ref(lib, book, (sc, sv), (ec, ev))
        label = t(f'{key}.items.{item["key"]}')
        text = chapter_plain(book, sc).get(sv, "") if single else ""
        quote = f'<blockquote class="lg-vtext lg-ctext"><p>{e(text)}</p></blockquote>' if text else ""
        rows = []
        for wid, cs in voices:
            a = lib.author_of(wid)
            c = cs[0]
            more = f' <span class="lg-quiet">{e(t("collection.and_more", n=len(cs) - 1))}</span>' if len(cs) > 1 else ""
            rows.append(f'<li><p class="lg-ex-ref"><a href="{excerpt_href(lib, c)}"><b>{e(short_name(a))}</b></a>'
                        f' <span class="lg-quiet">{e(a["dates"])}</span>{more}</p><div><p>{e(snippet(c["text"], 30))}</p></div></li>')
        where = verse_url(book, sc, sv) if single else section_url(lib, book, (sc, sv))
        all_link = (f'<p class="lg-vx-links"><a href="{where}">{e(t("collection.read_all" if single else "collection.read_passage", n=n, k=len(voices), ref=ref))}</a></p>'
                    if voices else "")
        anchor_id = item["key"]
        blocks.append(f'<section class="lg-voice" id="{e(anchor_id)}"><h3><span class="lg-cnum">{i}</span> {e(label)}</h3>'
                      f'<p class="lg-vmeta">{e(ref)}</p>{quote}<ul class="lg-excerpts">{"".join(rows)}</ul>{all_link}</section>')
        toc.append(f'<a href="#{e(anchor_id)}">{e(label)}</a>')
    note = f'<p class="lg-quiet">{e(t(key + ".note"))}</p>' if t(key + ".note") else ""
    body = f"""
<article class="lg-verse lg-collection">
<header class="page-head"><p class="eyebrow"><a href="/{book.lower()}/">{e(name)}</a> · {e(t("collection.eyebrow"))}</p>
<h1>{e(t(key + ".heading"))}</h1><p class="dek">{e(t(key + ".dek"))}</p>
<nav class="lg-chbar" aria-label="{e(t("verse.contents"))}">{"".join(toc)}</nav></header>
<section class="lg-block" id="items">{"".join(blocks)}</section>
{note}
<p class="lg-quiet">{e(t("collection.how", n=total))}</p>
</article>
<script type="application/ld+json">{breadcrumbs_ld([("Logia", "/"), (name, f"/{book.lower()}/"), (t(key + ".heading"), path)])}</script>"""
    return path, page(lib, t(key + ".heading"), body, path, current="/read/",
                      head_title=t(key + ".title") + " · Logia", description=t(key + ".description"))


def section_url(lib, book, at):
    """The passage page of the section a verse is in, or the verse in the reader."""
    for _h, start, end in book_sections(book, lib.books[book]["chapters"]):
        if start <= at <= end:
            return passage_url(book, start, end)
    return f"{chapter_url(book, at[0])}#v{at[1]}"


def collection_links(lib, book):
    return " · ".join(f'<a href="/{book.lower()}/{c["id"]}/">{e(t("collections." + c["id"] + ".heading"))}</a>'
                      for c in collections(lib) if c["book"] == book)


# --- Reading plans (/<book>/lent/) ------------------------------------------
#
# A book read through in Lent's forty days (Sundays are not counted), a few
# of its passages a day, with the dates of a given year. The plan is a
# schedule and links: nothing in it is commentary.

def easter_day(year):
    """Western Easter (the anonymous Gregorian computus)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e_ = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    lq = (32 + 2 * e_ + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lq) // 451
    month, day = divmod(h + lq - 7 * m + 114, 31)
    return datetime.date(year, month, day + 1)


def lent_days(year):
    """The forty days of Lent, Ash Wednesday to Holy Saturday, without the Sundays."""
    ash = easter_day(year) - datetime.timedelta(days=46)
    days = [ash + datetime.timedelta(days=i) for i in range(46)]
    return [d for d in days if d.weekday() != 6]


def section_verses(book, start, end):
    return sum(1 for c in range(start[0], end[0] + 1) for v in chapter_verses(book, c) if start <= (c, v) <= end)


def plan_days(lib, book, n_days):
    """The book's passages shared out over n_days in order, about the same number of verses each day."""
    secs = book_sections(book, lib.books[book]["chapters"])
    sizes = [section_verses(book, s_, e_) for _h, s_, e_ in secs]
    total, days, run, done = sum(sizes), [], [], 0
    for i, (sec, size) in enumerate(zip(secs, sizes)):
        run.append(sec)
        done += size
        left = len(secs) - i - 1          # sections still to share out
        to_fill = n_days - len(days) - 1  # days after this one
        if to_fill and (done >= total * (len(days) + 1) / n_days or left == to_fill) and left >= to_fill:
            days.append(run)
            run = []
    return days + [run] if run else days


def lent_page(lib, book, year):
    name = lib.books[book]["en"]
    dates = lent_days(year)
    days = plan_days(lib, book, len(dates))
    rows = []
    for i, (date, secs) in enumerate(zip(dates, days), 1):
        links = " · ".join(f'<a href="{passage_url(book, s_, e_)}">{e(h)}</a> <span class="lg-quiet">{e(passage_ref(lib, book, s_, e_).replace(name + " ", ""))}</span>'
                           for h, s_, e_ in secs)
        special = ""
        if i == 1:
            special = f' <span class="lg-badge">{e(t("plan.ash_wednesday"))}</span>'
        elif date == easter_day(year) - datetime.timedelta(days=2):
            special = f' <span class="lg-badge">{e(t("plan.good_friday"))}</span>'
        rows.append(f'<li><p class="lg-plan-day"><b>{e(t("plan.day", n=i))}</b> <span class="lg-quiet">{e(t("plan.date", weekday=t("plan.weekdays")[date.weekday()], day=date.day, month=t("plan.months")[date.month - 1], year=date.year))}</span>{special}</p>'
                    f'<p>{links}</p></li>')
    easter = easter_day(year)
    body = f"""
<article class="lg-verse lg-plan">
<header class="page-head"><p class="eyebrow"><a href="/{book.lower()}/">{e(name)}</a> · <a href="/readings/">{e(t("occasions.eyebrow"))}</a></p>
<h1>{e(t("plan.heading", book=name, n=len(dates)))}</h1><p class="dek">{e(t("plan.dek", book=name, year=year, start=f"{dates[0].day} {t('plan.months')[dates[0].month - 1]}", easter=f"{easter.day} {t('plan.months')[easter.month - 1]}"))}</p></header>
<ol class="lg-plan-days">{"".join(rows)}</ol>
<p class="lg-quiet">{e(t("plan.note"))} <a href="/easter/">{e(t("plan.easter_link"))}</a></p>
</article>"""
    return page(lib, t("plan.heading", book=name, n=len(dates)), body, f"/{book.lower()}/lent/", current="/read/",
                head_title=t("plan.title", book=name, year=year) + " · Logia",
                description=t("plan.description", book=name, year=year),
                ld=(breadcrumbs((name, f"/{book.lower()}/"), (t("plan.heading", book=name, n=len(dates)), f"/{book.lower()}/lent/")),))


# --- The Scripture cited (/<book>/scripture-cited/) --------------------------
#
# Counts of the Scripture the excerpts cite, from library/citations/ (found
# by scripts/find_refs.py, each still to be reviewed). Counts only.

def citations_on(book):
    """[citation] in every work's excerpts on a book, leaving out those a person rejected."""
    out = []
    for path in sorted(glob.glob(os.path.join(ROOT, "library", "citations", "*", f"{book}.json"))):
        data = load(path)
        out.extend({**x, "work": data["work"]} for x in data["citations"] if x.get("status") != "rejected")
    return out


def chapter_list(lib, book):
    return range(1, lib.books[book]["chapters"] + 1)


def cited_page(lib, book, top=20):
    name = lib.books[book]["en"]
    cites = citations_on(book)
    codes = list(lib.books)
    by_book, by_verse, by_work = {}, {}, {}
    for x in cites:
        b = x["start"].split(".")[0]
        by_book[b] = by_book.get(b, 0) + 1
        by_verse[(x["start"], x["end"])] = by_verse.get((x["start"], x["end"]), 0) + 1
        by_work[x["work"]] = by_work.get(x["work"], 0) + 1
    own = by_book.get(book, 0)
    ot = sum(n for b, n in by_book.items() if b in lib.books and codes.index(b) < OT_BOOKS)
    others = sorted(((b, n) for b, n in by_book.items() if b != book), key=lambda kv: -kv[1])

    def bars(rows, href, label):
        peak = max(n for _k, n in rows)
        return "".join(f'<li><a href="{href(k)}"><span class="lg-bar-label">{e(label(k))}</span>'
                       f'<span class="lg-bar"><span style="width:{n / peak * 100:.1f}%"></span></span>'
                       f'<span class="lg-bar-n">{n}</span></a></li>' for k, n in rows)

    def verse_text(ref):
        b, ch, v = ref_parts(ref)
        return snippet(chapter_plain(b, ch).get(v, ""), 12) if b in lib.books and ch in chapter_list(lib, b) else ""

    def verse_rows(rows, text=True):
        # Only within the book is the text shown: elsewhere the printed numbering
        # can differ from the Open Word Bible's (Micah 5:2 in English is its 5:1).
        return "".join(f'<tr><td><a href="{e(verse_href(lib, a))}"><b>{e(scripture.label(a, z))}</b></a></td><td>{n}</td>'
                       + (f'<td class="lg-quiet">{e(verse_text(a))}</td>' if text else "") + "</tr>"
                       for (a, z), n in rows)
    outside = sorted(((k, n) for k, n in by_verse.items() if not k[0].startswith(book + ".")), key=lambda kv: (-kv[1], kv[0]))[:top]
    inside = sorted(((k, n) for k, n in by_verse.items() if k[0].startswith(book + ".")), key=lambda kv: (-kv[1], kv[0]))[:top]
    head = "".join(f"<th>{e(x)}</th>" for x in t("cited.columns"))
    head2 = "".join(f"<th>{e(x)}</th>" for x in t("cited.columns")[:2])
    works = sorted(by_work.items(), key=lambda kv: -kv[1])
    body = f"""
<article class="lg-verse lg-most">
<header class="page-head"><p class="eyebrow"><a href="/{book.lower()}/">{e(name)}</a></p>
<h1>{e(t("cited.heading", book=name))}</h1>
<p class="dek">{e(t("cited.dek", n=f"{len(cites):,}", book=name, own=f"{own:,}", ot=f"{ot:,}", others=len(others)))}</p></header>
<section class="lg-block" id="books"><h2>{e(t("cited.books_title", book=name))}</h2>
<ol class="lg-bars lg-bars-wide">{bars(others[:20], lambda b: f"/{b.lower()}/" if b in lib.books else "#outside", lambda b: scripture.BOOK_NAMES[b])}</ol></section>
<section class="lg-block" id="outside"><h2>{e(t("cited.outside_title", n=top, book=name))}</h2>
<div class="lg-table-wrap"><table class="lg-words lg-rank lg-narrow"><thead><tr>{head2}</tr></thead><tbody>{verse_rows(outside, text=False)}</tbody></table></div></section>
<section class="lg-block" id="inside"><h2>{e(t("cited.inside_title", n=top, book=name))}</h2>
<p class="lg-quiet">{e(t("cited.inside_note", book=name))}</p>
<div class="lg-table-wrap"><table class="lg-words lg-rank"><thead><tr>{head}</tr></thead><tbody>{verse_rows(inside)}</tbody></table></div></section>
<section class="lg-block" id="works"><h2>{e(t("cited.works_title"))}</h2>
<ol class="lg-bars lg-bars-wide">{bars(works, lambda w: f"/works/{w}/", lambda w: short_name(lib.author_of(w)))}</ol></section>
<section class="lg-block"><h2>{e(t("most.how_title"))}</h2><p>{e(t("cited.how"))}</p></section>
</article>"""
    return page(lib, t("cited.heading", book=name), body, f"/{book.lower()}/scripture-cited/", current="/read/",
                description=t("cited.description", book=name, n=f"{len(cites):,}"),
                ld=(breadcrumbs((name, f"/{book.lower()}/"), (t("cited.heading", book=name), f"/{book.lower()}/scripture-cited/")),))


# --- Who the Catena quotes (/works/catena/fathers/) --------------------------
#
# The Catena Aurea is a chain of quotations, each opened by the Father's
# name as the edition prints it ("CHRYS.", "AUG."). This counts those
# labels in Logia's excerpts. A label the scan misread is not counted.

CATENA_LABELS = {"AUG.": "augustine", "CHRYS.": "chrysostom", "THEOPHYL.": "theophylact", "ALCUIN.": "alcuin",
                 "ORIGEN.": "origen", "BEDE.": "bede", "GREG.": "greg", "HILARY.": "hilary", "BASIL.": "basil",
                 "HAYMO.": "haymo", "GLOSS.": "gloss", "JEROME.": "jerome"}
CATENA_LABEL = re.compile(r"(?:^|(?<=[.;:?!\"”)\]] )|(?<=\n))(" + "|".join(re.escape(k) for k in CATENA_LABELS) + r")(?= )")


# The Catena on Matthew (Oxford, 1841) opens each quotation on a new
# paragraph with the Father's name and where the passage is, then a colon:
# "Jerome, Ez, i. 5. Hier. Prolog. in Com. in Matt.: ...", "Rabanus: ...".
# The names, as that edition abbreviates them; one it misprints is left alone.
CATENA_NAMES = {
    "Jerome": "jerome", "Chrys.": "chrysostom", "Chrys": "chrysostom", "Aug.": "augustine", "Aug": "augustine",
    "Augustine": "augustine", "Aug. Serm.": "augustine", "Pseudo-Chrys.": "pseudo_chrysostom", "Remig.": "remigius",
    "Remig": "remigius", "Remigius": "remigius", "Hilary": "hilary", "Hil.": "hilary", "Origen": "origen",
    "Raban.": "rabanus", "Raban": "rabanus", "Rabanus": "rabanus", "Greg.": "greg", "Greg": "greg", "Gregory": "greg",
    "Gloss.": "gloss", "Gloss": "gloss", "Gloss. Ordinaria": "gloss", "Gloss. Anselm": "gloss", "Ambrose": "ambrose",
    "Leo": "leo", "Bede": "bede", "Pseudo-Aug.": "pseudo_augustine", "Cyprian": "cyprian",
    "Pseudo-Origen": "pseudo_origen", "Chrysol.": "chrysologus", "Chrysol": "chrysologus",
    "Chrysologus": "chrysologus", "Cassian": "cassian", "Haymo": "haymo", "Euseb.": "eusebius", "Cyril": "cyril",
    "Isidore": "isidore", "Isid.": "isidore", "Damascenus": "damascene", "Damas.": "damascene",
    "Damasc.": "damascene", "Theodotus": "theodotus", "Gregory Nyss.": "gregory_nyssa", "Anselm": "anselm",
    "Josephus": "josephus", "Maximus": "maximus", "Gennadius": "gennadius", "Ambrosiaster": "ambrosiaster",
    "Nemesius": "nemesius", "Dionysius": "dionysius", "Dionys.": "dionysius"}
CATENA_HEAD = re.compile(r"(?:^|(?<=\n\n))([A-Z][A-Za-z\-]+\.?(?: [A-Z][A-Za-z]+\.?)?)(,[^:\n]{0,90})?:(?= )")


def catena_speakers(work, text):
    """Where each Father's name opens a quotation in a Catena excerpt, so the
    reader can set it apart and name who is quoted: [{at, len, who}]."""
    if not work.startswith("catena"):
        return []
    out = [{"at": m.start(1), "len": len(m.group(1)), "who": CATENA_LABELS[m.group(1)]} for m in CATENA_LABEL.finditer(text)]
    out += [{"at": m.start(1), "len": m.end() - m.start(1), "who": CATENA_NAMES[m.group(1)]}
            for m in CATENA_HEAD.finditer(text) if m.group(1) in CATENA_NAMES]
    return sorted(out, key=lambda x: x["at"])


def catena_labels(lib, work="catena"):
    """{label: [excerpt]} for each Father's label in the Catena's excerpts, in the work's order."""
    out = {}
    for c in sorted((c for c in lib.comments if c["work"] == work), key=order_key):
        for m in CATENA_LABEL.finditer(c["text"]):
            out.setdefault(m.group(1), []).append(c)
    return out


def catena_fathers_page(lib, work="catena"):
    w = lib.works[work]
    labels = catena_labels(lib, work)
    rows = sorted(labels.items(), key=lambda kv: -len(kv[1]))
    total = sum(len(cs) for _k, cs in rows)
    peak = len(rows[0][1])
    traced = {}
    for path in glob.glob(os.path.join(ROOT, "library", "quotations", work, "*.json")):
        for q in load(path)["quotations"]:
            if q.get("status") != "rejected":
                traced[q["work"]] = traced.get(q["work"], 0) + 1
    items = []
    for label, cs in rows:
        who = CATENA_LABELS[label]
        name = t(f"catena.names.{who}")
        held = ""
        if who in lib.authors:
            wid = next(x for x in lib.ordered_works() if lib.works[x]["author"] == who)
            held = (f'<p class="lg-quiet">{e(t("catena.held", name=name, n=traced.get(wid, 0)))} '
                    f'<a href="/commentators/{who}/">{e(t("catena.held_link", name=name))}</a></p>')
        seen, examples = set(), []
        for c in cs:
            if c["id"] in seen:
                continue
            seen.add(c["id"])
            examples.append(f'<a href="{excerpt_href(lib, c)}">{e(scripture.label(c["start"], c["end"]))}</a>')
            if len(examples) == 4:
                break
        items.append(f'<li><div class="lg-bars-row"><span class="lg-bar-label"><b>{e(name)}</b> <code>{e(label)}</code></span>'
                     f'<span class="lg-bar"><span style="width:{len(cs) / peak * 100:.1f}%"></span></span>'
                     f'<span class="lg-bar-n">{len(cs)}</span></div>'
                     f'<p class="lg-quiet lg-catena-ex">{e(t("catena.for_example"))} {" · ".join(examples)}</p>{held}</li>')
    path = f"/works/{work}/fathers/"
    body = f"""
<article class="lg-verse lg-most lg-catena">
<header class="page-head"><p class="eyebrow"><a href="/works/{work}/"><i>{e(t("catena.short_title"))}</i></a></p>
<h1>{e(t("catena.heading"))}</h1><p class="dek">{e(t("catena.dek", n=f"{total:,}", k=len(rows)))}</p></header>
<section class="lg-block"><ol class="lg-bars lg-bars-catena">{"".join(items)}</ol></section>
<section class="lg-block"><h2>{e(t("most.how_title"))}</h2><p>{e(t("catena.how", edition=short_edition(w["edition"])))}</p></section>
</article>"""
    return path, page(lib, t("catena.heading"), body, path, current="/commentators/",
                      description=t("catena.description", n=f"{total:,}"),
                      ld=(breadcrumbs((t("catena.short_title"), f"/works/{work}/"), (t("catena.heading"), path)),))


# --- The eras (/commentators/era/<era>/) -------------------------------------
#
# Each era's commentators on a book side by side: who they are, the chapters
# and verses they say most on, and the opening words of what each says on a
# few well-known verses, linking to the whole excerpt. Counts and copied
# words only.

ERA_SLUGS = {"Early church": "early-church", "Middle Ages": "middle-ages", "Reformation": "reformation",
             "Puritans and the 1700s": "1700s", "The 1800s": "1800s"}
# Well-known verses each era page shows every commentator of the era on.
ERA_VERSES = ("JHN.1.1", "JHN.1.14", "JHN.3.16", "JHN.6.53", "JHN.10.30", "JHN.14.6", "JHN.20.28")


def era_url(era):
    return f"/commentators/era/{ERA_SLUGS[era]}/"


def era_links(lib, here=None):
    """The eras with commentators, as links (the one shown is plain)."""
    return " · ".join(
        (f'<b>{e(t("eras." + era))}</b>' if era == here else f'<a href="{era_url(era)}">{e(t("eras." + era))}</a>')
        for era in ERAS if any(a["era"] == era for a in lib.authors.values()))


def first_on(lib, works, ref):
    """The excerpt, in any of the works, that comments most closely on ref:
    of those whose verses include it, the one that begins nearest it (the
    first in order where several begin there)."""
    b, ch, v = ref_parts(ref)
    best = None
    for c in sorted(lib.comments_in(b, ch), key=order_key):
        _, sc, sv = ref_parts(c["start"])
        _, ec, ev = ref_parts(c["end"])
        if c["work"] in works and sc == ch and sv <= v and (ec != ch or v <= ev):
            if best is None or sv > ref_parts(best["start"])[2]:
                best = c
    return best


def era_page(lib, era, book="JHN"):
    name = lib.books[book]["en"]
    people = [a for a in lib.ordered_authors() if a["era"] == era]
    works = {w for w, x in lib.works.items() if x["author"] in {a["id"] for a in people}}
    mine = [c for c in lib.comments if c["work"] in works and c["start"].startswith(book + ".")]
    lo, hi = next((a, b) for x, a, b in ERA_SPANS if x == era)
    cards = "".join(
        f'<li><a class="lg-person lg-era-{ERAS.index(era)}" href="/commentators/{a["id"]}/"><span><b>{e(a["name"])}</b>'
        f'<span class="lg-dates">{e(a["dates"])} · {e(a["tradition"])}</span>'
        + "".join(f'<span class="lg-meta"><i>{e(lib.works[w]["title"])}</i> · {e(t("work.excerpts", n=sum(1 for c in mine if c["work"] == w)))}</span>'
                  for w in lib.ordered_works([w for w in works if lib.works[w]["author"] == a["id"]]))
        + "</span></a></li>" for a in people)
    # The chapters they say most on, by excerpts.
    by_ch = {}
    for c in mine:
        ch = ref_parts(c["start"])[1]
        by_ch[ch] = by_ch.get(ch, 0) + 1
    peak = max(by_ch.values(), default=1)
    chapters = "".join(
        f'<li><a href="{chapter_url(book, ch)}"><span class="lg-bar-label">{e(name)} {ch}</span>'
        f'<span class="lg-bar"><span style="width:{n / peak * 100:.1f}%"></span></span><span class="lg-bar-n">{n}</span></a></li>'
        for ch, n in sorted(by_ch.items()))
    # The verses they say most on: excerpts whose verses include each one.
    counts = {}
    for c in mine:
        _, sc, sv = ref_parts(c["start"])
        _, ec, ev = ref_parts(c["end"])
        if sc == ec:
            for v in range(sv, ev + 1):
                counts[(sc, v)] = counts.get((sc, v), 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    verses = "".join(
        f'<tr><td><a href="{verse_url(book, ch, v)}"><b>{e(verse_ref(lib, book, ch, v))}</b></a></td><td>{n}</td>'
        f'<td class="lg-quiet">{e(snippet(chapter_plain(book, ch).get(v, ""), 12) or t("most.left_out"))}</td></tr>'
        for (ch, v), n in top)
    head = "".join(f"<th>{e(x)}</th>" for x in t("era.columns"))
    # What each of them says on a few well-known verses: the opening words.
    samples = ""
    for ref in ERA_VERSES:
        b, ch, v = ref_parts(ref)
        if b != book:
            continue
        items = ""
        for a in people:
            c = first_on(lib, {w for w in works if lib.works[w]["author"] == a["id"]}, ref)
            if c:
                items += (f'<li><b>{e(short_name(a))}</b> “{e(opening_words(c))}” '
                          f'<a href="{excerpt_href(lib, c)}">{e(t("era.read_on"))}</a></li>')
        if items:
            samples += (f'<section class="lg-era-verse"><h3><a href="{verse_url(book, ch, v)}">{e(verse_ref(lib, book, ch, v))}</a></h3>'
                        f'<p class="lg-quiet">{e(snippet(chapter_plain(book, ch).get(v, ""), 40))}</p><ul class="lg-era-says">{items}</ul></section>')
    title = t("era.heading", book=name, era=t("era.in." + era))
    body = f"""
<article class="lg-verse lg-era-page">
<header class="page-head"><p class="eyebrow"><a href="/commentators/">{e(t("commentators.title"))}</a> · {e(t("era.eyebrow"))}</p>
<h1>{e(title)}</h1><p class="dek">{e(t("era.dek", n=f"{len(mine):,}", names=" and ".join(a["name"] for a in people), book=name, a=lo, b=hi))}</p>
<p class="lg-quiet">{era_links(lib, era)}</p></header>
<section class="lg-block"><h2>{e(t("era.people"))}</h2><ul class="lg-grid lg-people-grid">{cards}</ul></section>
<section class="lg-block"><h2>{e(t("era.on_verses"))}</h2><p class="lg-quiet">{e(t("era.on_verses_note"))}</p>{samples}</section>
<section class="lg-block"><h2>{e(t("era.verses_title", n=len(top)))}</h2>
<div class="lg-table-wrap"><table class="lg-words lg-rank"><thead><tr>{head}</tr></thead><tbody>{verses}</tbody></table></div></section>
<section class="lg-block"><h2>{e(t("era.chapters_title"))}</h2><ol class="lg-bars">{chapters}</ol></section>
</article>"""
    return page(lib, title, body, era_url(era), current="/commentators/",
                head_title=t("era.head_title", book=name, era=t("era.in." + era)) + " · Logia",
                description=t("era.description", book=name, era=t("era.in." + era), names=", ".join(a["name"] for a in people)),
                ld=(breadcrumbs((t("commentators.title"), "/commentators/"), (title, era_url(era))),))


# --- Guides (library/guides/en/<id>.json) -----------------------------------
#
# Logia's own writing about the commentaries: short notes that frame a
# passage, never commentary. Each guide is a draft (status "ai_draft") until
# a named person reviews it, and its page says so. Where a guide points to a
# passage, the commentators then speak for themselves: the opening words of
# what each says on it, linked to the whole excerpt.

def guides():
    return [load(p) for p in sorted(glob.glob(os.path.join(ROOT, "library", "guides", "en", "*.json")))]


def opening_words(c, words=40):
    """An excerpt's first words, past a first paragraph that only quotes the verse."""
    paras = [x for x in c["text"].split("\n\n") if x.strip()]
    while len(paras) > 1 and len(paras[0].split()) < 30:
        paras.pop(0)
    return snippet(paras[0], words)


def voices_list(lib, ref, works=None):
    """Each work's excerpt nearest ref, as a list of opening words and links."""
    b, ch, v = ref_parts(ref)
    items = ""
    for w in lib.voices_on.get((b, ch, v), []):
        if works is not None and w not in works:
            continue
        c = first_on(lib, {w}, ref)
        if c:
            a = lib.author_of(w)
            items += (f'<li><b>{e(short_name(a))}</b> <span class="lg-quiet">{e(a["tradition"])}</span> '
                      f'“{e(opening_words(c))}” <a href="{excerpt_href(lib, c)}">{e(t("era.read_on"))}</a></li>')
    return f'<ul class="lg-era-says">{items}</ul>' if items else ""


def guide_links(book):
    """ · and a link to each guide on the book, for its book page."""
    return "".join(f' · <a href="{g["path"]}">{e(g["title"])}</a>' for g in guides() if g.get("book") == book)


def draft_note(g):
    return (f'<p class="lg-guide-draft"><span class="lg-pill lg-pill-draft">{e(t("guide.draft"))}</span> '
            f'{e(t("guide.draft_note"))}</p>' if g["status"] == "ai_draft" else "")


def prose(paras):
    return "".join("<p>" + re.sub(r"\*([^*]+)\*", r"<i>\1</i>", e(p)) + "</p>" for p in paras)


def guide_page(lib, g):
    book = g.get("book", "JHN")
    name = lib.books[book]["en"]
    parts = []
    for i, x in enumerate(g.get("topics", []), 1):
        _b, sc, sv = ref_parts(x["start"])
        _b, ec, ev = ref_parts(x["end"])
        _b, fc, fv = ref_parts(x["focus"])
        where = section_url(lib, book, (sc, sv))
        parts.append(
            f'<section class="lg-block lg-guide-topic" id="t{i}"><h2>{e(x["title"])}</h2>'
            f'<p class="lg-ex-ref"><a href="{where}">{e(scripture.label(x["start"], x["end"]))}</a></p>'
            f'<blockquote class="lg-guide-verse"><p>{e(" ".join(chapter_plain(book, c_).get(v_, "") for c_ in range(sc, ec + 1) for v_ in chapter_verses(book, c_) if (sc, sv) <= (c_, v_) <= (ec, ev)))}</p></blockquote>'
            f'<div class="prose">{prose(x["note"])}</div>'
            f'<h3 class="label">{e(t("guide.voices", ref=verse_ref(lib, book, fc, fv)))}</h3>{voices_list(lib, x["focus"])}</section>')
    # A glossary's terms: what each means, how many excerpts on the book use
    # it, and the first of them.
    mine = sorted((c for c in lib.comments if c["start"].startswith(book + ".")), key=order_key)
    for i, grp in enumerate(g.get("groups", []), 1):
        rows = ""
        for x in grp["terms"]:
            pat = re.compile(x["match"])
            hits = [c for c in mine if pat.search(c["text"])]
            links = []
            if x.get("see"):
                _b, ch, v = ref_parts(x["see"])
                links.append(f'<a href="{verse_url(book, ch, v)}">{e(verse_ref(lib, book, ch, v))}</a>')
            if x.get("link"):
                links.append(f'<a href="{x["link"]}">{e(x["link_label"])}</a>')
            if hits:
                first = hits[0]
                links.append(f'<a href="{excerpt_href(lib, first)}">{e(t("guide.used", n=f"{len(hits):,}", who=short_name(lib.author_of(first["work"])), ref=scripture.label(first["start"], first["end"])))}</a>')
            rows += (f'<div><dt>{e(x["term"])}</dt><dd><p>{e(x["text"])}</p>'
                     f'<p class="lg-quiet lg-gloss-links">{" · ".join(links)}</p></dd></div>')
        parts.append(f'<section class="lg-block" id="t{i}"><h2>{e(grp["title"])}</h2><dl class="lg-gloss">{rows}</dl></section>')
    # A guide's steps: its own words, then links to the pages they mean.
    for i, x in enumerate(g.get("sections", []), 1):
        links = " · ".join(f'<a href="{href}">{e(label)}</a>' for label, href in x.get("links", []))
        parts.append(f'<section class="lg-block" id="t{i}"><h2>{e(x["title"])}</h2><div class="prose">{prose(x["text"])}</div>'
                     + (f'<p class="lg-gloss-links">{links}</p>' if links else "") + "</section>")
    toc = "".join(f'<li><a href="#t{i}">{e(x["title"])}</a></li>'
                  for i, x in enumerate(g.get("topics", []) or g.get("groups", []) or g.get("sections", []), 1))
    body = f"""
<article class="lg-verse lg-guide">
<header class="page-head"><p class="eyebrow"><a href="/{book.lower()}/">{e(name)}</a> · {e(t("guide.eyebrow"))}</p>
<h1>{e(g["title"])}</h1><p class="dek">{e(g["dek"])}</p>{draft_note(g)}</header>
<div class="prose">{prose(g.get("intro", []))}</div>
{f'<nav class="lg-block"><ol class="lg-guide-toc">{toc}</ol></nav>' if toc else ""}
{"".join(parts)}
</article>"""
    return page(lib, g["title"], body, g["path"], current="/read/", head_title=g["head_title"] + " · Logia",
                description=g["description"], ld=(breadcrumbs((name, f"/{book.lower()}/"), (g["title"], g["path"])),))


# --- The most-discussed verses (/<book>/most-discussed/) ----------------------
#
# Counts only: how many excerpts in the library are on each verse and
# chapter. Nothing on the page is commentary or opinion.

def verse_counts(lib, book):
    """{(chapter, verse): excerpts on it}, an excerpt on a range counting on each of its verses."""
    n = {}
    for c in lib.comments:
        b, sc, sv = ref_parts(c["start"])
        _, ec, ev = ref_parts(c["end"])
        if b != book or sc != ec:
            continue
        for v in range(sv, ev + 1):
            n[(sc, v)] = n.get((sc, v), 0) + 1
    return n


def most_discussed_page(lib, book, top=25):
    name = lib.books[book]["en"]
    counts = verse_counts(lib, book)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
    all_works = len({c["work"] for c in lib.comments if c["start"].startswith(book + ".")})
    every = sum(1 for (b, _c, _v), ws in lib.voices_on.items() if b == book and len(ws) == all_works)
    verses_with = sum(1 for (b, _c, _v) in lib.voices_on if b == book)
    rows = []
    for i, ((ch, v), n) in enumerate(ranked, 1):
        ws = lib.voices_on.get((book, ch, v), [])
        rows.append(f'<tr><td class="lg-quiet">{i}</td><td><a href="{verse_url(book, ch, v)}"><b>{e(verse_ref(lib, book, ch, v))}</b></a></td>'
                    f'<td>{n}</td><td>{len(ws)}</td><td class="lg-quiet">{e(snippet(chapter_plain(book, ch).get(v, ""), 12) or t("most.left_out"))}</td></tr>')
    head = "".join(f"<th>{e(x)}</th>" for x in t("most.columns"))
    per_chapter = {}
    for (ch, _v), n in counts.items():
        per_chapter[ch] = per_chapter.get(ch, 0) + n
    starts = {}
    for c in lib.comments:
        b, sc, _sv = ref_parts(c["start"])
        if b == book:
            starts[sc] = starts.get(sc, 0) + 1
    peak = max(starts.values())
    bars = "".join(f'<li><a href="{chapter_url(book, ch)}"><span class="lg-bar-label">{e(t("chapter.eyebrow", chapter=ch))}</span>'
                   f'<span class="lg-bar"><span style="width:{starts[ch] / peak * 100:.1f}%"></span></span>'
                   f'<span class="lg-bar-n">{starts[ch]}</span></a></li>' for ch in sorted(starts))
    top_ch = max(starts, key=starts.get)
    lead = t("most.lead", book=name, verses=verses_with, every=every, works=all_works, n=f"{sum(starts.values()):,}")
    body = f"""
<article class="lg-verse lg-most">
<header class="page-head"><p class="eyebrow"><a href="/{book.lower()}/">{e(name)}</a></p>
<h1>{e(t("most.heading", book=name))}</h1><p class="dek">{e(lead)}</p></header>
<section class="lg-block" id="verses"><h2>{e(t("most.verses_title", n=top))}</h2>
<div class="lg-table-wrap"><table class="lg-words lg-rank"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>
<section class="lg-block" id="chapters"><h2>{e(t("most.chapters_title"))}</h2>
<p class="lg-quiet">{e(t("most.chapters_note", chapter=top_ch, n=starts[top_ch]))}</p><ol class="lg-bars">{bars}</ol></section>
<section class="lg-block"><h2>{e(t("most.how_title"))}</h2><p>{e(t("most.how", works=all_works))}</p>
<p><a class="lg-more" href="/open-data/">{e(t("open_data.about_link"))} {icon("arrow", 15)}</a></p></section>
</article>
<script type="application/ld+json">{breadcrumbs_ld([("Logia", "/"), (name, f"/{book.lower()}/"), (t("most.heading", book=name), f"/{book.lower()}/most-discussed/")])}</script>"""
    first = ranked[0]
    return page(lib, t("most.heading", book=name), body, f"/{book.lower()}/most-discussed/", current="/read/",
                description=t("most.description", book=name, ref=verse_ref(lib, book, *first[0]), n=first[1]))


# --- Open data (/open-data/ and /downloads/) ---------------------------------
#
# Every excerpt as one file, with its scan corrections applied, so someone
# can build on the library without cloning the repository. The repository
# stays the record: these are written from it at every build.

DOWNLOAD_FIELDS = ("id", "work", "author", "start", "end", "heading", "text", "locus", "source_url")


def download_rows(lib):
    for c in sorted(lib.comments, key=lambda c: (lib.ordered_works().index(c["work"]), order_key(c))):
        yield {**{k: c.get(k) or "" for k in DOWNLOAD_FIELDS}, "author": lib.works[c["work"]]["author"]}


def downloads(lib):
    """{file name: text} for /downloads/: the excerpts as JSON and CSV."""
    rows = list(download_rows(lib))
    works = {w: {k: lib.works[w][k] for k in ("title", "author", "edition", "translation", "published",
                                              "full_text_url", "rights", "status")}
             for w in lib.ordered_works()}
    authors = {a["id"]: {k: a[k] for k in ("name", "dates", "died", "era", "tradition")} for a in lib.ordered_authors()}
    data = {"about": t("open_data.file_about"), "licence": "CC0-1.0", "source": GITHUB_URL,
            "authors": authors, "works": works, "excerpts": rows}
    buf = io.StringIO()
    out = csv.DictWriter(buf, fieldnames=DOWNLOAD_FIELDS, lineterminator="\n")
    out.writeheader()
    out.writerows(rows)
    return {"logia-en.json": json.dumps(data, ensure_ascii=False, indent=0) + "\n", "logia-en.csv": buf.getvalue()}


def size_label(n):
    return f"{n / 1_000_000:.1f} MB" if n >= 1_000_000 else f"{n // 1000} KB"


def open_data_page(lib, files):
    n = len(lib.comments)
    cov = lib.coverage()
    books = [lib.books[c]["en"] for c in lib.books if any(b == c for b, _c in cov)]
    dl = "".join(
        f'<li><a href="/downloads/{name}" download><b>{e(name)}</b> '
        f'<span>{e(t("open_data.file_" + name.rsplit(".", 1)[1]))} · {size_label(len(text.encode("utf-8")))}</span></a></li>'
        for name, text in files.items())
    fields = "".join(f"<tr><td><code>{e(k)}</code></td><td>{e(v)}</td></tr>" for k, v in t("open_data.fields"))
    repo = "".join(f'<tr><td><a href="{GITHUB_URL}/tree/main/{e(path)}" rel="noopener"><code>{e(path)}</code></a></td><td>{e(what)}</td></tr>'
                   for path, what in t("open_data.repo"))
    licences = "".join(f"<li>{e(x)}</li>" for x in t("open_data.licences"))
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": t("open_data.ld_name"),
          "description": t("open_data.ld_description", n=n, works=len(lib.works), books=name_list(books)),
          "url": SITE_URL + "/open-data/", "license": "https://creativecommons.org/publicdomain/zero/1.0/",
          "isAccessibleForFree": True, "inLanguage": LANG, "sameAs": GITHUB_URL,
          "creator": {"@type": "Organization", "name": "Logia", "url": SITE_URL},
          "keywords": t("open_data.ld_keywords") + books,
          "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json" if name.endswith(".json") else "text/csv",
                            "contentUrl": f"{SITE_URL}/downloads/{name}"} for name in files]}
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("about.title"))}</p>
<h1>{e(t("open_data.heading"))}</h1><p class="dek">{e(t("open_data.dek", n=f"{n:,}", works=len(lib.works), authors=len(lib.authors)))}</p></header>
<section class="lg-block"><h2>{e(t("open_data.download"))}</h2><p class="lg-quiet">{e(t("open_data.download_note"))}</p>
<ul class="lg-people lg-wide">{dl}</ul></section>
<section class="lg-block"><h2>{e(t("open_data.fields_title"))}</h2><div class="lg-table-wrap"><table class="lg-words lg-fields"><tbody>{fields}</tbody></table></div></section>
<section class="lg-block"><h2>{e(t("open_data.repo_title"))}</h2><p class="lg-quiet">{e(t("open_data.repo_note"))}</p>
<div class="lg-table-wrap"><table class="lg-words lg-fields"><tbody>{repo}</tbody></table></div></section>
<section class="lg-block"><h2>{e(t("open_data.licences_title"))}</h2><ul class="lg-licences">{licences}</ul>
<p class="lg-quiet">{e(t("open_data.rights_note"))}</p></section>"""
    return page(lib, t("open_data.heading"), body, "/open-data/", current="/about/",
                description=t("open_data.description", n=f"{n:,}", books=name_list(books)), ld=(ld,))


# --- Build --------------------------------------------------------------------

# --- For search engines and answer engines ------------------------------------

def indexed(lib, path):
    """Whether a page is for search engines: every page but a book or a
    chapter with no commentary, which is only the Open Word Bible's text."""
    m = re.fullmatch(r"/([0-9a-z]{3})/(?:(\d+)/)?", path)
    if not m or m[1].upper() not in lib.books:
        return True
    cov = lib.coverage()
    book = m[1].upper()
    return (book, int(m[2])) in cov if m[2] else any(b == book for b, _c in cov)


# The crawlers of the answer engines, named so that robots.txt says plainly
# they are welcome: Logia's data is CC0 and its texts are in the public domain.
AI_CRAWLERS = ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User",
               "PerplexityBot", "Google-Extended", "Applebot-Extended", "CCBot")


def robots_txt():
    # One group: a crawler named in a group of its own would follow only that group.
    named = "".join(f"User-agent: {name}\n" for name in ("*",) + AI_CRAWLERS)
    return f"{named}Allow: /\nDisallow: /signed-in/\nDisallow: /saved/\n\nSitemap: {SITE_URL}/sitemap.xml\n"


def git_dates():
    """{path in the repository: the date of the last commit that changed it},
    or {} where the history is not all here (a shallow clone), since a date
    taken from a partial history would be wrong."""
    import subprocess
    try:
        shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT,
                                 capture_output=True, text=True, check=True).stdout.strip()
        if shallow != "false":
            return {}
        log = subprocess.run(["git", "log", "--format=%x00%cs", "--name-only", "--", "library", "bible"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return {}
    dates, when = {}, None
    for line in log.splitlines():
        if line.startswith("\0"):
            when = line[1:]
        elif line and when:
            dates.setdefault(line, when)
    return dates


def last_changed(lib, path, dates):
    """When the text of a Bible page last changed: its chapter of the Bible
    or the commentary on its book (None for other pages)."""
    m = re.fullmatch(r"/([0-9a-z]{3})/(\d+)/(?:\d+/)?", path)
    if not dates or not m or m[1].upper() not in lib.books:
        return None
    book = m[1].upper()
    files = [f"bible/owb/en/{book}.{m[2]}.json"] + [f"library/comments/{w}/{book}.json" for w in lib.works]
    return max((dates[f] for f in files if f in dates), default=None)


def sitemap_xml(lib, pages):
    dates = git_dates()
    rows = []
    for p in pages:
        if not indexed(lib, p):
            continue
        when = last_changed(lib, p, dates)
        rows.append(f"<url><loc>{SITE_URL}{p}</loc>{f'<lastmod>{when}</lastmod>' if when else ''}</url>\n")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(rows) + "</urlset>\n")


def llms_txt(lib):
    """/llms.txt: what Logia is and how its pages are addressed, for answer
    engines (llmstxt.org). Every line comes from the catalog or the library."""
    cov = lib.coverage()
    books = [b for b in lib.books if any(x == b for x, _c in cov)]
    L = CATALOG["llms"]
    lines = ["# Logia", "", f"> {t('site.description')}", "",
             t("llms.holds", excerpts=f"{len(lib.comments):,}", works=len(lib.works), authors=len(lib.authors),
               books=name_list([lib.books[b]["en"] for b in books])), "", L["rules"], "",
             f"## {L['addresses']}", ""]
    lines += [f"- {SITE_URL}{path}: {text}" for path, text in L["address_list"]]
    lines += ["", f"## {L['books']}", ""]
    for b in books:
        n = sum(1 for x, _c in cov if x == b)
        lines.append(f"- [{lib.books[b]['en']}]({SITE_URL}/{b.lower()}/): "
                     + t("llms.book", n=n, chapters=lib.books[b]["chapters"]))
    lines += ["", f"## {L['commentators']}", ""]
    for a in lib.ordered_authors():
        lines.append(f"- [{a['name']}]({SITE_URL}/commentators/{a['id']}/) ({a['dates']}), {a['tradition']}")
    lines += ["", f"## {L['guides']}", ""]
    lines += [f"- [{g['title']}]({SITE_URL}{g['path']}): {g['description']}" for g in guides()]
    lines += ["", f"## {L['more']}", ""]
    lines += [f"- [{text}]({SITE_URL}{path})" for path, text in L["more_list"]]
    lines += ["", f"## {L['cite']}", "", L["cite_how"], ""]
    return "\n".join(lines)


def write(rel, text):
    path = os.path.join(SITE, rel.strip("/"), "index.html") if not rel.endswith((".svg", ".xml", ".txt", ".html")) \
        else os.path.join(SITE, rel.strip("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build():
    lib = Library()
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(SITE)
    for name in ("style.css", "logia.css", "site.js", "account.js", "logia.js", "reader.js"):
        with open(os.path.join(SITE, name), "w", encoding="utf-8") as f:
            f.write(published(name))
    shutil.copytree(os.path.join(WEB, "fonts"), os.path.join(SITE, "fonts"))
    write("/favicon.svg", FAVICON)
    shutil.copy(os.path.join(WEB, "card.png"), os.path.join(SITE, "card.png"))
    pages = ["/"]
    write("/", home_page(lib))
    write("/read/", read_page(lib))
    pages.append("/read/")
    for book in dict.fromkeys(b for b, _c in lib.chapters):
        write(f"/{book.lower()}/", book_page(lib, book))
        pages.append(f"/{book.lower()}/")
    for book, chapter in lib.chapters:
        html_text, panel, comm = chapter_page(lib, book, chapter, lib.chapters)
        write(chapter_url(book, chapter), html_text)
        for folder, text in (("panel", panel), ("comm", comm)):
            if text is None:
                continue
            os.makedirs(os.path.join(SITE, folder), exist_ok=True)
            with open(os.path.join(SITE, folder, f"{book}.{chapter}.json"), "w", encoding="utf-8") as f:
                f.write(text)
        pages.append(chapter_url(book, chapter))
        here = lib.verse_pages(book, chapter)
        if here:
            bible = lib.bible(book, chapter)
            cited_by = lib.cited_by(book, chapter, bible["verses"])
            for verse in here:
                write(verse_url(book, chapter, verse), verse_page(lib, book, chapter, verse, bible, here, cited_by))
                pages.append(verse_url(book, chapter, verse))
    for book in dict.fromkeys(b for b, _c in lib.chapters):
        for heading, start, end, voices in passages_with_commentary(lib, book):
            write(passage_url(book, start, end), passage_page(lib, book, heading, start, end, voices))
            pages.append(passage_url(book, start, end))
    for col in collections(lib):
        path, text = collection_page(lib, col)
        write(path, text)
        pages.append(path)
    for book in dict.fromkeys(b for b, _c, _v in lib.voices_on):
        write(f"/{book.lower()}/lent/", lent_page(lib, book, LENT_YEAR))
        pages.append(f"/{book.lower()}/lent/")
        write(f"/{book.lower()}/scripture-cited/", cited_page(lib, book))
        pages.append(f"/{book.lower()}/scripture-cited/")
        write(f"/{book.lower()}/most-discussed/", most_discussed_page(lib, book))
        pages.append(f"/{book.lower()}/most-discussed/")
    for g in guides():
        write(g["path"], guide_page(lib, g))
        pages.append(g["path"])
    for era in ERAS:
        if any(a["era"] == era for a in lib.authors.values()):
            write(era_url(era), era_page(lib, era))
            pages.append(era_url(era))
    for oid, book, start, end, voices in occasions(lib):
        path = t(f"occasions.{oid}.path")
        write(path, passage_page(lib, book, "", start, end, voices, occasion=f"occasions.{oid}"))
        pages.append(path)
    write("/readings/", readings_page(lib))
    pages.append("/readings/")
    write("/commentators/", commentators_page(lib))
    pages.append("/commentators/")
    for author in lib.ordered_authors():
        write(f'/commentators/{author["id"]}/', author_page(lib, author))
        pages.append(f'/commentators/{author["id"]}/')
    for wid in lib.ordered_works():
        write(f"/works/{wid}/", work_page(lib, wid))
        pages.append(f"/works/{wid}/")
        comments = sorted((c for c in lib.comments if c["work"] == wid), key=order_key)
        for book, chapter in work_chapters(comments):
            write(work_chapter_url(wid, book, chapter), work_chapter_page(lib, wid, book, chapter, comments))
            pages.append(work_chapter_url(wid, book, chapter))
        for x in lib.texts.get(wid, []):
            write(f"/works/{wid}/{x['locus']}/", text_page(lib, wid, x))
            pages.append(f"/works/{wid}/{x['locus']}/")
    if "catena" in lib.works:
        path, text = catena_fathers_page(lib)
        write(path, text)
        pages.append(path)
    write("/about/", about_page(lib))
    pages.append("/about/")
    files = downloads(lib)
    os.makedirs(os.path.join(SITE, "downloads"))
    for name, text in files.items():
        with open(os.path.join(SITE, "downloads", name), "w", encoding="utf-8") as f:
            f.write(text)
    write("/open-data/", open_data_page(lib, files))
    pages.append("/open-data/")
    write("/signed-in/", signed_in_page(lib))
    write("/saved/", saved_page(lib))
    write("/404.html", not_found_page(lib))
    os.makedirs(os.path.join(SITE, "data"))
    for book, chapter in sorted(lib.coverage()):
        with open(os.path.join(SITE, "data", f"{book}.{chapter}.json"), "w", encoding="utf-8") as f:
            json.dump(chapter_file(lib, book, chapter), f, ensure_ascii=False, separators=(",", ":"))
    write("/sitemap.xml", sitemap_xml(lib, pages))
    write("/robots.txt", robots_txt())
    write("/llms.txt", llms_txt(lib))
    print(f"site/: {len(pages)} pages ({len(lib.chapters)} chapters), {len(lib.works)} works, "
          f"{len(lib.authors)} commentators, {len(lib.comments)} excerpts")


if __name__ == "__main__":
    build()
