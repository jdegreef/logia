"""Measure how often scripts/find_refs.py finds the right references.

    python3 scripts/score_refs.py                # print the scores and record them
    python3 scripts/score_refs.py --check        # exit 1 if docs/scores.json is out of date
    python3 scripts/score_refs.py --allow-drop   # record scores lower than before

Two measures, both read from the library, never typed:

- **Scripture citations.** In a page scan nothing is marked, so
  find_refs.py matches references by pattern ("Heb. i. 3", "v. 14"). In a
  CCEL transcription the editors marked each reference by hand. Running the
  pattern matcher on the CCEL excerpts, as if they had no marks, and
  comparing what it finds with what the editors marked gives its precision
  (of what it finds, how much the editors also marked) and recall (of what
  they marked, how much it finds). The editors did not mark everything, so a
  find they did not mark is not always wrong: precision is a floor.
- **The Catena's quotations of the Fathers.** Each is matched to a homily or
  tractate by shared words. The Catena prints the quotation under a verse,
  and library/texts/ records the verses each homily covers, as CCEL's
  headings print them. A match whose homily covers that verse, or whose
  paragraph is within a few verses of it, agrees; the rest are listed for a
  person to check first, against the margin note on the printed page.
  A quotation from a homily on another Gospel (the Catena on Mark quoting
  Chrysostom on Matthew) cannot be checked this way and is only counted. A
  homily runs from the first verse its heading names to the verse the next
  homily opens on, since the headings mark only some of the verses between.

docs/scores.json keeps the figures. Recording a lower figure needs
--allow-drop, so a change to the patterns cannot make them worse unnoticed.
"""
import argparse
import collections
import glob
import json
import os
import sys

import find_refs
import scripture

ROOT = find_refs.ROOT
PATH = os.path.join(ROOT, "docs", "scores.json")
NEAR = 3          # a quotation's paragraph this many verses from the Catena's verse still agrees


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def span(start, end):
    b, c, v = start.split(".")
    _, c2, v2 = end.split(".")
    return b, (int(c), int(v)), (int(c2), int(v2))


def overlap(a, b):
    return a[0] == b[0] and a[1] <= b[2] and b[1] <= a[2]


def citation_scores():
    """A reference found counts as right when it overlaps one the editors
    marked ("Ac 22:21, 22" is read as two references, CCEL marks it as one
    range), and a marked one counts as found when a reference found overlaps it."""
    fixes = find_refs.corrected_texts()
    works = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "library", "citations", "*", "*.json"))):
        data = load(path)
        marked = collections.defaultdict(list)
        for c in data["citations"]:
            if c["found"] == "source":
                marked[c["in"]].append(span(c["start"], c["end"]))
        if not marked:
            continue
        comments = load(os.path.join(ROOT, "library", "comments", data["work"], f"{data['book']}.json"))
        s = works.setdefault(data["work"], collections.Counter())
        for e in comments["entries"]:
            text = e["text"]
            for a, b in fixes.get(data["work"], []):
                text = text.replace(a, b)
            chapter = int(e["start"].split(".")[1])
            found = [span(*scripture.english_span(a, b))
                     for _, _, a, b in find_refs.scan_citations(text, data["book"], chapter, (e["start"], e["end"]))]
            gold = marked.get(e["id"], [])
            s["found"] += len(found)
            s["marked"] += len(gold)
            s["right"] += sum(1 for f in found if any(overlap(f, g) for g in gold))
            s["caught"] += sum(1 for g in gold if any(overlap(f, g) for f in found))
    return works


def ratio(a, b):
    return round(a / b, 3) if b else None


def verse_number(ref):
    _, c, v = ref.split(".")
    return int(c), int(v)


