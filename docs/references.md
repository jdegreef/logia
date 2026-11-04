# References

Every verse, excerpt and place in a work has an address that does not
change, so that links, citations and other sites can rely on it (roadmap,
phase 1).

## Bible verses

`BOOK.chapter.verse` with a USFM book code: `JHN.1.14`. A range is a
`start` and an `end`. The 66 books and their chapter counts come from the
Open Word Bible (`bible/owb/books.json`). The
deuterocanonical books (Tobit, Judith, Wisdom, Sirach, Baruch, 1 and 2
Maccabees), which the Fathers quote as Scripture and the Catholic and
Orthodox churches read, are listed in `scripts/scripture.py`. Citations of
them are kept like any other, though the Open Word Bible has no text to link
them to.

A citation keeps the commentator's own verse numbers. Nineteenth-century
English commentaries number the Old Testament as English Bibles do, which
differs from the Hebrew text in a few books (Malachi 4 is Hebrew Malachi
3:19–24), and the Catena and other Latin works may number the Psalms as
the Vulgate does.

## Excerpts

An excerpt's `id` is `<work>.<start>[-<end verse>].<n>`:
`calvin.JHN.1.1.1` is Calvin's first excerpt on John 1:1,
`ryle.JHN.1.15-18.1` is Ryle's first on John 1:15–18. Once published an id
never changes and is never reused.

## Places in a work

A work's `divisions` (in `library/works/<work>.json`) says how it is
divided:

- `"verse"`: a commentary arranged by the verses it comments on (Calvin,
  Henry, Bengel, Westcott, Ryle, the Catena). An excerpt's place is its
  verse.
- A list of names, such as `["Homily", "Section"]`: a work with its own
  divisions. Each excerpt has a `locus` giving where it begins, one number
  per division. Chrysostom `2.8` is Homily 2, section 8; Augustine `1.5` is
  Tractate 1, section 5. Cited in full: Chrysostom, *Homilies on the Gospel
  of St. John*, Homily 2.8.

`scripts/find_refs.py` reads each locus from the source page (the homily or
tractate heading, and the last section mark before the excerpt); no locus
is typed by hand. It reads CCEL pages only. A scanned work with its own
divisions will need its section marks read from the scan first.

## Whole texts

A work with its own divisions can also be read straight through.
`scripts/extract_texts.py` copies each of its CCEL source pages, one
homily or tractate each, into `library/texts/<work>/<n>.json`. Each
paragraph keeps:

- CCEL's paragraph id (`iii.ii-p34`), which is also its anchor on Logia and
  on CCEL;
- its locus (`1.13`);
- the Scripture references CCEL marks in it;
- the ids of the Logia excerpts that hold it.

The words are the page's own, with footnotes and page numbers left out as
for excerpts, and `scripts/verify_sources.py` checks every paragraph. The
site shows each text at `/works/<work>/<n>/`, with a section anchor
`#s<section>`, and each work's list at `/works/<work>/`.

## Two structures

A work with its own divisions can be read in two orders, as Sefaria's
alternate structures allow: by its own divisions (Homily 10, section 2)
and by the verses it expounds (John 1:12). The second is read from what
the CCEL page prints, never inferred:

- the verse a homily or tractate opens on, from its heading: "John i. 11"
  (Chrysostom), or a range, "Chapter I. 6–14" (Augustine);
- the verse marks a homily prints as it moves on: "Ver. 12.", "[3.] Ver. 13.".

`scripts/extract_texts.py` gives each whole text its `verses` (the heading's
verse or range, to the last verse marked) and each paragraph its `verse`:
the verse last marked before it, or `null` under a heading that names a
range and no mark yet. So Homily 10 covers John 1:11–13 and has paragraphs
on each verse, while Tractate 2 covers John 1:6–14 without saying which
paragraph is on which verse. Nothing is guessed in between. Homily 4 marks
only John 1:1, so it is not listed for John 1:2 even if it touches it.

The site uses both. A work's page lists its whole texts by homily and by
verse. A whole text labels the verse where its exposition moves on. The
reader lists, under every verse, the whole homilies and tractates on it,
even where Logia holds no excerpt from them.

## Versions

A work is what its author wrote; a version is one text of it, in one
language, as Sefaria keeps versions of each text. Each version has its own
record in `library/versions/<work>/<lang>.json`, id `<work>.<lang>`:

```json
{"id": "calvin.en", "work": "calvin", "language": "en", "kind": "translation",
 "edition": "Calvin Translation Society, tr. William Pringle, 1847",
 "translation": "Translated by William Pringle for the Calvin Translation Society (1847)",
 "published": 1847, "full_text_url": "https://www.ccel.org/ccel/calvin/calcom34.html",
 "source_kind": "digital", "rights": {"basis": "...", "worldwide": "..."},
 "made_by": "print", "status": "ai_draft", "reviewer": null, "notes": "..."}
```

- `kind` is `original` (the language the author wrote in: Henry's English,
  Calvin's Latin) or `translation`.
- `made_by` is `print`, a public-domain edition (published 1930 or earlier,
  copied from `source_kind` digital or scan), or `logia`, Logia's own
  translation (no published year or source; CC0).
- `status` is the version's own review: `ai_draft` until a named person
  reviews it, who is then its `reviewer`. A translation is reviewed by a
  native speaker; a copied edition by someone checking it against the page.
- Rights belong to a version, not a work: Calvin's Latin and Pringle's
  English have different translators, years and terms.

Each comments file names the version its excerpts are copied from
(`"version": "calvin.en"`), and a work's excerpts all come from one version.
The others are aligned to the same excerpt ids: a translation file in
`library/translations/` gives each excerpt's text in its version (`of` is the
excerpt id), and an edition of the original will do the same, so an excerpt
can be read in every version Logia holds. The whole texts in `library/texts/`
name their version too.

