"""Build the Logia site into site/.

    python3 scripts/build_site.py

Reads the library (library/authors, works, versions, comments, corrections,
citations, quotations, texts), the Bible
text (bible/owb), the interface text (i18n/en.json) and web/, and writes a
static site:

    /                        home
    /read/                   every book, by testament, with its chapters
    /<book>/                 a book: its chapters and who comments on it
    /<book>/<chapter>/       the reader: Bible text and the commentary panel
    /commentators/           every commentator, by era
    /commentators/<author>/  one commentator: biography, works, comments
    /works/<work>/           one commentary: edition, rights, every excerpt
    /works/<work>/<n>/       a whole homily or tractate (library/texts)
    /about/                  what Logia is and how its text is checked
    /library/                the catalogue: every work by genre and era, what it
                             covers, and what is still to come
    /topics/, /topics/<id>/  topics: the excerpts a topic's verses and terms gather
    /api/v1/                 the public read-only API (scripts/api.py, docs/api.md)
    /linker.js, /linker/     the script other sites embed to link Bible references
                             to Logia (web/linker.js), and how to use it
    /search/                 search every excerpt and whole text (web/search.js,
                             over /data/search.json, built here)

The look, the header, footer and settings menu follow openwordbible.org:
web/style.css and the fonts are the Open Word Bible's own, and web/site.js
is taken from its site script. web/logia.css adds Logia's own parts.
"""
import functools
import glob
import hashlib
import html
import json
import os
import re
import shutil
import types
from urllib.parse import quote

import api

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
NUMBER_WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine",
                10: "Ten", 11: "Eleven", 12: "Twelve"}


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
        # Every version of every work (library/versions): editions of the
        # original, printed translations, Logia's own translations.
        self.versions = {v["id"]: v for v in (load(p) for p in glob.glob(os.path.join(ROOT, "library", "versions", "*", "*.json")))}
        # The version each work's excerpts are copied from.
        self.base = {}
        for p in glob.glob(os.path.join(ROOT, "library", "comments", "*", "*.json")):
            d = load(p)
            self.base[d["work"]] = self.versions[d["version"]]
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
                text, fixed = entry["text"], []
                for a, b in self.fixes.get(work, []):
                    if a in text:
                        fixed.append([a, b])        # the scan corrections this excerpt shows
                    text = text.replace(a, b)
                self.comments.append({**entry, "work": work, "text": text, "fixed": fixed,
                                      "source_url": urls.get((work, entry["sources"][0]), self.base[work]["full_text_url"]),
                                      "cites": cites.get(entry["id"], []), "quotes": quotes.get(entry["id"], []),
                                      "quoted_in": quoted_in.get(entry["id"], [])})
        self.by_id = {c["id"]: c for c in self.comments}
        # Whole homilies and tractates (scripts/extract_texts.py), in order,
        # and where each excerpt begins in one.
        self.texts = {}
        for p in glob.glob(os.path.join(ROOT, "library", "texts", "*", "*.json")):
            x = load(p)
            self.texts.setdefault(x["work"], []).append(x)
        # Topics (library/topics): each gathers the excerpts on its verses and
        # those that use one of its terms.
        self.topics = sorted((load(p) for p in glob.glob(os.path.join(ROOT, "library", "topics", "*.json"))),
                             key=lambda x: x["order"])
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

    def edition(self, work_id):
        """The version a work's excerpts are copied from."""
        return self.base[work_id]

    def versions_of(self, work_id):
        """A work's versions: the one its excerpts come from first, then
        originals, then translations, by language."""
        vs = [v for v in self.versions.values() if v["work"] == work_id]
        return sorted(vs, key=lambda v: (v["id"] != self.base[work_id]["id"], v["kind"] != "original", v["id"]))

    def author_of(self, work_id):
        return self.authors[self.works[work_id]["author"]]

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
                "quotedIn": self.quoted_in_rows(c), "inFull": self.in_full.get(c["id"]), "fixed": c["fixed"],
                "sources": c["sources"]})
        return out

    # --- Links between texts (docs/references.md) ---

    def verse_link(self, ref, card=None, english=False):
        """Where to read a verse: on Logia if its chapter is here, else on the
        Open Word Bible, which has no deuterocanonical books (None). A
        commentator's citation is English-numbered (english=True) and is
        read at the Open Word Bible's number for it (Psalm 19:1 at PSA.19.2)."""
        book, chapter, verse = scripture.parse(scripture.to_source(ref) if english else ref)
        if (book, chapter) in self.chapters:
            return chapter_url(book, chapter) + f"#v{verse}" + (f"-{card}" if card else "")
        if book in scripture.DEUTEROCANON or card:
            return None
        return OWB_SITE + chapter_url(book, chapter)

    def cites_for(self, c):
        return [{"at": x["at"], "text": x["text"], "label": scripture.label(x["start"], x["end"]),
                 "href": self.verse_link(x["start"], english=True), "status": x["status"]} for x in c["cites"]]

    def quote_rows(self, c):
        """A catena excerpt's quotations, traced to the quoted works."""
        out = []
        for q in c["quotes"]:
            w, a = self.works[q["work"]], self.author_of(q["work"])
            held = self.by_id.get(q["excerpt"])
            url = (self.urls.get((q["work"], q["source"]), self.edition(q["work"])["full_text_url"])
                   + (f"#{q['para']}" if q["para"] else ""))
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

    def topic_members(self, topic):
        """[(comment, why)] for a topic: why is "verse" when the excerpt is on
        one of its verses, else the first of its terms the excerpt uses."""
        verses = [scripture.parse(v) for v in topic["verses"]]
        terms = [(x, re.compile(r"(?<![\w])" + re.escape(x), re.I)) for x in topic["terms"]]
        out = []
        for c in self.comments:
            b, ch, v = ref_parts(c["start"])
            _, ech, ev = ref_parts(c["end"])
            if any(vb == b and (ch, v) <= (vc, vv) <= (ech, ev) for vb, vc, vv in verses):
                out.append((c, "verse"))
                continue
            hit = next((x for x, rx in terms if rx.search(c["text"])), None)
            if hit:
                out.append((c, hit))
        return out

    def topics_on(self, ref):
        b, ch, v = scripture.parse(ref)
        return [tp for tp in self.topics if any(scripture.parse(x) == (b, ch, v) for x in tp["verses"])]

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
                b, ch, v = scripture.parse(scripture.to_source(x["start"]))
                _, ch2, v2 = scripture.parse(scripture.to_source(x["end"]))
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
                                 "tradition": a["tradition"], "era": a["era"], "family": a["family"], "died": a["died"],
                                 "ref": scripture.label(c["start"], c["end"]),
                                 "href": self.verse_link(c["start"], c["work"]) or self.edition(c["work"])["full_text_url"],
                                 "text": x["text"], "snippet": cite_snippet(c["text"], x["at"], len(x["text"]))})
        for rows in out.values():
            rows.sort(key=lambda r: (ERAS.index(r["era"]), r["died"]))
        return out

    def coverage(self):
        """{(book, chapter): (number of works, [verses with commentary])}."""
        cov = {}
        for c in self.comments:
            sb, sc, sv = ref_parts(c["start"])
            _, ec, ev = ref_parts(c["end"])
            for ch in range(sc, ec + 1):
                works, verses = cov.setdefault((sb, ch), (set(), set()))
                works.add(c["work"])
                verses.update(range(sv if ch == sc else 1, (ev if ch == ec else 999) + 1))
        return {k: (len(w), sorted(v)) for k, (w, v) in cov.items()}


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
            f'<div class="dd-alls">{all_link("/read/", t("nav.all_books"))}{all_link("/library/", t("nav.library"))}'
            f'{all_link("/topics/", t("nav.topics"))}'
            f'{all_link("/search/", t("nav.search"))}</div>')
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
        row("/about/rules/", t("nav.rules"), t("nav.rules_note"), "check"),
        row("/linker/", t("nav.linker"), t("nav.linker_note"), "code"),
        row("/api/v1/index.json", t("nav.api"), t("nav.api_note"), "code"),
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
        f'<a class="sign-in-btn" href="{e(href)}" data-login>{icon("user")}<span>{e(t("account.sign_in"))}</span></a>'
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

    def chip(code):
        done = sum(1 for (b, _c) in cov if b == code)
        total = lib.books[code]["chapters"]
        return (f'<li><a class="book-chip{"" if done == total else " part"}" href="/{code.lower()}/" '
                f'title="{e(t("read.commentary_on", n=done, total=total))}">{e(lib.books[code]["en"])}</a></li>')

    have = {b for b, _c in lib.chapters}
    codes = list(lib.books)
    tiers = []
    for key, part in (("old", codes[:OT_BOOKS]), ("new", codes[OT_BOOKS:])):
        started = [c for c in part if c in have]
        missing = len(part) - len(started)
        more = (f'<li><a class="book-chip none" href="/read/">{e(t("read.coming"))} ({missing})</a></li>' if missing else "")
        tiers.append(f'<section class="testament" aria-labelledby="foot-{key}"><div class="testament-head">'
                     f'<h3 id="foot-{key}">{e(t("testaments." + key))}</h3><span>{len(started)}/{len(part)}</span></div>'
                     f'<ul class="book-chips">{"".join(chip(c) for c in started)}{more}</ul></section>')

    def links(pairs):
        return "".join(f'<li><a href="{href}"{" rel=noopener" if href.startswith("http") else ""}>{e(label)}</a></li>'
                       for href, label in pairs)

    read = [("/read/", t("nav.all_books"))] + [(chapter_url(b, c), f'{lib.books[b]["en"]} {c}')
                                               for (b, c) in sorted(cov)][:6]
    people = [(f'/commentators/{a["id"]}/', a["name"]) for a in lib.ordered_authors()]
    project = [("/about/", t("nav.about_logia")), ("/about/#checked", t("nav.checked")),
               (OWB_SITE + "/", t("nav.owb")), (GITHUB_URL, t("nav.source")),
               (GITHUB_URL + "/issues/new", t("footer.report"))]
    return f"""<footer class="site"><div class="wrap">
<div class="foot-top"><div class="foot-about">
<a class="brand" href="/">{MARK}<span class="brand-name">Logia</span></a>
<p>{e(t("site.tagline"))}</p>
<p class="foot-licence"><span class="pill">{e(t("site.licence_pill"))}</span> {e(t("site.licence"))}</p>
</div></div>
<nav class="foot-books" aria-labelledby="foot-read"><h2 id="foot-read">{e(t("footer.books_with"))}</h2>
<div class="testaments">{"".join(tiers)}</div></nav>
<div class="foot-grid">
<nav aria-labelledby="foot-r"><h2 id="foot-r">{e(t("footer.read"))}</h2><ul>{links(read)}</ul></nav>
<nav aria-labelledby="foot-c"><h2 id="foot-c">{e(t("footer.commentators"))}</h2><ul>{links(people)}</ul></nav>
<nav aria-labelledby="foot-p"><h2 id="foot-p">{e(t("footer.project"))}</h2><ul>{links(project)}</ul></nav>
</div>
<div class="foot-base"><p class="foot-review">{e(t("footer.review"))}</p><p>{e(t("footer.licences"))}</p></div>
</div></footer>"""


