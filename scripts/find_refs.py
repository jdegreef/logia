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
- **Quotations of the Fathers**, in library/quotations/<work>/<BOOK>.json. A
  catena quotes the Fathers under printed labels ("CHRYS.", "AUG."). Where
  the library holds the quoted work's source pages, each quotation is
  matched to the paragraph of that work whose words it shares most: the
  Catena's English was made from Aquinas's Latin, so it is never word for
  word the same as the CCEL translation. A match names the section when one
  section stands out, only the homily or tractate when only that does, and
  is left out otherwise (`"found": "similar"`, with its `score`). A homily or
  tractate on the verse the catena is at (library/texts/, so run
  scripts/extract_texts.py first when texts change) needs a smaller lead. Like a
  citation it stays "detected" until a person checks it, for instance
  against the margin note printed beside it ("Aug. in Joan. tract. i. c. 13").
"""
import argparse
import glob
import json
import math
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
        self.text, self.paras, self.para_ids, self.refs = [], [], [], []
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
            self.para_ids.append(a.get("id"))
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


def read_page(path, part=None):
    """A CCEL page. `part` is the division a page sits in when the page does
    not name it: the manifest's "part" for the page, as CCEL's table of
    contents gives it ("Book II" for a section of Origen's second book)."""
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
    return {"text": text, "paras": p.paras, "para_ids": p.para_ids, "refs": p.refs,
            "letters": "".join(letters), "at": at, "part": part}


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


def locus(page, start, depth=2):
    """'3.2' for homily or tractate 3, section 2, read from the page; '3' for
    a work divided into homilies only (`depth` 1: its translation prints no
    section numbers); for a page that is one section of a book ("Book II",
    the page's `part`), the book's number and the section number the page
    opens with."""
    text = page["text"]
    if page.get("part"):
        number = scripture.roman(page["part"].split()[-1])
    else:
        head = re.search(r"\b(?:Homily|Tractate)\s+([IVXLC]+)\.", text)
        if not head or head.start() > start:
            return None
        number = scripture.roman(head[1])
    if depth == 1:
        return str(number)
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
        printed = full_refs(text, short=False)
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

# The short names some commentaries print with Arabic numbers and a colon,
# "Lu 1:1-4; 24:3", "Ac 22:26", "1Co 13:12" (Jamieson-Fausset-Brown). Several
# are also English words ("Am", "Re"), so they are read only before
# "chapter:verse".
SHORT_SINGLE = {
    "Ge": "GEN", "Ex": "EXO", "Le": "LEV", "Nu": "NUM", "De": "DEU", "Jos": "JOS", "Jud": "JDG",
    "Ru": "RUT", "Ezr": "EZR", "Ne": "NEH", "Es": "EST", "Job": "JOB", "Ps": "PSA", "Pr": "PRO",
    "Ec": "ECC", "So": "SNG", "Isa": "ISA", "Jer": "JER", "La": "LAM", "Eze": "EZK", "Da": "DAN",
    "Ho": "HOS", "Joe": "JOL", "Am": "AMO", "Ob": "OBA", "Jon": "JON", "Mic": "MIC", "Na": "NAM",
    "Hab": "HAB", "Zep": "ZEP", "Hag": "HAG", "Zec": "ZEC", "Mal": "MAL", "Mt": "MAT", "Mr": "MRK",
    "Lu": "LUK", "Joh": "JHN", "Ac": "ACT", "Ro": "ROM", "Ga": "GAL", "Eph": "EPH", "Php": "PHP",
    "Col": "COL", "Tit": "TIT", "Phm": "PHM", "Heb": "HEB", "Jas": "JAS", "Jude": "JUD", "Re": "REV",
}
SHORT_NUMBERED = {
    "Sa": ("1SA", "2SA"), "Ki": ("1KI", "2KI"), "Ch": ("1CH", "2CH"), "Co": ("1CO", "2CO"),
    "Th": ("1TH", "2TH"), "Ti": ("1TI", "2TI"), "Pe": ("1PE", "2PE"), "Jo": ("1JN", "2JN", "3JN"),
}
_CH = r"[ivxlcIVXL]+|\d+"
_VERSES = r"\d{1,3}(?:\s?[-–]\s?\d{1,3})?(?:\s?,\s?\d{1,3}(?:\s?[-–]\s?\d{1,3})?)*(?![\d])"
FULL = re.compile(rf"\b(?:(?P<ord>[123]|III|II|I)\s?)?(?P<book>{_BOOK})\.?\s(?P<ch>{_CH})[.,:]\s?(?P<vs>{_VERSES})")
MORE = re.compile(rf"\s?(?P<sep>[;,])\s?(?P<ch>{_CH})[.,:]\s?(?P<vs>{_VERSES})")
BARE = re.compile(rf"\b(?P<lead>[Cc]omp\.|[Cc]f\.|[Cc]h\.|[Cc]hap\.|c\.)\s(?P<ch>[ivxlcIVXL]+)\.\s?(?P<vs>{_VERSES})")
VERSE = re.compile(rf"\b(?:vv|[Vv]er|v)\.\s?(?P<vs>{_VERSES})(?!\s\d)")     # not "Ver. 1 1.", a scan's 11
LEMMA = re.compile(r"(?:\A|\n)\s*(?:\[\d+\.\]\s*)?\Z")    # nothing but a section mark before it in its paragraph
SHORT = re.compile(rf"\b(?:(?P<ord>[123])\s?)?(?P<book>{'|'.join(sorted(set(SHORT_SINGLE) | set(SHORT_NUMBERED), key=len, reverse=True))})"
                   rf"\s(?P<ch>\d{{1,3}}):(?P<vs>{_VERSES})(?![-–:\d])")    # not "10:1-22:16", a span of chapters


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
    return refs if refs and all(scripture.plausible(s) and scripture.plausible(e) for s, e in refs) else []


def full_refs(s, short=True):
    """References that name their book, with any that follow on from them:
    'Isa. xl. 12, 28; xli. 4', '1 John ii. 29, iii. 9'. Each is (at, end,
    text, start, end ref)."""
    found = []
    full = list(FULL.finditer(s))
    short = [m for m in SHORT.finditer(s) if short
             and not any(f.start() < m.end() and m.start() < f.end() for f in full)]
    for m in sorted(full + short, key=lambda m: m.start()):
        name, ordinal = m["book"], m["ord"]
        single, numbered = (SINGLE, NUMBERED) if m.re is FULL else (SHORT_SINGLE, SHORT_NUMBERED)
        if ordinal:
            codes = numbered.get(name)
            n = {"I": 1, "II": 2, "III": 3}.get(ordinal) or int(ordinal)
            code = codes[n - 1] if codes and n <= len(codes) else None
        else:
            code = single.get(name)          # "Tim. iii. 16" with no number is not guessed
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


def scan_citations(excerpt, book, chapter, own=None):
    """References printed in a scan's excerpt. With `own`, the excerpt's
    (start, end): a "Ver. 13" that opens a paragraph and names a verse the
    excerpt is on is its heading ("Ver. 13. A second quotation..."), not a
    citation. The same words inside a paragraph are a citation."""
    found = full_refs(excerpt)

    def heading(at, refs):
        if not own or not LEMMA.search(excerpt, 0, at):
            return refs
        lo, hi = (scripture.parse(r) for r in own)
        return [(a, b) for a, b in refs if not (lo <= scripture.parse(a) and scripture.parse(b) <= hi)]

    def free(s, e):
        return not any(a < e and s < b for a, b, *_ in found)

    for m in BARE.finditer(excerpt):
        ch = m["ch"]
        if free(m.start(), m.end()) and not (m["lead"].lower() == "comp." and ch.lower() == "v"):
            found += [(m.start("ch"), m.end(), excerpt[m.start("ch"):m.end()].rstrip(" ,;."), a, b)
                      for a, b in _refs(book, chapter_number(ch), m["vs"])]
    for m in VERSE.finditer(excerpt):
        if free(m.start(), m.end()):
            found += [(m.start(), m.end(), m[0].rstrip(" ,;."), a, b) for a, b in heading(m.start(), _refs(book, chapter, m["vs"]))]
    return sorted((at, text, a, b) for at, _, text, a, b in found)


# ---- Quotations of the Fathers in a catena ---------------------------------

# For each catena, the labels it prints before a quotation that the library
# can follow to the quoted work: the library's source pages for that work.
CATENAS = {"catena": {"CHRYS": "chrysostom", "AUG": "augustine"},
           "catena-matthew": {"CHRYS": "chrysostom-matthew"}}
# The Part II scans of the Catena (John 11-21), and CCEL's Matthew, print the names in
# this form: "Aug.", "Chrys."; "Pseudo-Chrys." (the Opus Imperfectum) is not Chrysostom.
LABEL = re.compile(r"(?<![\w-])(CHRYS|Chrys|AUG|Aug|HILARY|THEOPHYL|ALCUIN|BEDE|BASIL|ORIGEN|GREG)\s?[.;]")
STOPWORDS = set("""that this with which from have they their them there were been what when will would shall
should these those than then thus also into upon unto said saith says hath doth more being because such only
thing things other even very itself himself whom whose where while each some made make like after before same
through about against word""".split())
MIN_WORDS = 10                 # fewer shared-able words than this: too short to match
SECTION = (0.35, 0.10)         # a section: its score, and its lead over any other section
DIVISION = (0.20, 0.08)        # a homily or tractate: the same, over any other one
# The lead a homily or tractate needs when it is the one on the verse the catena
# is commenting on (library/texts/<work>/<n>.json, "verses"). A catena gathers
# the Fathers' comments verse by verse, so that is where a quotation is likeliest
# to come from, and the more of a Father's works the library holds, the closer
# some other homily comes by chance: "Grace for grace" (John 1:16) leads Tractate
# X by only 0.053 once Tractates IV-XI are in, though its margin note and its
# five best paragraphs all say Tractate III. And once the library reaches John 5,
# Tractate XVII comes within 0.01: so the homily on the verse is also taken when
# its two best paragraphs are the two best of all, which chance rarely gives.
NEAR_LEAD = 0.04
# With the whole Gospel in, one paragraph in a far homily can share a short
# quotation's words by chance ("Grace for grace" and Tractate CXXIV), so the
# homily on the verse is also taken when the mean of its SPREAD best paragraphs
# leads every other homily's by SPREAD_LEAD.
SPREAD = 3
SPREAD_LEAD = 0.02


def content_words(text):
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 4 and w not in STOPWORDS}