Today each work has one version, the English one its excerpts come from.
The work page lists each version with its edition, source, rights and
review.

## Links to an excerpt, and citing it

Every excerpt can be linked to on its own: the chapter page with the
excerpt's id, `https://logia.faith/jhn/1/#calvin.JHN.1.1.1`, opens the
reader at that verse and that excerpt. Because excerpt ids never change,
these links last. (`#v14` opens a verse, and `#v14-calvin` a verse at one
commentator's card.)

The reader's **Cite** button gives a citation built from the work and its
version: a translation names its translator, an original its year, and a
work with its own divisions gives its place:

> John Chrysostom, *Homilies on the Gospel of St. John*, the Oxford
> translation (Library of the Fathers), revised and edited by Philip Schaff,
> Nicene and Post-Nicene Fathers, Series 1, Vol. 14 (1889), Homily 2,
> section 8 (on John 1:1). In Logia: https://logia.faith/jhn/1/#chrysostom.JHN.1.1.1.

**How this was copied** shows where the excerpt came from (the CCEL page or
the archive.org scan), how `verify_sources.py` checks it, every scan
correction applied to it, its version and whether a person has reviewed it.
**Report a mistake** opens a GitHub issue with the excerpt's id, verse, link
and source filled in; a confirmed misreading becomes a pair in
`library/corrections/`.

## Traditions

Each author has a `family`, used only by the reader's tradition filter:
`undivided` for the Fathers before the East–West division (Chrysostom,
Augustine), whom Catholic, Orthodox and Protestant readers all claim, then
`catholic`, `orthodox`, `anglican` or `protestant`. It sorts; it does not
describe. The author's own `tradition` ("Reformed", "Lutheran Pietist",
"Anglican (Evangelical)") stays what the reader sees on each card. Like
the biographies, these assignments are a draft for a person to review.

## Topics

A topic (`library/topics/<id>.json`) is a rule, not a list: a title, a
one-line note, the verses at its centre and some terms.

```json
{"id": "incarnation", "title": "The Incarnation", "note": "Passages on the Word made flesh.",
 "order": 6, "verses": ["JHN.1.14"], "terms": ["incarnation", "incarnate", "made flesh"],
 "status": "ai_draft", "reviewer": null}
```

The topic page gathers every excerpt on one of its verses, and every other
excerpt that uses one of its terms (a term matches at the start of a word,
so "regenerat" finds regeneration and regenerate). It groups them by era,
shows how many come from each tradition, and prints the rule, so anyone can
see why each excerpt is there. Nothing is added to what the commentators
say. Choosing the verses and terms is editorial, so a topic stays
`ai_draft` until a named person reviews it. The reader lists, under each
verse, the topics it is at the centre of.

## Citations

`library/citations/<work>/<BOOK>.json` lists the Scripture each excerpt
cites:

```json
{"in": "calvin.JHN.1.1.1", "at": 184, "text": "1 Timothy 3:16",
 "start": "1TI.3.16", "end": "1TI.3.16", "found": "source", "status": "detected"}
```

- `in` is the excerpt, `at` and `text` where the reference is printed in it
  (after scan corrections).
- `found` is `source` when the transcription's editors marked the reference
  (CCEL), or `pattern` when `scripts/find_refs.py` matched it in a scan:
  "Heb. i. 3", "1 Tim. iii. 16, 17", "comp. vi. 46" (this book), "v. 14" (this
  chapter). A book name with no number ("Tim. iii. 16") is not guessed.
- `status` is `detected` until a person checks it: `reviewed`, or `rejected`
  for a false match. Rejected citations stay in the file, so they are not
  found again, and are not shown. Running the script again keeps every
  status.

The site uses citations both ways. Each reference in an excerpt links to
the verse (on Logia if the chapter is there, otherwise on the Open Word
Bible), and each verse lists the excerpts on other verses that refer to it
("Elsewhere in the library").

## Quotations of the Fathers

A catena is made of quotations: the Catena Aurea prints "CHRYS." or "AUG."
before each, and an abbreviated reference in the margin ("Chrys. Hom. ii. in
Joan."). The scans' OCR scatters those margin notes over several lines, so
they cannot be read reliably, and the excerpts leave them out.

Instead, `scripts/find_refs.py` traces each quotation from a work the
library holds (Chrysostom's homilies, Augustine's tractates) to the passage
of that work whose words it shares most. The Catena's English was made from
Aquinas's Latin, not from the Greek or Latin original the CCEL text was
translated from, so the words are never the same; the match weighs the
rarer words both share. `library/quotations/<work>/<BOOK>.json`:

```json
{"in": "catena.JHN.1.3.2", "at": 0, "label": "AUG.", "work": "augustine",
 "locus": "1.13", "source": "npnf107.iii.ii.html", "para": "iii.ii-p34",
 "excerpt": "augustine.JHN.1.3.1", "score": 0.7, "found": "similar", "status": "detected"}
```

- `locus` is a section ("1.13", Tractate 1, section 13) when one paragraph
  stands clearly above the rest (score 0.35 or more, 0.10 ahead of any other
  section), only the homily or tractate ("3") when only that stands out
  (0.20, 0.08 ahead of any other), and the quotation is left out otherwise.
- `para` is the CCEL paragraph, for a section match; `excerpt` the Logia
  excerpt that holds it, if there is one.
- `status` works as for citations. A reviewer checks a match against the
  margin note on the printed page; every legible note so far agrees with
  the match (tests/test_library.py).

The reader shows both directions: under a Catena excerpt, where each
quotation comes from; under the quoted excerpt, that the Catena quotes it.
