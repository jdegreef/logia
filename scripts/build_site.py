"""Build the Logia site into site/.

    python3 scripts/build_site.py

Reads the library (library/works, library/comments, library/corrections,
library/citations), the
Bible text (bible/owb) and the page templates (web/), and writes static pages:
site/index.html and one page per imported chapter, site/<book>/<chapter>/.
Each chapter page carries its own data inline, so the site needs no server.
Whole homilies and tractates (library/texts) get a page each,
site/works/<work>/<n>/, and each such work a list, site/works/<work>/.
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


def source_urls():
    return {(f["work"], os.path.basename(f["path"])): f["url"]
            for f in load(os.path.join(ROOT, "sources", "manifest.json"))["files"]}


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
    quotes, quoted_in = {}, {}
    for p in sorted(glob.glob(os.path.join(ROOT, "library", "quotations", "*", "*.json"))):
        for q in load(p)["quotations"]:
            if q["status"] != "rejected":
                quotes.setdefault(q["in"], []).append(q)
                if q["excerpt"]:
                    quoted_in.setdefault(q["excerpt"], []).append(q)
    comments = []
    for p in sorted(glob.glob(os.path.join(ROOT, "library", "comments", "*", "*.json"))):
        data = load(p)
        work = data["work"]
        for e in data["entries"]:
            text = e["text"]
            for a, b in fixes.get(work, []):
                text = text.replace(a, b)
            comments.append({**e, "work": work, "text": text, "cites": cites.get(e["id"], []),
                             "quotes": quotes.get(e["id"], []), "quoted_in": quoted_in.get(e["id"], []),
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


def locus_label(work, locus):
    """'4.1' in Chrysostom -> 'Homily 4, section 1'."""
    parts = locus.split(".")
    names = [n if i == 0 else n.lower() for i, n in enumerate(work["divisions"])]
    return ", ".join(f"{name} {n}" for name, n in zip(names, parts))


def excerpt_link(c, pages):
    """Where to read an excerpt: its verse on its chapter page."""
    b, ch, v = ref_parts(c["start"])
    return f"/{b.lower()}/{ch}/#v{v}" if (b, ch) in pages else None


def quote_rows(c, works, by_id, urls, pages):
    """A catena excerpt's quotations, traced to the quoted works."""
    out = []
    for q in c["quotes"]:
        w = works[q["work"]]
        held = by_id.get(q["excerpt"])
        url = urls.get((q["work"], q["source"]), w["full_text_url"]) + (f"#{q['para']}" if q["para"] else "")
        out.append({"label": q["label"], "author": w["author"], "title": w["title"],
                    "where": locus_label(w, q["locus"]), "exact": bool(q["para"]), "url": url,
                    "excerpt": q["excerpt"] if held else None, "work_id": q["work"],
                    "href": excerpt_link(held, pages) if held else None,
                    "verse": ref_parts(held["start"])[2] if held else None, "status": q["status"]})
    return out


def quoted_in_rows(c, works, by_id, pages):
    """The catena excerpts that quote this excerpt's passage."""
    out = []
    for q in c["quoted_in"]:
        cat = by_id[q["in"]]
        w = works[cat["work"]]
        out.append({"author": w["author"], "title": w["title"], "on": scripture.label(cat["start"], cat["end"]),
                    "work_id": w["id"], "href": excerpt_link(cat, pages),
                    "verse": ref_parts(cat["start"])[2], "status": q["status"]})
    return out


def chapter_data(bible, book_name, works, comments, pages=frozenset(), urls=None, in_full=None):
    book, chapter = bible["book"], bible["chapter"]
    first, last = bible["verses"][0], bible["verses"][-1]
    by_id = {c["id"]: c for c in comments}
    urls = urls or {}
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
             "locus": c.get("locus"), "source_url": c["source_url"], "cites": cites_for(c, pages),
             "quotes": quote_rows(c, works, by_id, urls, pages),
             "quotedIn": quoted_in_rows(c, works, by_id, pages), "inFull": (in_full or {}).get(c["id"])})
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


def load_texts():
    """{work: [text, ...]} in order, from library/texts."""
    out = {}
    for p in glob.glob(os.path.join(ROOT, "library", "texts", "*", "*.json")):
        t = load(p)
        out.setdefault(t["work"], []).append(t)
    for ts in out.values():
        ts.sort(key=lambda t: int(t["locus"]))
    return out


