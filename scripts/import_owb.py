"""Import Open Word Bible chapters into bible/owb/.

Logia does not translate Scripture: its Bible text is the Open Word Bible
(CC0), read from a checkout of https://github.com/jdegreef/open-word-bible at
the commit pinned in bible/owb/SOURCE.json. Each chapter becomes one file,
bible/owb/en/<BOOK>.<chapter>.json, holding what the reader needs: the
English text at three levels, the word alignments of the Balanced level, the
SBLGNT Greek words with their MACULA data, the translation notes, headings
and cross-references.

    python3 scripts/import_owb.py --owb ../open-word-bible JHN.1

Run it again after changing the pin; review the diff like any other change.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "bible", "owb")
FIELDS = ("id", "text", "after", "lemma", "morph", "gloss", "strong")
DECISION_FIELDS = ("id", "layer", "levels", "category", "tokens", "choice",
                   "alternatives", "reason", "uncertain", "footnote")


def verse_of(ref):
    return int(ref.split(".")[2])


def pack_chapter(owb, book, chapter, markup, morph):
    files = sorted(glob.glob(os.path.join(owb, "content", book, f"{book}.{chapter}.*.json")),
                   key=lambda p: int(os.path.basename(p).split(".")[2].split("-")[0]))
    if not files:
        sys.exit(f"no Open Word Bible content for {book} {chapter}")
    grc = json.load(open(os.path.join(owb, "data", "grc", f"{book}.{chapter}.json"), encoding="utf-8"))
    xref = json.load(open(os.path.join(owb, "data", "crossrefs", f"{book}.json"), encoding="utf-8"))["refs"]
    heads = json.load(open(os.path.join(owb, "data", "headings", f"{book}.json"), encoding="utf-8"))["headings"]

    def pieces(text, aligns):
        """Split a Balanced rendering into [verse, text, tokens] pieces."""
        ranges = markup.alignment_ranges(text, [a["target_span"] for a in aligns]) if aligns else []
        out, at = [], 0
        for (s, e), a in zip(ranges, aligns):
            if s > at:
                out.append((text[at:s], None))
            out.append((text[s:e], a["tokens"]))
            at = e
        if at < len(text):
            out.append((text[at:], None))
        res, verse = [], None
        for chunk, toks in out:
            if toks is None:
                for v, part in markup.split_verses(chunk):
                    if v is not None:
                        verse = v
                    if part:
                        res.append([verse, markup.render(part), None])
            else:
                res.append([verse, markup.render(chunk), toks])
        return res

    def by_verse(text, first):
        d, v = {}, first
        for vv, part in markup.split_verses(text):
            if vv is not None:
                v = vv
            d[str(v)] = (d.get(str(v), "") + " " + markup.render(part)).strip()
        return d

    records = []
    for f in files:
        for r in json.load(open(f, encoding="utf-8"))["records"]:
            first = verse_of(r["refs"][0])
            en = r["renderings"]["en"]
            aligns = [a for a in r.get("alignments", []) if a["language"] == "en" and a["level"] == "B"]
            pcs = pieces(en["B"], aligns)
            for p in pcs:
                if p[0] is None:
                    p[0] = first
            records.append({
                "id": r["id"],
                "verses": [verse_of(x) for x in r["refs"]],
                "greek": r["source"]["text"],
                "gloss": r["literal_gloss"],
                "pieces": pcs,
                "L": by_verse(en["L"], first),
                "R": by_verse(en["R"], first),
                "decisions": [{k: d.get(k) for k in DECISION_FIELDS} for d in r.get("decisions", [])
                              if d["layer"] == "meaning" or d.get("language") == "en"],
                "heading": heads.get(r["id"], {}).get("en"),
                "status": r.get("status"),
            })
    verses = sorted({v for r in records for v in r["verses"]})
    words = {}
    for v in verses:
        toks = grc["verses"].get(f"{book}.{chapter}.{v}", [])
        words[str(v)] = [{**{k: t.get(k) for k in FIELDS}, "parse": morph.describe(t["morph"])} for t in toks]
    return {
        "book": book, "chapter": chapter, "verses": verses,
        "records": records, "greek": words,
        "crossrefs": {str(v): xref.get(f"{book}.{chapter}.{v}", [])[:8] for v in verses},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--owb", required=True, help="path to an open-word-bible checkout")
    ap.add_argument("chapters", nargs="+", help="chapters to import, e.g. JHN.1")
    args = ap.parse_args()
    owb = os.path.abspath(args.owb)
    sys.path.insert(0, owb)
    from owb import markup, morph  # noqa: E402  (the Open Word Bible's own code)

    commit = subprocess.run(["git", "-C", owb, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    pin = json.load(open(os.path.join(OUT, "SOURCE.json"), encoding="utf-8"))
    if commit != pin["commit"]:
        sys.exit(f"open-word-bible checkout is at {commit or 'an unknown commit'}, but bible/owb/SOURCE.json "
                 f"pins {pin['commit']}. Check out the pin, or update the pin on purpose.")
    books = json.load(open(os.path.join(owb, "data", "books.json"), encoding="utf-8"))["books"]
    json.dump({k: v["en"] for k, v in books.items()},
              open(os.path.join(OUT, "books.en.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    for ch in args.chapters:
        book, chapter = ch.split(".")
        data = pack_chapter(owb, book, int(chapter), markup, morph)
        path = os.path.join(OUT, "en", f"{book}.{chapter}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        print(f"{path}: {len(data['records'])} sentences, verses {data['verses'][0]}-{data['verses'][-1]}")


if __name__ == "__main__":
    main()