@functools.lru_cache(maxsize=None)
def asset(name):
    """A file in web/ by an address that changes when its contents do
    (/style.css?v=1a2b3c4d5e), so browsers may keep it for a year
    (render.yaml) and still see each new version at once."""
    with open(os.path.join(WEB, name), "rb") as f:
        return f"/{name}?v={hashlib.sha256(f.read()).hexdigest()[:10]}"


def digest_url(path, text):
    return f"{path}?v={hashlib.sha256(text.encode()).hexdigest()[:10]}"


def page(lib, title, body, path, current="", description="", scripts=(), noindex=False, canonical=True):
    full = f"{title} · Logia" if title != "Logia" else "Logia"
    description = description or t("site.description")
    own = e(SITE_URL + path)
    js = "".join(f'\n<script src="{asset(s)}" defer></script>' for s in ("site.js", "account.js") + tuple(scripts))
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
<meta property="og:description" content="{e(description)}">{'<meta name="robots" content="noindex">' if noindex else ""}
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta name="logia-api" content="{API_URL}">
<meta name="logia-owb" content="{OWB_SITE}">
<meta name="theme-color" content="#f4eee3" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#2a241c" media="(prefers-color-scheme: dark)">
<script>{BOOT_SCRIPT}</script>
<link rel="preload" href="/fonts/hanken-grotesk-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/fonts/gentium-book-plus-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{asset("style.css")}">
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


# --- Pages --------------------------------------------------------------------

def home_page(lib):
    cov = lib.coverage()
    first = sorted(cov)[0] if cov else lib.chapters[0]
    cards = "".join(
        f'<li><a class="lg-card" href="{chapter_url(b, c)}"><b>{e(lib.books[b]["en"])} {c}</b>'
        f'<span>{e(NUMBER_WORDS.get(n, str(n)))} commentaries · verses {span_text(vs)}</span></a></li>'
        for (b, c), (n, vs) in sorted(cov.items()))
    voices = ""
    for era in ERAS:
        people = [a for a in lib.ordered_authors() if a["era"] == era]
        if people:
            voices += (f'<section><h3 class="label">{e(t("eras." + era))}</h3><ul class="lg-people">'
                       + "".join(f'<li><a href="/commentators/{a["id"]}/"><b>{e(a["name"])}</b> '
                                 f'<span>{e(a["dates"])}</span></a></li>' for a in people) + "</ul></section>")
    body = f"""
<section class="hero">
<p class="eyebrow">{e(t("home.verse"))}</p>
<h1>{e(t("home.title"))}</h1>
<p class="hero-sub">{e(t("home.lead"))}</p>
<p class="actions"><a class="button" href="{chapter_url(*first)}">{e(t("home.start"))}</a>
<a class="button ghost" href="/read/">{e(t("home.browse"))}</a></p>
</section>
<section class="lg-block" aria-labelledby="h-read"><h2 id="h-read">{e(t("home.read_heading"))}</h2>
<ul class="lg-cards">{cards}</ul></section>
<section class="lg-block" aria-labelledby="h-voices"><h2 id="h-voices">{e(t("home.voices_heading"))}</h2>
<div class="lg-eras">{voices}</div>
<p><a class="lg-more" href="/commentators/">{e(t("home.all_commentators"))} {icon("arrow", 15)}</a></p></section>
<section class="lg-block" aria-labelledby="h-how"><h2 id="h-how">{e(t("home.how_heading"))}</h2>
<div class="lg-cols">
<div><h3>{e(t("home.how_copied"))}</h3><p>{e(t("home.how_copied_text"))}</p></div>
<div><h3>{e(t("home.how_owb"))}</h3><p>{e(t("home.how_owb_text"))}</p></div>
<div><h3>{e(t("home.how_langs"))}</h3><p>{e(t("home.how_langs_text"))}</p></div>
</div></section>"""
    return page(lib, "Logia", body, "/", current="/")


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


