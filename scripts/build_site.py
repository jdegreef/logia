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
    /commentators/           every commentator, by era
    /commentators/<author>/  one commentator: biography, works, comments
    /works/<work>/           one commentary: edition, rights, every excerpt
    /works/<work>/<n>/       a whole homily or tractate (library/texts)
    /about/                  what Logia is and how its text is checked

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
                "quotedIn": self.quoted_in_rows(c), "inFull": self.in_full.get(c["id"])})
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
         preload=()):
    full = f"{title} · Logia" if title != "Logia" else "Logia"
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
<meta property="og:description" content="{e(description)}">{'<meta name="robots" content="noindex">' if noindex else ""}
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


def search_box(lib, sid, cls="hero-search"):
    """A search box that goes to a verse, a book or a commentator."""
    return (f'<form class="lg-search {cls}" role="search" action="/read/" autocomplete="off">'
            f'<span class="hero-search-ico" aria-hidden="true">{SEARCH_ICON}</span>'
            f'<input type="search" name="q" id="{sid}" placeholder="{e(t("search.placeholder"))}" aria-label="{e(t("search.label"))}" '
            f'role="combobox" aria-expanded="false" aria-controls="{sid}-list" aria-autocomplete="list">'
            f'<button type="submit" class="button">{e(t("search.go"))}</button>'
            f'<ul class="lg-sugg" id="{sid}-list" role="listbox" aria-label="{e(t("search.label"))}" hidden></ul></form>'
            f'<script type="application/json" id="search-data">{search_json(lib)}</script>')


SEARCH_ICON = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
               'stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>')


# --- Pages --------------------------------------------------------------------

# The verse the home page opens with, and the eras of the three voices shown
# beside it: the earliest, the Reformation and the latest.
HOME_VERSE = "JHN.3.16"
HOME_ERAS = ("Early church", "Reformation", "The 1800s")
# Well-known passages the home page offers as a way in, by chapter.
HOME_PASSAGES = (("JHN", 1), ("JHN", 3), ("JHN", 6), ("JHN", 10), ("JHN", 11), ("JHN", 14), ("JHN", 17), ("JHN", 20))


def home_verse(lib):
    """The home page's verse, its text, and a few words from three voices on
    it, copied from their excerpts as they read (a first paragraph that only
    repeats the verse is passed over)."""
    book, chapter, verse = ref_parts(HOME_VERSE)
    if (book, chapter) not in lib.chapters:
        return ""
    text = plain_verses(lib.bible(book, chapter)).get(verse, "")
    on = [c for c in lib.comments if c["start"] == c["end"] == HOME_VERSE]
    if not on:
        return ""
    voices = []
    for era in HOME_ERAS:
        for wid in lib.ordered_works({c["work"] for c in on}):
            a = lib.author_of(wid)
            if a["era"] != era:
                continue
            c = min((c for c in on if c["work"] == wid), key=lambda c: c["id"])
            paras = [p for p in c["text"].split("\n\n") if p.strip()]
            lead = paras[1] if len(paras) > 1 and len(paras[0].split()) < 30 else paras[0]
            voices.append(f'<li><p class="lg-vv-who"><a href="/commentators/{a["id"]}/"><b>{e(a["name"])}</b></a> '
                          f'<span>{e(t("eras." + era))} · {e(a["dates"])}</span></p>'
                          f'<p class="lg-vv-text">{e(snippet(lead, 26))}</p></li>')
            break
    n = len({c["work"] for c in on})
    href = chapter_url(book, chapter) + f"#v{verse}"
    ref = f'{lib.books[book]["en"]} {chapter}:{verse}'
    return (f'<section class="votd lg-votd" aria-labelledby="h-votd"><p class="eyebrow" id="h-votd">{e(t("home.verse_voices"))}</p>'
            f'<blockquote><p class="votd-text">{e(text)}</p></blockquote>'
            f'<footer><a class="votd-ref" href="{href}">{e(ref)}</a></footer>'
            f'<ul class="lg-vv">{"".join(voices)}</ul>'
            f'<p class="lg-vv-all"><a class="votd-why" href="{href}">{e(t("home.all_voices", n=n, ref=ref))} {icon("arrow", 15)}</a></p></section>')


