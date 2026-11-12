"""Import the Revised Common Lectionary's Sunday and feast-day readings.

    python3 scripts/import_rcl.py 2025-26 2026-27 2027-28

Reads the "All Seasons" calendar of each church year from the Vanderbilt
Divinity Library's Revised Common Lectionary site
(lectionary.library.vanderbilt.edu/calendar/<year>/?season=all), and writes
library/lectionary/rcl.json: each day's name, date and readings as the site
lists them, with the address, date and digest of each page read. Only
the day names, dates and references are kept; the pages also carry the
readings' NRSV text, which is not copied. The readings are numbered as
English Bibles number them; the site maps them to the Open Word Bible's
numbering when it builds.

The Revised Common Lectionary is copyright 1992 by the Consultation on Common
Texts, which allows its table of readings to be reproduced with that notice
(library/lectionary/rcl.json "rights").
"""
import datetime
import hashlib
import html
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://lectionary.library.vanderbilt.edu/calendar/{year}/?season=all"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (logia-import-rcl)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def clean(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def cell_refs(td):
    """The references in one cell, as the site prints them: a reading, or
    two joined by "or"."""
    refs = [clean(m) for m in re.findall(r"<span[^>]*>(.*?)</span>", td, re.S)]
    return [r for r in refs if r]


def parse(page):
    """[(name, date, note, {slot: [refs]})] for each row of the year's table."""
    text = page.decode("utf-8", "replace")
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", text, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 5:
            continue
        head = cells[0]
        m = re.search(r"<a[^>]*>(.*?)</a>", head, re.S)
        d = re.search(r"([A-Z][a-z]{2} \d{2}, \d{4})", head)
        if not m or not d:
            continue
        name = clean(m[1])
        date = datetime.datetime.strptime(d[1], "%b %d, %Y").date().isoformat()
        rest = clean(re.sub(r"<a[^>]*>.*?</a>", " ", head, flags=re.S).replace(d[1], ""))
        # The last cell is the art and prayer; the one before it the Gospel,
        # and before that the epistle. In the season after Pentecost the
        # Old Testament and psalm are printed for both of the lectionary's
        # tracks, so they are kept together, in the order printed.
        reading_cells = [c for c in cells[1:] if "<span" in c]
        if len(reading_cells) < 2:
            continue
        readings = {"first_and_psalm": [r for c in reading_cells[:-2] for r in cell_refs(c)],
                    "epistle": cell_refs(reading_cells[-2]), "gospel": cell_refs(reading_cells[-1])}
        out.append({"name": name, "date": date, **({"note": rest} if rest else {}), "readings": readings})
    return out


def main():
    years = sys.argv[1:] or ["2025-26", "2026-27", "2027-28"]
    days, sources = [], []
    for y in years:
        url = URL.format(year=y)
        page = fetch(url)
        rows = parse(page)
        if not rows:
            sys.exit(f"{url}: no readings found; the page may have changed")
        sources.append({"url": url, "retrieved": datetime.date.today().isoformat(),
                        "download_sha256": hashlib.sha256(page).hexdigest(), "days": len(rows)})
        days += rows
    days = sorted({(d["date"], d["name"]): d for d in days}.values(), key=lambda d: (d["date"], d["name"]))
    data = {"lectionary": "Revised Common Lectionary",
            "about": "Sunday and feast-day readings of the Revised Common Lectionary, as the Vanderbilt Divinity "
                     "Library lists them, imported by scripts/import_rcl.py. References are numbered as English "
                     "Bibles number them.",
            "rights": "Revised Common Lectionary copyright 1992 Consultation on Common Texts. Used by permission. "
                      "Only the table of readings is copied, not the Bible text.",
            "sources": sources, "days": days}
    os.makedirs(os.path.join(ROOT, "library", "lectionary"), exist_ok=True)
    with open(os.path.join(ROOT, "library", "lectionary", "rcl.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"library/lectionary/rcl.json: {len(days)} days")


if __name__ == "__main__":
    main()
