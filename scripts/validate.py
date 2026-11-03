"""Check the library's data: every work, excerpt, correction and translation.

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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ERAS = {"Early church", "Middle Ages", "Reformation", "Puritans and the 1700s", "The 1800s"}
WORK_FIELDS = {"id", "author", "title", "edition", "original_language", "translation", "published",
               "full_text_url", "rights", "source_kind", "notes", "status"}
AUTHOR_FIELDS = {"id", "name", "dates", "died", "era", "tradition", "bio", "bio_status", "portrait"}
ENTRY_FIELDS = {"id", "start", "end", "heading", "text", "sources"}
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
        if w.get("source_kind") not in ("digital", "scan"):
            say(f"{name}: source_kind {w.get('source_kind')!r}")
        works[w["id"]] = w

    texts = {}
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
            if set(e) != ENTRY_FIELDS:
                say(f"{name}: {eid}: fields {sorted(e)}")
                continue
            if eid in texts:
                say(f"{name}: duplicate id {eid}")
            texts[eid] = (work, e["text"])
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
