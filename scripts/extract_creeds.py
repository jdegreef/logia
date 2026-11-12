"""Copy the creeds, conciliar decrees and confessions from their CCEL source pages.

    python3 scripts/extract_creeds.py           # write library/creeds/
    python3 scripts/extract_creeds.py --check   # exit 1 if library/creeds/ is out of date

Logia's "Creeds and councils" layer sets the creeds and confessions of the
churches beside the Scripture they cite. Each document in DOCUMENTS below
is read from its saved CCEL pages (sources/creeds/, listed in
sources/manifest.json under the work "creeds") into
library/creeds/<id>.json, one section per paragraph, article, question
and answer, or canon, as the page divides it:

- the words are the page's own, as for excerpts and whole texts: footnotes,
  footnote markers and page numbers are left out, and spacing is
  normalised. Schaff prints the Latin, Greek or German beside the English,
  in a table; only the English column is taken (a cell whose words are
  mostly marked as another language is left out). An English paragraph that
  a page break splits over two rows of the table is joined again: where the
  page indents the first line of a paragraph, a row that is not indented
  goes on with the paragraph before it.
- a section's `label` is what the page prints over it and at its start:
  the last heading before it ("Chapter I. Of the Holy Scripture") and the
  number it opens with ("I", "CANON I", "1"), or null where the
  page prints neither. Headings are the page's headings (h1-h6, th, a
  centred cell or paragraph, or one listed for a part in DOCUMENTS).
- `cites` are the Scripture references CCEL's editors marked, read as
  scripts/extract_texts.py reads them for whole texts, in the English
  (KJV) verse numbering CCEL marks: `at` and `text` are where the
  reference is printed in the section's text. Proof texts, which Schaff
  prints as footnotes to an article (the Westminster Confession), are
  kept too, with `"note": true` and `at` where the footnote marker stands;
  a footnote is taken as proof texts only when it holds nothing but
  references, so Schaff's own notes on the text (which cite Scripture as
  he discusses it) are not made into the document's citations.

Which documents there are, which pages and which paragraphs of them make
each one up, and the facts of edition and rights are configured here; the
text is always read from the saved sources. scripts/verify_sources.py
checks every section against its source.
"""
import argparse
import glob
import os
import re
import sys
from html.parser import HTMLParser

