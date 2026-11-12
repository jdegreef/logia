"""Find the printed page of each excerpt copied from a page scan.

    python3 scripts/find_pages.py            # fetch archive.org's page index, write library/pages/
    python3 scripts/find_pages.py bengel     # only these works
    python3 scripts/find_pages.py --check    # exit 1 if a work's page file is missing or stale

The scanned works (kind "scan" in sources/manifest.json) come from
archive.org. For each scan, archive.org publishes its OCR as plain text with
an index of where each leaf's text begins and ends
(<id>_hocr_searchtext.txt.gz, <id>_hocr_pageindex.json.gz) and the page
number printed on each leaf (<id>_page_numbers.json); an older scan without
them has its DjVu XML (<id>_djvu.xml), which gives each leaf's words. This script finds the
opening words of each excerpt in that text, in the work's order, and records
the leaf and the printed page, so a reader can open the scan at the page the
excerpt was copied from. Nothing is typed: a page is recorded only where the
excerpt's words are found, and an excerpt not found is left without one.

The three files are fetched into a cache outside the repository
($LOGIA_CACHE, by default ~/.cache/logia/archive); library/pages/<work>.json
records each file's address and digest.
"""
import argparse
import datetime
import glob
import gzip
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get("LOGIA_CACHE", os.path.join(os.path.expanduser("~"), ".cache", "logia", "archive"))
FILES = ("hocr_pageindex.json.gz", "hocr_searchtext.txt.gz", "page_numbers.json")
LEAD = 7          # words of an excerpt's opening looked for in the scan
TRIES = 6         # windows of LEAD words tried, further into the excerpt


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def archive_id(url):
    """(item, the stem of its files) from a scan's address: most items name
    their files after the item, some after the book's title."""
    m = re.match(r"https://archive\.org/(?:stream|details|download)/([^/]+)/([^/?#]+?)(?:_djvu\.txt)?$", url)
    if not m:
        return None
    stem = urllib.parse.unquote(m[2])
    return m[1], stem


