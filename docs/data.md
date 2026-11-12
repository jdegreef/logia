# Logia's data

Everything in Logia is data in this repository, CC0 (the commentary texts
are in the public domain). This page describes the files, so a program can
use the library without the site's code. `scripts/validate.py` checks them
on every change; `docs/references.md` explains the reference scheme they
share, and `docs/api.md` the same data as the site's JSON API.

A reference is `BOOK.chapter.verse` with a USFM book code (`JHN.1.14`).
Excerpts, topics and readings use the Open Word Bible's verse numbers;
citations keep the commentator's own numbering (`docs/references.md`).

## Files

**`library/authors/<author>.json`**: one commentator. `id`, `name`,
`dates` (as printed: "c. 347–407"), `died` (a year), `era` (Early church,
Middle Ages, Reformation, Puritans and the 1700s, The 1800s), `tradition`,
`bio`, `bio_status` (`ai_draft` or `reviewed`), `portrait`.

**`library/works/<work>.json`**: one commentary. `id`, `author`, `title`,
`divisions` (`"verse"`, or the names of the work's own divisions:
`["Homily", "Section"]`), `edition`, `original_language`, `translation`,
`published` (a year, 1930 or earlier), `full_text_url`, `rights` (`basis`,
`worldwide`: what is still to confirm), `source_kind` (`digital` or `scan`),
`notes`, `status` (`ai_draft` until a named person reviews it).

**`library/comments/<work>/<BOOK>.json`**: the excerpts of one work on one
book. `work`, `book`, `entries`: each `id` (`<work>.<start>[-<end
verse>].<n>`, never changed once published), `start`, `end`, `heading` (the
source's own lemma, or empty), `text` (as the source reads, paragraphs
separated by a blank line, a cut marked " ... "), `sources` (file names in
`sources/manifest.json`), and `locus` for a work with its own divisions
("2.8").

**`library/corrections/<work>.json`**: scan misreadings, for scanned works
only: `{from, to}` pairs, applied in order to the text of every excerpt of
the work, as the site does.

**`library/citations/<work>/<BOOK>.json`**, **`library/quotations/…`**,
**`library/mentions/…`**: the Scripture each excerpt cites, the Catena's
quotations traced to the Fathers' works, and where an excerpt names another
commentator, each with a `status` (`detected`, `reviewed`, `rejected`) that
only a person changes (`docs/references.md`).

**`library/texts/<work>/<n>.json`**: a whole homily or tractate, paragraph
by paragraph (`docs/references.md`, "Whole texts").

**`library/pages/<work>.json`**: the leaf of the archive.org scan each
scanned excerpt begins on, and the page number printed on it
(`scripts/find_pages.py`).

**`library/creeds/<id>.json`**: creeds, councils and confessions, section by
section, with the Scripture each section cites.

**`library/topics.json`**, **`library/collections.json`**,
**`library/occasions.json`**: Logia's choices of passages (topics, the
signs and sayings of John, the great days of the year); a choice of
passages, never of excerpts. **`library/lectionary/rcl.json`**: the Revised
Common Lectionary's Sundays and holy days (references only).

**`library/guides/<lang>/<guide>.json`**, **`library/differ/<id>.json`**:
Logia's own framing notes, never commentary, each `ai_draft` until a named
person reviews it.

**`library/families.json`**, **`library/identifiers.json`**: which
traditions count as one family for the pages on passages read differently,
and each commentator's and work's Wikidata item, Wikipedia article and Clavis
Patrum number.

**`library/translations/<lang>/<work>/<BOOK>.json`**: Logia's own
translations of excerpts, none yet (`library/translations/README.md`).

**`sources/manifest.json`**: every source file an excerpt was copied from:
`path`, `work`, `url`, `retrieved`, `kind`, `download_sha256`, `extract`.

**`bible/owb/`**: the Open Word Bible's text, imported at the commit in
`SOURCE.json`. It is the Open Word Bible's data and is released by it;
Logia's data releases leave it out.

## Releases

A release of the data is a zip, `logia-data-<version>.zip`, attached to a
GitHub release tagged `data-v<version>`. It holds `library/`,
`sources/manifest.json`, this page, `docs/references.md`, `docs/api.md`, the
licences, and `logia-data.json` (the version, the format and counts).
`scripts/export_data.py <version>` builds it, byte for byte the same from
the same data, and `.github/workflows/release.yml` builds and attaches it
when the tag is pushed. The site's `/downloads/` (`/open-data/`) are the
excerpts alone, rebuilt on every deploy; a release is the whole library,
fixed at a version others can cite and depend on.

Versions are numbered `format.additions.fixes`:

- the first number is the data format (`FORMAT` in
  `scripts/export_data.py`, 1 today). It rises only when a file loses or
  renames a field or a field changes meaning; such a change is listed in the
  release notes;
- the second rises when data is added: works, excerpts, topics, creeds;
- the third, for corrections only: a scan fix, a citation reviewed.

Fields may be added within a format; a program should ignore fields it does
not know.

To release, from an up-to-date `main` with every check passing:

    git tag data-v1.0.0
    git push origin data-v1.0.0
