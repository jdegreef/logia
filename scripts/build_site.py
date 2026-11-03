"""Build the Logia site into site/.

    python3 scripts/build_site.py

Reads the library (library/authors, works, comments, corrections), the Bible
text (bible/owb), the interface text (i18n/en.json) and web/, and writes a
static site:

    /                        home
    /read/                   every book, by testament, with its chapters
    /<book>/                 a book: its chapters and who comments on it
    /<book>/<chapter>/       the reader: Bible text and the commentary panel
    /commentators/           every commentator, by era
    /commentators/<author>/  one commentator: biography, works, comments
    /works/<work>/           one commentary: edition, rights, every excerpt
    /about/                  what Logia is and how its text is checked

The look, the header, footer and settings menu follow openwordbible.org:
web/style.css and the fonts are the Open Word Bible's own, and web/site.js
is taken from its site script. web/logia.css adds Logia's own parts.
"""
import glob
import html
import json
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
WEB = os.path.join(ROOT, "web")
LANG = "en"
SITE_URL = "https://logia.faith"
OWB_SITE = "https://openwordbible.org"
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
                 ("excerpt", "preview", ("preview", "full")))
LEADING_GAPS = {"compact": 5, "normal": 7, "spacious": 9}

# Applies saved settings before the first paint, so a page never flashes the
# default colours or text size. Mirrors web/site.js.
BOOT_SCRIPT = ("try{var d=document.documentElement,t=localStorage.getItem('logia-theme');"
               "if(['auto','light','sepia','dark','night','contrast'].indexOf(t)>=0)d.setAttribute('data-theme',t);"
               "var p={" + ",".join(f"{name}:{[v for v in values if v != default]!r}"
                                   for name, default, values in DISPLAY_PREFS) + "};"
               "for(var k in p){var v=localStorage.getItem('logia-'+k);"
               "if(p[k].indexOf(v)>=0)d.setAttribute('data-'+k,v)}}catch(e){}")

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
        self.comments = []
        for p in sorted(glob.glob(os.path.join(ROOT, "library", "comments", "*", "*.json"))):
            data = load(p)
            work = data["work"]
            for entry in data["entries"]:
                text = entry["text"]
                for a, b in self.fixes.get(work, []):
                    text = text.replace(a, b)
                self.comments.append({**entry, "work": work, "text": text,
                                      "source_url": urls.get((work, entry["sources"][0]), self.works[work]["full_text_url"])})
        # The chapters whose Bible text is imported, in canonical order.
        order = list(self.books)
        self.chapters = sorted(
            (tuple(os.path.basename(p)[:-5].split(".")) for p in glob.glob(os.path.join(ROOT, "bible", "owb", "en", "*.json"))),
            key=lambda bc: (order.index(bc[0]), int(bc[1])))
        self.chapters = [(b, int(c)) for b, c in self.chapters]

    def bible(self, book, chapter):
        return load(os.path.join(ROOT, "bible", "owb", "en", f"{book}.{chapter}.json"))

    def author_of(self, work_id):
        return self.authors[self.works[work_id]["author"]]

    def ordered_works(self, ids=None):
        ids = self.works if ids is None else ids
        return sorted(ids, key=lambda w: (ERAS.index(self.author_of(w)["era"]), self.author_of(w)["died"], w))

    def ordered_authors(self):
        return sorted(self.authors.values(), key=lambda a: (ERAS.index(a["era"]), a["died"]))

    def in_chapter(self, book, chapter, last_verse):
        """{work: [entries clipped to this chapter as verse numbers]}."""
        out = {}
        for c in self.comments:
            sb, sc, sv = ref_parts(c["start"])
            eb, ec, ev = ref_parts(c["end"])
            if sb != book or not (sc <= chapter <= ec):
                continue
            out.setdefault(c["work"], []).append({
                "start": sv if sc == chapter else 1, "end": ev if ec == chapter else last_verse,
                "heading": c["heading"], "excerpt": c["text"], "source_url": c["source_url"]})
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
        if pref in ("motion", "level", "excerpt"):
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