import find_refs
import scripture

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "library", "creeds")
SKIP = find_refs.SKIP
VOID = find_refs.VOID
BLOCKS = {"p", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6"}
HEADS = {"th", "h1", "h2", "h3", "h4", "h5", "h6"}
# The number a section opens with: "1.", "I.", "CANON I.—", "Canon I.—",
# "Art. I.", "Article I.", "Question 1.", "Q. 1."
NUMBER = re.compile(r"^((?:CANON|Canon|ARTICLE|Article|Art\.|ART\.|Question|QUESTION|Ques\.|Q\.)\s+)?"
                    r"([IVXLC]+|\d+)\.(?=\s|—|-|$)")
# What a footnote of proof texts may hold besides its references.
PROOF_WORDS = {"comp", "compare", "see", "cf", "also", "and", "with", "ver", "vers", "vs", "v", "ch", "chap",
               "etc", "sqq", "f", "ff", "throughout", "the", "whole", "chapter", "chapters"}

NPNF14 = ("Henry R. Percival (ed.), The Seven Ecumenical Councils of the Undivided Church, A Select Library of "
          "Nicene and Post-Nicene Fathers, Second Series, Vol. XIV, ed. Philip Schaff and Henry Wace (1900), "
          "CCEL edition (from a reprint by T&T Clark, Edinburgh, and Wm. B. Eerdmans, Grand Rapids)")
SCHAFF2 = ("Philip Schaff, The Creeds of Christendom, with a History and Critical Notes, Vol. II, The Greek and "
           "Latin Creeds, with Translations (New York: Harper & Brothers, 1877), CCEL edition (from a printing "
           "marked 'Sixth Edition', reprinted by arrangement with Harper and Row; copyright 1877 by Harper & "
           "Brothers, 1905 and 1919 by David S. Schaff)")
SCHAFF3 = ("Philip Schaff, The Creeds of Christendom, with a History and Critical Notes, Vol. III, The "
           "Evangelical Protestant Creeds, with Translations (New York: Harper & Brothers, 1877), CCEL edition "
           "(from a printing marked 'Fourth Edition—Revised and Enlarged', Baker Book House paperback, Grand "
           "Rapids, 1977, reprinted by arrangement with Harper and Row; copyright 1877 by Harper & Brothers, "
           "1905 and 1919 by David S. Schaff)")
PD = "public domain: published before 1931 (US)"
SCHAFF_PRINTING = ("CCEL transcribes a later printing of Schaff, revised by David S. Schaff (copyright 1905 and "
                   "1919) and holding matter added up to 1928; confirm against a scan of the 1877 first edition "
                   "that this document reads the same there, and David S. Schaff's dates if a revision of his is "
                   "in it")
PERCIVAL = ("to confirm: Henry R. Percival died in 1903; the volume does not name the translator of this "
            "document (Percival's preface says the translations are mostly other scholars'), and the 1900 "
            "printing should be compared with CCEL's reprint")
SHARED = "Shared by the churches"
NOTES_FOOTNOTES = ("Schaff's footnotes are left out; Scripture references CCEL marks in the text are its cites.")

# Each document: its record, and the parts it is read from: a source page
# (sources/creeds/<page>) and the first and last block of it to take (CCEL
# ids; None for the page's first or last). A part may also give:
#   "cols": the table columns to read (where a page prints two English
#           texts side by side, the Thirty-Nine Articles of 1571 and 1801);
#   "headings": blocks the page sets as headings by a class only (NPNF);
#   "text": a pattern for blocks set like headings that are part of the
#           text ("Answer.", a rubric such as "Say:");
#   "indent": True: a row that is not indented goes on with the paragraph
#           before it (see the docstring);
#   "starts": a pattern a section starts with; any other block goes on
#           with the section before it (a question of a catechism and its
#           answer, numbered "1."); with "bold": True, only where the
#           page prints that number in bold (the Orthodox Catechism numbers
#           its questions in bold, the lists in its answers not);
#   "per_heading": True: everything under a heading is one section (a
#           commandment of Luther's Small Catechism with its explanation);
#   "omit": [first, last] blocks left out, marked " ... " in the section
#           (a list of books printed as a table), and said in the notes.
DOCUMENTS = [
    # Shared by the churches
    {"id": "apostles", "title": "The Apostles' Creed", "kind": "creed", "tradition": SHARED, "year": None,
     "edition": SCHAFF2, "translation": "The received English form, as Schaff prints it", "published": 1877,
     "rights": {"basis": PD, "worldwide": "to confirm: Philip Schaff died in 1893; " + SCHAFF_PRINTING},
     "notes": "The received form (forma recepta), in the English Schaff prints after the Latin and Greek; NPNF "
              "II.14 does not print the Apostles' Creed. The page gives the received form no year. "
              + NOTES_FOOTNOTES,
     "parts": [{"page": "creeds2.iv.i.i.i.html", "from": "iv.i.i.i-p12", "to": "iv.i.i.i-p16"}]},
    {"id": "nicaea", "title": "The Creed of Nicaea", "kind": "creed", "tradition": SHARED, "year": 325,
     "edition": NPNF14, "translation": "Not named in the volume", "published": 1900,
     "rights": {"basis": PD, "worldwide": PERCIVAL},
     "notes": "The creed of the First Council of Nicaea (A.D. 325, as the volume's title page for the council "
              "gives it), with its anathemas, as NPNF II.14 prints it under 'The Ecthesis of the Synod at Nice'. "
              "The Greek words in brackets are the translation's own.",
     "parts": [{"page": "npnf214.vii.iii.html", "from": "vii.iii-p5", "to": "vii.iii-p7", "headings": ["vii.iii-p5"]}]},
    {"id": "constantinople", "title": "The Niceno-Constantinopolitan Creed", "kind": "creed", "tradition": SHARED,
     "year": 381, "edition": NPNF14, "translation": "Not named in the volume", "published": 1900,
     "rights": {"basis": PD, "worldwide": PERCIVAL},
     "notes": "The creed of the First Council of Constantinople (A.D. 381), as NPNF II.14 prints it under 'The "
              "Holy Creed Which the 150 Holy Fathers Set Forth, Which is Consonant with the Holy and Great Synod "
              "of Nice'. The marks (I) and (II) in the text refer to the volume's Notes I and II, which follow the "
              "creed on the page.",
     "parts": [{"page": "npnf214.ix.iii.html", "from": "ix.iii-p6", "to": "ix.iii-p7"}]},
    {"id": "chalcedon", "title": "The Definition of Faith of the Council of Chalcedon", "kind": "council",
     "tradition": SHARED, "year": 451, "edition": NPNF14, "translation": "Not named in the volume",
     "published": 1900, "rights": {"basis": PD, "worldwide": PERCIVAL},
     "notes": "The Definition of Faith (A.D. 451), as NPNF II.14 prints it from Labbe and Cossart, Concilia, Tom. "
              "IV., col. 562. The Definition quotes the creeds of Nicaea and Constantinople only by their first "
              "words ('We believe in one God, etc.'), as printed. The bishops' acclamations that follow it on the "
              "page, and the volume's notes, are not part of it.",
     "parts": [{"page": "npnf214.xi.xiii.html", "from": "xi.xiii-p3", "to": "xi.xiii-p12"}]},
    {"id": "athanasian", "title": "The Athanasian Creed", "kind": "creed", "tradition": SHARED, "year": None,
     "edition": SCHAFF2,
     "translation": "The English of the sixteenth century (1548), as in the English editions of the Book of Common "
                    "Prayer, with Schaff's alternative readings in brackets",
     "published": 1877, "rights": {"basis": PD, "worldwide": "to confirm: Philip Schaff died in 1893; "
                                   + SCHAFF_PRINTING},
     "notes": "The Symbolum Quicunque in its forty-four verses, numbered as Schaff numbers them; the English column "
              "only. Schaff's note on the translation is on the page (Notes, 3); his notes on the verses are left "
              "out. The page gives the creed no year.",
     "parts": [{"page": "creeds2.iv.i.iv.html", "from": "iv.i.iv-p3", "to": "iv.i.iv-p89", "cols": [2]}]},
    # Roman Catholic
    *[{"id": f"trent-{n}", "title": f"The Council of Trent, {name} Session: {subject}", "kind": "council",
       "tradition": "Roman Catholic", "year": year, "edition": SCHAFF2,
       "translation": "J. Waterworth, The Canons and Decrees of the Sacred and Œcumenical Council of Trent "
                      "(London, 1848), as Schaff prints it",
       "published": 1877,
       "rights": {"basis": PD, "worldwide": "to confirm: Philip Schaff died in 1893, J. Waterworth in 1876; "
                  + SCHAFF_PRINTING},
       "notes": "The dogmatic decrees and canons of the session, in the English column of Schaff's parallel Latin "
                "and English. Schaff leaves out the Council's decrees on the reformation of discipline (his note on "
                "creeds2.v.i.i.html). " + NOTES_FOOTNOTES,
       "parts": [{"page": page, "from": None, "to": None, "cols": [2], "indent": True}]}
      for n, name, subject, year, page in (
          (4, "Fourth", "The Canonical Scriptures", 1546, "creeds2.v.i.i.ii.html"),
          (5, "Fifth", "Original Sin", 1546, "creeds2.v.i.i.iii.html"),
          (6, "Sixth", "Justification", 1547, "creeds2.v.i.i.iv.html"),
          (13, "Thirteenth", "The Most Holy Sacrament of the Eucharist", 1551, "creeds2.v.i.i.vi.html"))],
    # Orthodox
    {"id": "orthodox-catechism", "title": "The Longer Catechism of the Orthodox, Catholic, Eastern Church",
     "kind": "catechism", "tradition": "Orthodox", "year": 1830, "edition": SCHAFF2,
     "translation": "R. W. Blackmore, The Doctrine of the Russian Church (Aberdeen, 1845), as Schaff prints it",
     "published": 1877,
     "rights": {"basis": PD, "worldwide": "to confirm: Philip Schaff died in 1893; R. W. Blackmore's dates; "
                + SCHAFF_PRINTING},
     "notes": "The catechism of Philaret of Moscow, in the edition Schaff names (Moscow, at the Synodical Press, "
              "1830); Schaff prints the English only, and numbers the questions himself. Each section is a "
              "question with its answer. The Confession of Dositheus and the Orthodox Confession of Peter Mogila "
              "are in the same volume in Greek and Latin only, so they are not here.",
     "parts": [{"page": p, "from": None, "to": None, "starts": r"\d+\. ", "bold": True}
               for p in ("creeds2.vi.iii.i.html", "creeds2.vi.iii.ii.html", "creeds2.vi.iii.iii.html",
                         "creeds2.vi.iii.iv.html", "creeds2.vi.iii.v.html")]},
    # Lutheran
    {"id": "augsburg", "title": "The Augsburg Confession", "kind": "confession", "tradition": "Lutheran",
     "year": 1530, "edition": SCHAFF3,
     "translation": "Charles P. Krauth (1868), revised by him for Schaff (1874), from the Latin editio princeps "
                    "of 1531, with the chief additions of the German in brackets, as Schaff says on the page",
     "published": 1877,
     "rights": {"basis": PD, "worldwide": "to confirm: Philip Schaff died in 1893, Charles P. Krauth in 1883; "
                + SCHAFF_PRINTING},
     "notes": "The English column of Schaff's parallel Latin and English: the Preface to the Emperor, the "
              "twenty-one Chief Articles of Faith with Article XXII, the seven Articles on Abuses, and the "
              "Conclusion. The signatures printed after the Conclusion are not included. " + NOTES_FOOTNOTES,
     "parts": [{"page": "creeds3.iii.ii.html", "from": "iii.ii-p6.11", "to": "iii.ii-p6.1335", "cols": [2],
                "indent": True}]},
    {"id": "luther-small-catechism", "title": "Luther's Small Catechism", "kind": "catechism",
     "tradition": "Lutheran", "year": 1529, "edition": SCHAFF3,
     "translation": "Not named on the page; Schaff calls it 'more literal than those in use among the Lutheran "
                    "churches in America'",
     "published": 1877,
     "rights": {"basis": PD, "worldwide": "to confirm: Philip Schaff died in 1893; the translator; "
                + SCHAFF_PRINTING},
     "notes": "The English column of Schaff's parallel German and English, from the German of the third edition "
              "(Wittenberg, 1531): the five parts, with the form of confession Schaff prints in Part IV. Each "
              "section is what the page prints under one heading (a commandment, an article of the Creed, a "
              "petition) with its questions and answers. Schaff does not print the prayers and the table of "
              "duties that follow Part V in other editions. " + NOTES_FOOTNOTES,
     "parts": [{"page": "creeds3.iii.iii.html", "from": "iii.iii-p1.15", "to": None, "cols": [2],
                "per_heading": True, "text": r"(:|^Yes, dear sir\.)$"}]},
    # Reformed
    {"id": "heidelberg", "title": "The Heidelberg Catechism", "kind": "catechism", "tradition": "Reformed",
     "year": 1563, "edition": SCHAFF3, "translation": "Not named on the page", "published": 1877,
     "rights": {"basis": PD, "worldwide": "to confirm: Philip Schaff died in 1893; the translator; "
                + SCHAFF_PRINTING},
     "notes": "The English column of Schaff's parallel German and English, in its one hundred and twenty-nine "
              "questions; each section is a question with its answer, under the part headings the page prints "
              "(the answer to Question 92, the Ten Commandments, is printed under a heading for each commandment, "
              "so each is a section). Schaff prints no proof texts with it. " + NOTES_FOOTNOTES,
     "parts": [{"page": "creeds3.iv.vi.html", "from": None, "to": None, "cols": [2], "per_heading": True,
                "text": r"^Answer\.$"}]},
    {"id": "westminster", "title": "The Westminster Confession of Faith", "kind": "confession",
     "tradition": "Reformed (Presbyterian)", "year": 1647, "edition": SCHAFF3,
     "translation": None, "published": 1877,
     "rights": {"basis": PD, "worldwide": "to confirm: Philip Schaff died in 1893; " + SCHAFF_PRINTING},
     "notes": "The English column of Schaff's parallel English and Latin. Schaff takes the English from the second "
              "edition, 'with the Quotations and Texts of Scripture annexed' (Edinburgh: Evan Tyler, 1647), with "
              "spelling and punctuation modernised, and inserts the changes of the American revision in their "
              "places in italics (chiefly Chapters XXIII and XXXI), with minor changes in footnotes; those "
              "footnotes are left out. The proof texts are Schaff's footnotes to each clause, kept as cites "
              "with \"note\": true where CCEL marks them. Proof texts differ between editions of the Confession; "
              "which edition's proofs Schaff prints is to confirm. The list of the books of the Old and New "
              "Testaments in Chapter I, section II, is printed as a table in columns and is left out of the "
              "section (marked ' ... '); it is read on the CCEL page. The names of the Assembly's officers "
              "printed after Chapter XXXIII are not included.",
     "parts": [{"page": "creeds3.iv.xvii.ii.html", "from": "iv.xvii.ii-p3.12", "to": "iv.xvii.ii-p11.218", "cols": [1],
                "indent": True, "omit": [["iv.xvii.ii-p3.79", "iv.xvii.ii-p3.261"]]}]},
    # Anglican
    {"id": "thirty-nine-articles", "title": "The Thirty-Nine Articles of Religion", "kind": "confession",
     "tradition": "Anglican", "year": 1571, "edition": SCHAFF3, "translation": None, "published": 1877,
     "rights": {"basis": PD, "worldwide": "to confirm: Philip Schaff died in 1893; " + SCHAFF_PRINTING},
     "notes": "The English of 1571, with its old spelling, which Schaff reprints from the authorized London "
              "edition of John Cawood (1571), from the second of his three columns: the Latin of 1562 and the "
              "American revision of 1801 stand beside it on the page and are not taken. From the title of the "
              "Articles to the Ratification; the table of the Articles and the printer's colophon after it are "
              "not included, nor the Royal Declaration Schaff prints before them from later English editions.",
     "parts": [{"page": "creeds3.iv.xi.html", "from": "iv.xi-p19", "to": "iv.xi-p114", "cols": [2],
                "indent": True}]},
    {"id": "methodist-articles", "title": "The Methodist Articles of Religion", "kind": "confession",
     "tradition": "Anglican (Methodist)", "year": 1784, "edition": SCHAFF3, "translation": None,
     "published": 1877,
     "rights": {"basis": PD, "worldwide": "to confirm: Philip Schaff died in 1893; " + SCHAFF_PRINTING},
     "notes": "The twenty-five Articles John Wesley drew up for the American Methodists from the Thirty-Nine "
              "Articles, adopted in 1784; Schaff takes the text from The Doctrines and Discipline of the Methodist "
              "Episcopal Church (ed. Bishop Harris, New York, 1872), which has Article XXIII as adopted in 1804. "
              + NOTES_FOOTNOTES,
     "parts": [{"page": "creeds3.v.vi.html", "from": "v.vi-p3", "to": "v.vi-p61"}]},
    # Baptist
    {"id": "new-hampshire", "title": "The New Hampshire Baptist Confession", "kind": "confession",
     "tradition": "Baptist", "year": 1833, "edition": SCHAFF3, "translation": None, "published": 1877,
     "rights": {"basis": PD, "worldwide": "to confirm: Philip Schaff died in 1893; " + SCHAFF_PRINTING},
     "notes": "The Declaration of Faith in eighteen articles, drawn up by John Newton Brown about 1833, as Schaff "
              "prints it. The proof texts are Schaff's footnotes to each clause, kept as cites with \"note\": true "
              "where CCEL marks them; which edition of the Confession they follow is to confirm.",
     "parts": [{"page": "creeds3.v.ii.ii.html", "from": "v.ii.ii-p2", "to": "v.ii.ii-p37"}]},
]


def load(path):
    return find_refs.load(path)


class CreedPage(HTMLParser):
    """A CCEL page's main text (footnotes and page numbers left out, as in
    find_refs.Page), with each block (p, td, th, h1-h6) it is divided into,
    the Scripture references CCEL marks in it, and its footnotes (mnote):
    where each is anchored in the text, its words and its marked
    references."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.size, self.refs = [], 0, []
        self.blocks, self.notes = [], []
        self.stack = []                      # open elements: (tag, attrs, foreign, block)
        self.depth = 0                       # inside a skipped element
        self.note, self.note_depth = None, 0
        self.open_ref = None
        self.cols = []                       # cells seen in each open row

    def foreign(self):
        return bool(self.stack) and self.stack[-1][2]

    def block(self):
        return next((b for *_, b in reversed(self.stack) if b is not None), None)

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        if self.note is not None:
            self.note_depth += 1
            if self.note_depth > 1 and (self.depth or classes & (SKIP - {"Footnote"})):
                self.depth += 1
                return
            if tag == "a" and "scripRef" in classes:
                m = find_refs.GOBIBLE.search(a.get("onclick") or "")
                self.open_ref = [self.note["size"], m.groups() if m else None]
            return
        if self.depth:
            self.depth += 1
            return
        if "mnote" in classes:
            self.note = {"anchor": self.size, "text": [], "size": 0, "refs": []}
            self.note_depth = 1
            return
        if classes & SKIP:
            self.depth = 1
            return
        lang = a.get("lang")
        foreign = (self.foreign() if lang is None else not lang.lower().startswith("en")) or "Greek" in classes
        style = a.get("style") or ""
        b = None
        if tag == "tr":
            self.cols.append(0)
        if tag in BLOCKS:
            parent = self.block()
            if parent:
                parent["container"] = True
            col = parent["col"] if parent else None
            if tag in ("td", "th") and self.cols:
                self.cols[-1] += 1
                col = self.cols[-1]
            styles = [s[1].get("style") or "" for s in self.stack if s[0] in ("tr", "td", "th")] + [style]
            b = {"tag": tag, "id": a.get("id"), "class": a.get("class"), "style": ";".join(styles),
                 "col": col, "start": self.size, "end": None, "letters": 0, "foreign": 0, "container": False,
                 "bold": None}
            self.blocks.append(b)
        self.stack.append((tag, a, foreign, b))
        if tag == "a" and "scripRef" in classes:
            m = find_refs.GOBIBLE.search(a.get("onclick") or "")
            self.open_ref = [self.size, m.groups() if m else None]

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.note is not None:
            if self.depth:
                self.depth -= 1
            elif tag == "a" and self.open_ref:
                self.note["refs"].append((self.open_ref[0], self.note["size"], self.open_ref[1]))
                self.open_ref = None
            self.note_depth -= 1
            if self.note_depth == 0:
                self.note["text"] = "".join(self.note["text"])
                self.notes.append(self.note)
                self.note = None
            return
        if self.depth:
            self.depth -= 1
            return
        if tag == "a" and self.open_ref:
            self.refs.append((self.open_ref[0], self.size, self.open_ref[1]))
            self.open_ref = None
        while self.stack:
            t, _, _, b = self.stack.pop()
            if b is not None:
                b["end"] = self.size
            if t == "tr" and self.cols:
                self.cols.pop()
            if t == tag:
                break

    def handle_data(self, data):
        if self.note is not None:
            if not self.depth:
                self.note["text"].append(data)
                self.note["size"] += len(data)
            return
        if self.depth:
            return
        self.text.append(data)
        self.size += len(data)
        b = self.block()
        if b is not None:
            if b["bold"] is None and data.strip():
                b["bold"] = any(t in ("b", "strong") or "bold" in (a.get("style") or "")    # it opens in bold
                                for t, a, *_ in self.stack)
            n = sum(ch.isalpha() for ch in data)
            b["letters"] += n
            if self.foreign():
                b["foreign"] += n


def read_page(path):
    p = CreedPage()
    with open(path, encoding="utf-8") as f:
        p.feed(f.read())
    for b in p.blocks:
        if b["end"] is None:
            b["end"] = p.size
    return {"text": "".join(p.text), "refs": p.refs, "blocks": p.blocks, "notes": p.notes}


def words(s):
    return " ".join(s.split())


def proof_texts(note):
    """A footnote's marked references, if it holds nothing else."""
    text = note["text"]
    if not note["refs"]:
        return []
    rest = text
    for s, e, _ in sorted(note["refs"], reverse=True):
        rest = rest[:s] + " " + rest[e:]
    if any(w.lower() not in PROOF_WORDS for w in re.findall(r"[^\W\d_]+", rest)):
        return []
    w = words(text)
    shift = len(text) - len(text.lstrip())
    refs = [(max(0, s - shift), max(0, e - shift), p) for s, e, p in note["refs"]]
    page = {"text": text.lstrip(), "refs": refs}
    return find_refs.ccel_citations(page, (0, len(page["text"])), w)


def is_heading(b, part, w=""):
    if part.get("text") and re.search(part["text"], w):
        return False                         # set like a heading, but part of the text
    style = b["style"].replace(" ", "")
    return (b["tag"] in HEADS or "text-align:center" in style or b["id"] in part.get("headings", ()))


def indented(b):
    return "text-indent" in b["style"]


def sections(doc, part, page, source, problems):
    """The sections of one part of a document."""
    blocks = page["blocks"]
    ids = {b["id"]: b for b in blocks if b["id"]}
    whole = {"start": 0, "end": len(page["text"])}
    first = ids.get(part["from"]) if part["from"] else whole
    last = ids.get(part["to"]) if part["to"] else whole
    if not first or not last:
        problems.append(f"{doc['id']}: {source}: no block {part['from'] if not first else part['to']}")
        return []
    omit = []
    for a, z in part.get("omit", ()):
        if a not in ids or z not in ids:
            problems.append(f"{doc['id']}: {source}: no block {a if a not in ids else z} to leave out")
            continue
        omit.append((ids[a]["start"], ids[z]["end"]))
    chosen = [b for b in blocks if first["start"] <= b["start"] and b["end"] <= last["end"]
              and not b["container"] and b["letters"] and b["foreign"] * 2 < b["letters"]
              and (b["col"] is None or b["col"] in part.get("cols", (b["col"],)))]
    out, heading, in_heading, omitted = [], [], False, False
    for b in chosen:
        if any(a <= b["start"] and b["end"] <= z for a, z in omit):
            if out and not omitted:
                out[-1]["text"] += " ..."
            omitted = True
            continue
        text = page["text"][b["start"]:b["end"]]
        w = words(text)
        if not w:
            continue
        if is_heading(b, part, w) and not omitted:
            if not in_heading:
                heading = []
            heading.append(w)
            in_heading = True
            continue
        # after a part left out, the paragraph goes on
        joins = out and (omitted or (not in_heading and (part.get("per_heading") or (
            part.get("indent") and not indented(b)))) or bool(
            part.get("starts") and not (re.match(part["starts"], w) and (b["bold"] or not part.get("bold")))))
        in_heading = omitted = False
        if joins:
            sec = out[-1]
            # a sentence a page break splits goes on after a space; a new
            # paragraph (an answer under its question) after a blank line
            sep = " " if (not re.search(r"[.?!:;\]”’\"')]$", sec["text"]) or w[0].islower()
                          or sec["text"].endswith("...")) else "\n\n"
            offset = len(sec["text"]) + len(sep)
            sec["text"] += sep + w
        else:
            m = NUMBER.match(w)
            number = (m[1] or "") + m[2] if m else None
            head = " ".join(heading).rstrip(".:,") if heading else None
            label = ", ".join(x for x in (head, number) if x) or None
            sec = {"id": b["id"], "label": label, "text": w, "source": source, "cites": []}
            out.append(sec)
            offset = 0
        for at, t, s, e in find_refs.ccel_citations(page, (b["start"], b["end"]), w):
            sec["cites"].append({"at": offset + at, "text": t, "start": s, "end": e, "note": False})
        for n in page["notes"]:
            if b["start"] <= n["anchor"] <= b["end"]:
                at = offset + min(len(w), len(words(text[:n["anchor"] - b["start"]])))
                for _, t, s, e in proof_texts(n):
                    sec["cites"].append({"at": at, "text": t, "start": s, "end": e, "note": True})
    return out


def derive():
    manifest = load(os.path.join(ROOT, "sources", "manifest.json"))
    files = {os.path.basename(f["path"]): f for f in manifest["files"] if f["work"] == "creeds"}
    out, problems, pages = {}, [], {}
    for doc in DOCUMENTS:
        secs = []
        for part in doc["parts"]:
            f = files.get(part["page"])
            if not f:
                problems.append(f"{doc['id']}: {part['page']} is not in sources/manifest.json for creeds")
                continue
            path = os.path.join(ROOT, f["path"])
            if path not in pages:
                pages[path] = read_page(path)
            secs += sections(doc, part, pages[path], part["page"], problems)
        if not secs:
            problems.append(f"{doc['id']}: no sections")
            continue
        seen = set()
        for s in secs:
            if s["id"] in seen:
                problems.append(f"{doc['id']}: two sections with the id {s['id']}")
            seen.add(s["id"])
            for c in s["cites"]:
                if not (scripture.parse(c["start"]) and scripture.parse(c["end"])):
                    problems.append(f"{doc['id']}: {s['id']}: {c['text']!r} is not a reference")
        record = {k: v for k, v in doc.items() if k != "parts"}
        record["full_text_url"] = files[doc["parts"][0]["page"]]["url"]
        record["status"] = "ai_draft"
        record["sections"] = secs
        order = ["id", "title", "kind", "tradition", "year", "edition", "translation", "published",
                 "full_text_url", "rights", "notes", "status", "sections"]
        out[os.path.join(OUT, f"{doc['id']}.json")] = {k: record[k] for k in order}
    return out, problems


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="change nothing; exit 1 if anything would change")
    args = ap.parse_args(argv)
    docs, problems = derive()
    existing = set(glob.glob(os.path.join(OUT, "*.json")))
    changed = []
    for path, data in docs.items():
        if path not in existing or load(path) != data:
            changed.append(path)
            if not args.check:
                find_refs.dump(path, data)
    for path in sorted(existing - set(docs)):
        changed.append(path)
        if not args.check:
            os.remove(path)
    for p in problems:
        print(p)
    verb = "out of date" if args.check else "updated"
    for path in changed:
        print(f"{os.path.relpath(path, ROOT)}: {verb}")
    n = sum(len(d["sections"]) for d in docs.values())
    c = sum(len(s["cites"]) for d in docs.values() for s in d["sections"])
    print(f"{len(docs)} creeds and confessions, {n} sections, {c} citations of Scripture")
    if args.check and changed:
        print("run python3 scripts/extract_creeds.py and commit what it writes")
    return 1 if problems or (args.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
