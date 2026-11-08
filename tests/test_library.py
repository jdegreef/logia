"""The library is valid, every excerpt is in its source, and the site builds.

    python3 -m unittest discover -s tests -t .
"""
import html
import io
import json
import os
import re
import sys
import unicodedata
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_site  # noqa: E402
import extract_texts  # noqa: E402
import find_refs  # noqa: E402
import scripture  # noqa: E402
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


class Versification(unittest.TestCase):
    """English verse numbers, as the commentators print them, move to the Hebrew numbering of the Bible text."""

    def test_a_psalm_title_is_its_first_verse(self):
        self.assertEqual(scripture.from_english("PSA", 3, 1), [(3, 2)])
        self.assertEqual(scripture.from_english("PSA", 51, 1), [(51, 3)])
        self.assertEqual(scripture.title_verses("PSA", 51), [1, 2])
        self.assertEqual(scripture.title_verses("PSA", 1), [])

    def test_a_chapter_that_begins_elsewhere(self):
        self.assertEqual(scripture.from_english("ECC", 5, 1), [(4, 17)])

    def test_the_new_testament_is_unchanged(self):
        self.assertEqual(scripture.from_english("MAT", 5, 3), [(5, 3)])

    def test_the_psalms_commentaries_are_on_the_hebrew_verses(self):
        entries = json.load(open(os.path.join(ROOT, "library", "comments", "augustine-psalms", "PSA.json")))["entries"]
        on = {e["start"] for e in entries if "Have pity upon me, O God, after Thy great mercy” (ver. 1)" in e["text"]}
        self.assertEqual(on, {"PSA.51.3"})       # Psalm 51:1 in English


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

    def test_retyped_greek_fails(self):
        # Calvin on John 1:1 quotes a Greek word: as copied it is in the source;
        # the same word without its accents (as if retyped) is not.
        with open(os.path.join(ROOT, "library", "comments", "calvin", "JHN.json"), encoding="utf-8") as f:
            entry = next(e for e in json.load(f)["entries"] if verify_sources.ORIGINAL.search(e["text"]))
        raw = verify_sources.source_original(os.path.join(ROOT, "sources", "calvin", entry["sources"][0]))
        self.assertIsNone(verify_sources.check_original(entry["text"], raw))
        word = verify_sources.ORIGINAL.search(entry["text"])[0]
        bare = "".join(c for c in unicodedata.normalize("NFD", word) if not unicodedata.combining(c))
        self.assertNotEqual(bare, word)
        self.assertIsNotNone(verify_sources.check_original(entry["text"].replace(word, bare), raw))