def page(lib, title, body, path, current="", description="", scripts=()):
    full = f"{title} · Logia" if title != "Logia" else "Logia"
    description = description or t("site.description")
    own = e(SITE_URL + path)
    js = "".join(f'\n<script src="/{s}" defer></script>' for s in ("site.js",) + tuple(scripts))
    return f"""<!doctype html>
<html lang="{LANG}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{own}">
<meta property="og:site_name" content="Logia">
<meta property="og:type" content="website">
<meta property="og:url" content="{own}">
<meta property="og:title" content="{e(full)}">
<meta property="og:description" content="{e(description)}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta name="theme-color" content="#f4eee3" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#2a241c" media="(prefers-color-scheme: dark)">
<script>{BOOT_SCRIPT}</script>
<link rel="preload" href="/fonts/hanken-grotesk-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/fonts/gentium-book-plus-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/style.css">
<link rel="stylesheet" href="/logia.css">{js}
</head>
<body>
<a class="skip" href="#main">{e(t("site.skip"))}</a>
{site_header(lib, current, path)}
<main class="wrap" id="main" tabindex="-1">
{body}
</main>
{site_footer(lib)}
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


def chapter_page(lib, book, chapter, all_chapters):
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
            "work_url": f"/works/{wid}/", "entries": sorted(by_work[wid], key=lambda x: (x["start"], x["end"]))})
    ui = dict(CATALOG["reader"])
    ui["eras"] = CATALOG["eras"]
    ui["levels"] = CATALOG["level"]
    data = {**bible, "bookName": name, "commentaries": commentaries, "ui": ui, "eras": ERAS,
            "books": {k: v["en"] for k, v in lib.books.items()},
            "available": [f"{b}.{c}" for b, c in all_chapters], "owb_site": OWB_SITE}
    heading = next((r["heading"] for r in bible["records"] if r["heading"]), f"{name} {chapter}")
    # The text as plain Balanced verses, for search engines and readers
    # without JavaScript; web/reader.js replaces it.
    verses = {}
    for r in bible["records"]:
        for p in r["pieces"]:
            verses[p[0]] = verses.get(p[0], "") + p[1]
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
        f'{e(c["author"])}, <a href="{e(lib.works[c["work_id"]]["full_text_url"])}" rel="noopener"><i>{e(c["title"])}</i></a>'
        for c in commentaries)
    credits = f'<p class="cx-credits">{t("chapter.credits", works=works_credit)}</p>' if commentaries else ""
    owb_link = f'<a href="{OWB_SITE}{chapter_url(book, chapter)}" rel="noopener">Open Word Bible</a>'
    first_ref = f"{name} {chapter}:{bible['verses'][0]}"
    tabs = "".join(
        f'<button role="tab" id="tab-{k}" data-tab="{k}" aria-selected="{"true" if k == "comm" else "false"}">'
        f'{e(t("chapter.tab_" + k))}<span class="cx-n" id="n-{k}"></span></button>' for k in ("comm", "words", "notes", "xref"))
    body = f"""
<div class="cx-layout">
<article class="cx-passage">
<p class="cx-eyebrow"><a href="/{book.lower()}/">{e(name)}</a> · {e(t("chapter.eyebrow", chapter=chapter))}</p>
<h1>{e(heading)}</h1>
<p class="cx-sub">{e(t("chapter.pick"))}</p>
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
{credits}
<script type="application/json" id="chapter-data">{json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")}</script>"""
    n = len(commentaries)
    description = (t("chapter.description", book=name, chapter=chapter, n=n) if n
                   else t("chapter.description_none", book=name, chapter=chapter))
    return page(lib, f"{name} {chapter}", body, chapter_url(book, chapter), current="/read/",
                description=description, scripts=("reader.js",))


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
        f'<span>{e(short_edition(lib.works[w]["edition"]))}</span></a></li>' for w in works)
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


def work_page(lib, wid):
    w, a = lib.works[wid], lib.author_of(wid)
    comments = sorted((c for c in lib.comments if c["work"] == wid), key=order_key)
    source = (t("work.source_scan", n=len(lib.fixes.get(wid, []))) if w["source_kind"] == "scan"
              else t("work.source_digital"))
    facts = [(t("work.original"), w["original_language"]), (t("work.edition"), w["edition"])]
    if w["translation"]:
        facts.append((t("work.translation"), w["translation"]))
    facts += [(t("work.published"), str(w["published"])), (t("work.source"), source),
              (t("work.rights"), f'{w["rights"]["basis"]}; {w["rights"]["worldwide"]}'),
              (t("work.in_logia"), t("work.excerpts", n=len(comments)))]
    dl = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in facts)
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
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("work.eyebrow"))} · {e(t("eras." + a["era"]))}</p>
<h1>{e(w["title"])}</h1><p class="dek">{t("work.by", name=f'<a href="/commentators/{a["id"]}/">{e(a["name"])}</a>')} ({e(a["dates"])})</p>
<p class="actions"><a class="button ghost" href="{e(w["full_text_url"])}" rel="noopener">{e(t("work.full_text"))} ↗</a></p></header>
<dl class="lg-facts">{dl}</dl>
<section class="lg-block"><h2>{e(t("work.front_to_back"))}</h2><p class="lg-quiet">{e(t("work.front_to_back_note"))}</p>
<div class="lg-book">{"".join(full)}</div></section>"""
    return page(lib, w["title"], body, f"/works/{wid}/", current="/commentators/",
                description=f'{a["name"]}, {w["title"]}: {len(comments)} excerpts in Logia.')


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


# --- Build --------------------------------------------------------------------

def write(rel, text):
    path = os.path.join(SITE, rel.strip("/"), "index.html") if not rel.endswith((".svg", ".xml", ".txt")) \
        else os.path.join(SITE, rel.strip("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build():
    lib = Library()
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(SITE)
    for name in ("style.css", "logia.css", "site.js", "reader.js"):
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
        write(chapter_url(book, chapter), chapter_page(lib, book, chapter, lib.chapters))
        pages.append(chapter_url(book, chapter))
    write("/commentators/", commentators_page(lib))
    pages.append("/commentators/")
    for author in lib.ordered_authors():
        write(f'/commentators/{author["id"]}/', author_page(lib, author))
        pages.append(f'/commentators/{author["id"]}/')
    for wid in lib.ordered_works():
        write(f"/works/{wid}/", work_page(lib, wid))
        pages.append(f"/works/{wid}/")
    write("/about/", about_page(lib))
    pages.append("/about/")
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"<url><loc>{SITE_URL}{p}</loc></url>\n" for p in pages) + "</urlset>\n")
    write("/robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    print(f"site/: {len(pages)} pages ({len(lib.chapters)} chapters), {len(lib.works)} works, "
          f"{len(lib.authors)} commentators, {len(lib.comments)} excerpts")


if __name__ == "__main__":
    build()