def read_page(lib):
    """The books in Logia first, each a tile with a pill per chapter (gold
    where there is commentary), then the books still to come, by testament."""
    cov = lib.coverage()
    have = {b for b, _c in lib.chapters}
    codes = list(lib.books)
    tiles = []
    for code in codes:
        if code not in have:
            continue
        name = lib.books[code]["en"]
        total = lib.books[code]["chapters"]
        done = sum(1 for (b, _c) in cov if b == code)
        progress = (t("read.commentary_on_one", total=total) if done == 1 else
                    t("read.commentary_on", n=done, total=total) if done else t("read.text_only"))
        tiles.append(
            f'<li class="book-item"><details id="{code.lower()}" open>'
            f'<summary class="book-tile"><span class="book-tile-name">{e(name)}</span>'
            f'<span class="book-progress{" done" if done == total else ""}">{e(progress)}</span>'
            f'<span class="meter" aria-hidden="true"><span style="width:{100 * done / total:.0f}%"></span></span></summary>'
            f'<div class="book-open"><div class="chap-pills">{chapter_pills(lib, code, cov)}</div>'
            f'<p class="book-open-links"><a class="book-page-link" href="/{code.lower()}/">'
            f'{e(t("read.book_page", book=name))}&nbsp;&rarr;</a></p></div></details></li>')
    coming = ""
    for key, part in (("old", codes[:OT_BOOKS]), ("new", codes[OT_BOOKS:])):
        names = [f'<li><span class="book-chip none">{e(lib.books[c]["en"])}</span></li>' for c in part if c not in have]
        if names:
            coming += (f'<section class="testament"><div class="testament-head"><h3>{e(t("testaments." + key))}</h3>'
                       f'<span>{len(names)}</span></div><ul class="book-chips">{"".join(names)}</ul></section>')
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("read.title"))}</p>
<h1>{e(t("read.heading"))}</h1><p class="dek">{e(t("read.dek"))}</p></header>
<nav class="book-index" aria-label="{e(t("read.title"))}"><ul class="book-tiles">{"".join(tiles)}</ul></nav>
<section class="lg-block lg-coming" aria-labelledby="h-coming"><h2 id="h-coming">{e(t("read.coming"))}</h2>
<p class="lg-quiet">{e(t("read.coming_note"))}</p><div class="testaments">{coming}</div></section>"""
    return page(lib, t("read.title"), body, "/read/", current="/read/")


def book_page(lib, book):
    cov = lib.coverage()
    name = lib.books[book]["en"]
    total = lib.books[book]["chapters"]
    have = [c for b, c in lib.chapters if b == book]
    done = sum(1 for (b, _c) in cov if b == book)
    cards = []
    for c in have:
        if (book, c) in cov:
            n, vs = cov[(book, c)]
            note = t("book.chapter_card_one" if n == 1 else "book.chapter_card", n=n, span=span_text(vs))
        else:
            note = t("book.chapter_none")
        cards.append(f'<li><a class="lg-card{"" if (book, c) in cov else " lg-plain"}" href="{chapter_url(book, c)}">'
                     f'<b>{e(name)} {c}</b><span>{e(note)}</span></a></li>')
    works = {c["work"] for c in lib.comments if c["start"].startswith(book + ".")}
    people = "".join(
        f'<li><a href="/works/{w}/"><b>{e(lib.author_of(w)["name"])}</b> <span>{e(lib.works[w]["title"])}</span></a></li>'
        for w in lib.ordered_works(works))
    who = (f'<section class="lg-block"><h2>{e(t("book.commentators", book=name))}</h2><ul class="lg-people lg-wide">{people}</ul></section>'
           if people else "")
    body = f"""
<header class="page-head"><p class="eyebrow"><a href="/read/">{e(t("read.title"))}</a></p>
<h1>{e(name)}</h1><p class="dek">{e(t("book.dek", n=total, done=done))}</p></header>
<section class="lg-block"><h2>{e(t("book.chapters"))}</h2><div class="chap-pills lg-pills">{chapter_pills(lib, book, cov)}</div>
<ul class="lg-cards">{"".join(cards)}</ul></section>
{who}"""
    return page(lib, name, body, f"/{book.lower()}/", current="/read/")


def version_data(v):
    """What the reader's Cite and Source panels say about a version."""
    return {"id": v["id"], "kind": v["kind"], "language": v["language"], "edition": v["edition"],
            "edition_short": short_edition(v["edition"]), "translation": v["translation"],
            "published": v["published"], "source_kind": v["source_kind"], "made_by": v["made_by"],
            "status": v["status"], "reviewer": v["reviewer"]}


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