def text_link(texts):
    """{excerpt id: '/works/<work>/<n>/#<paragraph>'}: where each excerpt
    begins in its whole text."""
    out = {}
    for work, ts in texts.items():
        for t in ts:
            for para in t["paragraphs"]:
                for x in para["excerpts"]:
                    out.setdefault(x, f"/works/{work}/{t['locus']}/#{para['id']}")
    return out


def linked_html(text, cites, pages):
    h, pos = [], 0
    for c in sorted(cites, key=lambda c: c["at"]):
        if c["at"] < pos:
            continue
        href = cite_link(c["start"], pages)
        words = html.escape(text[c["at"]:c["at"] + len(c["text"])])
        label = html.escape(scripture.label(c["start"], c["end"]))
        h.append(html.escape(text[pos:c["at"]]))
        if href:
            ext = "" if href.startswith("/") else ' target="_blank" rel="noopener"'
            h.append(f'<a class="cite" href="{html.escape(href)}"{ext} title="{label}">{words}</a>')
        else:
            h.append(f'<span class="cite" title="{label}">{words}</span>')
        pos = c["at"] + len(c["text"])
    return "".join(h) + html.escape(text[pos:])


def plural(word):
    return word[:-1] + "ies" if word.endswith("y") else word + "s"


def text_page(tpl, work, t, siblings, by_id, quoted, pages):
    """A whole homily or tractate, paragraph by paragraph."""
    name = locus_label(work, t["locus"])
    paras = t["paragraphs"]
    lead = []                                # the short headings under the title: "John i. 1", "Chapter I. 1–5"
    for p in paras[1:3]:
        if len(p["text"]) >= 60 or p["excerpts"]:
            break
        lead.append(p)
    body, section = [], None
    rest = paras[1 + len(lead):]
    for n, p in enumerate(rest):
        sec = p["locus"].split(".")[-1] if p["locus"] else None
        if sec != section:
            if section is not None:
                body.append("</section>")
            body.append(f'<section id="s{sec}" aria-label="{html.escape(work["divisions"][-1])} {sec}">')
            section = sec
        head = len(p["text"]) < 60 and not p["cites"] and not re.search(r"[.?!”]$", p["text"])
        cls = " ".join(c for c in ("head" if head else "", "held" if p["excerpts"] else "") if c)
        body.append(f'<p id="{html.escape(p["id"])}"{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}>'
                    f'{linked_html(p["text"], p["cites"], pages)}</p>')
        marks = []
        after = rest[n + 1]["excerpts"] if n + 1 < len(rest) else []
        for x in (x for x in p["excerpts"] if x not in after):     # once, under its last paragraph
            c = by_id.get(x)
            href = c and excerpt_link(c, pages)
            if href:
                marks.append(f'<a href="{href}">In Logia on {html.escape(scripture.label(c["start"], c["end"]))}</a>')
        for q in quoted.get(p["id"], []):
            c = by_id[q["in"]]
            href = excerpt_link(c, pages)
            on = html.escape(scripture.label(c["start"], c["end"]))
            link = f'<a href="{href}">on {on}</a>' if href else f"on {on}"
            note = "" if q["status"] == "reviewed" else " (matched by wording, unchecked)"
            marks.append(f"<span>Quoted by Thomas Aquinas in the <i>Catena Aurea</i>, {link}{note}</span>")
        if marks:
            body.append(f'<div class="marks">{"".join(marks)}</div>')
    if section is not None:
        body.append("</section>")
    i = next(n for n, x in enumerate(siblings) if x is t)
    prev = siblings[i - 1] if i else None
    nxt = siblings[i + 1] if i + 1 < len(siblings) else None
    nav = [f'<a href="/works/{work["id"]}/{prev["locus"]}/">← {html.escape(locus_label(work, prev["locus"]))}</a>'
           if prev else "", f'<a href="/works/{work["id"]}/">All of {html.escape(work["title"])}</a>',
           '<span class="sp"></span>',
           f'<a href="{html.escape(t["url"])}" target="_blank" rel="noopener">On CCEL ↗</a>',
           f'<a href="/works/{work["id"]}/{nxt["locus"]}/">{html.escape(locus_label(work, nxt["locus"]))} →</a>'
           if nxt else ""]
    return fill(tpl, {
        "TITLE": html.escape(f"{work['author']}, {name} · Logia"),
        "DESCRIPTION": html.escape(f"{work['author']}, {work['title']}, {name}, read straight through."),
        "TOP": html.escape(work["author"]),
        "EYEBROW": html.escape(f"{work['author']} · {work['title']}"),
        "H1": html.escape(name),
        "SUB": html.escape(" · ".join(p["text"] for p in lead) or work["edition"]),
        "NAV": "".join(nav),
        "BODY": f'<div class="text">{"".join(body)}</div>',
        "FOOT": html.escape(f"Copied word for word from {work['edition']}, as transcribed by CCEL; the "
                            f"translator's footnotes are left out. {work['rights']['basis'].capitalize()}. "
                            "Scripture references are linked as CCEL marks them. A gold rule marks the "
                            "passages Logia sets beside a verse."),
    })


