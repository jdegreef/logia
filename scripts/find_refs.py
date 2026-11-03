"""Find where each excerpt sits in its work, and the Scripture it cites.

    python3 scripts/find_refs.py           # write what it finds
    python3 scripts/find_refs.py --check   # exit 1 if the library is out of date

Two things are read from the sources, never written by hand:

- **Locus.** A work arranged by its own divisions (Chrysostom's homilies,
  Augustine's tractates; `divisions` in library/works/<work>.json) gives each
  excerpt a `locus` such as "3.2", homily 3, section 2. It is read from the
  source page: the homily or tractate heading, and the last section number
  ("[2.]") or numbered paragraph ("5.") before the excerpt. A work arranged
  by verse (`"divisions": "verse"`) needs none: its excerpts are addressed by
  the verse they comment on.
- **Citations**, in library/citations/<work>/<BOOK>.json. In a CCEL
  transcription, CCEL's editors mark each Scripture reference; those are
  taken as marked (`"found": "source"`). In a page scan nothing is marked, so
  references printed in the usual way ("Heb. i. 3", "1 Tim. iii. 16",
  "comp. vi. 46", "v. 14") are matched by pattern (`"found": "pattern"`).
  Either way a citation starts as `"status": "detected"`; a person checking
  it sets "reviewed", or "rejected" for a false match, and running this
  script again keeps their status.
"""
import argparse
import glob
import json
import os
import re
import sys
from html.parser import HTMLParser

import scripture

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {"Note", "NoteRef", "mnote", "Footnote", "footer_note", "pb", "page"}
VOID = {"br", "img", "hr", "meta", "link", "input", "wbr", "col", "area", "base", "source"}
GOBIBLE = re.compile(r"goBible\('[a-z]+','(\w+)','(\d+)','(\d+)','(\d+)','(\d+)'\)")
STATUSES = ("detected", "reviewed", "rejected")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1))


# ---- CCEL pages ----------------------------------------------------------

class Page(HTMLParser):
    """A CCEL page's main text (footnotes and page numbers left out, as in
    verify_sources.py), with where each paragraph and each marked Scripture
    reference starts and ends."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.paras, self.refs = [], [], []
        self.depth, self.open_ref, self.size = 0, None, 0

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        a = dict(attrs)
        if self.depth or set((a.get("class") or "").split()) & SKIP:
            self.depth += 1
            return
        if tag == "p":
            self._add("\n")
            self.paras.append(self.size)
        if tag == "a" and "scripRef" in (a.get("class") or "").split():
            m = GOBIBLE.search(a.get("onclick") or "")
            self.open_ref = [self.size, m.groups() if m else None]

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.depth:
            self.depth -= 1
            return
        if tag == "a" and self.open_ref:
            self.refs.append((self.open_ref[0], self.size, self.open_ref[1]))
            self.open_ref = None

    def handle_data(self, data):
        if not self.depth:
            self._add(data)

    def _add(self, s):
        self.text.append(s)
        self.size += len(s)


def read_page(path):
    p = Page()
    with open(path, encoding="utf-8") as f:
        p.feed(f.read())
    text = "".join(p.text)
    # Letters only, with where each sits in the text: the excerpt and its
    # source differ in spacing, quotes and footnote markers, not in words.
    letters, at = [], []
    for i, ch in enumerate(text.lower()):
        if "a" <= ch <= "z":
            letters.append(ch)
            at.append(i)
    return {"text": text, "paras": p.paras, "refs": p.refs, "letters": "".join(letters), "at": at}


def letters(s):
    return re.sub(r"[^a-z]", "", s.lower())


def span(page, excerpt):
    """Where in the page's text an excerpt starts and ends, or None."""
    pieces = [letters(x) for x in re.split(r"\s*\.\.\.\s*", excerpt)]
    pieces = [x for x in pieces if x]
    if not pieces:
        return None
    head, tail = pieces[0][:80], pieces[-1][-80:]
    s = page["letters"].find(head)
    if s < 0:
        return None
    e = page["letters"].find(tail, s)
    if e < 0:
        return None
    return page["at"][s], page["at"][e + len(tail) - 1] + 1


def locus(page, start):
    """'3.2' for homily or tractate 3, section 2, read from the page."""
    text = page["text"]
    head = re.search(r"\b(?:Homily|Tractate)\s+([IVXLC]+)\.", text)
    if not head or head.start() > start:
        return None
    number = scripture.roman(head[1])
    sections = [(m.start(), int(m[1])) for m in re.finditer(r"\[(\d+)\.\]", text)]
    if not sections:                         # numbered paragraphs: "5. Accordingly, brethren"
        sections = [(p, int(m[1])) for p in page["paras"] if (m := re.match(r"\s*(\d+)\.\s", text[p:p + 12]))]
    before = [n for at, n in sections if at <= start]
    section = before[-1] if before else 1
    return f"{number}.{section}"


