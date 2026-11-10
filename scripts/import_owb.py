"""Import Open Word Bible chapters into bible/owb/.

Logia does not translate Scripture: its Bible text is the Open Word Bible
(CC0), read from a checkout of https://github.com/jdegreef/open-word-bible at
the commit pinned in bible/owb/SOURCE.json. Each chapter becomes one file,
bible/owb/en/<BOOK>.<chapter>.json, holding what the reader needs: the
English text at three levels, the word alignments of the Balanced level, the
original-language words with their MACULA data (SBLGNT Greek for the New
Testament, the Westminster Leningrad Codex for the Old), the translation
notes, headings and cross-references. bible/owb/versification.json is its
table of the Old Testament verses numbered otherwise in English Bibles.

The text keeps the Open Word Bible's variations as it has them: its reader
settings ({{gender:all people|men}}, {{christos:Christ|the Messiah}},
{{divine_name:the LORD|Yahweh}}, {{deity_pronoun:he|He}}, {{units:...}}) and
its poetry lines (\\q), so web/reader.js can show each reader the wording
they chose, as openwordbible.org does.

    python3 scripts/import_owb.py --owb ../open-word-bible --all
    python3 scripts/import_owb.py --owb ../open-word-bible JHN.1 PSA.23

Run it again after changing the pin; review the diff like any other change.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "bible", "owb")
FIELDS = ("id", "text", "after", "lemma", "morph", "gloss", "strong")
HEBREW_FIELDS = FIELDS + ("transliteration", "lang")
DECISION_FIELDS = ("id", "layer", "levels", "category", "tokens", "choice",
                   "alternatives", "reason", "uncertain", "footnote")


def verse_of(ref):
    return int(ref.split(".")[2])


def pack_chapter(owb, book, chapter, markup, morph):
    # A chapter is one file (JHN.2.json) or several passages (JHN.1.1-18.json).
    whole = os.path.join(owb, "content", book, f"{book}.{chapter}.json")
    files = [whole] if os.path.exists(whole) else sorted(
        glob.glob(os.path.join(owb, "content", book, f"{book}.{chapter}.*.json")),
        key=lambda p: int(os.path.basename(p).split(".")[2].split("-")[0]))
    if not files:
        sys.exit(f"no Open Word Bible content for {book} {chapter}")
    hebrew = os.path.exists(os.path.join(owb, "data", "hbo", f"{book}.{chapter}.json"))
    source = "hbo" if hebrew else "grc"
    words_file = json.load(open(os.path.join(owb, "data", source, f"{book}.{chapter}.json"), encoding="utf-8"))
    xref = json.load(open(os.path.join(owb, "data", "crossrefs", f"{book}.json"), encoding="utf-8"))["refs"]
    heads_path = os.path.join(owb, "data", "headings", f"{book}.json")
    heads = json.load(open(heads_path, encoding="utf-8"))["headings"] if os.path.exists(heads_path) else {}

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
                        res.append([verse, part, None])
            else:
                res.append([verse, chunk, toks])
        return res

    def by_verse(text, first):
        d, v = {}, first
        for vv, part in markup.split_verses(text):
            if vv is not None:
                v = vv
            d[str(v)] = (d.get(str(v), "") + " " + part).strip()
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
                "source": r["source"]["text"],
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
    def parse(t):
        if not hebrew:
            return morph.describe(t["morph"])
        try:
            return morph.describe_hebrew(t["morph"], "en", t.get("lang") or "H")
        except ValueError:
            return ""

    fields = HEBREW_FIELDS if hebrew else FIELDS
    words = {}
    for v in verses:
        toks = words_file["verses"].get(f"{book}.{chapter}.{v}", [])
        # The article a Hebrew preposition swallows has a row with no text;
        # the Open Word Bible leaves it out, and so does Logia.
        words[str(v)] = [{**{k: t.get(k) for k in fields}, "parse": parse(t)} for t in toks if t.get("text")]
    return {
        "book": book, "chapter": chapter, "source": source, "verses": verses,
        "records": records, "words": words,
        "crossrefs": {str(v): xref.get(f"{book}.{chapter}.{v}", [])[:8] for v in verses},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--owb", required=True, help="path to an open-word-bible checkout")
    ap.add_argument("--all", action="store_true", help="import every chapter of every book")
    ap.add_argument("chapters", nargs="*", help="chapters to import, e.g. JHN.1")
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
    # Every book in canonical order, with its English name and its number of
    # chapters (Hebrew numbering for the Old Testament, as the Open Word Bible).
    with open(os.path.join(OUT, "books.json"), "w", encoding="utf-8") as f:
        json.dump({k: {"en": v["en"], "chapters": v["chapters"]} for k, v in books.items()},
                  f, ensure_ascii=False, indent=1)
        f.write("\n")
    # The verses the Hebrew text numbers otherwise than English (KJV) Bibles,
    # which the commentators cite (a psalm's title is its verse 1): copied as is.
    shutil.copyfile(os.path.join(owb, "data", "versification.json"), os.path.join(OUT, "versification.json"))
    chapters = args.chapters
    if args.all:
        chapters = [f"{b}.{c}" for b, v in books.items() for c in range(1, v["chapters"] + 1)]
    if not chapters:
        ap.error("name the chapters to import, or pass --all")
    for ch in chapters:
        book, chapter = ch.split(".")
        data = pack_chapter(owb, book, int(chapter), markup, morph)
        path = os.path.join(OUT, "en", f"{book}.{chapter}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        print(f"{path}: {len(data['records'])} sentences, verses {data['verses'][0]}-{data['verses'][-1]}")


if __name__ == "__main__":
    main()
