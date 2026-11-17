"""Copy a commentator's own words, in the language he wrote, beside the English.

    python3 scripts/extract_originals.py            # write library/originals/
    python3 scripts/extract_originals.py --check    # exit 1 if a file is missing or stale

Logia's English excerpts are translations. Where the original edition is
public domain and scanned, this script copies the original's note on each
verse from the scan's text (saved under sources/), so a reader can see what
the commentator wrote. Nothing is typed or translated here: each paragraph is
the scan's text, with only line-end hyphens joined, running heads, page
numbers and footnotes left out, and a Greek word the scan has mixed with
Latin letters or digits left out (" ... ").

Which verse a note is on is read from the scan, not assumed. The original
numbers its verses its own way (Bengel's John 1 has 52 verses where English
Bibles have 51), so each note's Greek lemma is looked for in the Greek text
of the nearby verses (bible/owb/en/<BOOK>.<chapter>.json, "source"), and the
note goes with the verse whose Greek holds most of the lemma's words. The
pairing of a note with an English excerpt is the script's, and is ai_draft
until a person checks it.

Only Bengel's Gnomon on John so far (PILOTS below).
"""
import argparse
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PILOTS = [{
    "work": "bengel",
    "book": "JHN",
    "language": "la",
    "source": "djohalbertibenge00beng.txt",
    "edition": "D. Joh. Alberti Bengelii Gnomon Novi Testamenti, editio tertia (1773) by "
               "M. Ernst Bengel, reprinted by Johann Steudel, Tübingen: L. F. Fues, 1855; "
               "text from archive.org OCR",
    "edition_short": "Bengel's third edition (1773), as reprinted at Tübingen in 1855",
    "scan": "https://archive.org/details/djohalbertibenge00beng",
    "rights": "Public domain: Bengel died in 1752 and the 1855 reprint is out of copyright everywhere.",
    "about": "Fausset's English (1858) was translated from this third edition, so the notes "
             "follow the English closely, lemma by lemma. The scan's misreadings are kept "
             "(Greek χ for κ is common); a Greek word mixed with Latin letters is left out.",
}]

GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]")
LATIN = re.compile(r"[A-Za-z0-9]")
# A verse's note opens a line: "v. 14. σὰρξ, caro) ...". A line that only
# starts with a cross-reference ("v. 16. refertur ad plenum") has no lemma
# closed by ")" soon after.
MARK = re.compile(r"^\s*[‘'=.]?\s*(?:Vv|CV|lv|νυ|[vVΥνυγyY][il]?)(?:[.,:;]{1,2}\s?|\s)(\d{1,2})[.,:;]\s+(.*)$")
# (the scan reads "v. 12." as "Υ. 12.", "γ. 12.", "vi 24.", "v..32," and so on)
HEAD = re.compile(r"^\s*\S{0,4}\s*J[O0][HB][.,:;]?\s")     # a running head: "JOH. I, 1. 301", "JOH I, 14—16."
CHAPTER = re.compile(r"^\s*CAP")
NOTE = re.compile(r"^\s*(?:\d{1,2}|\*)\)\s")      # a footnote: "1) Hic Evangelistarum ..."


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def plain(word):
    """A Greek word without accents or breathings, for matching: the scan
    often reads κ as χ and ignores final sigma."""
    w = unicodedata.normalize("NFD", word.lower())
    w = "".join(c for c in w if not unicodedata.combining(c))
    return w.replace("ς", "σ").replace("χ", "κ")


def greek_words(text):
    return [plain(w) for w in re.findall(r"[Ͱ-Ͽἀ-῿]+", text) if len(w) > 1]


def verse_greek(book, chapter):
    """{verse: set of plain Greek words} from the OWB chapter's Greek. A
    record that spans verses is split between them in proportion to the
    words its pieces give each verse."""
    path = os.path.join(ROOT, "bible", "owb", "en", f"{book}.{chapter}.json")
    if not os.path.exists(path):
        return {}
    out = {}
    for r in load(path)["records"]:
        words = greek_words(r.get("source", ""))
        ids = {}
        for piece in r.get("pieces", []):
            for i in piece[2] or ():
                ids.setdefault(i, piece[0])
        counts = [sum(1 for v in ids.values() if v == verse) for verse in r["verses"]]
        if len(r["verses"]) < 2 or not sum(counts):
            for v in r["verses"]:
                out.setdefault(v, set()).update(words)
            continue
        at, total = 0, sum(counts)
        for v, n in zip(r["verses"], counts):
            take = round(len(words) * n / total)
            out.setdefault(v, set()).update(words[max(0, at - 1):at + take + 1])   # a word's overlap at the seam
            at += take
    return out