def ccel_citations(page, where, excerpt):
    """CCEL's marked references inside the excerpt, placed in it. Where the
    marked words name their book ("Ps. ciii. 20"), they are read as printed,
    which also splits a mark that holds several ("1 John i. 1; v. 7"); a mark
    without a book ("c. v. 34") takes CCEL's reading of it."""
    s, e = where
    out = []
    for rs, rend, passage in page["refs"]:
        if not (s <= rs and rend <= e):
            continue
        text = page["text"][rs:rend].strip()
        printed = full_refs(text)
        if printed:
            out.append((text, [(t, a, b, at) for at, _, t, a, b in printed]))
            continue
        if not passage:
            continue
        book, c1, v1, c2, v2 = passage
        code = scripture.CCEL_BOOKS.get(book)
        if not code or v1 == "0":
            continue                         # a book we do not know, or a whole chapter
        a, b = f"{code}.{int(c1)}.{int(v1)}", f"{code}.{int(c2)}.{int(v2 or v1)}"
        if scripture.parse(a) and scripture.parse(b):
            out.append((text, [(text, a, b, 0)]))
    # Place each in the excerpt, in order: the excerpt is the page's words.
    placed, pos = [], 0
    for text, refs in out:
        at = excerpt.find(text, pos)
        if at < 0:
            at = excerpt.find(text)
        if at < 0 or not text:
            continue
        placed += [(at + off, t, a, b) for t, a, b, off in refs]
        pos = at + len(text)
    return placed


# ---- Page scans: references printed in the usual ways ----------------------

def _names():
    single, numbered = {}, {}
    for code, names in scripture.NAMES.items():
        for n in names.split():
            single[n] = code
    for names, codes in scripture.NUMBERED.items():
        for n in names.split():
            numbered[n] = codes
    return single, numbered


SINGLE, NUMBERED = _names()
_BOOK = "|".join(sorted(set(SINGLE) | set(NUMBERED), key=len, reverse=True))
_CH = r"[ivxlcIVXL]+|\d+"
_VERSES = r"\d{1,3}(?:\s?[-–]\s?\d{1,3})?(?:\s?,\s?\d{1,3}(?:\s?[-–]\s?\d{1,3})?)*(?![\d])"
FULL = re.compile(rf"\b(?:(?P<ord>[123]|III|II|I)\s?)?(?P<book>{_BOOK})\.?\s(?P<ch>{_CH})[.,:]\s?(?P<vs>{_VERSES})")
MORE = re.compile(rf"\s?(?P<sep>[;,])\s?(?P<ch>{_CH})[.,:]\s?(?P<vs>{_VERSES})")
BARE = re.compile(rf"\b(?P<lead>[Cc]omp\.|[Cc]f\.|[Cc]h\.|[Cc]hap\.)\s(?P<ch>[ivxlcIVXL]+)\.\s?(?P<vs>{_VERSES})")
VERSE = re.compile(rf"\b(?:vv|ver|v)\.\s?(?P<vs>{_VERSES})")


def chapter_number(s):
    return int(s) if s.isdigit() else scripture.roman(s)


def verse_groups(vs):
    """'15, 16' -> [(15, 16)]; '27, 49' -> [(27, 27), (49, 49)]; '3-5' -> [(3, 5)].
    A list that goes backwards ('8, 1') stops there: OCR splits numbers."""
    groups = []
    for part in re.split(r"\s?,\s?", vs):
        ends = re.split(r"\s?[-–]\s?", part)
        a, b = int(ends[0]), int(ends[-1])
        if b < a or (groups and a <= groups[-1][1]):
            break
        if groups and a == groups[-1][1] + 1:
            groups[-1] = (groups[-1][0], b)
        else:
            groups.append((a, b))
    return groups


def _refs(code, ch, vs):
    groups = verse_groups(vs) if code and ch else []
    refs = [(f"{code}.{ch}.{a}", f"{code}.{ch}.{b}") for a, b in groups]
    return refs if refs and all(scripture.parse(s) and scripture.parse(e) for s, e in refs) else []


def full_refs(s):
    """References that name their book, with any that follow on from them:
    'Isa. xl. 12, 28; xli. 4', '1 John ii. 29, iii. 9'. Each is (at, end,
    text, start, end ref)."""
    found = []
    for m in FULL.finditer(s):
        name, ordinal = m["book"], m["ord"]
        if ordinal:
            codes = NUMBERED.get(name)
            n = {"I": 1, "II": 2, "III": 3}.get(ordinal) or int(ordinal)
            code = codes[n - 1] if codes and n <= len(codes) else None
        else:
            code = SINGLE.get(name)          # "Tim. iii. 16" with no number is not guessed
        refs = _refs(code, chapter_number(m["ch"]), m["vs"])
        if not refs:
            continue
        found += [(m.start(), m.end(), s, e) for s, e in refs]
        end = m.end()
        while more := MORE.match(s, end):
            if more["sep"] == "," and more["ch"].isdigit():
                break
            refs = _refs(code, chapter_number(more["ch"]), more["vs"])
            if not refs:
                break
            found += [(more.start("ch"), more.end(), a, b) for a, b in refs]
            end = more.end()
    return [(at, end, s[at:end].rstrip(" ,;."), a, b) for at, end, a, b in found]


