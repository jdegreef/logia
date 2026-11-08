"""Check that every commentary excerpt is really in its source.

Excerpts are copied, never written: library/comments/<work>/<BOOK>.json holds
each passage exactly as its source reads, and sources/ keeps the source text
the passage was copied from (listed in sources/manifest.json). This script
compares the two.

- A digital source (a transcription such as CCEL's) must contain the excerpt
  word for word. Footnotes, footnote markers (and any superscript) and page
  numbers are ignored,
  since the brief for copying drops them, and a passage cut with "..." is
  checked piece by piece.
- A whole homily or tractate (library/texts/, from scripts/extract_texts.py)
  is checked like a digital excerpt, paragraph by paragraph.
- A scan source (archive.org OCR) mixes margin notes, running heads and page
  numbers into its lines, so it is checked in runs of six words: at least
  MIN_SCAN_SHARE of an excerpt's words must lie in a run found in the scan.
- The checks above compare Latin letters, so every Greek or Hebrew word in an
  excerpt or a whole text is also looked for, as it is written, in its source:
  original-language text is copied, never typed.

Exit status 1 if any excerpt fails.

    python3 scripts/verify_sources.py           # every work
    python3 scripts/verify_sources.py calvin    # one work
"""
import glob
import html
import json
import os
import re
import sys
import unicodedata
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_SCAN_SHARE = 0.9
CHUNK = 80          # letters per piece checked in a digital source
SKIP = {"Note", "NoteRef", "mnote", "Footnote", "footer_note", "pb", "page"}
ORIGINAL = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff\u0590-\u05ff]+")    # Greek and Hebrew
VOID = {"br", "img", "hr", "meta", "link", "input", "wbr", "col", "area", "base", "source"}


class _Text(HTMLParser):
    """The text of an HTML extract, leaving out footnotes and page numbers."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.depth = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        # A superscript is a footnote marker ("<sup>f</sup>" in tertullian.org pages).
        if self.depth or tag == "sup" or set((dict(attrs).get("class") or "").split()) & SKIP:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag not in VOID and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            self.out.append(data)


def letters(text):
    """Lower-case letters only: spacing, punctuation and quote styles differ
    between a transcription and its copy, the words do not."""
    return re.sub(r"[^a-z]", "", text.lower())


def source_letters(path):
    text = open(path, encoding="utf-8").read()
    if path.endswith((".html", ".htm")):
        p = _Text()
        p.feed(text)
        text = " ".join(p.out)
    else:
        # archive.org's text view is an HTML page: "&" is saved as "&amp;".
        text = html.unescape(text)
    text = re.sub(r"-\s*\n\s*", "", text)   # a word broken at a line end
    return letters(text)


def source_original(path):
    """The source as written, for finding Greek and Hebrew words in it."""
    return unicodedata.normalize("NFC", html.unescape(open(path, encoding="utf-8").read()))


def check_original(excerpt, raw):
    for w in ORIGINAL.findall(unicodedata.normalize("NFC", excerpt)):
        if w not in raw:
            return f"Greek or Hebrew not in source: {w}"
    return None


def check_digital(excerpt, src):
    for piece in re.split(r"\s*\.\.\.\s*|\n\s*\n", excerpt):
        n = letters(piece)
        for i in range(0, len(n), CHUNK):
            chunk = n[i:i + CHUNK]
            if len(chunk) >= 20 and chunk not in src:
                return f"not in source: ...{piece.strip()[:70]}..."
            if len(n) < 20 and n and n not in src:
                return f"not in source: {piece.strip()[:70]}"
    return None


def check_scan(excerpt, src):
    """Share of the excerpt's words that sit in some six-word run found in
    the scan. A run that crosses a dropped margin note or page head is not
    found, but the words on either side are covered by the runs next to it."""
    words = []
    for piece in re.split(r"\s*\.\.\.\s*", excerpt):
        words.append([w for w in (letters(x) for x in piece.split()) if w])
    covered = total = 0
    for ws in words:
        total += len(ws)
        if len(ws) < 6:
            covered += len(ws) if "".join(ws) in src else 0
            continue
        hit = [False] * len(ws)
        for i in range(len(ws) - 5):
            if "".join(ws[i:i + 6]) in src:
                hit[i:i + 6] = [True] * 6
        covered += sum(hit)
    share = covered / total if total else 1
    return None if share >= MIN_SCAN_SHARE else f"only {covered} of {total} words found in the scan ({share:.0%})"


def main(argv):
    manifest = json.load(open(os.path.join(ROOT, "sources", "manifest.json"), encoding="utf-8"))
    files = {}
    for f in manifest["files"]:
        files.setdefault(f["work"], {})[os.path.basename(f["path"])] = f
    only = set(argv)
    failures = total = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "library", "comments", "*", "*.json"))):
        data = json.load(open(path, encoding="utf-8"))
        work = data["work"]
        if only and work not in only:
            continue
        cache = {}
        for e in data["entries"]:
            total += 1
            problems = []
            for key in e["sources"]:
                meta = files.get(work, {}).get(key)
                if not meta:
                    problems.append(f"source {key} is not in sources/manifest.json")
                    continue
                if key not in cache:
                    path = os.path.join(ROOT, meta["path"])
                    cache[key] = source_letters(path), source_original(path)
                check = check_digital if meta["kind"] == "digital" else check_scan
                problem = check(e["text"], cache[key][0]) or check_original(e["text"], cache[key][1])
                if problem is None:
                    problems = []
                    break           # one listed source holding it is enough
                problems.append(f"{key}: {problem}")
            if problems:
                failures += 1
                print(f"{e['id']}: " + "; ".join(problems))
    print(f"{total - failures} of {total} excerpts found in their sources")
    paras = bad = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "library", "texts", "*", "*.json"))):
        t = json.load(open(path, encoding="utf-8"))
        if only and t["work"] not in only:
            continue
        meta = files.get(t["work"], {}).get(t["source"])
        if not meta:
            bad += 1
            print(f"{os.path.relpath(path, ROOT)}: source {t['source']} is not in sources/manifest.json")
            continue
        read = {}
        for para in t["paragraphs"]:
            paras += 1
            key = para.get("source", t["source"])     # a book's text runs over several pages
            meta = files.get(t["work"], {}).get(key)
            if not meta:
                bad += 1
                print(f"{os.path.relpath(path, ROOT)}: {para['id']}: source {key} is not in sources/manifest.json")
                continue
            if key not in read:
                read[key] = (source_letters(os.path.join(ROOT, meta["path"])),
                             source_original(os.path.join(ROOT, meta["path"])))
            src, raw = read[key]
            problem = check_digital(para["text"], src) or check_original(para["text"], raw)
            if problem:
                bad += 1
                print(f"{os.path.relpath(path, ROOT)}: {para['id']}: {problem}")
    if paras:
        print(f"{paras - bad} of {paras} paragraphs of whole texts found in their sources")
    return 1 if failures or bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