def body_lines(text):
    """The scan's lines from the first verse note on, with page furniture
    left out: (line, chapter_break_before)."""
    lines = text.split("\n")
    start = next(i for i, x in enumerate(lines) if re.match(r"^\s*v\.\s?1\.\s", x))
    out, broke, in_note = [], False, False
    for x in lines[start:] + [""]:
        if not x.strip():
            in_note = False
            continue
        if HEAD.match(x):
            in_note = False
            continue
        if CHAPTER.match(x):
            broke = True
            continue
        if re.fullmatch(r"\s*[\dIVXL\W]{1,4}\s*", x):   # a page number or a stray mark
            continue
        x = re.sub(r"^\s*\d\)\s+(?=[vV]\.\s?\d)", "", x)     # "1) v. 9. ὅμοιος": a marker before the verse
        if NOTE.match(x) and not MARK.match(x):
            in_note = True
        if in_note:
            continue
        out.append((x.rstrip(), broke))
        broke = False
    return out


def tidy(text):
    """Join the lines of a note and leave out what is not Bengel's text."""
    text = re.sub(r"[-=]\s*\n\s*", "", text)          # a word broken at a line end
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"(?:(?<=\s)|^)\d\)(?=\s|$)", "", text)    # a footnote marker: "μέσος 1) ὑμῶν"
    words = []
    for w in text.split():
        # a Greek word the scan has mixed with Latin letters or digits is noise
        bare = w.strip(".,;:()[]?!·'‘’\"\u1fbd\u02bc")
        if GREEK.search(w) and (LATIN.search(bare) or (len(bare) == 1 and bare.isupper() and bare not in "ὉἩὮὍ")):
            if words and words[-1] != "...":
                words.append("...")
            continue
        words.append(w)
    return re.sub(r"\s+", " ", " ".join(words)).strip()


def fits(words, verses, lo, hi):
    """The best share of a lemma's Greek words found in one of verses lo..hi."""
    return max((sum(1 for w in words if w in verses.get(v, ())) / len(words) for v in range(lo, hi + 1)),
               default=0) if words else 0


def notes(text, book):
    """[(chapter, verse as numbered in the original, text)]: one per verse
    note, in the scan's order."""
    out, chapter, cur, buf, heading = [], 1, 0, None, False
    for x, broke in body_lines(text):
        heading = heading or broke          # a chapter heading counts at the next verse note
        m = MARK.match(x)
        if heading and not m and buf:
            # the first note under a chapter heading is on verse 1, however the
            # scan reads its "v. 1." ("Vidi Πρὸ ἐξ ἡμερῶν ...")
            m = re.match(r"^\s*(?:\S+\s)?\s*(.*)$", x)
            m = ["", "1", m[1]]
        lemma = m and (")" in m[2][:120] or GREEK.match(re.sub(r"^[\W\d]*", "", m[2]) or "-"))
        if lemma:
            broke, heading = heading, False
            n = int(m[1])
            if buf and not broke and n <= 2 and cur >= 12:
                # A chapter whose heading the scan lost ("CAPUT V."), or a
                # misread number ("v. 1." for "v. 51."): the Greek tells which.
                words = greek_words(m[2].split(")")[0])
                broke = fits(words, verse_greek(book, chapter + 1), 1, 3) >= fits(
                    words, verse_greek(book, chapter), max(1, cur - 8), cur + 3)
            if buf and broke:
                chapter, cur = chapter + 1, 0
            if not (cur < n <= cur + 8):
                n = cur + 1          # a misread number ("v. 33." for "v. 7."): it follows the last
            if buf:
                out.append(buf)
            buf = [chapter, n, [m[2]]]
            cur = n
        elif buf:
            buf[2].append(x)
    if buf:
        out.append(buf)
    return [(c, v, tidy("\n".join(ls))) for c, v, ls in out]


def lemmas(note):
    """A note's parts, one per lemma: Bengel puts " — " before each lemma
    ("— χάριτος χαὶ ἀληθείας, gratiae et veritatis) ..."). A dash not
    followed by a lemma closed with ")" is punctuation and stays."""
    parts = []
    for piece in re.split(r"\s—\s", note):
        if parts and not re.match(r"^(?:\.\.\.\s)?[^.()]{1,80}\)", piece):
            parts[-1] += " — " + piece
        else:
            parts.append(piece)
    return [p.strip() for p in parts if p.strip()]


def share(words, verse):
    """The share of a lemma's Greek words found in a verse's Greek. A word
    counts if the verse has one beginning with its first five letters, since
    the scan often misreads an ending ("ἔστι" for "ἔστιν"); short words
    (καί, ὁ) count only when a lemma has no others."""
    long = [w for w in words if len(w) > 3] or words
    if not long or not verse:
        return 0.0
    stems = {w[:k] for w in verse for k in (4, 5)}
    return sum(1 for w in long if w[:5] in stems) / len(long)


