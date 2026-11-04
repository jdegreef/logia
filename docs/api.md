# Logia's API

A free, read-only JSON API at `https://logia.faith/api/v1/`. It is static
files, written by `scripts/build_site.py` (`scripts/api.py`) on every build,
so it needs no key and has no limits beyond fair use. Every response allows
any origin (CORS), so a web page anywhere can read it. Logia's own
`linker.js` (`/linker/`) is built on it.

Licence: Logia's data is CC0; the commentary texts are in the public domain;
the Bible text is the Open Word Bible, CC0. The Greek and Hebrew word data
and the cross-references the reader shows are under CC BY and are not in
the API.

Within `v1` fields may be added, never removed or renamed; a breaking
change would be `/api/v2/`. Statuses are part of the data: an `ai_draft`
excerpt, version or topic has not yet been reviewed by a person, and a
`detected` citation has not been checked.

## Files

**`/api/v1/index.json`**: the API's name, version, licence, counts, and
the address of every file below.

**`/api/v1/chapters/<BOOK>.<chapter>.json`**: one chapter, for every
chapter of the Bible (`/api/v1/chapters/JHN.1.json`).

```json
{"book": "JHN", "chapter": 1, "name": "John 1", "url": "https://logia.faith/jhn/1/",
 "bible": {"text": "Open Word Bible", "level": "Balanced", "licence": "CC0 1.0", "url": "…"},
 "verses": [{"verse": 1, "ref": "JHN.1.1", "text": "In the beginning was the Word, …",
             "excerpts": ["calvin.JHN.1.1.1", …], "cited_by": ["…"], "topics": ["the-word"],
             "url": "https://logia.faith/jhn/1/#v1"}],
 "excerpts": {"calvin.JHN.1.1.1": {…}}}
```

- A verse's `excerpts` comment on it; `cited_by` are excerpts on other
  verses that cite it (converted to the Open Word Bible's numbering);
  `topics` are the topics it is at the centre of.
- Each excerpt in `excerpts`: `id`, `work`, `author`, `author_name`,
  `title`, `version`, `start`, `end`, `heading`, `locus` and `place` (for a
  work with its own divisions: "2.8", "Homily 2, section 8"), `text` (as the
  site shows it, scan corrections applied), `corrections` (the
  `{from, to}` pairs applied to it), `source` (the page it was copied from),
  `status`, `cites` (`at`, `text`, `start`, `end`, `found`, `status`), `url`
  (its own address on Logia).
- A verse's text is the Balanced level of the Open Word Bible, at its
  default reader settings.

**`/api/v1/works.json`**: every work: `id`, `title`, `author`, `genre`,
`divisions`, `original_language`, `status`, `versions` (ids), `excerpts` (a
count), `url`, `api`.

**`/api/v1/works/<work>.json`**: one work, with its `author` (the author
record), `versions` (the full version records: edition, translator, year,
source, rights, review), `excerpts` (each `id`, `start`, `end`, `locus` and
the `chapter` file that holds its text) and `texts` (its whole homilies or
tractates).

**`/api/v1/texts/<work>/<n>.json`**: a whole homily or tractate, as
`library/texts/` holds it (`docs/data.md`).

**`/api/v1/authors.json`**: every commentator: `id`, `name`, `dates`,
`died`, `era`, `tradition`, `family`, `bio`, `bio_status`, `url`.

**`/api/v1/topics.json`** and **`/api/v1/topics/<id>.json`**: each topic's
`id`, `title`, `note`, `verses`, `terms`, `status`, `url`, and, in its own
file, its `excerpts`: each `id`, `start` and `why` (`verse`, or the term
that brought it in).

**`/data/search.json`**: the site's search index (every excerpt and every
whole-text paragraph with its facets). Its shape may change with the
search page; it is not part of `v1`.

## Example

```js
const ch = await (await fetch("https://logia.faith/api/v1/chapters/JHN.1.json")).json();
const v14 = ch.verses.find(v => v.verse === 14);
for (const id of v14.excerpts) console.log(ch.excerpts[id].author_name, ch.excerpts[id].url);
```