def chapter_page(lib, book, chapter, all_chapters):
    """The reader page, and the text of its panel file."""
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
            "edition_short": short_edition(lib.edition(wid)["edition"]), "author_url": f'/commentators/{a["id"]}/',
            "divisions": w["divisions"], "family": a["family"], "version": version_data(lib.edition(wid)),
            "work_url": f"/works/{wid}/", "entries": sorted(by_work[wid], key=lambda x: (x["start"], x["end"]))})
    ui = dict(CATALOG["reader"])
    ui["eras"] = CATALOG["eras"]
    ui["families"] = CATALOG["families"]
    ui["languages"] = CATALOG["languages"]
    ui["levels"] = CATALOG["level"]
    hebrew = bible["source"] == "hbo"
    if hebrew:
        # Old Testament chapters read from the Hebrew: a string with an _hbo
        # variant uses it there ("Tap a Hebrew word...").
        ui.update({k[:-4]: v for k, v in CATALOG["reader"].items() if k.endswith("_hbo")})
    panel, records = panel_file(bible)
    text_data = {k: v for k, v in bible.items() if k not in ("records", "words")}
    data = {**text_data, "records": records, "wordCounts": {v: len(ws) for v, ws in bible["words"].items()},
            "panel": digest_url(f"/panel/{book}.{chapter}.json", panel),
            "bookName": name, "commentaries": commentaries, "ui": ui, "eras": ERAS,
            "wording": {name: list(values) for name, _d, values in DISPLAY_PREFS if name in WORDING},
            "citedBy": lib.cited_by(book, chapter, bible["verses"]),
            "wholeTexts": {str(v): lib.whole_on(f"{book}.{chapter}.{v}") for v in bible["verses"]},
            "topics": {str(v): [{"id": tp["id"], "title": tp["title"]} for tp in lib.topics_on(f"{book}.{chapter}.{v}")]
                       for v in bible["verses"]},
            "books": {k: v["en"] for k, v in lib.books.items()},
            "site_url": SITE_URL, "issues_url": GITHUB_URL + "/issues/new"}
    heading = default_wording(next((r["heading"] for r in bible["records"] if r["heading"]), f"{name} {chapter}"))
    # The text as plain Balanced verses, for search engines and readers
    # without JavaScript; web/reader.js replaces it.
    verses = {}
    for r in bible["records"]:
        for p in r["pieces"]:
            verses[p[0]] = verses.get(p[0], "") + default_wording(p[1])
    plain = " ".join(f'<span class="cx-verse"><span class="cx-vn">{v}</span>{e(verses[v].strip())}</span>'
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
        f'{e(c["author"])}, <a href="{e(lib.edition(c["work_id"])["full_text_url"])}" rel="noopener"><i>{e(c["title"])}</i></a>'
        for c in commentaries)
    credits = f'<p class="cx-credits">{t("chapter.credits", works=works_credit)}</p>' if commentaries else ""
    owb_link = f'<a href="{OWB_SITE}{chapter_url(book, chapter)}" rel="noopener">Open Word Bible</a>'
    first_ref = f"{name} {chapter}:{bible['verses'][0]}"
    tabs = "".join(
        f'<button role="tab" id="tab-{k}" data-tab="{k}" aria-selected="{"true" if k == "comm" else "false"}">'
        f'{e(t("chapter.tab_" + k + ("_hbo" if hebrew and k == "words" else "")))}<span class="cx-n" id="n-{k}"></span></button>'
        for k in ("comm", "words", "notes", "xref"))
    body = f"""
<div class="cx-layout">
<article class="cx-passage">
<p class="cx-eyebrow"><a href="/{book.lower()}/">{e(name)}</a> · {e(t("chapter.eyebrow", chapter=chapter))}</p>
<h1>{e(heading)}</h1>
<p class="cx-sub">{e(t("chapter.pick_hbo" if hebrew else "chapter.pick"))}</p>
<div class="cx-levels" role="group" aria-label="{e(t("chapter.level_label"))}">{levels}</div>
<div class="cx-strip" id="strip" role="group" aria-label="{e(t("reader.strip_label"))}"></div>
<div class="cx-text" id="text">{plain}</div>
<p class="cx-hint">{t("chapter.owb_hint", link=owb_link)}</p>
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
<div class="cx-rail" id="rail" aria-label="{e(t("chapter.rail_label"))}"></div>
<div class="cx-tabs" role="tablist">{tabs}</div>
</div>
<div class="cx-pb" id="pb"></div>
</aside>
</div>
{credits}
<script type="application/json" id="chapter-data">{json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")}</script>"""
    n = len(commentaries)
    description = (t("chapter.description", book=name, chapter=chapter, n=n) if n
                   else t("chapter.description_none", book=name, chapter=chapter))
    return page(lib, f"{name} {chapter}", body, chapter_url(book, chapter), current="/read/",
                description=description, scripts=("reader.js",)), panel


def lifespan(author):
    """(born, died) from dates like "c. 347-407" or "1509-1564"."""
    years = [int(y) for y in re.findall(r"\d{3,4}", author["dates"])]
    return (years[0] if len(years) > 1 else author["died"] - 60), author["died"]


def timeline(lib):
    """Every commentator's life on a line of centuries (roadmap, item 16),
    coloured by tradition."""
    lo, hi = 200, 1950
    pos = lambda y: (y - lo) / (hi - lo) * 100      # noqa: E731
    ticks, rows = [], []
    for y in range(300, hi, 300):
        ticks.append(f'<span class="lg-tl-tick" style="left:{pos(y):.2f}%">{y}</span>')
    for a in sorted(lib.authors.values(), key=lambda a: lifespan(a)):
        b, d = lifespan(a)
        rows.append(f'<li><a href="/commentators/{a["id"]}/" class="lg-tl-row">'
                    f'<span class="lg-tl-name">{e(a["name"])} <span class="lg-quiet">{e(a["dates"])}</span></span>'
                    f'<span class="lg-tl-track"><span class="lg-tl-life lg-fam-{a["family"]}" '
                    f'style="left:{pos(b):.2f}%;width:{max(pos(d) - pos(b), .8):.2f}%"></span></span></a></li>')
    return (f'<section class="lg-block lg-timeline" aria-labelledby="h-tl"><h2 id="h-tl">{e(t("commentators.timeline"))}</h2>'
            f'<p class="lg-quiet">{e(t("commentators.timeline_note"))}</p>'
            f'<ol class="lg-tl">{"".join(rows)}</ol>'
            f'<div class="lg-tl-axis"><span class="lg-tl-name"></span><span class="lg-tl-track">{"".join(ticks)}</span></div>'
            f'<p class="lg-tl-key">' + "".join(
                f'<span><i class="lg-tl-life lg-fam-{f}"></i>{e(t("families." + f))}</span>'
                for f in CATALOG["families"] if any(a["family"] == f for a in lib.authors.values())) + "</p></section>")


def commentators_page(lib):
    counts = {}
    for c in lib.comments:
        counts.setdefault(lib.works[c["work"]]["author"], set()).add(c["start"])
    sections = ""
    for era in ERAS:
        people = [a for a in lib.ordered_authors() if a["era"] == era]
        if not people:
            continue
        cards = "".join(
            f'<li><a class="lg-person" href="/commentators/{a["id"]}/">'
            f'<span class="lg-mono" aria-hidden="true">{e(short_name(a)[0])}</span>'
            f'<span><b>{e(a["name"])}</b><span class="lg-dates">{e(a["dates"])} · {e(a["tradition"])}</span>'
            f'<span class="lg-quiet">{e(t("commentators.verses", n=len(counts.get(a["id"], ()))))}</span></span></a></li>'
            for a in people)
        sections += f'<section class="lg-block"><h2>{e(t("eras." + era))}</h2><ul class="lg-grid">{cards}</ul></section>'
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("commentators.title"))}</p>
<h1>{e(t("commentators.heading"))}</h1><p class="dek">{e(t("commentators.dek"))}</p></header>
{timeline(lib)}
{sections}"""
    return page(lib, t("commentators.title"), body, "/commentators/", current="/commentators/")


def excerpt_list(lib, comments, show_work=False):
    """Excerpts grouped by chapter, one row per verse or range: its first
    words, how many passages there are, and a link to the verse in the reader."""
    out, rows = [], {}
    for c in comments:
        b, ch, v = ref_parts(c["start"])
        _, ech, ev = ref_parts(c["end"])
        rows.setdefault((b, ch), {}).setdefault((v, ech, ev, c["work"] if show_work else ""), []).append(c)
    for (b, ch), group in rows.items():
        out.append(f'<h3 class="label">{e(lib.books[b]["en"])} {ch}</h3><ul class="lg-excerpts">')
        for (v, ech, ev, work), cs in group.items():
            ref = f"{lib.books[b]['en']} {ch}:{v}" + (f"–{ev}" if (ech, ev) != (ch, v) else "")
            more = f' <span class="lg-quiet">· {e(t("commentators.passages", n=len(cs)))}</span>' if len(cs) > 1 else ""
            title = f' <span class="lg-quiet">· {e(lib.works[work]["title"])}</span>' if work else ""
            out.append(f'<li><a href="{chapter_url(b, ch)}#v{v}"><b>{e(ref)}</b></a>{title}{more}'
                       f'<p>{e(snippet(cs[0]["text"]))}</p></li>')
        out.append("</ul>")
    return "".join(out)


def order_key(c):
    b, ch, v = ref_parts(c["start"])
    return (b, ch, v, c["id"])


def author_page(lib, author):
    works = lib.ordered_works([w for w, x in lib.works.items() if x["author"] == author["id"]])
    work_cards = "".join(
        f'<li><a class="lg-card" href="/works/{w}/"><b>{e(lib.works[w]["title"])}</b>'
        f'<span>{e(short_edition(lib.edition(w)["edition"]))}</span></a></li>' for w in works)
    comments = sorted((c for c in lib.comments if c["work"] in works), key=order_key)
    bio = "".join(f"<p>{e(p)}</p>" for p in author["bio"].split("\n\n"))
    draft = f'<p class="lg-quiet">{e(t("commentators.bio_draft"))}</p>' if author["bio_status"] == "ai_draft" else ""
    body = f"""
