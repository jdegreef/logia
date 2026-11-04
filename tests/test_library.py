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
    PAGES = ("index.html", "read/index.html", "jhn/index.html", "jhn/1/index.html", "jhn/21/index.html",
             "commentators/index.html", "commentators/calvin/index.html", "works/ryle/index.html", "about/index.html")

    @classmethod
    def setUpClass(cls):
        quiet(build_site.build)

    def read(self, page):
        with open(os.path.join(build_site.SITE, page), encoding="utf-8") as f:
            return f.read()

    def test_pages_exist_with_the_site_frame(self):
        for page in self.PAGES:
            text = self.read(page)
            self.assertTrue(text.startswith("<!doctype html>"), page)
            self.assertIn('<header class="site">', text, page)
            self.assertIn('<footer class="site">', text, page)
            self.assertIn('id="colour-menu"', text, page)

    def test_every_internal_link_leads_to_a_page(self):
        missing = set()
        for root, _dirs, files in os.walk(build_site.SITE):
            for name in files:
                if not name.endswith(".html"):
                    continue
                with open(os.path.join(root, name), encoding="utf-8") as f:
                    for href in re.findall(r'href="(/[^"#]*)', f.read()):
                        path = os.path.join(build_site.SITE, href.lstrip("/"))
                        if not (os.path.isfile(path) or os.path.isfile(os.path.join(path, "index.html"))):
                            missing.add(href)
        self.assertEqual(missing, set())

    def test_chapter_page_carries_its_data(self):
        text = self.read(os.path.join("jhn", "1", "index.html"))
        m = re.search(r'<script type="application/json" id="chapter-data">(.*?)</script>', text, re.S)
        data = json.loads(m[1])
        self.assertEqual((data["book"], data["chapter"]), ("JHN", 1))
        self.assertEqual(len(data["commentaries"]), 8)
        self.assertTrue(all(w["entries"] for w in data["commentaries"]))
        for key in ("summary", "none_yet", "eras", "levels", "categories"):
            self.assertIn(key, data["ui"])

    def test_a_chapter_without_commentary_still_reads(self):
        text = self.read(os.path.join("jhn", "21", "index.html"))
        data = json.loads(re.search(r'id="chapter-data">(.*?)</script>', text, re.S)[1])
        self.assertEqual(data["commentaries"], [])
        self.assertEqual(data["verses"][-1], 25)

    def test_accounts_are_open_word_bible_s(self):
        text = self.read("index.html")
        self.assertIn('<meta name="logia-api" content="https://api.openwordbible.org">', text)
        self.assertIn('href="https://openwordbible.org/handoff/?site=logia&amp;to=%2F" data-login', text)
        for page in ("signed-in/index.html", "saved/index.html"):
            self.assertIn('<meta name="robots" content="noindex">', self.read(page), page)

    def test_the_not_found_page(self):
        text = self.read("404.html")
        self.assertIn("<title>Page not found · Logia</title>", text)
        self.assertIn('<meta name="robots" content="noindex">', text)
        self.assertNotIn('rel="canonical"', text)
        # Served at any depth, so nothing may be linked relatively.
        for link in re.findall(r'(?:href|src)="([^"]+)"', text):
            self.assertTrue(link.startswith(("/", "https://", "#")), link)
        self.assertNotIn("/404.html", self.read("sitemap.xml"))

    def test_the_saved_page_has_each_chapter_s_comments(self):
        data = json.loads(self.read(os.path.join("data", "JHN.1.json")))
        self.assertEqual(data["bookName"], "John")
        self.assertEqual({w["work_id"] for w in data["commentaries"]},
                         {"chrysostom", "augustine", "catena", "calvin", "henry", "bengel", "ryle", "westcott"})

    def test_corrections_are_applied(self):
        lib = build_site.Library()
        ryle = " ".join(c["text"] for c in lib.comments if c["work"] == "ryle")
        self.assertNotIn("Let ns", ryle)
        self.assertIn("Let us", ryle)


if __name__ == "__main__":
    unittest.main()
