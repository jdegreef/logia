# References

Every verse, excerpt and place in a work has an address that does not
change, so that links, citations and other sites can rely on it (roadmap,
phase 1).

## Bible verses

`BOOK.chapter.verse` with a USFM book code: `JHN.1.14`. A range is a
`start` and an `end`. The 66 books and their chapter counts come from the
Open Word Bible (`bible/owb/books.en.json`, `bible/owb/chapters.json`). The
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