def home_page(lib):
    cov = lib.coverage()
    first = sorted(cov)[0] if cov else lib.chapters[0]
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
    body = f"""
<section class="hero">
<p class="eyebrow">{e(t("home.verse"))}</p>
<h1>{e(t("home.title"))}</h1>
<p class="hero-sub">{e(t("home.lead"))}</p>
<p class="actions"><a class="button" href="/" data-resume="{e(t("home.resume"))}" hidden></a><a class="button" href="{chapter_url(*first)}">{e(t("home.start"))}</a>
<a class="button ghost" href="/read/">{e(t("home.browse"))}</a></p>
{search_box(lib, "home-q")}
<p class="hero-try">{e(t("search.try"))} <a href="/jhn/1/#v1">John 1:1</a> <a href="/jhn/3/#v16">John 3:16</a> <a href="/jhn/11/#v25">John 11:25</a> <a href="/jhn/14/#v6">John 14:6</a></p>
</section>
{home_verse(lib)}
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
                 f'{e(t("book.commentaries", n=n))}</span>' if n else "")
        rows.append(f'<li><a href="{chapter_url(book, c)}"><span class="lg-toc-n">{c}</span>'
                    f'<span class="lg-toc-title">{e(lib.chapter_title(book, c) or f"{name} {c}")}</span>{badge}'
                    f'<span class="lg-quiet">{e(t("book.verses", n=verses))}</span></a></li>')
    works = {c["work"] for c in lib.comments if c["start"].startswith(book + ".")}
    people = "".join(
        f'<li><a href="/works/{w}/"><b>{e(lib.author_of(w)["name"])}</b> <span>{e(lib.works[w]["title"])}</span></a></li>'
        for w in lib.ordered_works(works))
    who = (f'<section class="lg-block"><h2>{e(t("book.commentators", book=name))}</h2><ul class="lg-people lg-wide">{people}</ul></section>'
           if people else "")
    codes = list(lib.books)
    testament = "old" if codes.index(book) < OT_BOOKS else "new"
    start = f'<p class="actions"><a class="button" href="{chapter_url(book, have[0])}">{e(t("book.start", book=name, chapter=have[0]))}</a></p>' if have else ""
    body = f"""