def paragraphs(pages):
    """(work, source, paragraph id, locus, start, end, words) for each
    paragraph of the library's pages of the quoted works."""
    out = []
    for (work, source), page in pages.items():
        text, starts = page["text"], page["paras"] + [len(page["text"])]
        for i, (a, b) in enumerate(zip(starts, starts[1:])):
            words = content_words(text[a:b])
            loc = locus(page, a)
            if len(words) > 15 and loc:
                out.append((work, source, page["para_ids"][i], loc, a, b, words))
    return out


def judge(scored):
    """The best of scored paragraphs, as (score, paragraph, level), if it
    leads the others by enough: level "section" (that paragraph) or
    "division" (its homily or tractate)."""
    best, para = scored[0]
    division = para[3].split(".")[0]
    other_section = next((s for s, c in scored if c[3] != para[3]), 0)
    other_division = next((s for s, c in scored if c[3].split(".")[0] != division), 0)
    if best >= SECTION[0] and best - other_section >= SECTION[1]:
        return best, para, "section"
    if best >= DIVISION[0] and best - other_division >= DIVISION[1]:
        return best, para, "division"
    return None


def match_quotation(words, candidates, idf, near=lambda para: False):
    """The best paragraph for a quotation's words, as (score, paragraph,
    level): level "section", "division" or None.

    near(paragraph) says whether its homily or tractate is one on the verse
    being commented on. A catena gathers the Fathers' comments verse by verse,
    so when the best paragraph of all is in one of those, it is judged
    against them only: it does not have to beat every other homily in the
    library by a margin, though their number grows with every chapter added
    and brings chance near-misses with it. Otherwise, the whole library is searched with the same thresholds, and the
    homily on the verse is also taken when its own two best paragraphs are
    the two best of all, or it leads by NEAR_LEAD."""
    if len(words) < MIN_WORDS:
        return None
    total = sum(idf.get(w, max(idf.values())) for w in words)
    scored = sorted(((sum(idf[w] for w in words & c[6]) / total, c) for c in candidates),
                    key=lambda x: -x[0])
    if not scored:
        return None
    on_verse = [x for x in scored if near(x[1])]
    if near(scored[0][1]) and (found := judge(on_verse)):
        return found
    if found := judge(scored):
        return found
    best, para = scored[0]
    division = para[3].split(".")[0]
    other_division = next((s for s, c in scored if c[3].split(".")[0] != division), 0)
    if best >= DIVISION[0] and near(para) and (
            best - other_division >= NEAR_LEAD
            or (len(scored) > 1 and scored[1][1][3].split(".")[0] == division)):
        return best, para, "division"
    # Last, the homily on the verse when the quoted words run through it: its
    # three best paragraphs average higher than any other homily's, so one
    # paragraph elsewhere that happens to share them does not decide it.
    spread = {}
    for s, c in scored:
        top = spread.setdefault((c[0], c[3].split(".")[0]), [])
        if len(top) < SPREAD:
            top.append((s, c))
    ranked = sorted(spread.values(), key=lambda top: -sum(s for s, _ in top) / SPREAD)
    lead = ranked[0]
    mean = lambda top: sum(s for s, _ in top) / SPREAD    # noqa: E731
    if (near(lead[0][1]) and lead[0][0] >= DIVISION[0]
            and mean(lead) - (mean(ranked[1]) if len(ranked) > 1 else 0) >= SPREAD_LEAD):
        return lead[0][0], lead[0][1], "division"
    return None


