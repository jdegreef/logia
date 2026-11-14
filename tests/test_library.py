"""The library is valid, every excerpt is in its source, and the site builds.

    python3 -m unittest discover -s tests -t .
"""
import glob
import html
import io
import json
import os
import re
import sys
import unicodedata
import unittest
from unittest import mock
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import apply_reviews  # noqa: E402
import build_more  # noqa: E402
import build_site  # noqa: E402
import export_data  # noqa: E402
import differ  # noqa: E402
import extract_creeds  # noqa: E402
import extract_originals  # noqa: E402
import extract_texts  # noqa: E402
import fetch_wikidata  # noqa: E402
import find_pages  # noqa: E402
import find_refs  # noqa: E402
import score_refs  # noqa: E402
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

    def test_short_names_with_a_colon(self):
        # Jamieson-Fausset-Brown: "Lu 1:1-4; 24:3", "1Co 13:12"
        self.assertEqual(self.refs("(Lu 1:1-4; 24:3)", "LUK"),
                         [("Lu 1:1-4", "LUK.1.1", "LUK.1.4"), ("24:3", "LUK.24.3", "LUK.24.3")])
        self.assertEqual(self.refs("compare 1Co 13:12"), [("1Co 13:12", "1CO.13.12", "1CO.13.12")])
        self.assertEqual(self.refs("I am 3 years"), [])               # "Am" is read only before chapter:verse
        self.assertEqual(self.refs("Pr 10:1-22:16", "PRO"), [])        # a span of chapters is not cut short

    def test_capital_ver_and_this_book_s_chapters(self):
        self.assertEqual(self.refs("as he said, Ver. 4."), [("Ver. 4", "JHN.1.4", "JHN.1.4")])
        self.assertEqual(self.refs("I am the way ( c. xiv. 6 )"), [("xiv. 6", "JHN.14.6", "JHN.14.6")])

    def test_a_heading_is_not_a_citation(self):
        def refs(text):
            return [t for _, t, _, _ in find_refs.scan_citations(text, "ROM", 9, ("ROM.9.13", "ROM.9.13"))]
        self.assertEqual(refs("Ver. 13. A second quotation"), [])
        self.assertEqual(refs("x\n\n[2.] Ver. 13. Then"), [])
        self.assertEqual(refs("as Ver. 13 shows, and Ver. 11."), ["Ver. 13", "Ver. 11"])

    def test_a_verse_that_cannot_exist_is_a_misreading(self):
        self.assertEqual(self.refs("ver. 1 7, which", "ROM", 5), [])   # the scan's "17"
        self.assertEqual(self.refs("Isa. xv. 14"), [])                  # Isaiah 15 has nine verses
        self.assertEqual(self.refs("Joel ii. 32"), [("Joel ii. 32", "JOL.2.32", "JOL.2.32")])  # Hebrew 3:5
        self.assertEqual(self.refs("John viii. 51"), [("John viii. 51", "JHN.8.51", "JHN.8.51")])

    def test_the_scores_are_up_to_date(self):
        code, out = quiet(score_refs.main, ["--check"])
        self.assertEqual(code, 0, out)

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

    def test_a_reference_moves_with_its_verse(self):
        self.assertEqual(scripture.english_span("PSA.51.1", "PSA.51.2"), ("PSA.51.3", "PSA.51.4"))
        self.assertEqual(scripture.english_span("JHN.3.16", "JHN.3.16"), ("JHN.3.16", "JHN.3.16"))

    def test_citations_of_the_psalms_are_on_the_hebrew_verses(self):
        # Romans 3:4 quotes Psalm 51:4, "that thou mightest be justified", which is 51:6 here
        rows = json.load(open(os.path.join(ROOT, "library", "citations", "hodge-romans", "ROM.json")))["citations"]
        self.assertIn("PSA.51.6", {c["start"] for c in rows if c["text"] == "Ps. 51: 4"})

    def test_the_psalms_commentaries_are_on_the_hebrew_verses(self):
        entries = json.load(open(os.path.join(ROOT, "library", "comments", "augustine-psalms", "PSA.json")))["entries"]
        on = {e["start"] for e in entries if "Have pity upon me, O God, after Thy great mercy” (ver. 1)" in e["text"]}
        self.assertEqual(on, {"PSA.51.3"})       # Psalm 51:1 in English


class Differ(unittest.TestCase):
    """Pages on passages the churches read differently are published only when fair."""
    def test_families(self):
        self.assertEqual(differ.family("Anglican (Methodist)"), "methodist")
        self.assertEqual(differ.family("Baptist (Reformed)"), "reformed")
        self.assertEqual(differ.family("Patristic (Greek East)"), "early")
        self.assertEqual(differ.family("Roman Catholic (Jesuit)"), "catholic")

    def test_a_page_needs_the_early_church_a_catholic_or_orthodox_and_a_protestant_voice(self):
        self.assertEqual(differ.balance({"early", "catholic", "reformed", "anglican"}), (True, []))
        fair, missing = differ.balance({"early", "lutheran", "reformed"})
        self.assertFalse(fair)
        self.assertIn("Catholic or Orthodox", missing)
        self.assertFalse(differ.balance({"early", "orthodox", "reformed"})[0])      # three traditions only

    def test_every_page_is_resolved(self):
        for pg in differ.pages():
            self.assertNotIn("missing", pg, pg)
            self.assertTrue(pg["note"] and pg["status"] in ("ai_draft", "reviewed"), pg["id"])


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