class Site(unittest.TestCase):
    PAGES = ("index.html", "read/index.html", "jhn/index.html", "jhn/1/index.html", "jhn/21/index.html",
             "commentators/index.html", "commentators/calvin/index.html", "works/ryle/index.html", "about/index.html",
             "jhn/3/16/index.html")

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
        # The library covers John; Acts has no commentary yet.
        text = self.read(os.path.join("act", "1", "index.html"))
        data = json.loads(re.search(r'id="chapter-data">(.*?)</script>', text, re.S)[1])
        self.assertEqual(data["commentaries"], [])
        self.assertEqual(data["verses"][-1], 26)

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

    def test_commentary_is_a_file_of_its_own_preloaded_by_the_page(self):
        text = self.read(os.path.join("jhn", "1", "index.html"))
        data = json.loads(re.search(r'id="chapter-data">(.*?)</script>', text, re.S)[1])
        self.assertRegex(data["comm"], r"^/comm/JHN\.1\.json\?v=[0-9a-f]{10}$")
        self.assertIn(f'<link rel="preload" href="{data["comm"]}" as="fetch" crossorigin>', text)
        self.assertNotIn("citedBy", data)
        comm = json.loads(self.read(data["comm"].split("?")[0].lstrip("/")))
        # The page's index matches the file: same works, same verse ranges.
        self.assertEqual([w["work_id"] for w in data["commentaries"]], [w["work_id"] for w in comm["commentaries"]])
        for short, full in zip(data["commentaries"], comm["commentaries"]):
            self.assertNotIn("excerpt", json.dumps(short))
            self.assertEqual(short["entries"],
                             [{"start": x["start"], "end": x["end"], "words": x["words"]} for x in full["entries"]])
            self.assertTrue(all(x["words"] == len(x["excerpt"].split()) for x in full["entries"]))
            self.assertTrue(all(x["excerpt"] for x in full["entries"]))
        self.assertIn("citedBy", comm)

    def test_a_chapter_with_nothing_on_it_has_no_commentary_file(self):
        # The last chapter, in canonical order, that no excerpt is on or cites.
        lib = build_site.Library()
        book, chapter = next((b, c) for b, c in reversed(lib.chapters)
                             if not lib.in_chapter(b, c, 999) and not any(lib.cited_by(b, c, range(1, 200)).values()))
        text = self.read(os.path.join(book.lower(), str(chapter), "index.html"))
        data = json.loads(re.search(r'id="chapter-data">(.*?)</script>', text, re.S)[1])
        self.assertIsNone(data["comm"])
        self.assertNotIn('as="fetch"', text)
        self.assertFalse(os.path.exists(os.path.join(build_site.SITE, "comm", f"{book}.{chapter}.json")))

    def test_the_published_stylesheet_keeps_only_what_logia_uses(self):
        css = ".used{a:1}.unused{b:2}.used .unused,.used a{c:3}#skip{d:4}#gone{e:5}[href=\"#gone\"]{f:6}"
        css += "@media (max-width:9px){.unused{g:7}}@media print{.used{h:8}}@font-face{font-family:X}"
        out = build_site.trim_css(css, {"used", "skip"})
        self.assertEqual(out, ".used{a:1}\n.used a{c:3}\n#skip{d:4}\n[href=\"#gone\"]{f:6}\n"
                              "@media print{.used{h:8}}\n@font-face{font-family:X}\n")
        published = self.read("style.css")
        with open(os.path.join(build_site.WEB, "style.css"), encoding="utf-8") as f:
            self.assertLess(len(published), len(f.read()) / 2)
        for kept in (".prefs-menu", ".dd-item", ".page-head", "@font-face"):
            self.assertIn(kept, published, kept)

    def test_a_chosen_wording_waits_for_the_reader(self):
        text = self.read(os.path.join("psa", "23", "index.html"))
        self.assertIn(f"<style>{build_site.TEXT_WAITS}</style>", text)
        for name in ("level", *build_site.WORDING):
            self.assertIn(f"[data-{name}]", build_site.TEXT_WAITS)

    def test_assets_are_addressed_by_their_digest(self):
        text = self.read("index.html")
        for name in ("style.css", "logia.css", "site.js", "account.js"):
            self.assertRegex(text, rf'"/{re.escape(name)}\?v=[0-9a-f]{{10}}"', name)

    def test_a_verse_of_two_sentences_keeps_the_space_between_them(self):
        # John 3:4 is two records in the Open Word Bible: "...grown old?" and "He cannot..."
        self.assertIn("grown old? He cannot", build_site.chapter_plain("JHN", 3)[4])
        self.assertIn("voice. This", build_site.chapter_plain("JHN", 3)[29])

    def test_verses_left_out_are_noted_with_their_commentary(self):
        text = self.read("jhn/8/index.html")
        self.assertIn('class="lg-gap" id="gap-1" data-a="1" data-b="11"', text)
        self.assertIn('href="/works/augustine/jhn/8/#augustine.JHN.8.1-2.1"', text)
        self.assertIn('class="lg-gap" id="gap-4"', self.read("jhn/5/index.html"))
        self.assertNotIn("lg-gap", self.read("jhn/3/index.html"))

    def test_chapter_links_each_commentary_read_in_order(self):
        text = self.read("jhn/3/index.html")
        self.assertIn('class="lg-in-order"', text)
        self.assertIn('href="/works/westcott/jhn/3/"', text)
        self.assertNotIn('class="lg-in-order"', self.read("act/8/index.html"))

    def test_pages_carry_a_share_card_and_data_for_search_engines(self):
        home = self.read("index.html")
        self.assertIn('<meta property="og:image" content="https://logia.faith/card.png">', home)
        self.assertIn('"@type":"WebSite"', home)
        self.assertIn("<title>Logia: Bible commentary", home)
        self.assertTrue(os.path.exists(os.path.join(build_site.SITE, "card.png")))
        chapter = self.read("jhn/3/index.html")
        self.assertIn('"@type":"BreadcrumbList"', chapter)
        self.assertIn("<title>John 3 commentary: Chrysostom, Augustine, Aquinas and 5 more", chapter)
        self.assertIn('"@type":"Person"', self.read("commentators/calvin/index.html"))

    def test_a_commentator_page_lists_the_verses_they_pass_over(self):
        text = self.read("commentators/calvin/index.html")
        self.assertRegex(text, r'class="lg-missing"><summary>Verses with no comment from Calvin \(\d+\)</summary>')
        self.assertNotIn("lg-missing", self.read("commentators/ryle/index.html"))

    def test_a_commentator_page_opens_ways_into_the_work(self):
        text = self.read("commentators/chrysostom/index.html")
        # Three passages to start with, the verse beside each row, where each
        # sits in its homily, and the homilies themselves as a second tab.
        self.assertEqual(text.count('class="lg-start-text"'), 3)
        self.assertIn('<p class="lg-ex-verse">In the beginning was the Word', text)
        self.assertIn("Read the homily from here", text)
        self.assertIn('aria-controls="by-whole"', text)
        self.assertIn('href="/works/chrysostom/88/"', text)
        self.assertIn('class="lg-goto"', text)
        # The shape of the work, who reads the same verses, and the text's record.
        self.assertIn("John, verse by verse", text)
        self.assertIn('class="lg-nc" title="John 4:30"', text)
        self.assertIn('href="/commentators/augustine/"', text)
        self.assertIn('href="/works/catena/fathers/"', text)
        self.assertIn('class="lg-cite-box"', text)
        self.assertIn('"deathDate":"0407"', text)
        # A commentator with no whole texts has no tabs.
        self.assertNotIn('class="lg-tabs"', self.read("commentators/calvin/index.html"))

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
        data = json.loads(self.read(os.path.join("comm", "JHN.1.json")))
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
        # Romans, Homily XVIII prints its verse line ("Rom. X. 14, 15") above its title.
        self.assertEqual(text("chrysostom-romans", 18)["verses"]["start"], "ROM.10.14")
        # "Chap. x. ver. 1." says where a homily goes on into the next chapter (Homily LIX, John 9:34 to 10:12).
        h59 = text("chrysostom", 59)
        self.assertEqual(h59["verses"], {"start": "JHN.9.34", "end": "JHN.10.12"})
        self.assertEqual([p["verse"] for p in h59["paragraphs"] if p["text"].startswith("Chap. x.")], ["JHN.10.1"])
        # On such a page a mark before where the text began is a misprint, left unplaced
        # (Romans, Homily VI prints "Ver. 12." over 2:28).
        h6 = text("chrysostom-romans", 6)
        self.assertEqual([p["verse"] for p in h6["paragraphs"] if p["text"].startswith("Ver. 12.")], [None])

    def test_the_reader_lists_whole_texts_on_a_verse(self):
        with open(os.path.join(build_site.SITE, "jhn", "1", "index.html"), encoding="utf-8") as f:
            data = json.loads(re.search(r'id="chapter-data">(.*?)</script>', f.read(), re.S)[1].replace("<\\/", "</"))
        rows = {(r["work_id"], r["where"]) for r in data["wholeTexts"]["12"]}
        self.assertEqual(rows, {("chrysostom", "Homily 10, section 2"), ("augustine", "Tractate 2")})
        self.assertEqual({r["work_id"] for r in data["wholeTexts"]["2"]}, {"augustine"})   # no homily marks 1:2

    # --- Verse pages ---

    def test_every_verse_with_commentary_has_a_page(self):
        lib = build_site.Library()
        for book, chapter, verse in lib.voices_on:
            path = os.path.join(build_site.SITE, book.lower(), str(chapter), str(verse), "index.html")
            self.assertTrue(os.path.isfile(path), (book, chapter, verse))
        # Acts has no commentary, so no verse pages.
        self.assertFalse(os.path.exists(os.path.join(build_site.SITE, "act", "1", "1")))
        sitemap = self.read("sitemap.xml")
        self.assertIn("<loc>https://logia.faith/jhn/3/16/</loc>", sitemap)
        verse_locs = re.findall(r"<loc>https://logia\.faith/jhn/\d+/\d+/</loc>", sitemap)
        self.assertEqual(len(verse_locs), len([k for k in lib.voices_on if k[0] == "JHN"]))

    def test_a_verse_page_holds_its_commentary_in_the_html(self):
        lib = build_site.Library()
        text = self.read(os.path.join("jhn", "3", "16", "index.html"))
        self.assertNotIn('id="chapter-data"', text)
        self.assertIn("<h1>John 3:16</h1>", text)
        on_it = [c for c in lib.comments if c["start"] == "JHN.3.16"]
        self.assertTrue(on_it)
        for c in on_it:
            first = re.split(r"\n\s*\n", c["text"])[0].strip()
            self.assertIn(build_site.e(first[:80]), re.sub(r"<[^>]+>", "", text), c["id"])   # cites are links
            self.assertIn(f'id="{c["id"]}"', text)
        works = lib.voices_on[("JHN", 3, 16)]
        for wid in works:
            self.assertIn(f'What does {build_site.short_name(lib.author_of(wid))} say about John 3:16?', text)
        self.assertIn(f"{len(works)} commentators in Logia comment on John 3:16", text)
        for section in ('id="words"', 'id="notes"', 'id="xrefs"'):
            self.assertIn(section, text)

    def test_an_excerpt_on_a_range_is_printed_in_full_once(self):
        lib = build_site.Library()
        c = next(c for c in lib.comments if c["start"].startswith("JHN.3.")
                 and build_site.ref_parts(c["end"])[2] > build_site.ref_parts(c["start"])[2])
        _b, ch, sv = build_site.ref_parts(c["start"])
        start = self.read(os.path.join("jhn", str(ch), str(sv), "index.html"))
        later = self.read(os.path.join("jhn", str(ch), str(sv + 1), "index.html"))
        self.assertIn(f'id="{c["id"]}"', start)
        self.assertNotIn(f'id="{c["id"]}"', later)
        self.assertIn(f'href="/jhn/{ch}/{sv}/#{c["id"]}"', later)

    def test_a_verse_page_has_breadcrumbs_and_its_own_description(self):
        text = self.read(os.path.join("jhn", "3", "16", "index.html"))
        data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)[1])
        ld = next(x for x in data["@graph"] if x["@type"] == "BreadcrumbList")
        self.assertEqual([x["item"] for x in ld["itemListElement"]][-2:],
                         ["https://logia.faith/jhn/3/", "https://logia.faith/jhn/3/16/"])
        self.assertIn('<link rel="canonical" href="https://logia.faith/jhn/3/16/">', text)
        self.assertRegex(text, r'<title>John 3:16 commentary: [^<]+ · Logia</title>')
        self.assertNotIn(re.search(r'name="description" content="([^"]*)"', text)[1],
                         self.read(os.path.join("jhn", "3", "17", "index.html")))

    def test_a_verse_page_for_a_verse_left_out_says_so(self):
        text = self.read(os.path.join("jhn", "8", "3", "index.html"))
        self.assertNotIn('<blockquote class="lg-vtext"><p></p>', text)
        self.assertIn('<p class="lg-gap">Verses 1–11 are not in the Greek text', text)
        self.assertIn("a verse the oldest manuscripts leave out", text)

    # --- Passage pages ---

    def test_passages_follow_the_bible_headings(self):
        sections = build_site.book_sections("JHN", 21)
        self.assertEqual(sections[0], ("The Word became flesh", (1, 1), (1, 18)))
        cana = next(x for x in sections if x[0] == "The wedding at Cana")
        self.assertEqual(cana[1:], ((2, 1), (2, 12)))
        # A heading inside a verse (John 12:36b) shares that verse with the passage before it.
        self.assertIn(("Why many did not believe", (12, 36), (12, 50)), sections)
        self.assertIn(((12, 20), (12, 36)), [x[1:] for x in sections])
        # The passage the Bible text leaves out runs across the chapter break.
        self.assertIn(("The woman caught in adultery", (7, 53), (8, 11)), sections)

    def test_a_passage_page_lists_every_excerpt_on_it(self):
        lib = build_site.Library()
        text = self.read(os.path.join("jhn", "2", "1-12", "index.html"))
        self.assertIn("<h1>The wedding at Cana (John 2:1–12)</h1>", text)
        self.assertRegex(text, r"<title>The wedding at Cana \(John 2:1–12\) commentary: [^<]+ · Logia</title>")
        on_it = [c for c in lib.comments if "JHN.2.1" <= c["start"] and c["start"].startswith("JHN.2.")
                 and build_site.ref_parts(c["start"])[2] <= 12]
        self.assertTrue(on_it)
        for c in on_it:
            self.assertIn(f'#{c["id"]}"', text, c["id"])
        self.assertIn('href="/jhn/2/1-12/"', self.read(os.path.join("jhn", "index.html")))
        self.assertIn('href="/jhn/2/1-12/"', self.read(os.path.join("jhn", "2", "index.html")))
        self.assertIn("<loc>https://logia.faith/jhn/2/1-12/</loc>", self.read("sitemap.xml"))

    def test_the_christmas_page_is_john_1_1_to_14(self):
        text = self.read(os.path.join("christmas", "index.html"))
        self.assertIn("<h1>The Gospel for Christmas Day: John 1:1–14</h1>", text)
        self.assertIn("calvin.JHN.1.14", text)
        self.assertNotIn("#calvin.JHN.1.15.", text)
        self.assertIn('href="/christmas/"', self.read("index.html"))

    def test_the_most_discussed_verses_are_counted_from_the_library(self):
        lib = build_site.Library()
        counts = build_site.verse_counts(lib, "JHN")
        (ch, v), n = min(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        text = self.read(os.path.join("jhn", "most-discussed", "index.html"))
        self.assertIn(f'<a href="/jhn/{ch}/{v}/"><b>John {ch}:{v}</b></a></td><td>{n}</td>', text)
        self.assertIn('href="/jhn/most-discussed/"', self.read(os.path.join("jhn", "index.html")))

    # --- Open data ---

    def test_the_downloads_hold_every_excerpt_as_the_site_shows_it(self):
        lib = build_site.Library()
        data = json.loads(self.read(os.path.join("downloads", "logia-en.json")))
        self.assertEqual(len(data["excerpts"]), len(lib.comments))
        self.assertEqual(data["licence"], "CC0-1.0")
        by_id = {c["id"]: c for c in lib.comments}
        for row in data["excerpts"][:50] + data["excerpts"][-50:]:
            self.assertEqual(row["text"], by_id[row["id"]]["text"])
        ryle = " ".join(r["text"] for r in data["excerpts"] if r["work"] == "ryle")
        self.assertNotIn("Let ns", ryle)   # corrections applied
        import csv as csv_
        with open(os.path.join(build_site.SITE, "downloads", "logia-en.csv"), encoding="utf-8") as f:
            rows = list(csv_.DictReader(f))
        self.assertEqual([r["id"] for r in rows], [r["id"] for r in data["excerpts"]])

    def test_the_open_data_page_describes_a_dataset(self):
        text = self.read(os.path.join("open-data", "index.html"))
        self.assertIn('href="/downloads/logia-en.json"', text)
        self.assertIn('"@type":"Dataset"', text)
        self.assertIn('href="/open-data/"', self.read(os.path.join("about", "index.html")))

    def test_the_about_page_shows_real_examples_from_the_library(self):
        text = self.read(os.path.join("about", "index.html"))
        lib = build_site.Library()
        # The excerpt it follows through the checks is quoted as copied.
        c = lib.by_id[build_site.ABOUT_EXAMPLE]
        lead = next(p for p in c["text"].split("\n\n") if p.strip())
        self.assertIn(build_site.e(" ".join(lead.split()[:12])), text)
        # Each correction it shows is a real pair from library/corrections/.
        for work, wrong in build_site.ABOUT_FIXES:
            self.assertIn(wrong, dict(lib.fixes[work]))
            self.assertIn(f"<del>{build_site.e(wrong)}</del>", text)
        for key in build_site.t("about.h"):
            self.assertIn(f'id="{key}"', text)
        self.assertIn(f'{len(lib.comments):,}', text)

    def test_each_reading_has_a_page_and_the_readings_page_lists_them(self):
        readings = self.read(os.path.join("readings", "index.html"))
        for oid, _book, _start, _end, voices in build_site.occasions(build_site.Library()):
            path = build_site.t(f"occasions.{oid}.path")
            self.assertIn(f'href="{path}"', readings)
            text = self.read(os.path.join(path.strip("/"), "index.html"))
            self.assertIn("<h1>The Gospel for ", text)
            self.assertTrue(voices, oid)
        good_friday = self.read(os.path.join("good-friday", "index.html"))
        self.assertIn("<h1>The Gospel for Good Friday: John 18:1–19:42</h1>", good_friday)
        self.assertIn("#calvin.JHN.19.", good_friday)
        self.assertIn('href="/readings/"', self.read("index.html"))

    def test_the_i_am_sayings_page_links_each_commentator_on_each_saying(self):
        lib = build_site.Library()
        text = self.read(os.path.join("jhn", "i-am", "index.html"))
        self.assertIn("The seven “I am” sayings in John", text)
        col = next(c for c in build_site.collections(lib) if c["id"] == "i-am")
        self.assertEqual(len(col["items"]), 7)
        for item in col["items"]:
            _b, ch, v = build_site.ref_parts(item["start"])
            self.assertIn("I am", build_site.chapter_plain("JHN", ch)[v], item)
            for _wid, cs in build_site.in_passage(lib, "JHN", (ch, v), (ch, v)):
                self.assertIn(build_site.excerpt_href(lib, cs[0]), text)
        self.assertIn('href="/jhn/i-am/"', self.read(os.path.join("jhn", "index.html")))

    def test_the_signs_page_lists_seven_passages_with_their_commentators(self):
        lib = build_site.Library()
        text = self.read(os.path.join("jhn", "signs", "index.html"))
        self.assertIn("<h1>The seven signs in John</h1>", text)
        col = next(c for c in build_site.collections(lib) if c["id"] == "signs")
        self.assertEqual(len(col["items"]), 7)
        for item in col["items"]:
            _b, sc, sv = build_site.ref_parts(item["start"])
            _b, ec, ev = build_site.ref_parts(item["end"])
            where = build_site.section_url(lib, "JHN", (sc, sv))
            self.assertIn(f'href="{where}"', text)
            self.assertTrue(os.path.isfile(os.path.join(build_site.SITE, where.strip("/"), "index.html")), where)
        self.assertIn("first of the signs", build_site.chapter_plain("JHN", 2)[11])
        self.assertIn("second sign", build_site.chapter_plain("JHN", 4)[54])

    def test_the_lent_plan_reads_every_passage_once_over_forty_days(self):
        import datetime
        self.assertEqual(build_site.easter_day(2027), datetime.date(2027, 3, 28))
        self.assertEqual(build_site.easter_day(2026), datetime.date(2026, 4, 5))
        days = build_site.lent_days(2027)
        self.assertEqual(len(days), 40)
        self.assertEqual(days[0], datetime.date(2027, 2, 10))   # Ash Wednesday
        self.assertEqual(days[-1], datetime.date(2027, 3, 27))  # Holy Saturday
        self.assertFalse(any(d.weekday() == 6 for d in days))
        lib = build_site.Library()
        plan = build_site.plan_days(lib, "JHN", 40)
        self.assertEqual(len(plan), 40)
        self.assertEqual([s for day in plan for s in day], list(build_site.book_sections("JHN", 21)))
        text = self.read(os.path.join("jhn", "lent", "index.html"))
        self.assertIn("Wednesday 10 February 2027", text)
        self.assertIn('href="/jhn/21/20-25/"', text)

    def test_the_scripture_cited_page_counts_the_citations(self):
        cites = build_site.citations_on("JHN")
        self.assertTrue(cites)
        text = self.read(os.path.join("jhn", "scripture-cited", "index.html"))
        self.assertIn(f"cite Scripture {len(cites):,} times", text)
        matthew = sum(1 for x in cites if x["start"].startswith("MAT."))
        self.assertIn(f'<span class="lg-bar-n">{matthew}</span>', text)
        self.assertIn('href="/jhn/scripture-cited/"', self.read(os.path.join("jhn", "index.html")))

    def test_the_catena_page_counts_the_fathers_by_their_printed_names(self):
        lib = build_site.Library()
        labels = build_site.catena_labels(lib)
        self.assertGreater(len(labels["AUG."]), len(labels["BEDE."]))
        # On the reader, each quotation's printed name is marked, both the
        # John edition's "CHRYS." and the Matthew edition's "Jerome, ...:".
        sp = build_site.catena_speakers("catena-matthew",
                                        "Jerome, Ez, i. 5.: The face.\n\nRabanus: By this.\n\nThus: not a name.")
        self.assertEqual([(x["at"], x["len"], x["who"]) for x in sp], [(0, 18, "jerome"), (30, 8, "rabanus")])
        self.assertEqual(build_site.catena_speakers("chrysostom-matthew", "Jerome: x"), [])
        self.assertTrue(all(x["who"] in build_site.CATALOG["catena"]["names"] for c in lib.comments
                            for x in build_site.catena_speakers(c["work"], c["text"])))
        text = self.read(os.path.join("works", "catena", "fathers", "index.html"))
        self.assertIn(f'<span class="lg-bar-n">{len(labels["CHRYS."])}</span>', text)
        self.assertIn('href="/commentators/chrysostom/"', text)
        self.assertIn('href="/works/catena/fathers/"', self.read(os.path.join("works", "catena", "index.html")))

    def test_each_era_page_shows_its_commentators_on_well_known_verses(self):
        lib = build_site.Library()
        for era in build_site.ERAS:
            people = [a for a in lib.authors.values() if a["era"] == era]
            if not people:
                continue
            text = self.read(os.path.join(build_site.era_url(era).strip("/"), "index.html"))
            for a in people:
                self.assertIn(f'href="/commentators/{a["id"]}/"', text)
            works = {w for w, x in lib.works.items() if lib.authors[x["author"]]["era"] == era}
            c = build_site.first_on(lib, works, "JHN.1.1")
            self.assertIsNotNone(c)
            self.assertIn(build_site.excerpt_href(lib, c), text)
        self.assertIn('href="/commentators/era/early-church/"', self.read(os.path.join("commentators", "index.html")))

    def test_the_guides_are_drafts_that_link_each_commentator(self):
        lib = build_site.Library()
        for g in build_site.guides():
            self.assertEqual(g["status"], "ai_draft")   # only a person marks one reviewed
            self.assertIsNone(g["reviewed_by"])
            text = self.read(os.path.join(g["path"].strip("/"), "index.html"))
            self.assertIn("A draft awaiting review", text)
            for x in g.get("topics", []):
                for w in lib.voices_on[build_site.ref_parts(x["focus"])]:
                    c = build_site.first_on(lib, {w}, x["focus"])
                    self.assertIn(build_site.excerpt_href(lib, c), text)
            for grp in g.get("groups", []):
                for x in grp["terms"]:
                    self.assertIn(f"<dt>{html.escape(x['term'], quote=True)}</dt>", text)
                    if x.get("link"):
                        where = os.path.join(build_site.SITE, x["link"].strip("/"), "index.html")
                        self.assertTrue(os.path.isfile(where), x["link"])
            for x in g.get("sections", []):
                for _label, href in x["links"]:
                    where = os.path.join(build_site.SITE, href.split("#")[0].strip("/"), "index.html")
                    self.assertTrue(os.path.isfile(where), href)
        self.assertIn('href="/jhn/traditions/"', self.read(os.path.join("jhn", "index.html")))
        self.assertIn('href="/glossary/"', self.read(os.path.join("jhn", "index.html")))
        self.assertIn('href="/jhn/study/"', self.read(os.path.join("jhn", "index.html")))

    def test_a_chapter_page_links_to_its_verse_pages(self):
        text = self.read(os.path.join("jhn", "3", "index.html"))
        self.assertIn('href="/jhn/3/16/"', text)
        self.assertIn('id="vpage"', text)
        self.assertNotIn('id="by-verse"', self.read(os.path.join("act", "1", "index.html")))

    # --- Search engines and answer engines ---

    def test_pages_with_only_the_bible_text_stay_out_of_search(self):
        sitemap = self.read("sitemap.xml")
        for page in ("gen/1/index.html", "gen/index.html", "act/1/index.html"):
            self.assertIn('<meta name="robots" content="noindex">', self.read(page), page)
            self.assertNotIn(f"<loc>https://logia.faith/{page[:-len('index.html')]}</loc>", sitemap)
        for page in ("jhn/3/index.html", "jhn/index.html", "rom/8/index.html", "jhn/3/16/index.html"):
            self.assertNotIn('content="noindex"', self.read(page), page)
            self.assertIn(f"<loc>https://logia.faith/{page[:-len('index.html')]}</loc>", sitemap)
        lib = build_site.Library()
        indexed = {c for c in lib.chapters if build_site.indexed(lib, build_site.chapter_url(*c))}
        self.assertEqual(indexed, set(lib.coverage()))

    def test_robots_welcomes_the_answer_engines_in_one_group(self):
        text = self.read("robots.txt")
        group = text.split("\n\n")[0]
        for name in ("*",) + build_site.AI_CRAWLERS:
            self.assertIn(f"User-agent: {name}\n", group)
        self.assertIn("Disallow: /saved/", group)
        self.assertIn("Sitemap: https://logia.faith/sitemap.xml", text)

    def test_llms_txt_describes_the_library_and_links_only_to_pages(self):
        lib = build_site.Library()
        text = self.read("llms.txt")
        self.assertTrue(text.startswith("# Logia\n"))
        self.assertIn(f"{len(lib.comments):,} excerpts", text)
        for a in lib.authors.values():
            self.assertIn(f"/commentators/{a['id']}/", text)
        for href in re.findall(r"https://logia\.faith(/[^\s)]*)", text):
            path = os.path.join(build_site.SITE, href.strip("/").rstrip(".:"))
            self.assertTrue(os.path.isfile(path) or os.path.isfile(os.path.join(path, "index.html")), href)

    def test_a_verse_page_marks_its_excerpts_as_quotations(self):
        lib = build_site.Library()
        text = self.read(os.path.join("jhn", "3", "16", "index.html"))
        ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)[1]
        data = json.loads(ld.replace("<\\/", "</"))
        page = next(x for x in data["@graph"] if x["@type"] == "WebPage")
        quotes = page["hasPart"]
        self.assertEqual({q["url"].split("#")[1] for q in quotes},
                         {c["id"] for c in lib.comments if c["start"] == "JHN.3.16"})
        for q in quotes:
            self.assertEqual(q["@type"], "Quotation")
            self.assertTrue(q["creator"]["name"] and q["isPartOf"]["datePublished"])
            self.assertTrue(q["isBasedOn"].startswith("http"))
        self.assertIn("BreadcrumbList", [x["@type"] for x in data["@graph"]])

    def test_the_sitemap_dates_bible_pages_when_the_history_is_here(self):
        dates = build_site.git_dates()
        if not dates:
            self.skipTest("no full git history")
        self.assertRegex(self.read("sitemap.xml"), r"<loc>https://logia\.faith/jhn/3/16/</loc><lastmod>\d{4}-\d\d-\d\d</lastmod>")

    def test_corrections_are_applied(self):
        lib = build_site.Library()
        ryle = " ".join(c["text"] for c in lib.comments if c["work"] == "ryle")
        self.assertNotIn("Let ns", ryle)
        self.assertIn("Let us", ryle)


if __name__ == "__main__":
    unittest.main()
