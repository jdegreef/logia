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
| `library/authors/<author>.json` | One commentator: dates, era, tradition, a short biography (a draft until reviewed) |
| `library/works/<work>.json` | One commentary: its author, edition, translator, rights, status |
| `library/comments/<work>/<BOOK>.json` | Its excerpts on one book, each tied to a verse range (`JHN.1.6`–`JHN.1.8`) |
| `library/corrections/<work>.json` | Scan misreadings fixed at build time (scanned sources only) |
| `library/translations/<lang>/<work>/<BOOK>.json` | Translations of excerpts, once they start (see `library/translations/README.md`) |
| `sources/` | The source text each excerpt was copied from, and `manifest.json` listing where each came from |
| `bible/owb/` | The Bible text: Open Word Bible chapters, imported at a pinned commit |
| `i18n/en.json` | Every word of the interface, so a language can be added by adding a catalog |
| `web/` | The stylesheets, scripts and fonts the pages use (see "The site" below) |
| `scripts/` | Import, validate, verify and build |
| `docs/` | How to add a work, and the editorial rules |

The library today: the whole Gospel of John in the Open Word Bible text, and
John 1:1–18 with eight commentaries (Chrysostom,
Augustine, the Catena Aurea, Calvin, Matthew Henry, Bengel, J. C. Ryle and
Westcott), 246 excerpts in all.

## The site

`scripts/build_site.py` writes a static site to `site/`:

| Path | Page |
|---|---|
| `/` | Home |
| `/read/` | Every book; the ones in Logia with a pill per chapter, gold where there is commentary |
| `/<book>/` | A book's chapters and who comments on it |
| `/<book>/<chapter>/` | The reader: the Open Word Bible text, and the panel of commentary, Greek words, translation notes and cross-references for the chosen verse |
| `/commentators/`, `/commentators/<author>/` | Every commentator by era; one commentator's biography, works and comments |
| `/works/<work>/` | One commentary: edition, rights, source, and every excerpt front to back |
| `/about/` | What Logia is and how excerpts are checked |

It looks and works like [openwordbible.org](https://openwordbible.org), its
sister site: `web/style.css` and `web/fonts/` are the Open Word Bible's own
(copied from its repository at the pinned commit; refresh them together with
the Bible text), and `web/site.js` is taken from its site script: the header's
menus and the settings menu (theme, text size, typeface, line spacing, motion,
and Logia's own: the translation level and how much of each excerpt to show).
`web/logia.css` and `web/reader.js` are Logia's own.

Accounts (sign-in, saving, likes) will be shared with openwordbible.org: one
account for both sites.

## How the text stays honest

- **Excerpts are copied, never written.** Each is the source's own words,
  and `scripts/verify_sources.py` checks every one against the source text in
  `sources/`. A digital transcription must hold the excerpt word for word; a
  page scan, whose lines carry margin notes and running heads, is checked in
  runs of six words.
- **Scan misreadings are corrected in the open.** An excerpt keeps the scan's
  text; `library/corrections/` lists each fix ("Let ns" → "Let us"), and the
  build applies them.
- **Rights are recorded per work**: the edition, the translator, the year,
  and what is still to confirm for worldwide use.
- **Nothing is marked reviewed by an AI.** Works and translations stay
  `ai_draft` until a named human reviewer approves them.

## Commands

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
