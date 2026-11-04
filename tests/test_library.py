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
import extract_texts  # noqa: E402
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

    def test_whole_texts_are_up_to_date(self):
        code, out = quiet(extract_texts.main, ["--check"])
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


class Quotations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "library", "quotations", "catena", "JHN.json"), encoding="utf-8") as f:
            cls.rows = {(q["in"], q["label"]): q for q in json.load(f)["quotations"]}

    def test_matches_agree_with_the_printed_margin_notes(self):
        # The scan's margin notes read "Aug. in Joan. tract. i. c. 13", "Aug. ... Joan. ii c. 11",
        # "Chrys. ... xv. [xiv.] 3" and "Aug. ... tract. iii": the matching found the same places.
        self.assertEqual(self.rows[("catena.JHN.1.3.2", "AUG.")]["locus"], "1.13")
        self.assertEqual(self.rows[("catena.JHN.1.10.1", "AUG.")]["locus"], "2.11")
        self.assertEqual(self.rows[("catena.JHN.1.18.2", "CHRYS.")]["locus"], "15.3")
        self.assertEqual(self.rows[("catena.JHN.1.16-17.1", "AUG.")]["locus"], "3")

    def test_an_unclear_match_is_left_out(self):
        # "Not because the light wanted the testimony": Homilies 6 and 7 score almost the same.
        self.assertNotIn(("catena.JHN.1.7.1", "CHRYS."), self.rows)

    def test_a_quoted_passage_links_to_the_excerpt_that_holds_it(self):
        self.assertEqual(self.rows[("catena.JHN.1.3.2", "AUG.")]["excerpt"], "augustine.JHN.1.3.1")


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
                    for href in re.findall(r'href="(/[^"#?]*)', f.read()):
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

    def test_the_whole_bible_is_here(self):
        lib = build_site.Library()
        self.assertEqual(len(lib.chapters), sum(b["chapters"] for b in lib.books.values()))
        self.assertEqual({b for b, _c in lib.chapters}, set(lib.books))

    def test_an_old_testament_chapter_reads_from_the_hebrew(self):
        text = self.read(os.path.join("psa", "23", "index.html"))
        data = json.loads(re.search(r'id="chapter-data">(.*?)</script>', text, re.S)[1])
        self.assertEqual(data["source"], "hbo")
        panel = json.loads(self.read(os.path.join("panel", "PSA.23.json")))
        self.assertIn("transliteration", panel["words"]["1"][0])
        self.assertIn("Hebrew words", text)
        self.assertEqual(data["ui"]["tap_word"], build_site.CATALOG["reader"]["tap_word_hbo"])

    def test_the_text_keeps_the_open_word_bible_s_variations(self):
        data = build_site.Library().bible("PSA", 23)
        balanced = " ".join(p[1] for r in data["records"] for p in r["pieces"])
        self.assertIn("{{divine_name:", balanced)
        self.assertIn("{{deity_pronoun:", balanced)
        self.assertIn("\\q", balanced)
        text = self.read(os.path.join("psa", "23", "index.html"))
        page = json.loads(re.search(r'id="chapter-data">(.*?)</script>', text, re.S)[1])
        self.assertEqual(set(page["wording"]), set(build_site.WORDING))
        for name in build_site.WORDING:
            self.assertIn(f'data-pref="{name}"', self.read("index.html"), name)

    def test_the_plain_text_shows_the_default_wording(self):
        poem = "{{divine_name:the LORD|Yahweh}} is my shepherd; \\q I lack nothing"
        self.assertEqual(build_site.default_wording(poem), "the LORD is my shepherd; I lack nothing")
        self.assertEqual(build_site.default_wording("{{deity_pronoun:he|He}} leads me"), "He leads me")
        text = self.read(os.path.join("psa", "23", "index.html"))
        plain = text.split('id="text">')[1].split("</div>")[0]
        self.assertNotIn("{{", plain)
        self.assertNotIn("\\q", plain)
        self.assertIn("The LORD is my shepherd", plain)

    def test_words_and_notes_are_a_file_of_their_own(self):
        text = self.read(os.path.join("jhn", "1", "index.html"))
        data = json.loads(re.search(r'id="chapter-data">(.*?)</script>', text, re.S)[1])
        self.assertNotIn("words", data)
        self.assertTrue(all("decisions" not in r and r["notes"] >= 0 for r in data["records"]))
        self.assertRegex(data["panel"], r"^/panel/JHN\.1\.json\?v=[0-9a-f]{10}$")
        panel = json.loads(self.read(data["panel"].split("?")[0].lstrip("/")))
        self.assertEqual(set(panel["records"]), {r["id"] for r in data["records"]})
        self.assertEqual({v: len(ws) for v, ws in panel["words"].items()}, data["wordCounts"])
        self.assertEqual(sum(r["notes"] for r in data["records"]),
                         sum(len(r["decisions"]) for r in panel["records"].values()))

    def test_assets_are_addressed_by_their_digest(self):
        text = self.read("index.html")
        for name in ("style.css", "logia.css", "site.js", "account.js"):
            self.assertRegex(text, rf'"/{re.escape(name)}\?v=[0-9a-f]{{10}}"', name)

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

    def test_citations_link_both_ways(self):
        with open(os.path.join(build_site.SITE, "jhn", "1", "index.html"), encoding="utf-8") as f:
            data = json.loads(re.search(r'id="chapter-data">(.*?)</script>', f.read(), re.S)[1].replace("<\\/", "</"))
        westcott = next(w for w in data["commentaries"] if w["work_id"] == "westcott")
        first = westcott["entries"][0]
        self.assertIn(("v. 14", "/jhn/1/#v14"), [(c["text"], c["href"]) for c in first["cites"]])
        self.assertIn(first["id"], [r["id"] for r in data["citedBy"]["14"]])
        for verse, rows in data["citedBy"].items():    # an excerpt is not listed on its own verse
            on_it = {e["id"] for w in data["commentaries"] for e in w["entries"]
                     if e["start"] <= int(verse) <= e["end"]}
            self.assertFalse(on_it & {r["id"] for r in rows}, verse)

    def test_whole_texts_have_pages(self):
        with open(os.path.join(build_site.SITE, "works", "augustine", "1", "index.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn("<h1>Tractate 1</h1>", page)
        # Section 13 is the passage Logia sets beside John 1:3 and the Catena quotes.
        sec = page[page.index('id="s13"'):page.index('id="s14"')]
        self.assertIn('class="lg-held"', sec)
        self.assertIn('href="/jhn/1/#v3-augustine">In Logia on John 1:3', sec)
        self.assertIn("Catena Aurea", sec)
        with open(os.path.join(build_site.SITE, "works", "chrysostom", "index.html"), encoding="utf-8") as f:
            self.assertIn('href="/works/chrysostom/15/"', f.read())     # the work page lists its whole texts

    def test_whole_texts_are_divided_by_verse_too(self):
        def text(work, n):
            with open(os.path.join(ROOT, "library", "texts", work, f"{n}.json"), encoding="utf-8") as f:
                return json.load(f)
        # Homily 10 opens on "John i. 11" and marks "Ver. 12." and "Ver. 13." as it goes on.
        h10 = text("chrysostom", 10)
        self.assertEqual(h10["verses"], {"start": "JHN.1.11", "end": "JHN.1.13"})
        marked = [p for p in h10["paragraphs"] if p["text"].startswith(("Ver. 12.", "[3.] Ver. 13."))]
        self.assertEqual([p["verse"] for p in marked][:1], ["JHN.1.12"])
        # Tractate 2's heading gives a range and no verse marks: no paragraph claims a verse.
        t2 = text("augustine", 2)
        self.assertEqual(t2["verses"], {"start": "JHN.1.6", "end": "JHN.1.14"})
        self.assertEqual({p["verse"] for p in t2["paragraphs"]}, {None})

    def test_the_reader_lists_whole_texts_on_a_verse(self):
        with open(os.path.join(build_site.SITE, "jhn", "1", "index.html"), encoding="utf-8") as f:
            data = json.loads(re.search(r'id="chapter-data">(.*?)</script>', f.read(), re.S)[1].replace("<\\/", "</"))
        rows = {(r["work_id"], r["where"]) for r in data["wholeTexts"]["12"]}
        self.assertEqual(rows, {("chrysostom", "Homily 10, section 2"), ("augustine", "Tractate 2")})
        self.assertEqual({r["work_id"] for r in data["wholeTexts"]["2"]}, {"augustine"})   # no homily marks 1:2

    def test_each_work_has_its_versions(self):
        lib = build_site.Library()
        for wid in lib.works:
            v = lib.edition(wid)
            self.assertEqual((v["work"], v["made_by"]), (wid, "print"))
        self.assertEqual(lib.edition("calvin")["kind"], "translation")      # Calvin wrote in Latin
        self.assertEqual(lib.edition("henry")["kind"], "original")
        with open(os.path.join(build_site.SITE, "works", "calvin", "index.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn('id="calvin.en"', page)
        self.assertIn("Translation into English", page)

    def test_the_reader_has_what_cite_and_source_need(self):
        with open(os.path.join(build_site.SITE, "jhn", "1", "index.html"), encoding="utf-8") as f:
            page = f.read()
        data = json.loads(re.search(r'id="chapter-data">(.*?)</script>', page, re.S)[1].replace("<\\/", "</"))
        self.assertIn('id="strip"', page)
        self.assertTrue(data["issues_url"].endswith("/issues/new"))
        by_work = {w["work_id"]: w for w in data["commentaries"]}
        self.assertEqual({w["family"] for w in by_work.values()}, {"undivided", "catholic", "anglican", "protestant"})
        self.assertEqual(by_work["calvin"]["version"]["id"], "calvin.en")
        ryle = {e["id"]: e for e in by_work["ryle"]["entries"]}
        # The scan corrections an excerpt shows are listed with it, as applied.
        self.assertIn(["pecuUar", "peculiar"], ryle["ryle.JHN.1.1.2"]["fixed"])
        self.assertEqual(by_work["calvin"]["entries"][0]["fixed"], [])

    def test_search_index_holds_every_excerpt_and_whole_text(self):
        with open(os.path.join(build_site.SITE, "data", "search.json"), encoding="utf-8") as f:
            index = json.load(f)
        excerpts = [r for r in index["rows"] if r["k"] == "x"]
        self.assertEqual(len(excerpts), len(build_site.Library().comments))
        self.assertTrue(all(re.match(r"^/[a-z0-9]+/\d+/#[a-z]+\.", r["u"]) for r in excerpts))
        paras = [r for r in index["rows"] if r["k"] == "p"]
        self.assertTrue(paras and all(r["u"].startswith("/works/") for r in paras))
        self.assertTrue(any(r["x"] for r in paras))        # paragraphs know the excerpts they hold
        self.assertTrue(os.path.exists(os.path.join(build_site.SITE, "search", "index.html")))

    def test_library_and_timeline_pages(self):
        with open(os.path.join(build_site.SITE, "library", "index.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertEqual(page.count('class="lg-cat-work"'), 8)
        for genre in ("Commentaries", "Homilies and lectures", "Catenas"):
            self.assertIn(f"<h2>{genre}</h2>", page)
        with open(os.path.join(build_site.SITE, "commentators", "index.html"), encoding="utf-8") as f:
            self.assertEqual(f.read().count('class="lg-tl-row"'), 8)

    def test_topics_gather_by_their_rule(self):
        lib = build_site.Library()
        tp = next(x for x in lib.topics if x["id"] == "incarnation")
        members = {c["id"]: why for c, why in lib.topic_members(tp)}
        on_14 = {c["id"] for c in lib.comments
                 if build_site.ref_parts(c["start"])[:2] == ("JHN", 1) == build_site.ref_parts(c["end"])[:2]
                 and build_site.ref_parts(c["start"])[2] <= 14 <= build_site.ref_parts(c["end"])[2]}
        self.assertTrue(on_14 <= set(members))                 # every excerpt on John 1:14
        self.assertEqual(members["chrysostom.JHN.1.1.3"], "made flesh")   # and one elsewhere that uses a term
        self.assertTrue(os.path.exists(os.path.join(build_site.SITE, "topics", "incarnation", "index.html")))

    def test_the_api(self):
        def get(rel):
            with open(os.path.join(build_site.SITE, "api", "v1", rel), encoding="utf-8") as f:
                return json.load(f)
        index = get("index.json")
        self.assertEqual(index["api_version"], 1)
        jn1 = get("chapters/JHN.1.json")
        v1 = jn1["verses"][0]
        self.assertTrue(v1["text"].startswith("In the beginning was the Word"))
        self.assertTrue(v1["excerpts"] and all(x in jn1["excerpts"] for x in v1["excerpts"]))
        self.assertEqual(jn1["excerpts"]["calvin.JHN.1.1.1"]["author_name"], "John Calvin")
        # Every chapter has a file, even without commentary, and citations reach it:
        # Ryle on John 1:1 cites Gen. i. 1.
        self.assertIn("ryle.JHN.1.1.1", get("chapters/GEN.1.json")["verses"][0]["cited_by"])
        # Citations are English-numbered; the API files them at the Open Word Bible's
        # number (Ryle's "Psalm lxxxix. 19" is PSA.89.20, the psalm's title being verse 1).
        self.assertTrue(any(v["verse"] == 20 and v["cited_by"] for v in get("chapters/PSA.89.json")["verses"]))
        self.assertEqual({w["id"] for w in get("works.json")}, set(build_site.Library().works))
        self.assertEqual(get("works/calvin.json")["versions"][0]["id"], "calvin.en")

    def test_the_linker_and_the_rules_page(self):
        with open(os.path.join(build_site.SITE, "linker.js"), encoding="utf-8") as f:
            js = f.read()
        for placeholder in ("/*SITE*/", "/*NAMES*/", "/*CHAPTERS*/", "/*RENUMBER*/"):
            self.assertNotIn(placeholder, js)
        self.assertIn('"1 cor":"1CO"', js)
        self.assertIn('"PSA.19":[[1,', js)
        self.assertEqual(build_site.scripture.to_source("PSA.19.1"), "PSA.19.2")
        self.assertEqual(build_site.scripture.to_source("JHN.3.16"), "JHN.3.16")
        with open(os.path.join(build_site.SITE, "about", "rules", "index.html"), encoding="utf-8") as f:
            self.assertEqual(f.read().count('#versions"><i>'), len(build_site.Library().versions))

    def test_corrections_are_applied(self):
        lib = build_site.Library()
        ryle = " ".join(c["text"] for c in lib.comments if c["work"] == "ryle")
        self.assertNotIn("Let ns", ryle)
        self.assertIn("Let us", ryle)


if __name__ == "__main__":
    unittest.main()
