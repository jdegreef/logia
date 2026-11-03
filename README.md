# Logia

**[logia.faith](https://logia.faith)** sets each verse of Scripture beside two
thousand years of public-domain commentary, from the early church to the
1800s, free and open. It starts in English and will grow into many languages.

The name comes from *ta logia tou theou*, "the oracles of God" (Romans 3:2),
and from Papias's lost *Exposition of the Logia of the Lord*, one of the first
Christian commentaries.

## What is here

| Path | Holds |
|---|---|
| `library/works/<work>.json` | One commentary: author, dates, tradition, era, divisions, edition, translator, rights, status |
| `library/comments/<work>/<BOOK>.json` | Its excerpts on one book, each tied to a verse range (`JHN.1.6`–`JHN.1.8`) and, in a work with its own divisions, to its place in the work (Homily 2, section 8) |
| `library/citations/<work>/<BOOK>.json` | The Scripture each excerpt cites, found by `scripts/find_refs.py` (see `docs/references.md`) |
| `library/corrections/<work>.json` | Scan misreadings fixed at build time (scanned sources only) |
| `library/translations/<lang>/<work>/<BOOK>.json` | Translations of excerpts, once they start (see `library/translations/README.md`) |
| `sources/` | The source text each excerpt was copied from, and `manifest.json` listing where each came from |
| `bible/owb/` | The Bible text: Open Word Bible chapters, imported at a pinned commit |
| `web/` | Page templates: the home page and the chapter reader |
| `scripts/` | Import, validate, verify and build |
| `docs/` | How to add a work, the editorial rules, and the roadmap (`docs/roadmap.md`) |

The library today: John 1:1–18 with eight commentaries (Chrysostom,
Augustine, the Catena Aurea, Calvin, Matthew Henry, Bengel, J. C. Ryle and
Westcott), 246 excerpts in all.

## How the text stays honest

- **Excerpts are copied, never written.** Each is the source's own words,
  and `scripts/verify_sources.py` checks every one against the source text in
  `sources/`. A digital transcription must hold the excerpt word for word; a
  page scan, whose lines carry margin notes and running heads, is checked in
  runs of six words.
- **Scan misreadings are corrected in the open.** An excerpt keeps the scan's
  text; `library/corrections/` lists each fix ("Let ns" → "Let us"), and the
  build applies them.
- **Places and citations are read from the sources.** `scripts/find_refs.py`
  reads where each excerpt sits in its work, and the Scripture it cites,
  from the source pages; a citation stays `detected` until a person checks
  it.
- **Rights are recorded per work**: the edition, the translator, the year,
  and what is still to confirm for worldwide use.
- **Nothing is marked reviewed by an AI.** Works and translations stay
  `ai_draft` until a named human reviewer approves them.

## Commands

    python3 scripts/find_refs.py --check # loci and citations are up to date
    python3 scripts/validate.py          # the data is well formed
    python3 scripts/verify_sources.py    # every excerpt is in its source
    python3 -m unittest discover -s tests -t .
    python3 scripts/build_site.py        # writes site/
    uvx ruff@0.16.9 check .              # lint (pyproject.toml)

Preview the built site with `python3 -m http.server -d site` and open
<http://localhost:8000/jhn/1/>.

To refresh the Bible text, check out
[open-word-bible](https://github.com/jdegreef/open-word-bible) at the commit
in `bible/owb/SOURCE.json` (change the pin first to move to a newer one) and
run:

    python3 scripts/import_owb.py --owb ../open-word-bible JHN.1

## Licences

Logia's own data and writing are CC0 (`LICENSE`); the code is MIT
(`LICENSE-CODE`). The commentary texts are in the public domain. The Bible text
is the Open Word Bible (CC0); its Greek word data is MACULA Greek (CC BY 4.0)
and its cross-references are from OpenBible.info (CC BY), credited on every
page.
