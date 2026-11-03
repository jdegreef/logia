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