def overlaps(span, entry):
    """True if a text's verses (from library/texts/) overlap an excerpt's."""
    if not span:
        return False
    key = lambda ref: tuple(int(x) for x in ref.split(".")[1:])     # noqa: E731
    return key(span["start"]) <= key(entry["end"]) and key(entry["start"]) <= key(span["end"])


def text_spans():
    """{(work, source page): verses} for the whole texts in library/texts/."""
    spans = {}
    for p in glob.glob(os.path.join(ROOT, "library", "texts", "*", "*.json")):
        t = load(p)
        for source in {t["source"]} | {para["source"] for para in t["paragraphs"] if "source" in para}:
            spans[(t["work"], source)] = t["verses"]
    return spans


def catena_quotations(entries, labels, candidates, idf, held, spans=None):
    spans = spans or {}
    rows = []
    for e in entries:
        text = e["text"]
        marks = list(LABEL.finditer(text))
        for i, m in enumerate(marks):
            work = labels.get(m[1].upper())
            if not work:
                continue
            seg = text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)]
            found = match_quotation(content_words(seg), [c for c in candidates if c[0] == work], idf,
                                    near=lambda c, e=e: overlaps(spans.get((c[0], c[1])), e))
            if not found:
                continue
            score, (_, source, pid, loc, a, b, _), level = found
            excerpt = None
            if level == "section":
                excerpt = next((x for s, t, x in held.get((work, source), []) if s < b and a < t), None)
            rows.append({"in": e["id"], "at": m.start(), "label": m[0], "work": work,
                         "locus": loc if level == "section" else loc.split(".")[0], "source": source,
                         "para": pid if level == "section" else None, "excerpt": excerpt,
                         "score": round(score, 2), "found": "similar", "status": "detected"})
    return rows


