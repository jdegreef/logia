# Logia's data

Everything in Logia is data in this repository, CC0 (the commentary texts
are in the public domain). This page describes every file, so a program can
use the library without the site's code. `scripts/validate.py` checks every
rule below on every change; `docs/references.md` explains the reference
scheme they share, and `docs/api.md` the same data as the site's JSON API.

A reference is `BOOK.chapter.verse` with a USFM book code (`JHN.1.14`).
Excerpts and topics use the Open Word Bible's verse numbers; citations keep
the commentator's own, English, numbering (`docs/references.md`).

## Files

**`library/authors/<author>.json`**: one commentator.
`id`, `name`, `dates` (as written: "c. 347-407"), `died` (a year),
`era` (Early church, Middle Ages, Reformation, Puritans and the 1700s, The
1800s), `tradition` (as the commentator is usually described), `family`
(`undivided`, `catholic`, `orthodox`, `anglican`, `protestant`: for the
tradition filter only), `bio`, `bio_status` (`ai_draft` or `reviewed`),
`portrait` (null).

**`library/works/<work>.json`**: what an author wrote.
`id`, `author` (an author id), `title`, `divisions` (`"verse"`, or the names
of the work's own divisions: `["Homily", "Section"]`), `genre` (`commentary`,
`homilies`, `catena`), `original_language`, `status`.

**`library/versions/<work>/<lang>.json`**: one text of a work in one
language. `id` (`<work>.<lang>`), `work`, `language` (ISO 639), `kind`
(`original` or `translation`), `edition`, `translation` (who translated it,
or null), `published` (a year, 1930 or earlier, or null for Logia's own),
`full_text_url`, `source_kind` (`digital` or `scan`, or null), `rights`
(`basis`, `worldwide`), `made_by` (`print` or `logia`), `status`,
`reviewer` (a name once reviewed), `notes`.

**`library/comments/<work>/<BOOK>.json`**: the excerpts of one work on one
book, all from one version. `work`, `book`, `version`, `entries`: each with
`id` (`<work>.<start>[-<end verse>].<n>`, never changed once published),
`start`, `end`, `heading` (the source's own lemma, or empty), `text` (as the
source reads: paragraphs separated by a blank line, a cut marked " ... "),
`sources` (file names in `sources/manifest.json`), and `locus` for a work
with its own divisions ("2.8").

**`library/corrections/<work>.json`**: scan misreadings, for scanned
versions only. `work`, `about`, `corrections`: `{from, to}` pairs, applied in
order to the text of every excerpt of the work, as the site does.

**`library/citations/<work>/<BOOK>.json`**: the Scripture each excerpt
cites. `work`, `book`, `citations`: each `in` (an excerpt id), `at` and
`text` (where it is printed in the corrected text), `start`, `end`, `found`
(`source`: marked by the transcription's editors; `pattern`: matched in a
scan), `status` (`detected`, `reviewed`, `rejected`).

**`library/quotations/<work>/<BOOK>.json`**: a catena's quotations traced
to the Fathers' works. `work`, `book`, `quotations`: each `in`, `at`,
`label` ("AUG."), `work` (the quoted work), `locus`, `source`, `para` (the
CCEL paragraph id, or null), `excerpt` (the Logia excerpt holding it, or
null), `score`, `found` (`similar`), `status`.

**`library/texts/<work>/<n>.json`**: a whole homily or tractate. `work`,
`version`, `locus`, `title`, `source`, `url`, `verses` (`start`, `end`),
`paragraphs`: each `id` (CCEL's), `locus`, `text`, `cites` (`at`, `text`,
`start`, `end`), `excerpts` (the excerpt ids it holds), `verse` (the verse it
expounds, or null).

**`library/topics/<id>.json`**: a topic, as a rule. `id`, `title`, `note`,
`order`, `verses`, `terms`, `status`, `reviewer`. Its excerpts are those on
its verses and those that use one of its terms (`docs/references.md`).

**`library/translations/<lang>/<work>/<BOOK>.json`**: Logia's own
translations of excerpts, none yet (`library/translations/README.md`).

**`sources/manifest.json`**: every source file an excerpt was copied from:
`path`, `work`, `url`, `retrieved`, `kind`, `download_sha256`, `extract`.

**`bible/owb/`**: the Open Word Bible's text, imported at the commit in
`SOURCE.json`; `books.json` (names, chapter counts) and
`versification.json` (English verse numbers to its own). It is the Open
Word Bible's data and is released by it; Logia's data releases leave it out.

## Releases

A release of the data is a zip, `logia-data-<version>.zip`, attached to a
GitHub release tagged `data-v<version>`. It holds `library/`,
`sources/manifest.json`, this page, `docs/references.md`, `docs/api.md`, the
licences, and `logia-data.json` (the version, the format and counts).
`scripts/export_data.py <version>` builds it, byte for byte the same from
the same data, and `.github/workflows/release.yml` builds and attaches it
when the tag is pushed.

Versions are numbered `format.additions.fixes`:

- the first number is the data format (`FORMAT` in
  `scripts/export_data.py`, 1 today). It rises only when a file loses or
  renames a field or a field changes meaning; such a change is listed in the
  release notes;
- the second rises when data is added: works, excerpts, versions, topics;
- the third, for corrections only: a scan fix, a citation reviewed.

Fields may be added within a format; a program should ignore fields it does
not know.

To release, from an up-to-date `main` with every check passing:

    git tag data-v1.0.0
    git push origin data-v1.0.0
