"""Build the Logia site into site/.

    python3 scripts/build_site.py

Reads the library (library/works, library/comments, library/corrections,
library/citations), the
Bible text (bible/owb) and the page templates (web/), and writes static pages:
site/index.html and one page per imported chapter, site/<book>/<chapter>/.
Each chapter page carries its own data inline, so the site needs no server.
"""
import glob
import html
import json
import os
import re
import shutil

import scripture

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
OWB_SITE = "https://openwordbible.org"
ERAS = ["Early church", "Middle Ages", "Reformation", "Puritans and the 1700s", "The 1800s"]
NUMBER_WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight",
                9: "Nine", 10: "Ten", 11: "Eleven", 12: "Twelve"}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ref_parts(ref):
    book, chapter, verse = ref.split(".")
    return book, int(chapter), int(verse)


def death_year(work):
    years = re.findall(r"\d{3,4}", work["author_dates"])
    return int(years[-1]) if years else 0


def load_library():
    works = {w["id"]: w for w in (load(p) for p in glob.glob(os.path.join(ROOT, "library", "works", "*.json")))}
    fixes = {}
    for p in glob.glob(os.path.join(ROOT, "library", "corrections", "*.json")):
        c = load(p)
        fixes[c["work"]] = [(x["from"], x["to"]) for x in c["corrections"]]
    urls = {}
    for f in load(os.path.join(ROOT, "sources", "manifest.json"))["files"]:
        urls[(f["work"], os.path.basename(f["path"]))] = f["url"]
    cites = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "library", "citations", "*", "*.json"))):
        for c in load(p)["citations"]:
            if c["status"] != "rejected":
                cites.setdefault(c["in"], []).append(
                    {k: c[k] for k in ("at", "text", "start", "end", "status")})
    comments = []
    for p in sorted(glob.glob(os.path.join(ROOT, "library", "comments", "*", "*.json"))):
        data = load(p)
        work = data["work"]
        for e in data["entries"]:
            text = e["text"]
            for a, b in fixes.get(work, []):
                text = text.replace(a, b)
            comments.append({**e, "work": work, "text": text, "cites": cites.get(e["id"], []),
                             "source_url": urls.get((work, e["sources"][0]), works[work]["full_text_url"])})
    return works, comments


def cite_link(ref, pages):
    """Where a cited verse is read: its Logia chapter page if there is one,
    else the Open Word Bible, which has no deuterocanonical books."""
    book, chapter, verse = scripture.parse(ref)
    if (book, chapter) in pages:
        return f"/{book.lower()}/{chapter}/#v{verse}"
    if book in scripture.DEUTEROCANON:
        return None
    return f"{OWB_SITE}/{book.lower()}/{chapter}/"


SENTENCE_END = re.compile(r"[.?!][\"”’)]*\s+(?=[A-Z“\"‘(\[])|\n\s*\n")


def snippet(text, at, length):
    """The sentence a citation sits in, copied from the excerpt as it reads
    (cut at about 220 characters on either side, marked with …)."""
    lo, hi = max(0, at - 220), min(len(text), at + length + 220)
    ends = [m.end() for m in SENTENCE_END.finditer(text, lo, at)]
    s = ends[-1] if ends else lo
    if not ends and s > 0:
        s = text.find(" ", s) + 1
    m = SENTENCE_END.search(text, at + length, hi)
    e = m.start() + 1 if m else hi
    if not m and e < len(text):
        e = text.rfind(" ", at + length, e)
    if text[e - 1:e] not in ".?!" and m:
        e = m.start() + 1
    piece = " ".join(text[s:e].split())
    return ("… " if s > 0 and not ends else "") + piece + (" …" if not m and e < len(text) else "")


def cites_for(c, pages):
    return [{**x, "label": scripture.label(x["start"], x["end"]), "href": cite_link(x["start"], pages)}
            for x in c["cites"]]