def quotation_scores():
    paras, texts, book_of = {}, collections.defaultdict(list), {}
    for p in glob.glob(os.path.join(ROOT, "library", "texts", "*", "*.json")):
        t = load(p)
        if t.get("verses"):
            texts[t["work"]].append((int(t["locus"]), t["verses"]))
            book_of[t["work"]] = t["verses"]["start"].split(".")[0]
        for para in t["paragraphs"]:
            paras[(t["work"], para["id"])] = para.get("verse")
    covers = {}
    for work, rows in texts.items():
        rows.sort()
        for i, (n, v) in enumerate(rows):
            end = verse_number(v["end"])
            if i + 1 < len(rows):
                end = max(end, verse_number(rows[i + 1][1]["start"]))
            covers[(work, str(n))] = (verse_number(v["start"]), end)
    out = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "library", "quotations", "*", "*.json"))):
        data = load(path)
        tally = collections.Counter()
        flagged = []
        for q in data["quotations"]:
            if q["status"] == "rejected":
                continue
            if book_of.get(q["work"]) not in (None, data["book"]):
                tally["from another book"] += 1        # the Catena on Mark quoting Chrysostom on Matthew
                continue
            ref = q["in"].split(".", 1)[1].rsplit(".", 1)[0].split("-")[0]
            at = verse_number(ref)
            verse = paras.get((q["work"], q["para"])) if q["para"] else None
            if verse:
                c, v = verse_number(verse)
                if c == at[0] and abs(v - at[1]) <= NEAR:
                    tally["paragraph near"] += 1
                    continue
                tally["outside"] += 1
                flagged.append(q["in"])
                continue
            span = covers.get((q["work"], q["locus"].split(".")[0]))
            if not span:
                tally["no verses printed"] += 1
                continue
            if span[0] <= at <= span[1]:
                tally["inside the homily"] += 1
            else:
                tally["outside"] += 1
                flagged.append(q["in"])
        key = f"{data['work']}/{data['book']}"
        out[key] = {"quotations": sum(tally.values()), **dict(sorted(tally.items())),
                    "check_first": sorted(set(flagged))}
    return out


def scores():
    works = citation_scores()
    total = collections.Counter()
    rows = {}
    for w, s in sorted(works.items()):
        total.update(s)
        rows[w] = {**dict(s), "precision": ratio(s["right"], s["found"]), "recall": ratio(s["caught"], s["marked"])}
    return {
        "about": "Written by scripts/score_refs.py: the pattern matcher of scripts/find_refs.py scored "
                 "against the references CCEL's editors marked, and the Catena's quotations checked "
                 "against the verses each homily or tractate covers. Never typed.",
        "citations": {"all": {**dict(total), "precision": ratio(total["right"], total["found"]),
                              "recall": ratio(total["caught"], total["marked"])},
                      "works": rows},
        "quotations": quotation_scores(),
    }


def drops(old, new):
    out = []
    pairs = [("all", old["citations"]["all"], new["citations"]["all"])]
    pairs += [(w, old["citations"]["works"].get(w), s) for w, s in new["citations"]["works"].items()]
    for name, a, b in pairs:
        if not a:
            continue
        for k in ("precision", "recall"):
            if a.get(k) is not None and b.get(k) is not None and b[k] < a[k]:
                out.append(f"{name}: {k} {a[k]} -> {b[k]}")
    return out


def report(s):
    print("Scripture citations: the pattern matcher against CCEL's marks")
    print(f"  {'':22}{'found':>7}{'marked':>8}{'precision':>11}{'recall':>8}")
    for w, r in sorted(s["citations"]["works"].items(), key=lambda x: (x[1]["recall"] or 0)):
        print(f"  {w:22}{r['found']:>7}{r['marked']:>8}{r['precision'] or 0:>11.2f}{r['recall'] or 0:>8.2f}")
    a = s["citations"]["all"]
    print(f"  {'all':22}{a['found']:>7}{a['marked']:>8}{a['precision']:>11.3f}{a['recall']:>8.3f}")
    print("The Catena's quotations against the verses each homily covers")
    for k, q in s["quotations"].items():
        parts = ", ".join(f"{n} {v}" for n, v in q.items() if n not in ("quotations", "check_first"))
        print(f"  {k}: {q['quotations']} ({parts})")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="change nothing; exit 1 if docs/scores.json is out of date")
    ap.add_argument("--allow-drop", action="store_true", help="record figures lower than the ones recorded")
    args = ap.parse_args(argv)
    new = scores()
    old = load(PATH) if os.path.exists(PATH) else None
    report(new)
    fell = drops(old, new) if old else []
    for d in fell:
        print(f"lower than recorded: {d}")
    if args.check:
        if old != new:
            print("docs/scores.json is out of date: run python3 scripts/score_refs.py and commit it")
            return 1
        return 0
    if fell and not args.allow_drop:
        print("not recorded: a figure fell. Fix the patterns, or pass --allow-drop if the drop is intended")
        return 1
    if old != new:
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(new, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print("docs/scores.json updated")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
