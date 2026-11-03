"""The library is valid, every excerpt is in its source, and the site builds.

    python3 -m unittest discover -s tests -t .
"""
import io
import json
import os
import re
import sys
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_site  # noqa: E402
import find_refs  # noqa: E402
import validate  # noqa: E402
import verify_sources  # noqa: E402


def quiet(fn, *args):
    out = io.StringIO()
    with redirect_stdout(out):
        code = fn(*args)
    return code, out.getvalue()


class Library(unittest.TestCase):
    def test_data_is_valid(self):
        code, out = quiet(validate.main)
        self.assertEqual(code, 0, out)

    def test_every_excerpt_is_in_its_source(self):
        code, out = quiet(verify_sources.main, [])
        self.assertEqual(code, 0, out)

    def test_loci_and_citations_are_up_to_date(self):
        code, out = quiet(find_refs.main, ["--check"])
        self.assertEqual(code, 0, out)


class FindRefs(unittest.TestCase):
    def refs(self, text, book="JHN", chapter=1):
        return [(t, a, b) for _, t, a, b in find_refs.scan_citations(text, book, chapter)]

    def test_printed_references(self):
        self.assertEqual(self.refs("as Heb. i. 3, and Col. i. 16, 17 ;"),
                         [("Heb. i. 3", "HEB.1.3", "HEB.1.3"), ("Col. i. 16, 17", "COL.1.16", "COL.1.17")])
        self.assertEqual(self.refs("1 Tim. iii. 16"), [("1 Tim. iii. 16", "1TI.3.16", "1TI.3.16")])
        self.assertEqual(self.refs("Psalm Ixxxix. 19."), [("Psalm Ixxxix. 19", "PSA.89.19", "PSA.89.19")])

    def test_a_list_keeps_its_book(self):
        got = self.refs("as 1 John ii. 29, iii. 9, v. 1, 4")
        self.assertEqual([a for _, a, _ in got], ["1JN.2.29", "1JN.3.9", "1JN.5.1", "1JN.5.4"])
        got = self.refs("Isa. xl. 12, 28; xli. 4")
        self.assertEqual([a for _, a, _ in got], ["ISA.40.12", "ISA.40.28", "ISA.41.4"])

    def test_this_book_and_this_chapter(self):
        self.assertEqual(self.refs("(comp. vi. 46)"), [("vi. 46", "JHN.6.46", "JHN.6.46")])
        self.assertEqual(self.refs("declared in v. 14."), [("v. 14", "JHN.1.14", "JHN.1.14")])

    def test_what_is_not_guessed(self):
        self.assertEqual(self.refs("Tim. iii. 16"), [])          # which Timothy?
        self.assertEqual(self.refs("Matt. li. 22"), [])          # Matthew has 28 chapters: a misread
        self.assertEqual(self.refs("Comp. v. 5"), [("v. 5", "JHN.1.5", "JHN.1.5")])   # verse 5, not chapter 5

    def test_ccel_marks_are_read_as_printed(self):
        with open(os.path.join(ROOT, "library", "citations", "chrysostom", "JHN.json"), encoding="utf-8") as f:
            cites = json.load(f)["citations"]
        # CCEL's mark says Psalm 3:20; the page prints Ps. ciii. 20.
        self.assertIn(("Ps. ciii. 20", "PSA.103.20"), [(c["text"], c["start"]) for c in cites])

    def test_loci_are_read_from_the_page(self):
        loci = {}
        for work in ("chrysostom", "augustine"):
            with open(os.path.join(ROOT, "library", "comments", work, "JHN.json"), encoding="utf-8") as f:
                loci.update({e["id"]: e["locus"] for e in json.load(f)["entries"]})
        self.assertEqual(loci["chrysostom.JHN.1.1.1"], "2.8")
        self.assertEqual(loci["chrysostom.JHN.1.18.3"], "15.3")       # the excerpt begins "[3.]"
        self.assertEqual(loci["augustine.JHN.1.1.1"], "1.5")          # the paragraph begins "5."


class VerifyCatchesChanges(unittest.TestCase):
    def setUp(self):
        self.digital = verify_sources.source_letters(os.path.join(ROOT, "sources", "calvin", "calcom34.vii.i.html"))
        with open(os.path.join(ROOT, "library", "comments", "calvin", "JHN.json"), encoding="utf-8") as f:
            self.entry = json.load(f)["entries"][0]

    def test_the_real_excerpt_passes(self):
        self.assertIsNone(verify_sources.check_digital(self.entry["text"], self.digital))

    def test_one_changed_word_fails(self):
        changed = self.entry["text"].replace("eternal", "temporal", 1)
        self.assertNotEqual(changed, self.entry["text"])
        self.assertIsNotNone(verify_sources.check_digital(changed, self.digital))

    def test_invented_text_fails_a_scan(self):
        scan = verify_sources.source_letters(
            os.path.join(ROOT, "sources", "catena", "catenaaureacomme04thomuoft.txt"))
        invented = ("The Word here signifies the eternal reason of the Father, which every believer may "
                    "contemplate in quiet prayer each morning before the work of the day begins.")
        self.assertIsNotNone(verify_sources.check_scan(invented, scan))


class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        quiet(build_site.build)

    def test_pages_exist_and_are_filled(self):
        for page in ("index.html", os.path.join("jhn", "1", "index.html")):
            with open(os.path.join(build_site.SITE, page), encoding="utf-8") as f:
                text = f.read()
            self.assertNotRegex(text, r"\{\{[A-Z_]+\}\}", page)
            self.assertTrue(text.startswith("<!doctype html>"), page)

    def test_chapter_page_carries_its_data(self):
        with open(os.path.join(build_site.SITE, "jhn", "1", "index.html"), encoding="utf-8") as f:
            text = f.read()
        m = re.search(r"const DATA = (\{.*?\});\n", text, re.S)
        data = json.loads(m[1].replace("<\\/", "</"))
        self.assertEqual(data["book"], "JHN")
        self.assertEqual(len(data["commentaries"]), 8)
        self.assertTrue(all(w["entries"] for w in data["commentaries"]))

    def test_citations_link_both_ways(self):
        with open(os.path.join(build_site.SITE, "jhn", "1", "index.html"), encoding="utf-8") as f:
            data = json.loads(re.search(r"const DATA = (\{.*?\});\n", f.read(), re.S)[1].replace("<\\/", "</"))
        westcott = next(w for w in data["commentaries"] if w["work_id"] == "westcott")
        first = westcott["entries"][0]
        self.assertIn(("v. 14", "/jhn/1/#v14"), [(c["text"], c["href"]) for c in first["cites"]])
        self.assertIn(first["id"], [r["id"] for r in data["citedBy"]["14"]])
        for verse, rows in data["citedBy"].items():    # an excerpt is not listed on its own verse
            on_it = {e["id"] for w in data["commentaries"] for e in w["entries"]
                     if e["start"] <= int(verse) <= e["end"]}
            self.assertFalse(on_it & {r["id"] for r in rows}, verse)

    def test_corrections_are_applied(self):
        works, comments = build_site.load_library()
        ryle = " ".join(c["text"] for c in comments if c["work"] == "ryle")
        self.assertNotIn("Let ns", ryle)
        self.assertIn("Let us", ryle)


if __name__ == "__main__":
    unittest.main()
