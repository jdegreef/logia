"""Copy whole homilies and tractates from their CCEL source pages.

    python3 scripts/extract_texts.py           # write library/texts/
    python3 scripts/extract_texts.py --check   # exit 1 if library/texts/ is out of date

An excerpt is the part of a work Logia sets beside a verse; a homily or a
tractate is also worth reading straight through (roadmap, item 5). For each
work with its own divisions (`divisions` in library/works/<work>.json), each
of its CCEL source pages is copied, paragraph by paragraph, into
library/texts/<work>/<n>.json, where n is the homily or tractate number:

- the words are the page's own, as for excerpts: footnotes, footnote
  markers and page numbers are left out, and spacing is normalised;
- each paragraph keeps CCEL's id (so a link can reach the same paragraph on
  CCEL), its locus ("2.8", Homily 2, section 8), the Scripture references
  CCEL marks in it, and the ids of the Logia excerpts that hold it;
- each paragraph also has the verse it expounds (`verse`), and the text the
  span of verses it covers (`verses`): a second way of dividing the work,
  by the Gospel it comments on (roadmap, item 6). Both are read from what
  the page prints: the heading's verse ("John i. 6", "Chapter I. 6–14") and
  the verse marks a homily gives as it moves on ("Ver. 7."). A homily that
  prints no later mark is taken to stay on its heading's verse; under a
  heading that names a range, a paragraph has no verse until a mark gives
  one.

The book's title lines before the first homily or tractate heading are not
part of it and are left out. scripts/verify_sources.py checks every paragraph
against its source.
"""
import argparse
import glob
import json
import os
import re
import sys

import find_refs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEADING = re.compile(r"^(Homily|Tractate)\s+([IVXLC]+)\.")
# The verse a homily or tractate opens on, as its heading prints it.
# "John i. 6", "John i. 28, 29", "John i. 35–37", "Chapter I. 33", "Chapter I. 32, 33", "Chapter I. 1–5",
# "Chapter II. 23–25; III. 1–5", "John iv. 54; v. 1", "Chapter XI. 55–57; XII", "Chapter IX".
OPENS = re.compile(r"^(?:John\s+(?P<ch>[ivxl]+)\.\s+(?P<v>\d+)(?:(?:[–-]|,\s*)(?P<v2>\d+))?"
                   r"(?:;\s*(?P<ch2>[ivxl]+)\.\s+(?P<e>\d+)(?:[–-](?P<f>\d+))?)?"
                   r"|Chapter\s+(?P<CH>[IVXL]+)\.\s+(?P<a>\d+)(?:(?:[–-]|,\s*)(?P<b>\d+))?"
                   # and on into the next chapter: "Chapter II. 23–25; III. 1–5"
                   # ("Chapter XI. 55–57; XII": into the next chapter, its verses unnamed)
                   r"(?:;\s*(?P<CH2>[IVXL]+)(?:\.\s+(?P<c>\d+)(?:[–-](?P<d>\d+))?)?)?"
                   # or a whole chapter: "Chapter IX"
                   r"|Chapter\s+(?P<WH>[IVXL]+)\.?)$")
# A verse mark at the start of a paragraph or of a section: "Ver. 7.", "[2.] Ver. 13."
VER = re.compile(r"^(?:\[\d+\.\]\s*)?Ver\.\s+(\d+)\.")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def verse_count(book, chapter):
    """The number of verses in a chapter, from the Open Word Bible text."""
    return len(load(os.path.join(ROOT, "bible", "owb", "en", f"{book}.{chapter}.json"))["verses"])