<header class="page-head"><p class="eyebrow"><a href="/read/">{e(t("read.title"))}</a> · <a href="/read/#{"ot" if testament == "old" else "nt"}">{e(t("testaments." + testament))}</a> · {e(t("canon." + canon_section(lib, book)))}</p>
<h1>{e(name)}</h1><p class="dek">{e(t("book.dek", n=total, done=done))}</p>{start}</header>
<section class="lg-block"><h2>{e(t("book.chapters"))}</h2><ol class="lg-toc">{"".join(rows)}</ol></section>
{who}"""
    return page(lib, name, body, f"/{book.lower()}/", current="/read/")


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
# verses: enough for the timeline, the summary and the gold verse numbers.
INDEX_FIELDS = ("work_id", "author", "short_name", "era", "died")


def comm_file(commentaries, cited_by):
    """The commentary file's text (None when there is nothing in it), and the page's index."""
    index = [{**{k: w[k] for k in INDEX_FIELDS}, "entries": [{"start": x["start"], "end": x["end"]} for x in w["entries"]]}
             for w in commentaries]
    if not commentaries and not any(cited_by.values()):
        return None, index
    return json.dumps({"commentaries": commentaries, "citedBy": cited_by},
                      ensure_ascii=False, separators=(",", ":")), index


def plain_verses(bible):
    """{verse: its Balanced text at the default wording}, as the reader shows it."""
    verses = {}
    for r in bible["records"]:
        for p in r["pieces"]:
            verses[p[0]] = verses.get(p[0], "") + default_wording(p[1])
    return {v: " ".join(x.split()) for v, x in verses.items()}


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
    heading = lib.chapter_title(book, chapter) or f"{name} {chapter}"
    # The text as plain Balanced verses, for search engines and readers
    # without JavaScript; web/reader.js replaces it.
    verses = plain_verses(bible)
    plain = " ".join(f'<span class="cx-verse"><span class="cx-vn">{v}</span>{e(verses[v])}</span>'
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
<dialog class="cx-compare" id="compare" aria-labelledby="compare-ref">
<div class="cx-compare-head"><h2 id="compare-ref"></h2>
<button type="button" class="cx-compare-close" data-close aria-label="{e(t("reader.close"))}">{icon("close", 20)}</button></div>
<p class="cx-compare-text" id="compare-text"></p>
<div class="cx-picks" id="compare-picks"></div>
<div class="cx-cols" id="compare-cols"></div>
</dialog>
{credits}
<script type="application/json" id="chapter-data">{json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")}</script>"""
    n = len(commentaries)
    description = (t("chapter.description", book=name, chapter=chapter, n=n) if n
                   else t("chapter.description_none", book=name, chapter=chapter))
    return page(lib, f"{name} {chapter}", body, chapter_url(book, chapter), current="/read/",
                description=description, scripts=("reader.js",), preload=(comm_url,) if comm_url else ()), panel, comm


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
        initials = "".join(w[0] for w in a["name"].replace(".", " ").split() if w[0].isupper())
        initials = initials[0] + initials[-1] if len(initials) > 1 else initials
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
{sections}"""
    return page(lib, t("commentators.title"), body, "/commentators/", current="/commentators/")


def excerpt_list(lib, comments, show_work=False):
    """Excerpts grouped by chapter, each chapter closed but the first, with a
    bar of the chapters above them: one row per verse or range, its first
    words, how many passages there are, and a link to the verse in the reader."""
    out, rows = [], {}
    for c in comments:
        b, ch, v = ref_parts(c["start"])
        _, ech, ev = ref_parts(c["end"])
        rows.setdefault((b, ch), {}).setdefault((v, ech, ev, c["work"] if show_work else ""), []).append(c)
    bar = "".join(f'<a href="#ch-{b.lower()}-{ch}">{e(lib.books[b]["en"]) + " " if len({x for x, _y in rows}) > 1 else ""}{ch}</a>'
                  for b, ch in rows)
    out.append(f'<nav class="lg-chbar" aria-label="{e(t("commentators.chapters"))}">{bar}</nav>')
    works = {c["work"] for c in comments}
    for n, ((b, ch), group) in enumerate(rows.items()):
        name = f'{lib.books[b]["en"]} {ch}'
        passages = sum(len(cs) for cs in group.values())
        whole = (f'<p class="lg-chlink"><a href="{work_chapter_url(next(iter(works)), b, ch)}">'
                 f'{e(t("commentators.in_order", chapter=name))} {icon("arrow", 15)}</a></p>' if len(works) == 1 else "")
        out.append(f'<details class="lg-ch" id="ch-{b.lower()}-{ch}"{" open" if n == 0 else ""}><summary><b>{e(name)}</b>'
                   f'<span class="lg-quiet">{e(t("commentators.passages", n=passages))}</span>{icon("chevron", 16, "icon lg-caret")}</summary>'
                   f'{whole}<ul class="lg-excerpts">')
        for (v, ech, ev, work), cs in group.items():
            ref = f"{ch}:{v}" + (f"–{ev}" if (ech, ev) != (ch, v) else "") if ech == ch else f"{ch}:{v}–{ech}:{ev}"
            more = f'<span class="lg-quiet">{e(t("commentators.passages", n=len(cs)))}</span>' if len(cs) > 1 else ""
            title = f'<span class="lg-quiet">{e(lib.works[work]["title"])}</span>' if work else ""
            h = cs[0]["heading"]
            lead = re.sub(r"^\s*\d+\.\s*", "", cs[0]["text"]).lower()
            lemma = f'<i>{e(h)}</i> ' if h and not lead.startswith(h.lower().strip(" .")) else ""
            out.append(f'<li><p class="lg-ex-ref"><a href="{chapter_url(b, ch)}#v{v}" title="{e(lib.books[b]["en"])} {e(ref)}"><b>{e(ref)}</b></a>{more}</p>'
                       f'<div>{title}<p>{lemma}{e(snippet(cs[0]["text"]))}</p></div></li>')
        out.append("</ul></details>")
    return "".join(out)


def order_key(c):
    b, ch, v = ref_parts(c["start"])
    return (b, ch, v, c["id"])


def author_page(lib, author):
    works = lib.ordered_works([w for w, x in lib.works.items() if x["author"] == author["id"]])
    comments = sorted((c for c in lib.comments if c["work"] in works), key=order_key)
    bio = "".join(f"<p>{e(p)}</p>" for p in author["bio"].split("\n\n"))
    draft = f'<p><span class="lg-pill lg-pill-draft">{e(t("commentators.bio_draft"))}</span></p>' if author["bio_status"] == "ai_draft" else ""
    # The facts beside the biography: when they lived, their tradition, the
    # language they wrote in, their works here and how much they cover.
    facts = [(t("commentators.lived"), author["dates"]), (t("commentators.era"), t("eras." + author["era"])),
             (t("commentators.tradition"), author["tradition"]),
             (t("work.original"), " · ".join(dict.fromkeys(lib.works[w]["original_language"] for w in works)))]
    for w in works:
        x = lib.works[w]
        facts.append((t("commentators.work"), f'<a href="/works/{w}/"><i>{e(x["title"])}</i></a>'
                      + (f'<span class="lg-quiet">{e(short_edition(x["edition"]))}</span>' if x["edition"] else "")))
    covered = {}
    for c in comments:
        b, ch, v = ref_parts(c["start"])
        _, ech, ev = ref_parts(c["end"])
        covered.setdefault(b, set()).update((ch, x) for x in lib.verses(b, ch) if v <= x and (ech != ch or x <= ev))
    for b, vs in covered.items():
        total = sum(len(lib.verses(b, ch)) for bb, ch in lib.chapters if bb == b)
        facts.append((t("commentators.covers"), f'<span class="lg-meter"><span style="width:{100 * len(vs) / total:.0f}%"></span></span>'
                      + e(t("commentators.coverage", book=lib.books[b]["en"], n=len(vs), total=total))))
    dl = "".join(f"<div><dt>{e(k)}</dt><dd>{v if k in (t('commentators.work'), t('commentators.covers')) else e(v)}</dd></div>"
                 for k, v in facts)
    body = f"""
