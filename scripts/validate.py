"""Check the library's data: every work, excerpt, citation, correction and
translation.

    python3 scripts/validate.py

Exit status 1 with a list of problems if anything is wrong. CI runs this
with scripts/verify_sources.py (excerpts against their sources) and the
site build.
"""
import glob
import json
import os
import re
import sys

import scripture

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ERAS = {"Early church", "Middle Ages", "Reformation", "Puritans and the 1700s", "The 1800s"}
WORK_FIELDS = {"id", "author", "title", "divisions", "edition", "original_language", "translation", "published",
               "full_text_url", "rights", "source_kind", "notes", "status"}
AUTHOR_FIELDS = {"id", "name", "dates", "died", "era", "tradition", "bio", "bio_status", "portrait"}
ENTRY_FIELDS = {"id", "start", "end", "heading", "text", "sources"}
CITATION_FIELDS = {"in", "at", "text", "start", "end", "found", "status"}
CITATION_STATUSES = {"detected", "reviewed", "rejected"}   # set by a person checking it
QUOTATION_FIELDS = {"in", "at", "label", "work", "locus", "source", "para", "excerpt", "score", "found", "status"}
STATUSES = {"ai_draft", "reviewed"}          # "reviewed" is set only by a named human reviewer
REF = re.compile(r"^([1-3]?[A-Z]{2,3})\.(\d+)\.(\d+)$")
GREEK_OR_HEBREW = re.compile(r"[Ͱ-Ͽἀ-῿֐-׿]")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    problems = []
    say = problems.append
    books = load(os.path.join(ROOT, "bible", "owb", "books.json"))
    verse_counts = {}
    for p in glob.glob(os.path.join(ROOT, "bible", "owb", "en", "*.json")):
        b = load(p)
        verse_counts[(b["book"], b["chapter"])] = b["verses"][-1]
    manifest = load(os.path.join(ROOT, "sources", "manifest.json"))
    sources = {}
    for f in manifest["files"]:
        if not os.path.exists(os.path.join(ROOT, f["path"])):
            say(f"sources/manifest.json: {f['path']} does not exist")
        if f["kind"] not in ("digital", "scan"):
            say(f"sources/manifest.json: {f['path']} has kind {f['kind']!r}")
        sources.setdefault(f["work"], set()).add(os.path.basename(f["path"]))

    authors = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "library", "authors", "*.json"))):
        a = load(p)
        name = os.path.relpath(p, ROOT)
        if os.path.basename(p) != f"{a.get('id')}.json":
            say(f"{name}: file name does not match id {a.get('id')!r}")
        if set(a) != AUTHOR_FIELDS:
            say(f"{name}: fields differ from the schema: missing {sorted(AUTHOR_FIELDS - set(a))}, "
                f"extra {sorted(set(a) - AUTHOR_FIELDS)}")
        if a.get("era") not in ERAS:
            say(f"{name}: era {a.get('era')!r} is not one of {sorted(ERAS)}")
        if a.get("bio_status") not in STATUSES:
            say(f"{name}: bio_status {a.get('bio_status')!r}")
        if not isinstance(a.get("died"), int):
            say(f"{name}: died must be a year")
        authors[a.get("id")] = a

    works = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "library", "works", "*.json"))):
        w = load(p)
        name = os.path.relpath(p, ROOT)
        if os.path.basename(p) != f"{w.get('id')}.json":
            say(f"{name}: file name does not match id {w.get('id')!r}")
        if set(w) != WORK_FIELDS:
            say(f"{name}: fields differ from the schema: missing {sorted(WORK_FIELDS - set(w))}, "
                f"extra {sorted(set(w) - WORK_FIELDS)}")
        if w.get("author") not in authors:
            say(f"{name}: author {w.get('author')!r} has no library/authors/ file")
        if w.get("status") not in STATUSES:
            say(f"{name}: status {w.get('status')!r}")
        if not isinstance(w.get("published"), int) or w["published"] > 1930:
            say(f"{name}: published {w.get('published')!r}: only editions published in 1930 or earlier are "
                "public domain in the US; anything later needs a rights note and a decision")
        div = w.get("divisions")
        if div != "verse" and not (isinstance(div, list) and div and all(isinstance(x, str) and x for x in div)):
            say(f"{name}: divisions {div!r}: \"verse\" for a work arranged by verse, or the names of its own "
                "divisions, e.g. [\"Homily\", \"Section\"]")
        if w.get("source_kind") not in ("digital", "scan"):
            say(f"{name}: source_kind {w.get('source_kind')!r}")
        works[w["id"]] = w

    texts, entries = {}, {}
    for p in sorted(glob.glob(os.path.join(ROOT, "library", "comments", "*", "*.json"))):
        d = load(p)
        name = os.path.relpath(p, ROOT)
        work = d.get("work")
        if work not in works:
            say(f"{name}: work {work!r} has no library/works/{work}.json")
            continue
        if os.path.basename(os.path.dirname(p)) != work or os.path.basename(p) != f"{d.get('book')}.json":
            say(f"{name}: file path does not match work {work!r} and book {d.get('book')!r}")
        if d.get("book") not in books:
            say(f"{name}: unknown book {d.get('book')!r}")
        last = None
        for e in d["entries"]:
            eid = e.get("id", "?")
            divisions = works[work].get("divisions")
            want = ENTRY_FIELDS | ({"locus"} if isinstance(divisions, list) else set())
            if set(e) != want:
                say(f"{name}: {eid}: fields {sorted(e)}, not {sorted(want)}")
                continue
            if "locus" in e and not re.fullmatch(r"[1-9]\d*(\.[1-9]\d*){%d}" % (len(divisions) - 1), e["locus"]):
                say(f"{name}: {eid}: locus {e['locus']!r} is not {len(divisions)} numbers like "
                    + ".".join(["2"] * len(divisions)) + f" ({', '.join(divisions)})")
            if eid in texts:
                say(f"{name}: duplicate id {eid}")
            texts[eid] = (work, e["text"])
            entries[eid] = e
            refs = []
            for key in ("start", "end"):
                m = REF.match(e[key])
                if not m or m[1] != d["book"]:
                    say(f"{name}: {eid}: {key} {e[key]!r} is not a {d['book']} reference like {d['book']}.1.1")
                    break
                refs.append((int(m[2]), int(m[3])))
                top = verse_counts.get((d["book"], int(m[2])))
                if top is not None and not 1 <= int(m[3]) <= top:
                    say(f"{name}: {eid}: {e[key]} is past the end of the chapter ({top} verses)")
            if len(refs) == 2:
                if refs[0] > refs[1]:
                    say(f"{name}: {eid}: starts after it ends")
                if last and refs[0] < last:
                    say(f"{name}: {eid}: entries must be in verse order")
                last = refs[0]
            if not e["text"].strip():
                say(f"{name}: {eid}: empty text")
            if not e["sources"]:
                say(f"{name}: {eid}: no source listed")
            for s in e["sources"]:
                if s not in sources.get(work, set()):
                    say(f"{name}: {eid}: source {s!r} is not in sources/manifest.json for {work}")

    for p in sorted(glob.glob(os.path.join(ROOT, "library", "corrections", "*.json"))):
        c = load(p)
        name = os.path.relpath(p, ROOT)
        if c.get("work") not in works:
            say(f"{name}: unknown work {c.get('work')!r}")
            continue
        if works[c["work"]]["source_kind"] != "scan":
            say(f"{name}: corrections are only for scanned sources; {c['work']} is digital")
        body = "\n".join(t for w, t in texts.values() if w == c["work"])
        for x in c["corrections"]:          # applied in order, as the build does
            if x["from"] not in body:
                say(f"{name}: correction {x['from']!r} matches no excerpt any more; remove it")
            body = body.replace(x["from"], x["to"])
            if GREEK_OR_HEBREW.search(x["to"]):
                say(f"{name}: correction {x['from']!r} would type Greek or Hebrew; leave it out instead")

    fixes = {}
    for p in glob.glob(os.path.join(ROOT, "library", "corrections", "*.json")):
        c = load(p)
        fixes[c.get("work")] = [(x["from"], x["to"]) for x in c.get("corrections", [])]
    for p in sorted(glob.glob(os.path.join(ROOT, "library", "citations", "*", "*.json"))):
        c = load(p)
        name = os.path.relpath(p, ROOT)
        work = c.get("work")
        if os.path.basename(os.path.dirname(p)) != work or os.path.basename(p) != f"{c.get('book')}.json":
            say(f"{name}: file path does not match work {work!r} and book {c.get('book')!r}")
        for x in c.get("citations", []):
            where = f"{name}: {x.get('in')} {x.get('text')!r}"
            if set(x) != CITATION_FIELDS:
                say(f"{where}: fields {sorted(x)}, not {sorted(CITATION_FIELDS)}")
                continue
            if x["in"] not in texts or texts[x["in"]][0] != work:
                say(f"{where}: {x['in']!r} is not an excerpt of {work}")
                continue
            text = texts[x["in"]][1]
            for a, b in fixes.get(work, []):
                text = text.replace(a, b)
            if text[x["at"]:x["at"] + len(x["text"])] != x["text"]:
                say(f"{where}: is not at {x['at']} in the excerpt any more; run scripts/find_refs.py")
            s, e = scripture.parse(x["start"]), scripture.parse(x["end"])
            if not s or not e:
                say(f"{where}: {x['start']}–{x['end']} is not a reference to a chapter that exists")
            elif s[0] != e[0] or s[1:] > e[1:]:
                say(f"{where}: {x['start']}–{x['end']} is not a forward range in one book")
            if x["found"] not in ("source", "pattern"):
                say(f"{where}: found {x['found']!r}")
            if x["status"] not in CITATION_STATUSES:
                say(f"{where}: status {x['status']!r}")

    for p in sorted(glob.glob(os.path.join(ROOT, "library", "quotations", "*", "*.json"))):
        q = load(p)
        name = os.path.relpath(p, ROOT)
        work = q.get("work")
        if os.path.basename(os.path.dirname(p)) != work or os.path.basename(p) != f"{q.get('book')}.json":
            say(f"{name}: file path does not match work {work!r} and book {q.get('book')!r}")
        for x in q.get("quotations", []):
            where = f"{name}: {x.get('in')} {x.get('label')!r}"
            if set(x) != QUOTATION_FIELDS:
                say(f"{where}: fields {sorted(x)}, not {sorted(QUOTATION_FIELDS)}")
                continue
            if x["in"] not in texts or texts[x["in"]][0] != work:
                say(f"{where}: {x['in']!r} is not an excerpt of {work}")
                continue
            if texts[x["in"]][1][x["at"]:x["at"] + len(x["label"])] != x["label"]:
                say(f"{where}: the label is not at {x['at']} in the excerpt any more; run scripts/find_refs.py")
            quoted = works.get(x["work"])
            if not quoted:
                say(f"{where}: quoted work {x['work']!r} is not in the library")
                continue
            div = quoted["divisions"]
            if not isinstance(div, list) or not re.fullmatch(r"[1-9]\d*(\.[1-9]\d*){0,%d}" % (len(div) - 1),
                                                             x["locus"]):
                say(f"{where}: locus {x['locus']!r} does not fit {x['work']}'s divisions {div!r}")
            if x["source"] not in sources.get(x["work"], set()):
                say(f"{where}: source {x['source']!r} is not in sources/manifest.json for {x['work']}")
            if x["excerpt"] is not None and (x["excerpt"] not in texts or texts[x["excerpt"]][0] != x["work"]):
                say(f"{where}: {x['excerpt']!r} is not an excerpt of {x['work']}")
            if x["found"] != "similar" or x["status"] not in CITATION_STATUSES:
                say(f"{where}: found {x['found']!r}, status {x['status']!r}")

    for p in sorted(glob.glob(os.path.join(ROOT, "library", "texts", "*", "*.json"))):
        t = load(p)
        name = os.path.relpath(p, ROOT)
        w = works.get(t.get("work"))
        if not w or not isinstance(w["divisions"], list):
            say(f"{name}: work {t.get('work')!r} is not a work with its own divisions")
            continue
        if os.path.basename(os.path.dirname(p)) != w["id"] or os.path.basename(p) != f"{t.get('locus')}.json":
            say(f"{name}: file path does not match work {w['id']!r} and locus {t.get('locus')!r}")
        if t.get("source") not in sources.get(w["id"], set()):
            say(f"{name}: source {t.get('source')!r} is not in sources/manifest.json for {w['id']}")
        vs = t.get("verses") or {}
        start, end = scripture.parse(vs.get("start")), scripture.parse(vs.get("end"))
        if not start or not end or start[0] != end[0] or start[1:] > end[1:]:
            say(f"{name}: verses {vs!r} is not a forward range of verses")
        for para in t.get("paragraphs", []):
            v = para.get("verse")
            if v is not None and not (start and end and (p_ := scripture.parse(v))
                                      and p_[0] == start[0] and start[1:] <= p_[1:] <= end[1:]):
                say(f"{name}: {para['id']}: verse {v!r} is outside the text's verses")
            for x in para["excerpts"]:
                if x not in texts or texts[x][0] != w["id"]:
                    say(f"{name}: {para['id']}: {x!r} is not an excerpt of {w['id']}")
            for c in para["cites"]:
                if para["text"][c["at"]:c["at"] + len(c["text"])] != c["text"] or not scripture.parse(c["start"]):
                    say(f"{name}: {para['id']}: citation {c['text']!r} does not fit; run scripts/extract_texts.py")

    for p in sorted(glob.glob(os.path.join(ROOT, "library", "translations", "*", "*", "*.json"))):
        t = load(p)
        name = os.path.relpath(p, ROOT)
        for e in t.get("entries", []):
            if e.get("of") not in texts:
                say(f"{name}: {e.get('of')!r} is not an excerpt id")
            if e.get("status") not in STATUSES:
                say(f"{name}: {e.get('of')}: status {e.get('status')!r}")

    for a in authors:
        if not any(w["author"] == a for w in works.values()):
            say(f"library/authors/{a}.json: no work in library/works/ is by this author")
    for msg in problems:
        print(msg)
    print(f"{len(authors)} authors, {len(works)} works, {len(texts)} excerpts: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