def derive():
    manifest = load(os.path.join(ROOT, "sources", "manifest.json"))
    works = {w["id"]: w for w in (load(p) for p in glob.glob(os.path.join(ROOT, "library", "works", "*.json")))}
    out, problems = {}, []
    for f in manifest["files"]:
        work = works.get(f["work"])
        if not work or not isinstance(work["divisions"], list) or not f["path"].endswith(".html"):
            continue
        path = os.path.join(ROOT, f["path"])
        page = find_refs.read_page(path)
        text, starts = page["text"], page["paras"] + [len(page["text"])]
        source = os.path.basename(path)
        held = []
        for c in glob.glob(os.path.join(ROOT, "library", "comments", work["id"], "*.json")):
            for e in load(c)["entries"]:
                if e["sources"][0] == source and (where := find_refs.span(page, e["text"])):
                    held.append((*where, e["id"]))
        comment_files = glob.glob(os.path.join(ROOT, "library", "comments", work["id"], "*.json"))
        books = {os.path.basename(c)[:-5] for c in comment_files}       # the book the work comments on
        book = books.pop() if len(books) == 1 else None
        paras, number, title, chapter, start_chapter, verse, span = [], None, None, None, None, None, None
        heading_end = None                   # where a heading that crosses a chapter says the text ends
        for i, (a, b) in enumerate(zip(starts, starts[1:])):
            words = " ".join(text[a:b].split())
            if not words:
                continue
            if number is None:
                m = HEADING.match(words)
                if not m:
                    continue                 # the book's title lines
                number, title = find_refs.scripture.roman(m[2]), words
            o = OPENS.match(words)
            if o and book and chapter is None:
                chapter = start_chapter = find_refs.scripture.roman(o["ch"] or o["CH"] or o["WH"])
                if o["WH"]:
                    span = [1, verse_count(book, chapter)]
                else:
                    first = int(o["v"] or o["a"])
                    span = [first, int(o["v2"] or o["b"] or first)]
                if o["CH2"] or o["ch2"]:
                    # with no verse named in the next chapter, at least its first
                    heading_end = (find_refs.scripture.roman(o["CH2"] or o["ch2"]),
                                   int(o["d"] or o["c"] or o["f"] or o["e"] or 1))
                # A heading with a range ("Chapter I. 1–5") says what the whole
                # text covers, not which verse each paragraph is on.
                verse = span[0] if span[0] == span[1] else None
            elif (m := VER.match(words)) and chapter is not None:
                verse = int(m[1])
                if verse < span[1] and verse < span[0]:
                    # A mark that goes back past where the text began: it has
                    # gone on into the next chapter (Homily XXI, John i. 49 to ii. 4).
                    chapter += 1
                    span[1] = verse
                else:
                    span[1] = max(span[1], verse)
            cites = find_refs.ccel_citations(page, (a, b), words)
            paras.append({
                "id": page["para_ids"][i], "locus": find_refs.locus(page, a), "text": words,
                "cites": [{"at": at, "text": t, "start": s, "end": e} for at, t, s, e in cites],
                "excerpts": [x for s, t, x in held if s < b and a < t],
                "verse": f"{book}.{chapter}.{verse}" if verse else None,
            })
        if number is None:
            problems.append(f"{f['path']}: no Homily or Tractate heading")
            continue
        dest = os.path.join(ROOT, "library", "texts", work["id"], f"{number}.json")
        if dest in out:
            problems.append(f"{f['path']}: a second page for {work['id']} {number}")
            continue
        if span is None:
            problems.append(f"{f['path']}: no heading names the verse it opens on")
            continue
        out[dest] = {"work": work["id"], "locus": str(number), "title": title, "source": source, "url": f["url"],
                     "verses": {"start": f"{book}.{start_chapter}.{span[0]}",
                                "end": "{}.{}.{}".format(book, *max((chapter, span[1]), heading_end or (0, 0)))},
                     "paragraphs": paras}
    return out, problems


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="change nothing; exit 1 if anything would change")
    args = ap.parse_args(argv)
    texts, problems = derive()
    existing = set(glob.glob(os.path.join(ROOT, "library", "texts", "*", "*.json")))
    changed = []
    for path, data in texts.items():
        if path not in existing or load(path) != data:
            changed.append(path)
            if not args.check:
                find_refs.dump(path, data)
    for path in sorted(existing - set(texts)):
        changed.append(path)
        if not args.check:
            os.remove(path)
    for p in problems:
        print(p)
    verb = "out of date" if args.check else "updated"
    for path in changed:
        print(f"{os.path.relpath(path, ROOT)}: {verb}")
    n = sum(len(t["paragraphs"]) for t in texts.values())
    print(f"{len(texts)} whole homilies and tractates, {n} paragraphs")
    if args.check and changed:
        print("run python3 scripts/extract_texts.py and commit what it writes")
    return 1 if problems or (args.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