<header class="page-head lg-person-head"><p class="eyebrow"><a href="/commentators/">{e(t("commentators.title"))}</a> · {e(t("eras." + author["era"]))}</p>
<h1>{e(author["name"])}</h1><p class="dek">{e(author["dates"])} · {e(author["tradition"])}</p></header>
<section class="prose lg-bio">{bio}{draft}</section>
<section class="lg-block"><h2>{e(t("commentators.works"))}</h2><ul class="lg-cards">{work_cards}</ul></section>
<section class="lg-block"><h2>{e(t("commentators.comments_on", name=author["name"]))}</h2>{excerpt_list(lib, comments, show_work=len(works) > 1)}</section>"""
    return page(lib, author["name"], body, f'/commentators/{author["id"]}/', current="/commentators/",
                description=author["bio"].split("\n\n")[0])


def version_card(lib, wid, v):
    """One version of a work: what it is, where it was copied from, its
    rights and whether a person has reviewed it."""
    lang = t("languages." + v["language"]) if v["language"] in CATALOG["languages"] else v["language"]
    kind = t("version.original" if v["kind"] == "original" else "version.translation", language=lang)
    facts = [(t("work.edition"), v["edition"])]
    if v["translation"]:
        facts.append((t("work.translation"), v["translation"]))
    if v["made_by"] == "print":
        source = (t("work.source_scan", n=len(lib.fixes.get(wid, []))) if v["source_kind"] == "scan"
                  else t("work.source_digital"))
        facts += [(t("work.published"), str(v["published"])), (t("work.source"), source)]
    facts += [(t("work.rights"), f'{v["rights"]["basis"]}; {v["rights"]["worldwide"]}'),
              (t("version.status"), t("version.reviewed", name=v["reviewer"]) if v["status"] == "reviewed"
               else t("version.ai_draft_logia" if v["made_by"] == "logia" else "version.ai_draft"))]
    used = (f'<p class="lg-quiet">{e(t("version.excerpts_from"))}</p>' if v["id"] == lib.edition(wid)["id"] else "")
    dl = "".join(f"<dt>{e(k)}</dt><dd>{e(x)}</dd>" for k, x in facts)
    return (f'<article class="lg-version" id="{e(v["id"])}"><h3>{e(kind)}</h3>{used}'
            f'<dl class="lg-facts">{dl}</dl></article>')


def work_page(lib, wid):
    w, a = lib.works[wid], lib.author_of(wid)
    comments = sorted((c for c in lib.comments if c["work"] == wid), key=order_key)
    facts = [(t("work.original"), w["original_language"]),
             (t("work.in_logia"), t("work.excerpts", n=len(comments)))]
    dl = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in facts)
    versions = "".join(version_card(lib, wid, v) for v in lib.versions_of(wid))
    full = []
    chapter = None
    for c in comments:
        b, ch, v = ref_parts(c["start"])
        _, ech, ev = ref_parts(c["end"])
        if (b, ch) != chapter:
            chapter = (b, ch)
            full.append(f'<h3 class="lg-chapter">{e(lib.books[b]["en"])} {ch}</h3>')
        ref = f"{lib.books[b]['en']} {ch}:{v}" + (f"–{ev}" if (ech, ev) != (ch, v) else "")
        heading = f'<p class="lg-lemma">{e(c["heading"])}</p>' if c["heading"] else ""
        paras = "".join(f"<p>{e(p.strip())}</p>" for p in c["text"].split("\n\n"))
        full.append(f'<article class="lg-excerpt" id="{e(c["id"])}"><p class="lg-ref"><a href="{chapter_url(b, ch)}#v{v}" '
                    f'title="{e(t("work.open_verse", ref=ref))}">{e(ref)}</a></p>{heading}<div class="lg-text">{paras}</div></article>')
    texts = lib.texts.get(wid, [])
    whole = ""
    if texts:
        items = "".join(
            f'<li><a href="/works/{wid}/{x["locus"]}/"><b>{e(locus_label(w, x["locus"]))}</b></a>'
            f'<span class="lg-quiet">{e(text_lead(x))}</span></li>' for x in texts)
        verses = []
        for x in texts:
            b, c, a1 = scripture.parse(x["verses"]["start"])
            _, _, a2 = scripture.parse(x["verses"]["end"])
            verses += [f"{b}.{c}.{v}" for v in range(a1, a2 + 1) if f"{b}.{c}.{v}" not in verses]
        by_verse = "".join(
            f'<li><a href="{e(lib.verse_link(ref, english=True) or "")}"><b>{e(scripture.label(ref))}</b></a><span>'
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
<p class="actions"><a class="button ghost" href="{e(lib.edition(wid)["full_text_url"])}" rel="noopener">{e(t("work.full_text"))} ↗</a></p></header>
<dl class="lg-facts">{dl}</dl>
<section class="lg-block" id="versions"><h2>{e(t("work.versions"))}</h2><p class="lg-quiet">{e(t("work.versions_note"))}</p>
<div class="lg-versions">{versions}</div></section>
{whole}
<section class="lg-block"><h2>{e(t("work.front_to_back"))}</h2><p class="lg-quiet">{e(t("work.front_to_back_note"))}</p>
<div class="lg-book">{"".join(full)}</div></section>"""
    return page(lib, w["title"], body, f"/works/{wid}/", current="/commentators/",
                description=f'{a["name"]}, {w["title"]}: {len(comments)} excerpts in Logia.')


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
        href = lib.verse_link(c["start"], english=True)
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
            href = lib.verse_link(p["verse"], english=True)
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
<p class="lg-quiet lg-whole-note">{e(t("text.note", edition=lib.edition(wid)["edition"]))}</p>"""
    return page(lib, f'{a["name"]}, {name}', html_body, f"/works/{wid}/{x['locus']}/", current="/commentators/",
                description=t("text.description", name=a["name"], title=w["title"], where=name))


GENRES = ("commentary", "homilies", "catena")


def library_page(lib):
    """The catalogue (roadmap, item 15): every work by genre, then era, with
    what it covers, its versions and whole texts, and what is still to come."""
    cov = lib.coverage()
    verses = {}                                  # book -> verses in its imported text
    for b, c in lib.chapters:
        verses[b] = verses.get(b, 0) + len(lib.bible(b, c)["verses"])
    held = {}                                    # work -> {book: set of verses}
    for c in lib.comments:
        b, ch, v = ref_parts(c["start"])
        _, ech, ev = ref_parts(c["end"])
        if (ech, ev) != (ch, v) and ech == ch:
            held.setdefault(c["work"], {}).setdefault(b, set()).update((ch, x) for x in range(v, ev + 1))
        else:
            held.setdefault(c["work"], {}).setdefault(b, set()).add((ch, v))
    n_verses = len({(b, x) for w in held.values() for b, xs in w.items() for x in xs})
    total = {"works": len(lib.works), "authors": len(lib.authors), "versions": len(lib.versions),
             "excerpts": len(lib.comments), "texts": sum(len(ts) for ts in lib.texts.values()), "verses": n_verses}
    summary = "".join(f'<div><b>{n}</b><span>{e(t("library.count_" + k))}</span></div>' for k, n in total.items())

    def card(wid):
        w, a = lib.works[wid], lib.author_of(wid)
        langs = sorted({lib.versions[v]["language"] for v in lib.versions if lib.versions[v]["work"] == wid})
        langs = " · ".join(t("languages." + x) if x in CATALOG["languages"] else x for x in langs)
        spans = []
        for b, xs in sorted(held.get(wid, {}).items()):
            chs = sorted({ch for ch, _ in xs})
            for ch in chs:
                vs = sorted(v for c2, v in xs if c2 == ch)
                runs, start = [], vs[0]
                for prev, cur in zip(vs, vs[1:] + [None]):
                    if cur != prev + 1:
                        runs.append(f"{start}–{prev}" if prev != start else f"{start}")
                        start = cur
                spans.append(f'{lib.books[b]["en"]} {ch}:{", ".join(runs)}')
        n = sum(1 for c in lib.comments if c["work"] == wid)
        texts = lib.texts.get(wid, [])
        whole = (f' · <a href="/works/{wid}/#whole">{e(t("library.whole", n=len(texts), kind=plural(w["divisions"][0]).lower()))}</a>'
                 if texts else "")
        draft = "" if w["status"] == "reviewed" else f' · <span class="lg-quiet">{e(t("library.draft"))}</span>'
        return (f'<li class="lg-cat-work"><a href="/works/{wid}/"><b><i>{e(w["title"])}</i></b></a>'
                f'<span class="lg-cat-by"><a href="/commentators/{a["id"]}/">{e(a["name"])}</a> · {e(a["dates"])} · '
                f'{e(a["tradition"])}</span>'
                f'<span class="lg-quiet">{e(t("library.covers", spans=", ".join(spans) or "—"))} · '
                f'{e(t("library.excerpts", n=n))}{whole} · {e(t("library.in", langs=langs))}{draft}</span></li>')

    sections = []
    for genre in GENRES:
        ids = [w for w in lib.ordered_works() if lib.works[w]["genre"] == genre]
        if not ids:
            continue
        groups = ""
        for era in ERAS:
            ws = [w for w in ids if lib.author_of(w)["era"] == era]
            if ws:
                groups += (f'<h3 class="label">{e(t("eras." + era))}</h3>'
                           f'<ul class="lg-cat">{"".join(card(w) for w in ws)}</ul>')
        sections.append(f'<section class="lg-block"><h2>{e(t("library.genre_" + genre))}</h2>'
                        f'<p class="lg-quiet">{e(t("library.genre_" + genre + "_note"))}</p>{groups}</section>')
    # What is still to come: books in the Bible text with chapters and verses
    # no commentary reaches yet.
    gaps, none = [], []
    for b in dict.fromkeys(b for b, _c in lib.chapters):
        have = {x for w in held.values() for x in w.get(b, ())}
        if not have:
            none.append(f'<a href="/{b.lower()}/">{e(lib.books[b]["en"])}</a>')
            continue
        chs = [c for bb, c in lib.chapters if bb == b]
        empty = [c for c in chs if (b, c) not in cov]
        gaps.append(f'<li><a href="/{b.lower()}/"><b>{e(lib.books[b]["en"])}</b></a> '
                    f'<span class="lg-quiet">{e(t("library.gap", have=len(have), total=verses[b], empty=len(empty), chapters=len(chs)))}</span></li>')
    if none:
        gaps.append(f'<li><b>{e(t("library.none_yet", n=len(none)))}</b><span class="lg-quiet">{", ".join(none)}</span></li>')
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("library.eyebrow"))}</p>
<h1>{e(t("library.heading"))}</h1><p class="dek">{e(t("library.dek"))}</p></header>
<div class="lg-summary">{summary}</div>
{"".join(sections)}
<section class="lg-block"><h2>{e(t("library.to_come"))}</h2><p class="lg-quiet">{e(t("library.to_come_note"))}</p>
<ul class="lg-cat">{"".join(gaps)}</ul></section>"""
    return page(lib, t("library.title"), body, "/library/", current="/read/", description=t("library.dek"))