# ---- The library ---------------------------------------------------------

def corrected_texts():
    fixes = {}
    for p in glob.glob(os.path.join(ROOT, "library", "corrections", "*.json")):
        c = load(p)
        fixes[c["work"]] = [(x["from"], x["to"]) for x in c["corrections"]]
    return fixes


def derive():
    """What the library should hold: {comments path: entries with loci},
    {citations path: file}, {quotations path: file}, problems."""
    manifest = load(os.path.join(ROOT, "sources", "manifest.json"))
    paths = {(f["work"], os.path.basename(f["path"])): os.path.join(ROOT, f["path"]) for f in manifest["files"]}
    parts = {os.path.join(ROOT, f["path"]): f.get("part") for f in manifest["files"]}
    works = {w["id"]: w for w in (load(p) for p in glob.glob(os.path.join(ROOT, "library", "works", "*.json")))}
    fixes = corrected_texts()
    pages, comments, citations, problems = {}, {}, {}, []
    held = {}                                # (work, source) -> [(start, end, excerpt id)]
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
                    pages[src] = read_page(src, parts[src])
                where = span(pages[src], e["text"])
                if where is None:
                    problems.append(f"{e['id']}: could not place the excerpt in {os.path.basename(src)}")
                    found = []
                else:
                    found = ccel_citations(pages[src], where, text)
                    held.setdefault((work["id"], os.path.basename(src)), []).append((*where, e["id"]))
                    if by_division:
                        loc = locus(pages[src], where[0], len(work["divisions"]))
                        if loc:
                            e = {**e, "locus": loc}
                        else:
                            problems.append(f"{e['id']}: no homily or tractate heading before it")
                kind = "source"
            else:
                if by_division:
                    problems.append(f"{e['id']}: loci are read from CCEL pages only")
                found = scan_citations(text, data["book"], int(ch), (e["start"], e["end"]))
                kind = "pattern"
            for at, ctext, start, end in found:
                start, end = scripture.english_span(start, end)
                rows.append({"in": e["id"], "at": at, "text": ctext, "start": start, "end": end,
                             "found": kind, "status": "detected"})
            comments.setdefault(path, {**data, "entries": []})["entries"].append(e)
        if rows:
            out = os.path.join(ROOT, "library", "citations", work["id"], f"{data['book']}.json")
            citations[out] = {"work": work["id"], "book": data["book"], "citations": rows}

    quotations = {}
    quoted = {w for labels in CATENAS.values() for w in labels.values()}
    for (work, _), path in sorted(paths.items()):
        if work in quoted and path.endswith(".html") and path not in pages:
            pages[path] = read_page(path, parts[path])
    by_work = {(w, os.path.basename(p)): pages[p] for (w, _), p in paths.items() if w in quoted and p in pages}
    every = paragraphs(by_work)
    for data in comments.values():
        labels = CATENAS.get(data["work"])
        if not labels:
            continue
        # word weights from the works this catena quotes only, so that adding
        # another catena's works leaves its quotations as they were
        candidates = [c for c in every if c[0] in labels.values()]
        df = {}
        for c in candidates:
            for w in c[6]:
                df[w] = df.get(w, 0) + 1
        idf = {w: math.log(len(candidates) / n) for w, n in df.items()}
        rows = catena_quotations(data["entries"], labels, candidates, idf, held, text_spans())
        if rows:
            out = os.path.join(ROOT, "library", "quotations", data["work"], f"{data['book']}.json")
            quotations[out] = {"work": data["work"], "book": data["book"], "quotations": rows}
    return comments, citations, quotations, problems