def place(book, found, english=frozenset()):
    """Give each note the English-Bible verse whose Greek holds its lemma:
    within a chapter the verses go in order, so the best order of verses for
    all its notes is chosen at once. Each note scores the share of its
    lemma's words in the verse, less a little for each verse skipped and,
    to break a tie, for straying from the verse the original numbers. A
    verse the English translation comments on (english, {(chapter, verse)})
    scores a little more the first time a note reaches it, since the
    translation follows the original note for note."""
    placed, chapters = [], {}
    for n in found:
        chapters.setdefault(n[0], []).append(n)
    for chapter, notes_ in chapters.items():
        verses = verse_greek(book, chapter)
        if not verses:
            continue
        top = max(verses)
        words = [greek_words(text.split(")")[0]) for _c, _v, text in notes_]
        score = [[share(w, verses.get(v, ())) - STRAY * abs(v - n[1]) if v else float("-inf")
                  for v in range(top + 1)] for w, n in zip(words, notes_)]
        wanted = [WANTED if (chapter, v) in english else 0 for v in range(top + 1)]
        best = [[sc + w for sc, w in zip(score[0], wanted)]]
        back = []
        for i in range(1, len(notes_)):
            row, arg, run, at = [], [], float("-inf"), 0
            for v in range(top + 1):
                # the best earlier verse u <= v, less a little for each verse skipped
                if v and best[-1][v - 1] + 0.02 * (v - 1) > run:
                    run, at = best[-1][v - 1] + 0.02 * (v - 1), v - 1
                stay, skip = best[-1][v], run - 0.02 * v + wanted[v]
                prev, u = (stay, v) if stay >= skip else (skip, at)
                row.append(score[i][v] + prev)
                arg.append(u)
            best.append(row)
            back.append(arg)
        v = max(range(1, top + 1), key=lambda x: best[-1][x])
        path = [v]
        for arg in reversed(back):
            v = arg[v]
            path.append(v)
        path.reverse()
        for (c, numbered, text), v, sc in zip(notes_, path, score):
            placed.append({"chapter": c, "verse": max(v, 1), "numbered": numbered, "text": text,
                           "matched": round(max(sc[v] + STRAY * abs(v - numbered), 0), 2)})
    return placed


WANTED = 0.25       # what reaching a verse the English comments on is worth
STRAY = 0.03        # what each verse away from the one the original numbers costs


def build(pilot):
    src = os.path.join(ROOT, "sources", pilot["work"] + "-latin" if pilot["language"] == "la" else pilot["work"],
                       pilot["source"])
    with open(src, encoding="utf-8") as f:
        text = f.read()
    comments = load(os.path.join(ROOT, "library", "comments", pilot["work"], pilot["book"] + ".json"))
    english = set()
    for c in comments["entries"]:
        _b, ch, v1 = c["start"].split(".")
        english.update((int(ch), v) for v in range(int(v1), int(c["end"].split(".")[2]) + 1))
    placed = place(pilot["book"], notes(text, pilot["book"]), english)
    verses = {}
    for n in placed:
        key = f'{n["chapter"]}.{n["verse"]}'
        verses.setdefault(key, []).extend(lemmas(n["text"]))
    have = 0
    for c in comments["entries"]:
        _b, ch, v1 = c["start"].split(".")
        _b, _ch, v2 = c["end"].split(".")
        if any(f"{ch}.{v}" in verses for v in range(int(v1), int(v2) + 1)):
            have += 1
    return {
        "work": pilot["work"], "book": pilot["book"], "language": pilot["language"],
        "edition": pilot["edition"], "edition_short": pilot["edition_short"],
        "scan": pilot["scan"], "rights": pilot["rights"],
        "about": pilot["about"], "sources": [pilot["source"]], "status": "ai_draft",
        "reviewer": None,
        "excerpts": len(comments["entries"]), "excerpts_with_original": have,
        "verses": verses,
    }


def out_path(pilot):
    return os.path.join(ROOT, "library", "originals", pilot["work"], pilot["book"] + ".json")


def dump(data):
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if a file is missing or out of date")
    args = ap.parse_args()
    stale = 0
    for pilot in PILOTS:
        data, path = build(pilot), out_path(pilot)
        rel = os.path.relpath(path, ROOT)
        if args.check:
            if not os.path.exists(path) or open(path, encoding="utf-8").read() != dump(data):
                print(f"{rel} is out of date: run scripts/extract_originals.py")
                stale += 1
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(dump(data))
        print(f"{rel}: {len(data['verses'])} verses, {data['excerpts_with_original']} of "
              f"{data['excerpts']} English excerpts have the original beside them")
    if args.check and not stale:
        print("library/originals/ is up to date")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