def chapter_data(bible, book_name, works, comments, pages=frozenset()):
    book, chapter = bible["book"], bible["chapter"]
    first, last = bible["verses"][0], bible["verses"][-1]
    by_work = {}
    for c in comments:
        sb, sc, sv = ref_parts(c["start"])
        eb, ec, ev = ref_parts(c["end"])
        if sb != book or not (sc <= chapter <= ec):
            continue
        start = sv if sc == chapter else first
        end = ev if ec == chapter else last
        by_work.setdefault(c["work"], []).append(
            {"id": c["id"], "start": start, "end": end, "heading": c["heading"], "excerpt": c["text"],
             "locus": c.get("locus"), "source_url": c["source_url"], "cites": cites_for(c, pages)})
    commentaries = []
    for wid, entries in by_work.items():
        w = works[wid]
        commentaries.append({
            "work_id": wid, "author": w["author"], "author_dates": w["author_dates"], "tradition": w["tradition"],
            "era": w["era"], "title": w["title"], "divisions": w["divisions"], "edition": w["edition"],
            "full_text_url": w["full_text_url"], "scan": w["source_kind"] == "scan",
            "entries": sorted(entries, key=lambda e: (e["start"], e["end"])),
        })
    commentaries.sort(key=lambda w: (ERAS.index(w["era"]) if w["era"] in ERAS else 99, death_year(works[w["work_id"]])))

    # The other way: excerpts anywhere in the library that cite a verse of
    # this chapter while commenting on another verse.
    cited_by = {str(v): [] for v in bible["verses"]}
    for c in comments:
        cb, cc, cv = ref_parts(c["start"])
        _, ec, ev = ref_parts(c["end"])
        for x in c["cites"]:
            b, ch, v = scripture.parse(x["start"])
            _, ch2, v2 = scripture.parse(x["end"])
            if b != book or not (ch <= chapter <= ch2):
                continue
            for verse in range(v if ch == chapter else first, (v2 if ch2 == chapter else last) + 1):
                if str(verse) not in cited_by or (cb == book and (cc, cv) <= (chapter, verse) <= (ec, ev)):
                    continue                     # this excerpt is already on the verse
                w = works[c["work"]]
                rows = cited_by[str(verse)]
                if any(r["id"] == c["id"] for r in rows):
                    continue
                rows.append({
                    "id": c["id"], "work_id": w["id"], "author": w["author"], "author_dates": w["author_dates"],
                    "tradition": w["tradition"], "era": w["era"], "on": scripture.label(c["start"], c["end"]),
                    "href": f"/{cb.lower()}/{cc}/#v{cv}" if (cb, cc) in pages else w["full_text_url"],
                    "here": (cb, cc) == (book, chapter), "verse": cv, "text": x["text"],
                    "snippet": snippet(c["text"], x["at"], len(x["text"])),
                })
    for rows in cited_by.values():
        rows.sort(key=lambda r: (ERAS.index(r["era"]) if r["era"] in ERAS else 99, death_year(works[r["work_id"]])))
    return {**bible, "bookName": book_name, "commentaries": commentaries, "citedBy": cited_by,
            "books": scripture.BOOK_NAMES}


def fill(template, values):
    for k, v in values.items():
        template = template.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{[A-Z_]+\}\}", template)
    if left:
        raise SystemExit(f"template placeholders not filled: {left}")
    return template


def inline_json(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def build():
    works, comments = load_library()
    books = load(os.path.join(ROOT, "bible", "owb", "books.en.json"))
    chapter_tpl = open(os.path.join(ROOT, "web", "chapter.html"), encoding="utf-8").read()
    home_tpl = open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8").read()
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(SITE)
    chapters = []
    paths = sorted(glob.glob(os.path.join(ROOT, "bible", "owb", "en", "*.json")))
    pages = {tuple(os.path.basename(p)[:-5].split(".")) for p in paths}
    pages = {(b, int(c)) for b, c in pages}
    for path in paths:
        bible = load(path)
        name = books[bible["book"]]
        data = chapter_data(bible, name, works, comments, pages)
        covered = sorted({v for w in data["commentaries"] for e in w["entries"]
                          for v in range(e["start"], e["end"] + 1)})
        n = len(data["commentaries"])
        span = f"verses {covered[0]}–{covered[-1]}" if covered else "no verses yet"
        heading = next((r["heading"] for r in data["records"] if r["heading"]), f"{name} {bible['chapter']}")
        page = fill(chapter_tpl, {
            "TITLE": html.escape(f"{name} {bible['chapter']} · Logia"),
            "DESCRIPTION": html.escape(f"{name} {bible['chapter']} with {n} public-domain commentaries "
                                       f"from the early church to the 1800s, verse by verse."),
            "PROTO": html.escape(f"{NUMBER_WORDS.get(n, str(n))} commentaries on {span}"),
            "EYEBROW": html.escape(f"{name} · Chapter {bible['chapter']}"),
            "H1": html.escape(heading),
            "FIRST_REF": html.escape(f"{name} {bible['chapter']}:{bible['verses'][0]}"),
            "OWB_URL": f"{OWB_SITE}/{bible['book'].lower()}/{bible['chapter']}/",
        }).replace("/*DATA*/null", inline_json(data))
        out = os.path.join(SITE, bible["book"].lower(), str(bible["chapter"]))
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
            f.write(page)
        chapters.append((name, bible, n, span))

    def work_card(w):
        return (f'<li><b>{html.escape(w["author"])}</b> <span class="d">{html.escape(w["author_dates"])}</span>'
                f'<span class="w"><i>{html.escape(w["title"])}</i></span>'
                f'<span class="t">{html.escape(w["tradition"])}</span></li>')

    eras = ""
    for era in ERAS:
        ws = sorted((w for w in works.values() if w["era"] == era), key=death_year)
        if ws:
            eras += f'<section><h3>{html.escape(era)}</h3><ul>{"".join(work_card(w) for w in ws)}</ul></section>'
    links = "".join(
        f'<a class="ch" href="/{b["book"].lower()}/{b["chapter"]}/"><b>{html.escape(name)} {b["chapter"]}</b>'
        f'<span>{NUMBER_WORDS.get(n, str(n))} commentaries · {html.escape(span)}</span></a>'
        for name, b, n, span in chapters)
    first = chapters[0][1] if chapters else None
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
        f.write(fill(home_tpl, {
            "START_URL": f"/{first['book'].lower()}/{first['chapter']}/" if first else "/",
            "CHAPTERS": links, "ERAS": eras, "WORK_COUNT": NUMBER_WORDS.get(len(works), str(len(works))).lower(),
        }))
    print(f"site/: home page and {len(chapters)} chapter page(s), {len(works)} works, {len(comments)} excerpts")


if __name__ == "__main__":
    build()