def topics_page(lib):
    items = "".join(
        f'<li><a href="/topics/{tp["id"]}/"><b>{e(tp["title"])}</b></a><span class="lg-quiet">{e(tp["note"])} · '
        f'{e(t("topics.count", n=len(lib.topic_members(tp))))}</span></li>' for tp in lib.topics)
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("topics.eyebrow"))}</p>
<h1>{e(t("topics.heading"))}</h1><p class="dek">{e(t("topics.dek"))}</p></header>
<ul class="lg-cat lg-topics">{items}</ul>
<p class="lg-quiet lg-topic-rule">{e(t("topics.how"))}</p>"""
    return page(lib, t("topics.title"), body, "/topics/", current="/read/", description=t("topics.dek"))


def topic_page(lib, tp):
    """One topic (roadmap, item 18): every excerpt its verses and terms
    gather, by era, from every tradition alike; nothing is added to them."""
    members = lib.topic_members(tp)
    verses = ", ".join(f'<a href="{e(lib.verse_link(v) or "")}">{e(scripture.label(v))}</a>' for v in tp["verses"])
    terms = ", ".join(f"“{e(x)}”" for x in tp["terms"])
    rule = t("topics.rule", verses=verses, terms=terms) if tp["terms"] else t("topics.rule_verses", verses=verses)
    fams = {}
    for c, _why in members:
        f = lib.author_of(c["work"])["family"]
        fams[f] = fams.get(f, 0) + 1
    spread = " · ".join(f'{e(t("families." + f))} {n}' for f, n in sorted(fams.items(), key=lambda x: list(CATALOG["families"]).index(x[0])))
    groups = ""
    for era in ERAS:
        cs = [(c, why) for c, why in members if lib.author_of(c["work"])["era"] == era]
        if not cs:
            continue
        cs.sort(key=lambda x: (lib.author_of(x[0]["work"])["died"], order_key(x[0])))
        rows = []
        for c, why in cs:
            a = lib.author_of(c["work"])
            b, ch, v = ref_parts(c["start"])
            ref = scripture.label(c["start"], c["end"])
            if why == "verse":
                text, note = snippet(c["text"], 60), ""
            else:
                at = re.search(r"(?<![\w])" + re.escape(why), c["text"], re.I).start()
                text, note = cite_snippet(c["text"], at, len(why)), f' <span class="lg-quiet">· {e(t("topics.uses", term=why))}</span>'
            rows.append(f'<li><a href="{chapter_url(b, ch)}#{e(c["id"])}"><b>{e(a["name"])}</b> · {e(ref)}</a>{note}'
                        f'<p>{e(text)}</p></li>')
        groups += f'<h3 class="label">{e(t("eras." + era))}</h3><ul class="lg-excerpts">{"".join(rows)}</ul>'
    draft = f'<p class="lg-quiet">{e(t("topics.draft"))}</p>' if tp["status"] != "reviewed" else ""
    body = f"""