<div class="lg-profile lg-era-{ERAS.index(author["era"])}">
<div class="lg-profile-main"><header class="page-head lg-person-head"><p class="eyebrow"><a href="/commentators/">{e(t("commentators.title"))}</a> · {e(t("eras." + author["era"]))}</p>
<h1>{e(author["name"])}</h1><p class="dek">{e(author["dates"])} · {e(author["tradition"])}</p></header>
<section class="prose lg-bio">{bio}{draft}</section></div>
<dl class="lg-facts-card">{dl}</dl></div>
<section class="lg-block"><h2>{e(t("commentators.comments_on", name=author["name"]))}</h2>{excerpt_list(lib, comments, show_work=len(works) > 1)}</section>"""
    return page(lib, author["name"], body, f'/commentators/{author["id"]}/', current="/commentators/",
                description=author["bio"].split("\n\n")[0])


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
    # Rights, said plainly: the status in the US and worldwide as pills, and
    # the record's own words beneath.
    r = w["rights"]
    us = r["basis"].lower().startswith("public domain")
    world = r["worldwide"].lower()
    pills = (f'<span class="lg-pill {"lg-pill-ok" if us else "lg-pill-draft"}">{e(t("work.rights_us" if us else "work.rights_us_check"))}</span> '
             f'<span class="lg-pill {"lg-pill-ok" if world.startswith("public domain") else "lg-pill-draft"}">'
             f'{e(t("work.rights_world" if world.startswith("public domain") else "work.rights_world_check"))}</span>')
    dl += (f'<dt>{e(t("work.rights"))}</dt><dd><span class="lg-pills">{pills}</span>'
           f'<span class="lg-quiet lg-rights-note">{e(r["basis"])}; {e(r["worldwide"])}</span></dd>')
    # The edition as a citation gives it: up to its first note in brackets
    # or after a semicolon (which name the scan or the series).
    edition = re.match(r"^[^;(]+", w["edition"])[0].strip().rstrip(",.")
    citation = t("work.citation", name=a["name"], title=w["title"], edition=edition)
    cite = (f'<div class="lg-cite-box"><p class="label">{e(t("work.cite"))}</p><p class="lg-cite-text">{e(citation)}</p>'
            f'<button type="button" class="button ghost lg-copy" data-copy="{e(citation)}" data-done="{e(t("work.cite_copied"))}">'
            f'{e(t("work.cite_copy"))}</button></div>')
    contents = work_contents(lib, wid, comments)
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
<p class="actions"><a class="button ghost" href="{e(w["full_text_url"])}" rel="noopener">{e(t("work.full_text"))} ↗</a></p></header>
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
    on = sorted((c for c in lib.comments if c["start"] == c["end"] == HOME_VERSE), key=lambda c: (lib.ordered_works().index(c["work"]), c["id"]))
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


# The correction the About page shows, from library/corrections/.
ABOUT_FIX = ("ryle", "Let ns")


def checking_figure(lib):
    """How an excerpt reaches Logia, step by step, and one real correction
    pair as the build applies it."""
    steps = "".join(f'<li><b>{e(title)}</b><span>{e(text)}</span></li>' for title, text in t("about.steps"))
    work, wrong = ABOUT_FIX
    right = dict(lib.fixes.get(work, [])).get(wrong)
    fix = ""
    if right:
        fix = (f'<p class="lg-fix"><span class="label">{e(t("about.fix", work=lib.author_of(work)["name"], n=f"{len(lib.fixes[work]):,}"))}</span>'
               f'<del>{e(wrong)}</del> {icon("arrow", 15)} <ins>{e(right)}</ins></p>')
    total = sum(len(v) for v in lib.fixes.values())
    return (f'<figure class="lg-steps-fig"><ol class="lg-steps">{steps}</ol>{fix}'
            f'<figcaption class="lg-quiet">{e(t("about.steps_note", n=f"{len(lib.comments):,}", fixes=f"{total:,}"))}</figcaption></figure>')


def about_page(lib):
    parts = []
    for block in t("about.body"):
        if block.startswith("## "):
            title = block[3:]
            anchor = ' id="checked"' if title == "How excerpts are checked" else ""
            parts.append(f"<h2{anchor}>{e(title)}</h2>")
            if anchor:
                parts.append(checking_figure(lib))
        else:
            parts.append("<p>" + re.sub(r"\*([^*]+)\*", r"<i>\1</i>", e(block)) + "</p>")
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("about.title"))}</p>
<h1>{e(t("about.heading"))}</h1><p class="dek">{e(t("about.dek"))}</p></header>
<div class="prose">{"".join(parts)}</div>"""
    return page(lib, t("about.title"), body, "/about/", current="/about/")


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
    for name in ("style.css", "logia.css", "site.js", "account.js", "logia.js", "reader.js"):
        with open(os.path.join(SITE, name), "w", encoding="utf-8") as f:
            f.write(published(name))
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
        html_text, panel, comm = chapter_page(lib, book, chapter, lib.chapters)
        write(chapter_url(book, chapter), html_text)
        for folder, text in (("panel", panel), ("comm", comm)):
            if text is None:
                continue
            os.makedirs(os.path.join(SITE, folder), exist_ok=True)
            with open(os.path.join(SITE, folder, f"{book}.{chapter}.json"), "w", encoding="utf-8") as f:
                f.write(text)
        pages.append(chapter_url(book, chapter))
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
    write("/about/", about_page(lib))
    pages.append("/about/")
    write("/signed-in/", signed_in_page(lib))
    write("/saved/", saved_page(lib))
    write("/404.html", not_found_page(lib))
    os.makedirs(os.path.join(SITE, "data"))
    for book, chapter in sorted(lib.coverage()):
        with open(os.path.join(SITE, "data", f"{book}.{chapter}.json"), "w", encoding="utf-8") as f:
            json.dump(chapter_file(lib, book, chapter), f, ensure_ascii=False, separators=(",", ":"))
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"<url><loc>{SITE_URL}{p}</loc></url>\n" for p in pages) + "</urlset>\n")
    write("/robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    print(f"site/: {len(pages)} pages ({len(lib.chapters)} chapters), {len(lib.works)} works, "
          f"{len(lib.authors)} commentators, {len(lib.comments)} excerpts")


if __name__ == "__main__":
    build()
