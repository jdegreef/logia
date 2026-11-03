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

    def test_corrections_are_applied(self):
        works, comments = build_site.load_library()
        ryle = " ".join(c["text"] for c in comments if c["work"] == "ryle")
        self.assertNotIn("Let ns", ryle)
        self.assertIn("Let us", ryle)


if __name__ == "__main__":
    unittest.main()