<header class="page-head"><p class="eyebrow"><a href="/topics/">{e(t("topics.eyebrow"))}</a></p>
<h1>{e(tp["title"])}</h1><p class="dek">{e(tp["note"])}</p></header>
<p class="lg-topic-rule">{rule} {e(t("topics.count", n=len(members)))}: {spread}.</p>{draft}
<section class="lg-block">{groups}</section>"""
    return page(lib, tp["title"], body, f'/topics/{tp["id"]}/', current="/read/", description=tp["note"])


def linker_script(lib):
    """web/linker.js with the book names it recognises, each book's chapter
    count and the site's address filled in."""
    with open(os.path.join(WEB, "linker.js"), encoding="utf-8") as f:
        js = f.read()
    chapters = {}
    for b, c in lib.chapters:
        chapters[b] = max(chapters.get(b, 0), c)
    names = {k: v for k, v in scripture.linker_names().items() if v in chapters}
    for key, value in (("/*SITE*/", SITE_URL), ("/*NAMES*/{}", json.dumps(names, separators=(",", ":"))),
                       ("/*CHAPTERS*/{}", json.dumps(chapters, separators=(",", ":"))),
                       ("/*RENUMBER*/{}", json.dumps(scripture.renumber_runs(), separators=(",", ":")))):
        if key not in js:
            raise SystemExit(f"web/linker.js: placeholder {key} is missing")
        js = js.replace(key, value)
    return js


def linker_page(lib):
    snippet_html = e(f'<script src="{SITE_URL}/linker.js" defer></script>')
    examples = t("linker.example")
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("linker.eyebrow"))}</p>
<h1>{e(t("linker.heading"))}</h1><p class="dek">{e(t("linker.dek"))}</p></header>
<section class="prose">
<h2>{e(t("linker.how"))}</h2>
<p>{e(t("linker.how_text"))}</p>
<pre class="lg-code"><code>{snippet_html}</code></pre>
<p>{e(t("linker.options"))}</p>
<ul>
<li><code>data-logia-scope="article"</code>: {e(t("linker.scope"))}</li>
<li><code>data-logia-preview="off"</code>: {e(t("linker.preview_off"))}</li>
<li><code>data-logia-skip</code>: {e(t("linker.skip"))}</li>
</ul>
<h2>{e(t("linker.try"))}</h2>
<div class="lg-linker-demo" id="linker-demo"><p>{e(examples)}</p></div>
<h2>{e(t("linker.data"))}</h2>
<p>{t("linker.data_text", api='<a href="/api/v1/index.json">/api/v1/</a>', docs=f'<a href="{GITHUB_URL}/blob/main/docs/api.md">docs/api.md</a>')}</p>
</section>
<script src="/linker.js" defer data-logia-scope="#linker-demo"></script>"""
    return page(lib, t("linker.title"), body, "/linker/", current="/about/", description=t("linker.dek"))


def search_index(lib):
    """Everything a reader can search, for web/search.js: each excerpt (as
    the reader shows it, scan corrections applied) and each paragraph of a
    whole text, with the facets it can be narrowed by."""
    rows = []
    for c in sorted(lib.comments, key=order_key):
        w, a = lib.works[c["work"]], lib.author_of(c["work"])
        b, ch, v = ref_parts(c["start"])
        where = scripture.label(c["start"], c["end"])
        if c.get("locus"):
            where += " · " + locus_label(w, c["locus"])
        rows.append({"k": "x", "id": c["id"], "w": c["work"], "a": a["name"], "e": a["era"], "f": a["family"],
                     "r": where, "u": chapter_url(b, ch) + "#" + c["id"], "t": c["text"]})
    for wid in lib.ordered_works(lib.texts):
        w, a = lib.works[wid], lib.author_of(wid)
        for x in lib.texts[wid]:
            for p in x["paragraphs"]:
                if len(p["text"]) < 60:
                    continue                     # headings
                rows.append({"k": "p", "id": p["id"], "w": wid, "a": a["name"], "e": a["era"], "f": a["family"],
                             "r": locus_label(w, p["locus"]), "u": f"/works/{wid}/{x['locus']}/#{p['id']}",
                             "t": p["text"], "x": p["excerpts"]})
    ui = dict(CATALOG["search"])
    ui["eras"] = CATALOG["eras"]
    ui["families"] = CATALOG["families"]
    return {"ui": ui, "eras": ERAS, "works": {w: lib.works[w]["title"] for w in lib.works}, "rows": rows}


def search_page(lib):
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("search.eyebrow"))}</p>
<h1>{e(t("search.heading"))}</h1><p class="dek">{e(t("search.dek"))}</p></header>
<form class="lg-search" id="search-form" role="search" action="/search/">
<label class="sr-only" for="q">{e(t("search.label"))}</label>
<input type="search" id="q" name="q" autocomplete="off" placeholder="{e(t("search.placeholder"))}">
<button class="button" type="submit">{e(t("search.go"))}</button></form>
<p class="lg-quiet">{e(t("search.tips"))}</p>
<div class="lg-search-body"><aside class="lg-facets" id="facets" aria-label="{e(t("search.narrow"))}"></aside>
<section id="results" aria-live="polite"></section></div>
<noscript><p>{e(t("search.noscript"))}</p></noscript>"""
    return page(lib, t("search.title"), body, "/search/", current="/read/",
                description=t("search.dek"), scripts=("search.js",))


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
    """The reader's saved comments; web/account.js fills it in."""
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("account.saved_title"))}</p>
<h1>{e(t("account.saved_heading"))}</h1><p class="dek">{e(t("account.saved_dek"))}</p></header>
<section id="saved-page"><p class="lg-quiet" id="saved-note" role="status"></p><ul class="lg-saved-list" id="saved-list"></ul></section>"""
    return page(lib, t("account.saved_title"), body, "/saved/", noindex=True)


def not_found_page(lib):
    """Served by Render for any address with no page (/404.html). It can be
    served at any depth, so every link on it is absolute; signing in from it
    returns to the home page."""
    body = f"""