def work_page(tpl, work, ts):
    items = "".join(
        f'<li><a href="/works/{work["id"]}/{t["locus"]}/">{html.escape(locus_label(work, t["locus"]))}</a>'
        f'<span>{html.escape(next((p["text"] for p in t["paragraphs"][1:4] if len(p["text"]) < 60), ""))}</span></li>'
        for t in ts)
    first, last = ts[0]["locus"], ts[-1]["locus"]
    return fill(tpl, {
        "TITLE": html.escape(f"{work['author']}, {work['title']} · Logia"),
        "DESCRIPTION": html.escape(f"{work['title']} by {work['author']}, read straight through."),
        "TOP": html.escape(work["author"]),
        "EYEBROW": html.escape(f"{work['author']} · {work['author_dates']}"),
        "H1": html.escape(work["title"]),
        "SUB": html.escape(f"{plural(work['divisions'][0])} {first}–{last} so far, read straight through. "
                           f"{work['edition']}."),
        "NAV": f'<a href="{html.escape(work["full_text_url"])}" target="_blank" rel="noopener">'
               "The whole work on CCEL ↗</a>",
        "BODY": f'<ul class="list">{items}</ul>',
        "FOOT": "Logia copies the homilies and tractates that hold its excerpts; the rest of the work is on CCEL.",
    })


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
    texts = load_texts()
    in_full = text_link(texts)
    chapters = []
    paths = sorted(glob.glob(os.path.join(ROOT, "bible", "owb", "en", "*.json")))
    pages = {tuple(os.path.basename(p)[:-5].split(".")) for p in paths}
    pages = {(b, int(c)) for b, c in pages}
    for path in paths:
        bible = load(path)
        name = books[bible["book"]]
        data = chapter_data(bible, name, works, comments, pages, source_urls(), in_full)
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

    text_tpl = open(os.path.join(ROOT, "web", "text.html"), encoding="utf-8").read()
    by_id = {c["id"]: c for c in comments}
    quoted = {}
    for c in comments:
        for q in c["quotes"]:
            if q["para"]:
                quoted.setdefault(q["para"], []).append(q)
    n_texts = 0
    for wid, ts in sorted(texts.items()):
        work = works[wid]
        out = os.path.join(SITE, "works", wid)
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
            f.write(work_page(text_tpl, work, ts))
        for t in ts:
            os.makedirs(os.path.join(out, t["locus"]), exist_ok=True)
            with open(os.path.join(out, t["locus"], "index.html"), "w", encoding="utf-8") as f:
                f.write(text_page(text_tpl, work, t, ts, by_id, quoted, pages))
            n_texts += 1

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
        for name, b, n, span in chapters) + "".join(
        f'<a class="ch" href="/works/{wid}/"><b>{html.escape(works[wid]["author"])}</b>'
        f'<span>{html.escape(plural(works[wid]["divisions"][0]))} {ts[0]["locus"]}–{ts[-1]["locus"]}, '
        f'read straight through</span></a>'
        for wid, ts in sorted(texts.items()))
    first = chapters[0][1] if chapters else None
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
        f.write(fill(home_tpl, {
            "START_URL": f"/{first['book'].lower()}/{first['chapter']}/" if first else "/",
            "CHAPTERS": links, "ERAS": eras, "WORK_COUNT": NUMBER_WORDS.get(len(works), str(len(works))).lower(),
        }))
    print(f"site/: home page, {len(chapters)} chapter page(s), {n_texts} whole homilies and tractates; "
          f"{len(works)} works, {len(comments)} excerpts")


if __name__ == "__main__":
    build()