def fetch(scan, name):
    ident, stem = scan
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9_.-]", "_", f"{stem}_{name}"))
    url = f"https://archive.org/download/{ident}/{urllib.parse.quote(stem)}_{name}"
    if os.path.exists(path + ".missing"):
        return url, None, None
    if not os.path.exists(path):
        req = urllib.request.Request(url, headers={"User-Agent": "logia-find-pages/1.0"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=120) as r, open(path + ".part", "wb") as f:
                    f.write(r.read())
                break
            except urllib.error.HTTPError as err:
                if err.code == 404:
                    open(path + ".missing", "w").close()
                    return url, None, None
                if err.code < 500 or attempt == 3:
                    print(f"  {url}: HTTP {err.code}, left out", file=sys.stderr)
                    return url, None, None
                time.sleep(2 ** (attempt + 1))
        os.replace(path + ".part", path)
    with open(path, "rb") as f:
        data = f.read()
    return url, hashlib.sha256(data).hexdigest(), data


def djvu_pages(xml):
    """(text, [[start, end]] per leaf) from a scan's DjVu XML."""
    parts, index, at = [], [], 0
    for obj in re.findall(r"<OBJECT\b.*?</OBJECT>", xml, re.S):
        page = " ".join(html.unescape(w) for w in re.findall(r"<WORD[^>]*>([^<]*)</WORD>", obj)) + "\n"
        parts.append(page)
        index.append([at, at + len(page)])
        at += len(page)
    return "".join(parts), index


def words(text):
    """[(word, offset)]: letters only, lower case, as both texts are compared."""
    return [(m[0].lower(), m.start()) for m in re.finditer(r"[A-Za-z]+", text)]


class Scan:
    def __init__(self, scan):
        ident = scan
        self.ident = scan[0]
        self.files = []
        got = {}
        for name in FILES:
            url, digest, data = fetch(ident, name)
            if data is not None:
                self.files.append({"url": url, "sha256": digest})
                got[name] = data
        if "hocr_searchtext.txt.gz" in got and "hocr_pageindex.json.gz" in got:
            text = gzip.decompress(got["hocr_searchtext.txt.gz"]).decode("utf-8", "replace")
            self.index = json.loads(gzip.decompress(got["hocr_pageindex.json.gz"]))
        else:
            # Older scans have no hOCR; their DjVu XML holds each leaf's words.
            url, digest, data = fetch(ident, "djvu.xml")
            if data is None:
                self.ok = False
                return
            self.files.append({"url": url, "sha256": digest})
            text, self.index = djvu_pages(data.decode("utf-8", "replace"))
        self.ok = True
        numbers = json.loads(got["page_numbers.json"]).get("pages", []) if "page_numbers.json" in got else []
        self.printed = [p.get("pageNumber") or "" for p in numbers]
        ws = words(text)
        self.seq = [w for w, _o in ws]
        self.offsets = [o for _w, o in ws]
        self.grams = {}
        for i in range(len(self.seq) - LEAD + 1):
            self.grams.setdefault(tuple(self.seq[i:i + LEAD]), []).append(i)

    def leaf(self, offset):
        """The leaf (counted from 0) whose text holds a character offset."""
        lo, hi = 0, len(self.index) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            start, end = self.index[mid][0], self.index[mid][1]
            if offset < start:
                hi = mid - 1
            elif offset >= end:
                lo = mid + 1
            else:
                return mid
        return None

    def find(self, text, after):
        """(word index, leaf) of an excerpt's opening, at or after word `after`."""
        seq = [w for w, _o in words(text)]
        for k in range(TRIES):
            gram = tuple(seq[k * LEAD:(k + 1) * LEAD])
            if len(gram) < LEAD:
                break
            hits = self.grams.get(gram, [])
            later = [i for i in hits if i >= after] or hits
            if later and len(set(hits)) <= 3:
                i = later[0]
                leaf = self.leaf(self.offsets[i])
                if leaf is not None:
                    return i, leaf
        return None


def work_scans(work):
    ids = []
    for f in load(os.path.join(ROOT, "sources", "manifest.json"))["files"]:
        if f["work"] == work and f["kind"] == "scan":
            ident = archive_id(f["url"])
            if ident and ident not in ids:
                ids.append(ident)
    return ids


def entries(work):
    out = []
    for path in sorted(glob.glob(os.path.join(ROOT, "library", "comments", work, "*.json"))):
        out += load(path)["entries"]
    return out


def find_work(work):
    scans = [s for s in (Scan(i) for i in work_scans(work)) if s.ok]
    pages, missed, pos = {}, 0, {s.ident: 0 for s in scans}
    for c in entries(work):
        hit = None
        for s in scans:
            got = s.find(c["text"], pos[s.ident])
            if got:
                hit = (s, *got)
                break
        if not hit:
            missed += 1
            continue
        s, i, leaf = hit
        pos[s.ident] = i
        printed = s.printed[leaf] if leaf < len(s.printed) else ""
        pages[c["id"]] = [s.ident, leaf, printed]
    about = ("The leaf of the archive.org scan each excerpt begins on (counted from 0) and the page number printed "
             "on it, found by scripts/find_pages.py. Excerpts not found are left out.")
    return {"work": work, "about": about,
            "scans": [{"id": s.ident, "files": s.files} for s in scans],
            "retrieved": datetime.date.today().isoformat(), "found": len(pages), "missed": missed, "pages": pages}


def scanned_works():
    files = load(os.path.join(ROOT, "sources", "manifest.json"))["files"]
    return sorted({f["work"] for f in files if f["kind"] == "scan"})


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("works", nargs="*")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if a page file names an excerpt the library no longer has")
    args = ap.parse_args()
    works = args.works or scanned_works()
    out_dir = os.path.join(ROOT, "library", "pages")
    if args.check:
        bad = []
        for w in works:
            path = os.path.join(out_dir, f"{w}.json")
            if os.path.exists(path):
                ids = {c["id"] for c in entries(w)}
                stale = [x for x in load(path)["pages"] if x not in ids]
                if stale:
                    bad.append(f"{w}: {len(stale)} excerpts no longer in the library, e.g. {stale[0]}")
        print("\n".join(bad) or "library/pages/ is up to date")
        sys.exit(1 if bad else 0)
    os.makedirs(out_dir, exist_ok=True)
    for w in works:
        data = find_work(w)
        with open(os.path.join(out_dir, f"{w}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(f"{w}: {data['found']} excerpts placed on a page, {data['missed']} not found")


if __name__ == "__main__":
    main()