<section class="auth lg-not-found"><div class="auth-card auth-message">
{MARK}
<h1>{e(t("not_found.heading"))}</h1>
<p class="auth-dek">{e(t("not_found.dek"))}</p>
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


def about_page(lib):
    parts = []
    for block in t("about.body"):
        if block.startswith("## "):
            title = block[3:]
            anchor = ' id="checked"' if title == "How excerpts are checked" else ""
            parts.append(f"<h2{anchor}>{e(title)}</h2>")
        else:
            parts.append("<p>" + re.sub(r"\*([^*]+)\*", r"<i>\1</i>", e(block)) + "</p>")
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("about.title"))}</p>
<h1>{e(t("about.heading"))}</h1><p class="dek">{e(t("about.dek"))}</p></header>
<div class="prose">{"".join(parts)}</div>"""
    return page(lib, t("about.title"), body, "/about/", current="/about/")


def rules_page(lib):
    """The editorial rules in plain words, and every version's rights, from
    the version records (roadmap, item 22)."""
    rules = "".join(f"<h3>{e(title)}</h3><p>{e(text)}</p>" for title, text in t("rules.rules"))
    docs = t("rules.procedure",
             adding=f'<a href="{GITHUB_URL}/blob/main/docs/adding-a-work.md">docs/adding-a-work.md</a>',
             references=f'<a href="{GITHUB_URL}/blob/main/docs/references.md">docs/references.md</a>')
    rows = []
    for wid in lib.ordered_works():
        w = lib.works[wid]
        for v in lib.versions_of(wid):
            lang = t("languages." + v["language"]) if v["language"] in CATALOG["languages"] else v["language"]
            kind = t("version.original" if v["kind"] == "original" else "version.translation", language=lang)
            src = (f'<a href="{e(v["full_text_url"])}" rel="noopener">{e(t("rules." + v["source_kind"]))}</a>'
                   if v["source_kind"] else "—")
            review = t("rules.reviewed", name=v["reviewer"]) if v["status"] == "reviewed" else t("rules.draft")
            rows.append(f'<tr><td><a href="/works/{wid}/#versions"><i>{e(w["title"])}</i></a><br>'
                        f'<span class="lg-quiet">{e(lib.author_of(wid)["name"])}</span></td>'
                        f'<td>{e(kind)}<br><span class="lg-quiet">{e(short_edition(v["edition"]))}</span></td>'
                        f'<td>{e(v["published"] or "—")}</td><td>{src}</td>'
                        f'<td>{e(v["rights"]["basis"])}<br><span class="lg-quiet">{e(v["rights"]["worldwide"])}</span></td>'
                        f'<td>{e(review)}</td></tr>')
    head = "".join(f"<th>{e(t('rules.col_' + k))}</th>"
                   for k in ("work", "version", "published", "source", "rights", "review"))
    body = f"""
<header class="page-head"><p class="eyebrow"><a href="/about/">{e(t("rules.eyebrow"))}</a></p>
<h1>{e(t("rules.heading"))}</h1><p class="dek">{e(t("rules.dek"))}</p></header>
<section class="prose lg-rules"><h2>{e(t("rules.rules_heading"))}</h2>{rules}<p>{docs}</p></section>
<section class="lg-block" id="rights"><h2>{e(t("rules.rights_heading"))}</h2><p class="lg-quiet">{e(t("rules.rights_note"))}</p>
<div class="lg-table-wrap"><table class="lg-table"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<p class="lg-quiet">{e(t("rules.report"))}</p></section>"""
    return page(lib, t("rules.title"), body, "/about/rules/", current="/about/", description=t("rules.dek"))


# --- Build --------------------------------------------------------------------

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
    for name in ("style.css", "logia.css", "site.js", "account.js", "reader.js", "search.js"):
        shutil.copy(os.path.join(WEB, name), os.path.join(SITE, name))
    shutil.copytree(os.path.join(WEB, "fonts"), os.path.join(SITE, "fonts"))
    write("/favicon.svg", FAVICON)
    pages = ["/"]
    write("/", home_page(lib))
    write("/read/", read_page(lib))
    pages.append("/read/")
    for book in dict.fromkeys(b for b, _c in lib.chapters):
        write(f"/{book.lower()}/", book_page(lib, book))
        pages.append(f"/{book.lower()}/")
    for book, chapter in lib.chapters:
        html_text, panel = chapter_page(lib, book, chapter, lib.chapters)
        write(chapter_url(book, chapter), html_text)
        os.makedirs(os.path.join(SITE, "panel"), exist_ok=True)
        with open(os.path.join(SITE, "panel", f"{book}.{chapter}.json"), "w", encoding="utf-8") as f:
            f.write(panel)
        pages.append(chapter_url(book, chapter))
    write("/commentators/", commentators_page(lib))
    pages.append("/commentators/")
    for author in lib.ordered_authors():
        write(f'/commentators/{author["id"]}/', author_page(lib, author))
        pages.append(f'/commentators/{author["id"]}/')
    for wid in lib.ordered_works():
        write(f"/works/{wid}/", work_page(lib, wid))
        pages.append(f"/works/{wid}/")
        for x in lib.texts.get(wid, []):
            write(f"/works/{wid}/{x['locus']}/", text_page(lib, wid, x))
            pages.append(f"/works/{wid}/{x['locus']}/")
    write("/about/", about_page(lib))
    pages.append("/about/")
    write("/about/rules/", rules_page(lib))
    pages.append("/about/rules/")
    write("/search/", search_page(lib))
    pages.append("/search/")
    write("/library/", library_page(lib))
    pages.append("/library/")
    with open(os.path.join(SITE, "linker.js"), "w", encoding="utf-8") as f:
        f.write(linker_script(lib))
    write("/linker/", linker_page(lib))
    pages.append("/linker/")
    write("/topics/", topics_page(lib))
    pages.append("/topics/")
    for tp in lib.topics:
        write(f'/topics/{tp["id"]}/', topic_page(lib, tp))
        pages.append(f'/topics/{tp["id"]}/')
    write("/signed-in/", signed_in_page(lib))
    write("/saved/", saved_page(lib))
    write("/404.html", not_found_page(lib))
    os.makedirs(os.path.join(SITE, "data"))
    with open(os.path.join(SITE, "data", "search.json"), "w", encoding="utf-8") as f:
        json.dump(search_index(lib), f, ensure_ascii=False, separators=(",", ":"))
    for book, chapter in sorted(lib.coverage()):
        with open(os.path.join(SITE, "data", f"{book}.{chapter}.json"), "w", encoding="utf-8") as f:
            json.dump(chapter_file(lib, book, chapter), f, ensure_ascii=False, separators=(",", ":"))
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"<url><loc>{SITE_URL}{p}</loc></url>\n" for p in pages) + "</urlset>\n")
    write("/robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    api.write(lib, SITE, SITE_URL, types.SimpleNamespace(
        ref_parts=ref_parts, chapter_url=chapter_url, default_wording=default_wording, locus_label=locus_label))
    print(f"site/: {len(pages)} pages ({len(lib.chapters)} chapters), {len(lib.works)} works, "
          f"{len(lib.authors)} commentators, {len(lib.comments)} excerpts")


if __name__ == "__main__":
    build()