class Creeds(unittest.TestCase):
    """library/creeds/: the creeds and confessions, read from their CCEL pages."""

    def doc(self, name):
        with open(os.path.join(ROOT, "library", "creeds", f"{name}.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_creeds_are_up_to_date(self):
        code, out = quiet(extract_creeds.main, ["--check"])
        self.assertEqual(code, 0, out)

    def test_every_tradition_is_here_and_nothing_is_reviewed(self):
        docs = [self.doc(os.path.basename(p)[:-5])
                for p in glob.glob(os.path.join(ROOT, "library", "creeds", "*.json"))]
        self.assertTrue(all(d["status"] == "ai_draft" for d in docs))
        shared = {d["id"] for d in docs if d["tradition"] == "Shared by the churches"}
        self.assertEqual(shared, {"apostles", "nicaea", "constantinople", "chalcedon", "athanasian"})
        traditions = {d["tradition"] for d in docs}
        for t in ("Roman Catholic", "Orthodox", "Lutheran", "Reformed", "Anglican", "Baptist"):
            self.assertTrue(any(x.startswith(t) for x in traditions), t)
        self.assertTrue(any("Methodist" in x for x in traditions))

    def test_only_the_english_column_is_taken(self):
        ath = self.doc("athanasian")["sections"]
        self.assertEqual([s["label"] for s in ath], [str(n) for n in range(1, 45)])
        self.assertTrue(ath[0]["text"].startswith("1. Whosoever will be saved"))
        self.assertFalse(any("Quicunque" in s["text"] or "Credimus" in s["text"] for s in ath))
        # the Thirty-Nine Articles: the English of 1571, not the American revision beside it
        art1 = self.doc("thirty-nine-articles")["sections"][1]
        self.assertEqual(art1["label"], "I. Of fayth in the holy Trinitie")
        self.assertIn("lyuyng and true God", art1["text"])
        self.assertNotIn("living and true God", art1["text"])

    def test_a_paragraph_split_by_a_page_break_is_one_section(self):
        canon = next(s for s in self.doc("trent-6")["sections"] if s["label"] == "ON JUSTIFICATION, CANON XVI")
        self.assertTrue(canon["text"].startswith("CANON XVI.—If any one saith, that he will for certain"))

    def test_proof_texts_are_kept_and_editors_notes_are_not(self):
        first = self.doc("westminster")["sections"][0]
        self.assertEqual(first["label"], "Chapter I. Of the Holy Scripture, I")
        proof = next(c for c in first["cites"] if c["start"] == "ROM.1.19")
        self.assertEqual((proof["end"], proof["note"]), ("ROM.1.20", True))
        self.assertEqual(first["text"][:proof["at"]].rstrip()[-len("inexcusable;"):], "inexcusable;")
        # Schaff's note on "he descended into hell" cites Scripture as he discusses the text: not a citation
        self.assertEqual([c for s in self.doc("apostles")["sections"] for c in s["cites"]], [])

    def test_a_question_and_its_answer_are_one_section(self):
        q1 = self.doc("heidelberg")["sections"][0]
        self.assertEqual(q1["label"], "Question 1")
        self.assertTrue(q1["text"].startswith("What is thy only comfort in life and in death?\n\nAnswer.\n\nThat I"))
        orthodox = self.doc("orthodox-catechism")["sections"]
        self.assertEqual(len(orthodox), 611)          # Schaff numbers the questions 1-611

    def test_a_changed_word_in_a_creed_fails(self):
        s = self.doc("trent-5")["sections"][1]
        streams = verify_sources.column_letters(os.path.join(ROOT, "sources", "creeds", s["source"]))
        self.assertTrue(any(verify_sources.check_digital(s["text"], x) is None for x in streams.values()))
        changed = s["text"].replace("Paradise", "Eden", 1)
        self.assertNotEqual(changed, s["text"])
        self.assertTrue(all(verify_sources.check_digital(changed, x) for x in streams.values()))


class Plurals(unittest.TestCase):
    def test_a_count_of_one_takes_the_singular_form(self):
        self.assertEqual(build_site.t("home.n_voices", n=1), "1 voice")
        self.assertEqual(build_site.t("home.n_voices", n=2), "2 voices")
        self.assertEqual(build_site.t("work.excerpts", n=1), "1 excerpt")
        # A formatted string such as "1,204" is never taken for one.
        self.assertEqual(build_site.t("passage.n_excerpts", n="1"), "1 excerpts")

    def test_every_singular_form_fills_from_the_same_values(self):
        def walk(node):
            for key, value in node.items():
                if isinstance(value, dict):
                    yield from walk(value)
                elif key.endswith("_one") and isinstance(node.get(key[:-4]), str):
                    yield node[key[:-4]], value
        names = re.compile(r"(?<!{){(\w+)}")
        for plural, one in walk(build_site.CATALOG):
            if one in ("{name} ({dates}) comments on {ref} in Logia.", "{n} excerpts from {name} ({dates}) on {ref}."):
                continue  # chosen by hand in the code, with their own values
            self.assertLessEqual(set(names.findall(one)), set(names.findall(plural)), one)


class Quoting(unittest.TestCase):
    def test_an_excerpt_that_opens_with_a_quote_gets_no_second_mark(self):
        self.assertEqual(build_site.in_quotes("Now some"), "“Now some”")
        self.assertEqual(build_site.in_quotes("“In the beginning was the Word.” It is"),
                         "“In the beginning was the Word.” It is")
        self.assertEqual(build_site.in_quotes("a < b"), "“a &lt; b”")


class ReadPage(unittest.TestCase):
    def test_chapter_lists_read_as_ranges(self):
        self.assertEqual(build_site.ranges_text([1, 2, 3, 7, 9, 10]), "1–3, 7, 9–10")
        self.assertEqual(build_site.ranges_text([40]), "40")

    def test_long_books_break_into_lines(self):
        psalms = build_site.bar_lines("PSA", 150)
        self.assertEqual([(x[0], x[-1]) for x in psalms], [(1, 41), (42, 72), (73, 89), (90, 106), (107, 150)])
        self.assertEqual([(x[0], x[-1]) for x in build_site.bar_lines("ISA", 66)], [(1, 33), (34, 66)])
        self.assertEqual(len(build_site.bar_lines("GEN", 50)), 1)

    def test_heat_falls_in_thirds(self):
        steps = build_site.heat_steps({("GEN", c): c for c in range(1, 10)})
        self.assertEqual(steps[("GEN", 1)], 1)
        self.assertEqual(steps[("GEN", 9)], 3)


class Dashes(unittest.TestCase):
    def test_lifespans_take_an_en_dash(self):
        self.assertEqual(build_site.en_dash("1509-1564"), "1509–1564")
        self.assertEqual(build_site.en_dash("c. 185-c. 253"), "c. 185–c. 253")
        self.assertEqual(build_site.en_dash("fl. 1680"), "fl. 1680")


class Counting(unittest.TestCase):
    def test_counter_and_owner_tags_are_off_unless_set(self):
        with mock.patch.multiple(build_site, GOATCOUNTER="", GOOGLE_VERIFY="", BING_VERIFY=""):
            self.assertEqual(build_site.counter_script(), "")
            self.assertEqual(build_site.site_owner_meta(), "")
        with mock.patch.multiple(build_site, GOATCOUNTER="logia", GOOGLE_VERIFY="abc", BING_VERIFY=""):
            self.assertIn('data-goatcounter="https://logia.goatcounter.com/count"', build_site.counter_script())
            self.assertEqual(build_site.counter_script(noindex=True), "")
            self.assertEqual(build_site.site_owner_meta(), '\n<meta name="google-site-verification" content="abc">')


class OfflineApp(unittest.TestCase):
    def test_manifest_names_the_icons_it_ships(self):
        m = json.loads(build_site.app_manifest())
        self.assertEqual((m["start_url"], m["display"]), ("/", "standalone"))
        for icon in m["icons"]:
            self.assertTrue(os.path.isfile(os.path.join(build_site.WEB, icon["src"].lstrip("/"))), icon["src"])

    def test_service_worker_keeps_the_frame_and_changes_version_with_it(self):
        a, b = build_site.service_worker("<p>one</p>"), build_site.service_worker("<p>two</p>")
        self.assertIn('"/offline/"', a)
        self.assertIn(build_site.asset("logia.css"), a)
        self.assertNotIn("var SHELL = [];", a)
        self.assertNotEqual(re.search(r'VERSION = "(\w+)"', a)[1], re.search(r'VERSION = "(\w+)"', b)[1])


def ref_is_verse_page(lib, c):
    return build_site.ref_parts(c["start"]) in lib.voices_on


class SefariaIdeas(unittest.TestCase):
    """The parts taken from Sefaria: AI marks, Sunday readings, the linker, scan pages."""

    def test_ai_marks(self):
        self.assertIn("lg-ai-draft", build_site.ai_mark("ai_draft"))
        self.assertIn("Ada Example", build_site.ai_mark("reviewed", "Ada Example"))
        self.assertEqual(build_site.ai_mark("reviewed"), "")   # reviewed needs a named person
        self.assertEqual(build_site.ai_mark(None), "")

    def test_readings_are_parsed_and_renumbered(self):
        self.assertEqual(build_site.parse_reading("Luke 2:1-14, (15-20)"), ("LUK", (2, 1), (2, 14)))
        self.assertEqual(build_site.parse_reading("Isaiah 61:10-62:3"), ("ISA", (61, 10), (62, 3)))
        self.assertEqual(build_site.parse_reading("2 Peter 3:8-15a"), ("2PE", (3, 8), (3, 15)))
        # Psalm 51's title is verse 1 and 2 in the Hebrew numbering the Bible text uses.
        self.assertEqual(build_site.parse_reading("Psalm 51:1-17"), ("PSA", (51, 3), (51, 19)))
        self.assertIsNone(build_site.parse_reading("Wisdom of Solomon 12:13"))

    def test_lectionary_holds_references_only(self):
        with open(os.path.join(ROOT, "library", "lectionary", "rcl.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("Consultation on Common Texts", data["rights"])
        for d in data["days"]:
            self.assertRegex(d["date"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertEqual(set(d["readings"]), {"first_and_psalm", "epistle", "gospel"})
            for refs in d["readings"].values():
                for r in refs:
                    self.assertLess(len(r), 80, r)   # a reference, never the reading's text

    def test_linker_knows_numbered_books(self):
        single, numbered = build_site.linker_names()
        self.assertEqual(single["Rom"], "ROM")
        self.assertEqual(numbered["Cor"], ["1CO", "2CO"])
        self.assertEqual(numbered["John"], ["1JN", "2JN", "3JN"])
        self.assertIn('"Rom": "ROM"', build_site.linker_js())

    def test_scan_pages_name_excerpts_in_the_library(self):
        for path in sorted(os.listdir(os.path.join(ROOT, "library", "pages"))):
            work = path[:-5]
            with open(os.path.join(ROOT, "library", "pages", path), encoding="utf-8") as f:
                data = json.load(f)
            ids = {c["id"] for c in find_pages.entries(work)}
            self.assertTrue(set(data["pages"]) <= ids, work)
            for ident, leaf, _printed in data["pages"].values():
                self.assertIn(ident, {x["id"] for x in data["scans"]})
                self.assertGreaterEqual(leaf, 0)


class Originals(unittest.TestCase):
    """The original beside the English: copied from the scan, placed by its Greek, a draft."""

    def test_notes_find_their_verse_from_the_greek(self):
        found = [(1, 1, "ἐν ἀρχῇ, in principio) ..."), (1, 14, "ὅσοι, quotquot) ..."),
                 (1, 48, "βηθσαϊδὰ, Bethsaida) ...")]
        placed = extract_originals.place("JHN", found, {(1, v) for v in range(1, 52)})
        # Bengel's scan numbers them 1, 14 and 48; their Greek is in John 1:1, 1:12 and 1:44.
        self.assertEqual([p["verse"] for p in placed], [1, 12, 44])

    def test_tidy_leaves_out_greek_noise_and_joins_lines(self):
        self.assertEqual(extract_originals.tidy("pro-\nxima ὁ υἱὸς imνv 1) est"), "proxima ὁ υἱὸς ... est")
        self.assertEqual(extract_originals.lemmas("a) b — quam Abrahamus — χαὶ, et) c"),
                         ["a) b — quam Abrahamus", "χαὶ, et) c"])

    def test_originals_are_drafts_copied_from_a_scan(self):
        for path in glob.glob(os.path.join(ROOT, "library", "originals", "*", "*.json")):
            with open(path, encoding="utf-8") as f:
                o = json.load(f)
            self.assertEqual(o["status"], "ai_draft")       # only a person marks the pairing reviewed
            self.assertTrue(o["scan"].startswith("https://archive.org/details/"))
            self.assertGreater(o["excerpts_with_original"], 0.9 * o["excerpts"])


class DataRelease(unittest.TestCase):
    """scripts/export_data.py: a release is the whole library, reproducibly."""

    def test_release_holds_the_library_and_its_docs(self):
        names = export_data.files()
        self.assertIn("sources/manifest.json", names)
        for doc in ("docs/data.md", "docs/api.md", "docs/references.md", "LICENSE"):
            self.assertIn(doc, names)
        self.assertTrue(any(n.startswith("library/comments/") for n in names))
        # The Bible text is the Open Word Bible's to release.
        self.assertFalse(any(n.startswith(("bible/", "site/")) for n in names))
        counts = export_data.counts()
        self.assertEqual(counts["works"], len(glob.glob(os.path.join(ROOT, "library", "works", "*.json"))))

    def test_release_version_follows_the_format(self):
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            export_data.main(["2.0.0"])       # the major number is the data format
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            export_data.main(["latest"])


class Site(unittest.TestCase):
    PAGES = ("index.html", "read/index.html", "jhn/index.html", "jhn/1/index.html", "jhn/21/index.html",
             "commentators/index.html", "commentators/calvin/index.html", "works/ryle/index.html", "about/index.html",
             "jhn/3/16/index.html", "ai/index.html", "new/index.html", "explore/index.html", "linker/index.html",
             "sheets/index.html", "readings/index.html", "about/rules/index.html", "open-data/index.html")

    @classmethod
    def setUpClass(cls):
        # CI builds site/ in the step before the tests and sets LOGIA_SITE_BUILT, so it is built once.
        if not (os.environ.get("LOGIA_SITE_BUILT") and os.path.isdir(build_site.SITE)):
            quiet(build_site.build)

    def read(self, page):
        with open(os.path.join(build_site.SITE, page), encoding="utf-8") as f:
            return f.read()

    def sitemap(self):
        """Every address in the sitemap: sitemap.xml is an index of one file per book and one for the rest."""
        index = self.read("sitemap.xml")
        parts = re.findall(r"<sitemap><loc>https://logia\.faith/(sitemap-[a-z0-9]+\.xml)</loc>", index)
        self.assertIn("sitemap-site.xml", parts)
        return "".join(self.read(p) for p in parts)

    def test_bengels_latin_is_folded_under_his_english(self):
        page = self.read("jhn/1/14/index.html")
        self.assertEqual(page.count('class="lg-orig"'), 1)       # once for his three excerpts on the verse
        self.assertIn('lang="la"', page)
        self.assertIn("σὰρξ, caro)", page)
        with open(os.path.join(build_site.SITE, "comm", "JHN.1.json"), encoding="utf-8") as f:
            bengel = [w for w in json.load(f)["commentaries"] if w["work_id"] == "bengel"][0]
        self.assertEqual(bengel["original"]["lang"], "la")
        self.assertTrue(bengel["original"]["verses"]["14"][0].startswith("σὰρξ, caro)"))

    def test_linker_files_are_numbered_as_english_bibles(self):
        with open(os.path.join(build_site.SITE, "linker", "PSA.51.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.assertTrue(data["verses"]["1"]["href"].startswith("/psa/51/3"))
        self.assertTrue(os.path.isfile(os.path.join(build_site.SITE, "linker.js")))

    def test_the_commentators_page_cards(self):
        text = self.read("commentators/index.html")
        monos = re.findall(r'<span class="lg-mono" aria-hidden="true">(\w+)</span>', text)
        self.assertEqual(len(monos), len(set(monos)), "two commentators share a monogram")
        self.assertNotIn("about 1 hours", text.lower())
        cards = dict(re.findall(r'<li[^>]*class="lg-cmt" data-author="(\w+)".*?<blockquote><p>(.*?)</p>', text, re.S))
        self.assertFalse(cards["fausset"].startswith("Ec 1"))          # a heading, not a sentence
        self.assertTrue(cards["gregory"].startswith("Thus we possess"))  # the scan's "3&. ..." left off
        self.assertTrue(cards["basil"].startswith("I stop struck"))     # the verse he quotes first left off
        for part in ("lg-findbar", "lg-erastrip", "lg-tl-mark", "lg-covgrid", "lg-new-list", 'role="tablist"'):
            self.assertIn(part, text)
        # Cards go in the order the commentators were born, era by era.
        order = re.findall(r'class="lg-cmt" data-author="(\w+)"', text)
        self.assertLess(order.index("brown"), order.index("spurgeon"))

    def test_card_sizes_and_bios(self):
        self.assertIn("About an hour to read", build_site.card_size(12000, 30))
        self.assertIn("Under an hour to read", build_site.card_size(3000, 9))
        self.assertIn("minutes a day for a year", build_site.card_size(2_000_000, 8000))
        self.assertEqual(build_site.bio_line({"bio": "Bishop of Caesarea in Cappadocia from 370, one of the three "
                                                     "Cappadocian Fathers with his brother Gregory; he wrote rules."}),
                         "Bishop of Caesarea in Cappadocia from 370")
        self.assertEqual(build_site.tradition_tag("Roman Catholic (Jesuit)"),
                         '<span class="lg-trad" title="Roman Catholic (Jesuit)">'
                         'Roman Catholic <span>Jesuit</span></span>')

    def test_ai_marks_replace_the_draft_pills(self):
        calvin = self.read("commentators/calvin/index.html")
        self.assertIn('class="lg-ai lg-ai-draft" href="/ai/"', calvin)
        self.assertNotIn("a draft awaiting review", calvin)

    def test_readings_hold_the_sundays_and_the_great_days(self):
        text = self.read("readings/index.html")
        self.assertIn('id="sundays"', text)
        self.assertIn('id="great-days"', text)
        self.assertEqual(text.count("<h1>"), 1)

    def test_verse_pages_name_their_topics_and_printed_pages(self):
        lib = build_site.Library()
        on = build_site.topics_on_verse(lib)
        verse = next(k for k in sorted(on) if k in lib.voices_on)
        text = self.read(build_site.verse_url(*verse).strip("/") + "/index.html")
        for x in on[verse]:
            self.assertIn(f'href="/topics/{x}/"', text)
        scanned = next(c for c in lib.comments if c["scan"] and ref_is_verse_page(lib, c))
        text = self.read(build_site.verse_url(*build_site.ref_parts(scanned["start"])).strip("/") + "/index.html")
        self.assertIn(scanned["scan"]["url"], text)

    def test_api_chapters_hold_verses_and_excerpts(self):
        api_dir = os.path.join(build_site.SITE, "api", "v1")
        with open(os.path.join(api_dir, "index.json"), encoding="utf-8") as f:
            index = json.load(f)
        self.assertEqual(index["api_version"], 1)
        with open(os.path.join(api_dir, "chapters", "JHN.1.json"), encoding="utf-8") as f:
            ch = json.load(f)
        v14 = next(v for v in ch["verses"] if v["verse"] == 14)
        self.assertTrue(v14["text"] and v14["excerpts"])
        first = v14["excerpts"][0]
        self.assertEqual(ch["excerpts"][first]["text"], build_site.Library().by_id[first]["text"])
        # Every chapter, with or without commentary.
        self.assertTrue(os.path.isfile(os.path.join(api_dir, "chapters", "OBA.1.json")))
        with open(os.path.join(api_dir, "works.json"), encoding="utf-8") as f:
            works = json.load(f)
        self.assertTrue(all(w["rights"]["basis"] and w["status"] in ("ai_draft", "reviewed") for w in works))

    def test_rules_page_lists_every_work_and_its_rights(self):
        text = self.read("about/rules/index.html")
        lib = build_site.Library()
        for wid, w in lib.works.items():
            self.assertIn(f'href="/works/{wid}/"', text)
            self.assertIn(html.escape(w["rights"]["basis"], quote=True), text)
        self.assertIn("docs/adding-a-work.md", text)

    def test_new_feed_is_atom(self):
        text = self.read("new.xml")
        self.assertTrue(text.startswith('<?xml version="1.0" encoding="utf-8"?>'))
        self.assertIn('<feed xmlns="http://www.w3.org/2005/Atom"', text)

    def test_pages_exist_with_the_site_frame(self):
        for page in self.PAGES:
            text = self.read(page)
            self.assertTrue(text.startswith("<!doctype html>"), page)
            self.assertIn('<header class="site">', text, page)
            self.assertIn('<footer class="site">', text, page)
            self.assertIn('id="colour-menu"', text, page)

    def test_header_has_the_search_pop_up_and_the_chapter_switcher(self):
        home = self.read("index.html")
        self.assertIn('<dialog class="palette lg-palette" id="palette"', home)
        self.assertIn('data-search-open', home)
        self.assertNotIn('class="lg-where"', home)
        chapter = self.read(os.path.join("jhn", "3", "index.html"))
        self.assertIn('<div class="lg-where" data-book="JHN" data-chapter="3">', chapter)
        self.assertIn('rel="prev" href="/jhn/2/"', chapter)
        self.assertIn('rel="next" href="/jhn/4/"', chapter)
        self.assertIn('class="lg-progress"', chapter)
        verse = self.read(os.path.join("jhn", "3", "16", "index.html"))
        self.assertIn('data-chapter="3"', verse)
        self.assertNotIn('class="lg-progress"', verse)
        data = json.loads(re.search(r'id="nav-data">(.*?)</script>', home, re.S)[1].replace("<\\/", "</"))
        self.assertEqual(data["books"]["JHN"]["n"], 21)
        self.assertIn(3, data["books"]["JHN"]["has"])

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
        self.assertEqual(len(data["commentaries"]), 12)
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
        self.assertRegex(chapter, r"<title>John 3 commentary: Chrysostom, Augustine, [A-Z][a-z]+ and \d+ more")
        self.assertIn('"@type":"Person"', self.read("commentators/calvin/index.html"))

    def test_a_commentator_page_lists_the_verses_they_pass_over(self):
        text = self.read("commentators/calvin/index.html")
        self.assertRegex(text, r'class="lg-missing"><summary>Verses with no comment from Calvin \(\d+\)</summary>')
        self.assertNotIn("lg-missing", self.read("commentators/ryle/index.html"))

    def test_a_commentator_with_several_books_has_a_page_for_them(self):
        text = self.read("commentators/calvin/index.html")
        # The works as cards, the four numbers, the Bible strip, a passage in
        # their words, a switch between books and the bar of sections.
        self.assertIn('class="lg-wk-cards"', text)
        self.assertIn('href="/works/calvin-romans/rom/1/">Read Romans 1</a>', text)
        self.assertIn("hours to read them all", text)
        self.assertEqual(text.count('class="lg-on"'), text.count('class="lg-bp"') - 1)
        self.assertGreaterEqual(text.count('class="lg-on"'), 3)
        self.assertIn('class="lg-own" data-quotes=', text)
        self.assertIn('class="lg-bp" aria-pressed="false" data-book="ROM"', text)
        self.assertIn('<nav class="lg-secbar"', text)
        # Two readings from another era, the words used most, more on Logia,
        # and the commentators either side in time.
        self.assertIn('id="voices"', text)
        self.assertIn('class="lg-vocab"', text)
        self.assertIn('href="/commentators/era/reformation/"', text)
        self.assertIn('class="lg-prev" href="/commentators/luther/"', text)
        self.assertIn('class="lg-next" href="/commentators/bellarmine/"', text)

    def test_the_reader_can_report_a_mistake_on_github(self):
        text = self.read("jhn/3/index.html")
        self.assertIn('"issues":"https://github.com/jdegreef/logia/issues/new"', text)
        self.assertIn('"report":"Report a mistake"', text)

    def test_a_commentator_page_opens_ways_into_the_work(self):
        text = self.read("commentators/chrysostom/index.html")
        # A passage to start with in each of the four books, the verse beside each row, where each
        # sits in its homily, and the homilies themselves as a second tab.
        start = text.split('id="start"', 1)[1].split("</section>", 1)[0]
        self.assertEqual(len(re.findall(r'<li data-book="\w+" data-rank="\d+"><a', start)), 4)
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
        self.assertNotIn("/404.html", self.sitemap())

    def test_the_saved_page_has_each_chapter_s_comments(self):
        data = json.loads(self.read(os.path.join("data", "JHN.1.json")))
        self.assertEqual(data["bookName"], "John")
        self.assertEqual({w["work_id"] for w in data["commentaries"]},
                         {"chrysostom", "augustine", "catena", "calvin", "henry", "bengel", "ryle", "westcott",
                          "origen", "wesley", "cyril", "lapide"})

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

    def test_a_book_of_origen_is_one_text_over_many_pages(self):
        # Each CCEL page of Origen's Commentary is one section; the manifest gives its book.
        with open(os.path.join(ROOT, "library", "comments", "origen", "JHN.json"), encoding="utf-8") as f:
            loci = {e["id"]: e["locus"] for e in json.load(f)["entries"]}
        self.assertEqual(loci["origen.JHN.1.2.2"], "2.5")         # Book II, section 5
        self.assertEqual(loci["origen.JHN.2.20.1"], "10.22")      # Book X, section 22
        with open(os.path.join(ROOT, "library", "texts", "origen", "2.json"), encoding="utf-8") as f:
            b2 = json.load(f)
        self.assertEqual(b2["title"], "Book II.")
        self.assertEqual(b2["verses"], {"start": "JHN.1.1", "end": "JHN.1.8"})
        self.assertEqual(len({p["source"] for p in b2["paragraphs"]}), 30)
        self.assertEqual({p["locus"] for p in b2["paragraphs"] if p["source"] == "anf09.xv.iii.ii.v.html"}, {"2.5"})

    def test_the_reader_lists_whole_texts_on_a_verse(self):
        with open(os.path.join(build_site.SITE, "jhn", "1", "index.html"), encoding="utf-8") as f:
            data = json.loads(re.search(r'id="chapter-data">(.*?)</script>', f.read(), re.S)[1].replace("<\\/", "</"))
        rows = {(r["work_id"], r["where"]) for r in data["wholeTexts"]["12"]}
        self.assertEqual(rows, {("chrysostom", "Homily 10, section 2"), ("augustine", "Tractate 2")})
        # No homily marks 1:2; Origen's first two books take in John 1:1-9 and 1:1-8.
        self.assertEqual({r["work_id"] for r in data["wholeTexts"]["2"]}, {"augustine", "origen"})
        self.assertIn(("origen", "Book 2, section 4"), {(r["work_id"], r["where"]) for r in data["wholeTexts"]["2"]})

    # --- Verse pages ---

    def test_every_verse_with_commentary_has_a_page(self):
        lib = build_site.Library()
        for book, chapter, verse in lib.voices_on:
            path = os.path.join(build_site.SITE, book.lower(), str(chapter), str(verse), "index.html")
            self.assertTrue(os.path.isfile(path), (book, chapter, verse))
        # Acts has no commentary, so no verse pages.
        self.assertFalse(os.path.exists(os.path.join(build_site.SITE, "act", "1", "1")))
        sitemap = self.sitemap()
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
        self.assertIn("<loc>https://logia.faith/jhn/2/1-12/</loc>", self.sitemap())

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
        self.assertIn(f'<a href="/jhn/{ch}/{v}/"><b>John {ch}:{v}</b></a>', text)
        bar = r'<span class="lg-rank-bar"[^>]*><span style="width:100%"></span></span>'
        self.assertRegex(text, rf'<td class="lg-num" data-sort="{n}">{bar}{n}</td>')
        self.assertIn('href="/jhn/most-discussed/"', self.read(os.path.join("jhn", "index.html")))
        # The controls' data and the download hold the same counts.
        data = json.loads(self.read(os.path.join("jhn", "most-discussed", "data.json")))
        row = next(r for r in data["rows"] if r[:2] == [ch, v])
        self.assertEqual(sum(row[3]), n)
        import csv as csv_
        path = os.path.join(build_site.SITE, "jhn", "most-discussed", "jhn-most-discussed.csv")
        with open(path, encoding="utf-8") as f:
            rows = {(int(r["chapter"]), int(r["verse"])): r for r in csv_.DictReader(f)}
        self.assertEqual(int(rows[(ch, v)]["excerpts"]), n)
        self.assertEqual(sum(int(r["excerpts"]) for r in rows.values()), sum(counts.values()))
        # The verse page says where it stands.
        verse = self.read(os.path.join("jhn", str(ch), str(v), "index.html"))
        self.assertIn('href="/jhn/most-discussed/#verses"', verse)

    def test_ranks_share_a_place_when_counts_are_equal(self):
        self.assertEqual(build_site.rank_with_ties({"a": 5, "b": 3, "c": 3, "d": 1, "e": 0}),
                         {"a": (1, False), "b": (2, True), "c": (2, True), "d": (4, False)})

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
            self.assertIn("AI draft, not yet reviewed", text)
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
        sitemap = self.sitemap()
        for page in ("exo/1/index.html", "exo/index.html", "act/1/index.html"):
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
        self.assertRegex(self.sitemap(), r"<loc>https://logia\.faith/jhn/3/16/</loc><lastmod>\d{4}-\d\d-\d\d</lastmod>")

    # --- Topics ---

    def test_topic_passages_are_real_and_their_words_are_in_the_catalog(self):
        lib = build_site.Library()
        data = build_site.load(os.path.join(build_site.ROOT, "library", "topics.json"))["topics"]
        self.assertEqual(len({x["id"] for x in data}), len(data))
        for tp in data:
            words = build_site.CATALOG["topics"][tp["id"]]
            for k in ("heading", "dek", "note"):
                self.assertIn(k, words, tp["id"])
            for item in tp["items"]:
                book, start, end = build_site.topic_span(item)
                self.assertLessEqual(start, end, item)
                self.assertIn(start[1], build_site.chapter_verses(book, start[0]), item)
                self.assertIn(end[1], build_site.chapter_verses(book, end[0]), item)
                self.assertIn(item["key"], words["items"], (tp["id"], item["key"]))
            self.assertTrue(any(build_site.in_passage(lib, *build_site.topic_span(x)) for x in tp["items"]), tp["id"])

    def test_a_topic_shows_every_commentator_on_each_passage(self):
        lib = build_site.Library()
        tp = next(x for x in build_site.topics(lib) if x["id"] == "baptism")
        text = self.read(os.path.join("topics", "baptism", "index.html"))
        for item in tp["items"]:
            section = text.split(f'id="{item["key"]}"')[1].split("</section>")[0]
            for wid, _cs in build_site.in_passage(lib, *build_site.topic_span(item)):
                self.assertIn(f"<b>{build_site.short_name(lib.author_of(wid))}</b>", section, (item["key"], wid))
        self.assertIn("<loc>https://logia.faith/topics/baptism/</loc>", self.sitemap())
        index = self.read(os.path.join("topics", "index.html"))
        for x in build_site.topics(lib):
            self.assertIn(f'href="/topics/{x["id"]}/"', index)
        self.assertIn('href="/topics/"', self.read("index.html"))

    def test_corrections_are_applied(self):
        lib = build_site.Library()
        ryle = " ".join(c["text"] for c in lib.comments if c["work"] == "ryle")
        self.assertNotIn("Let ns", ryle)
        self.assertIn("Let us", ryle)


class Wikidata(unittest.TestCase):
    """scripts/fetch_wikidata.py accepts only one human who died in the author's year."""

    @staticmethod
    def item(qid, human=True, died=430, article=None):
        claims = {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5" if human else "Q4167410"}}}}],
                  "P570": [{"mainsnak": {"datavalue": {"value": {"time": f"+{died:04d}-08-28T00:00:00Z"}}}}]}
        return {"id": qid, "claims": claims, "sitelinks": {"enwiki": {"title": article}} if article else {}}

    def test_one_human_with_the_same_year_of_death(self):
        author = {"name": "Augustine of Hippo", "died": 430}
        got = fetch_wikidata.pick(author, [self.item("Q1", human=False), self.item("Q2", died=604),
                                           self.item("Q3", article="Augustine of Hippo")])
        self.assertEqual(got, {"wikidata": "Q3", "wikipedia": "Augustine_of_Hippo"})

    def test_no_match_or_two_matches_is_left_for_a_person(self):
        author = {"name": "John", "died": 407}
        self.assertIsNone(fetch_wikidata.pick(author, [self.item("Q1", died=408)]))
        self.assertIsNone(fetch_wikidata.pick(author, [self.item("Q1", died=407), self.item("Q2", died=407)]))

    def test_a_work_is_the_author_s_one_item_with_its_title(self):
        def work(qid, label, author="Q100", cpg=None):
            claims = {"P50": [{"mainsnak": {"datavalue": {"value": {"id": author}}}}]}
            if cpg:
                claims["P9"] = [{"mainsnak": {"datavalue": {"value": cpg}}}]
            return {"id": qid, "labels": {"en": {"value": label}}, "claims": claims}
        title = "Homilies on the Gospel of St. John"
        items = [work("Q1", "Homilies on John", cpg="1234"), work("Q2", "Homilies on Matthew"),
                 work("Q3", "Homilies on John the Baptist", author="Q999")]
        self.assertEqual(fetch_wikidata.pick_work(title, "Q100", items, {"cpg": "P9"}),
                         {"wikidata": "Q1", "label": "Homilies on John", "cpg": "1234"})
        # two items as like the title, or one sharing a single word: none
        self.assertIsNone(fetch_wikidata.pick_work(title, "Q100", items + [work("Q4", "John: homilies")], {}))
        self.assertIsNone(fetch_wikidata.pick_work("On the Psalms", "Q100", items, {}))

    def test_identifiers_become_same_as_links(self):
        a = {"id": "x", "name": "X", "dates": "354-430", "died": 430}
        ld = build_site.person_ld(a, {"wikidata": "Q8018", "wikipedia": "Augustine_of_Hippo"})
        self.assertEqual(ld["sameAs"], ["https://www.wikidata.org/wiki/Q8018", "https://en.wikipedia.org/wiki/Augustine_of_Hippo"])
        self.assertNotIn("sameAs", build_site.person_ld(a))


class StudyToolsTest(unittest.TestCase):
    """Reading plans, calendar feeds and the reference checker's answers (scripts/build_more.py, apply_reviews.py)."""

    @classmethod
    def setUpClass(cls):
        build_more.setup(build_site)

    def test_the_advent_plan_has_a_passage_for_each_day_to_christmas_eve(self):
        readings = build_more.plans_data()["advent"]["readings"]
        self.assertEqual(len(readings), 24)
        for ref in readings:
            book, start, end = build_more.span_of(ref)
            self.assertLessEqual(start, end, ref)
            self.assertIn(end[1], build_site.chapter_verses(book, end[0]), ref)

    def test_a_book_plan_keeps_every_chapter_whole_and_in_order(self):
        lib = mock.Mock(books={"PSA": {"chapters": 150}})
        days = build_more.book_plan_days(lib, "PSA", 30)
        self.assertEqual(len(days), 30)
        self.assertEqual([c for d in days for c in d], list(range(1, 151)))

    def test_calendar_lines_are_folded_at_75_octets(self):
        line = "SUMMARY:" + "Advent, day 1: John 1:1–5 " * 6
        for part in build_more.ics_fold(line).split("\r\n"):
            self.assertLessEqual(len(part.encode("utf-8")), 75)
        self.assertEqual(build_more.ics_fold(line).replace("\r\n ", ""), line)

    def test_answers_set_a_status_only_on_the_citation_they_name(self):
        def cite(at, text, ref):
            return {"in": "x.JHN.1.1.1", "at": at, "text": text, "start": ref, "end": ref,
                    "found": "pattern", "status": "detected"}
        cites = [cite(5, "Rom. 1:1", "ROM.1.1"), cite(40, "Heb. 1:3", "HEB.1.3")]
        data = {"work": "x", "book": "JHN", "citations": cites}
        with mock.patch.object(apply_reviews, "ROOT", self.tmp(data)):
            got = apply_reviews.apply([{"in": "x.JHN.1.1.1", "at": 5, "start": "ROM.1.1", "ok": False},
                                       {"in": "x.JHN.1.1.1", "at": 99, "start": "ROM.1.1", "ok": True}])
            with open(apply_reviews.citations_path("x.JHN.1.1.1"), encoding="utf-8") as f:
                after = json.load(f)
        self.assertEqual(got, (1, 0, 1))
        self.assertEqual([c["status"] for c in after["citations"]], ["rejected", "detected"])

    def tmp(self, data):
        import tempfile
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "library", "citations", "x"))
        with open(os.path.join(root, "library", "citations", "x", "JHN.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)
        return root


if __name__ == "__main__":
    unittest.main()