def keep_status(new, old, rows, fields):
    """Carry each person-set status over to the same row found again."""
    def key(c, seen):
        k = tuple(c[f] for f in fields)
        seen[k] = seen.get(k, 0) + 1
        return k + (seen[k],)
    seen = {}
    status = {key(c, seen): c["status"] for c in (old or {}).get(rows, [])}
    seen = {}
    for c in new[rows]:
        c["status"] = status.get(key(c, seen), "detected")
    return new


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="change nothing; exit 1 if anything would change")
    args = ap.parse_args(argv)
    comments, citations, quotations, problems = derive()
    changed = []
    for path, data in comments.items():
        if load(path) != data:
            changed.append(path)
            if not args.check:
                dump(path, data)
    for kind, found, rows, fields in (("citations", citations, "citations", ("in", "text", "start", "end")),
                                      ("quotations", quotations, "quotations", ("in", "label", "work", "locus"))):
        existing = set(glob.glob(os.path.join(ROOT, "library", kind, "*", "*.json")))
        for path, data in found.items():
            old = load(path) if path in existing else None
            data = keep_status(data, old, rows, fields)
            if old != data:
                changed.append(path)
                if not args.check:
                    dump(path, data)
        for path in sorted(existing - set(found)):
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
    q = sum(len(c["quotations"]) for c in quotations.values())
    print(f"{loci} excerpts placed in their works, {n} citations of Scripture found, "
          f"{q} quotations of the Fathers traced")
    if args.check and changed:
        print("run python3 scripts/find_refs.py and commit what it writes")
    return 1 if problems or (args.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