def scan_citations(excerpt, book, chapter):
    found = full_refs(excerpt)

    def free(s, e):
        return not any(a < e and s < b for a, b, *_ in found)

    for m in BARE.finditer(excerpt):
        ch = m["ch"]
        if free(m.start(), m.end()) and not (m["lead"].lower() == "comp." and ch.lower() == "v"):
            found += [(m.start("ch"), m.end(), excerpt[m.start("ch"):m.end()].rstrip(" ,;."), a, b)
                      for a, b in _refs(book, chapter_number(ch), m["vs"])]
    for m in VERSE.finditer(excerpt):
        if free(m.start(), m.end()):
            found += [(m.start(), m.end(), m[0].rstrip(" ,;."), a, b) for a, b in _refs(book, chapter, m["vs"])]
    return sorted((at, text, a, b) for at, _, text, a, b in found)


# ---- The library ---------------------------------------------------------

def corrected_texts():
    fixes = {}
    for p in glob.glob(os.path.join(ROOT, "library", "corrections", "*.json")):
        c = load(p)
        fixes[c["work"]] = [(x["from"], x["to"]) for x in c["corrections"]]
    return fixes


def derive():
    """What the library should hold: {comments path: entries with loci},
    {citations path: file}."""
    manifest = load(os.path.join(ROOT, "sources", "manifest.json"))
    paths = {(f["work"], os.path.basename(f["path"])): os.path.join(ROOT, f["path"]) for f in manifest["files"]}
    works = {w["id"]: w for w in (load(p) for p in glob.glob(os.path.join(ROOT, "library", "works", "*.json")))}
    fixes = corrected_texts()
    pages, comments, citations, problems = {}, {}, {}, []
    for path in sorted(glob.glob(os.path.join(ROOT, "library", "comments", "*", "*.json"))):
        data = load(path)
        work = works[data["work"]]
        by_division = isinstance(work["divisions"], list)
        rows = []
        for e in data["entries"]:
            e = {k: v for k, v in e.items() if k != "locus"}
            text = e["text"]
            for a, b in fixes.get(work["id"], []):
                text = text.replace(a, b)
            src = paths.get((work["id"], e["sources"][0]))
            _, ch, _ = e["start"].split(".")
            if work["source_kind"] == "digital" and src and src.endswith(".html"):
                if src not in pages:
                    pages[src] = read_page(src)
                where = span(pages[src], e["text"])
                if where is None:
                    problems.append(f"{e['id']}: could not place the excerpt in {os.path.basename(src)}")
                    found = []
                else:
                    found = ccel_citations(pages[src], where, text)
                    if by_division:
                        loc = locus(pages[src], where[0])
                        if loc:
                            e = {**e, "locus": loc}
                        else:
                            problems.append(f"{e['id']}: no homily or tractate heading before it")
                kind = "source"
            else:
                if by_division:
                    problems.append(f"{e['id']}: loci are read from CCEL pages only")
                found = scan_citations(text, data["book"], int(ch))
                kind = "pattern"
            for at, ctext, start, end in found:
                rows.append({"in": e["id"], "at": at, "text": ctext, "start": start, "end": end,
                             "found": kind, "status": "detected"})
            comments.setdefault(path, {**data, "entries": []})["entries"].append(e)
        if rows:
            out = os.path.join(ROOT, "library", "citations", work["id"], f"{data['book']}.json")
            citations[out] = {"work": work["id"], "book": data["book"], "citations": rows}
    return comments, citations, problems


def keep_status(new, old):
    """Carry each person-set status over to the same citation found again."""
    def key(c, seen):
        k = (c["in"], c["text"], c["start"], c["end"])
        seen[k] = seen.get(k, 0) + 1
        return k + (seen[k],)
    seen = {}
    status = {key(c, seen): c["status"] for c in (old or {}).get("citations", [])}
    seen = {}
    for c in new["citations"]:
        c["status"] = status.get(key(c, seen), "detected")
    return new


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="change nothing; exit 1 if anything would change")
    args = ap.parse_args(argv)
    comments, citations, problems = derive()
    changed = []
    for path, data in comments.items():
        if load(path) != data:
            changed.append(path)
            if not args.check:
                dump(path, data)
    existing = set(glob.glob(os.path.join(ROOT, "library", "citations", "*", "*.json")))
    for path, data in citations.items():
        old = load(path) if path in existing else None
        data = keep_status(data, old)
        if old != data:
            changed.append(path)
            if not args.check:
                dump(path, data)
    for path in sorted(existing - set(citations)):
        changed.append(path)
        if not args.check:
            os.remove(path)
    for p in problems:
        print(p)
    n = sum(len(c["citations"]) for c in citations.values())
    loci = sum(1 for d in comments.values() for e in d["entries"] if "locus" in e)
    verb = "out of date" if args.check else "updated"
    for path in changed:
        print(f"{os.path.relpath(path, ROOT)}: {verb}")
    print(f"{loci} excerpts placed in their works, {n} citations of Scripture found")
    if args.check and changed:
        print("run python3 scripts/find_refs.py and commit what it writes")
    return 1 if problems or (args.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
