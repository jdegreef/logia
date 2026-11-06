# Adding a commentary

A new work, or more of an existing one, is three files and its sources. Two
people adding different works touch different files, so they never conflict.

## 1. Choose the edition

- The text, and any translation of it, must be published in 1930 or earlier.
  Note the translator and editor: for worldwide use they must have died in
  1955 or earlier, which is often still to confirm.
- Prefer a clean transcription (CCEL) over a page scan (archive.org). If only
  a scan exists, use the cleanest copy and expect to list corrections.
- Don't copy from BibleHub, StudyLight or newadvent.org: they claim rights
  in their typed editions.

## 2. Save the source

Fetch each page or scan text with curl. Save the part the excerpts come from
under `sources/<work>/`: a CCEL page's `book-content` block, or the stretch of
a scan's full text that holds the passage, with some margin on each side. Add
a row to `sources/manifest.json` with the URL, the date, `kind` (`digital` or
`scan`), the SHA-256 of the full download and a note on what the extract is.
Where each CCEL page is one section of a book and the page does not name the
book (Origen's Commentary on John), add `"part": "Book II"`, as CCEL's table
of contents gives it, so the section's locus and the book's whole text can
be read.

## 3. Write the author and work records

A new commentator gets `library/authors/<author>.json`: name, dates, the year
they died (it places them on the reader's line of centuries), `era` (one of
Early church, Middle Ages, Reformation, Puritans and the 1700s, and The 1800s),
tradition, and a short biography of plain facts. `bio_status` starts as
`ai_draft`.

The work is `library/works/<work>.json`, copying the fields of an existing
work; `author` names the author file. `divisions` is `"verse"` for a
commentary arranged by the verses it comments on, or the names of the
work's own divisions, such as `["Homily", "Section"]`, for homilies,
sermons or treatises (docs/references.md). `status` starts as `ai_draft`.

## 4. Copy the excerpts

`library/comments/<work>/<BOOK>.json`. Each entry is one passage on one verse
or range:

```json
{"id": "calvin.JHN.1.1.1", "start": "JHN.1.1", "end": "JHN.1.1",
 "heading": "In the beginning was the Speech",
 "text": "1. In the beginning was the Speech. In this introduction...",
 "sources": ["calcom34.vii.i.html"]}
```

- Copy the source's words exactly, paragraphs separated by a blank line.
  Drop footnote markers, footnotes, page numbers and running heads, nothing
  Once published an id never changes: a new excerpt takes the next free
  `<n>`, even if it sits before an older one.
  else. Mark a cut inside a paragraph with " ... ".
- Take the commentator's most substantive one to three paragraphs on the
  verse (about 80–350 words), cut only at sentence ends.
- `heading` is the source's own lemma or section heading, or empty.
- `id` is `<work>.<start>[-<end verse>].<n>`; entries are in verse order.

## 5. Correct scan misreadings

For a scanned source only: `library/corrections/<work>.json` lists
`{"from": "Let ns", "to": "Let us"}` pairs, applied in order to every entry of
the work at build time. Fix only what the printed page plainly reads. Never
add Greek or Hebrew; leave unreadable Greek out of the excerpt instead.

## 6. Find its place and its citations

    python3 scripts/find_refs.py

writes each excerpt's `locus` (for a work with its own divisions) and
`library/citations/<work>/<BOOK>.json`, the Scripture each excerpt cites, and,
for a catena, `library/quotations/`. Never edit these by hand except a
`status`; read what is new and set `"rejected"` on a false match. A new
work by a Father the Catena quotes can be added to `CATENAS` in the script,
so the Catena's quotations of it are traced too.

For a work with its own divisions, also run

    python3 scripts/extract_texts.py

to copy each whole homily or tractate from its source pages into
`library/texts/`, so it can be read straight through. Save the whole CCEL
page (its book-content block) under `sources/`, not only the part an
excerpt comes from.

## 7. Check

    python3 scripts/find_refs.py --check
    python3 scripts/extract_texts.py --check
    python3 scripts/validate.py
    python3 scripts/verify_sources.py <work>
    python3 scripts/build_site.py

and read the chapter page: does each card read well, and is each excerpt on
the verse it claims?
