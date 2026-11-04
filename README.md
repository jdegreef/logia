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
| `library/works/<work>.json` | One commentary: its author, title, divisions and original language |
| `library/versions/<work>/<lang>.json` | One version of it: an edition of the original, a printed translation, or Logia's own translation, with its edition, translator, year, source, rights and review status |
| `library/comments/<work>/<BOOK>.json` | Its excerpts on one book, each tied to a verse range (`JHN.1.6`–`JHN.1.8`) and, in a work with its own divisions, to its place in the work (Homily 2, section 8) |
| `library/citations/<work>/<BOOK>.json` | The Scripture each excerpt cites, found by `scripts/find_refs.py` (see `docs/references.md`) |
| `library/quotations/<work>/<BOOK>.json` | The Catena's quotations of the Fathers, traced to the passages of their works in the library |
| `library/topics/<id>.json` | A topic: its title, note, the verses at its centre and the terms that gather excerpts (docs/references.md) |
| `library/texts/<work>/<n>.json` | Whole homilies and tractates, copied paragraph by paragraph from their CCEL pages by `scripts/extract_texts.py` |
| `library/corrections/<work>.json` | Scan misreadings fixed at build time (scanned sources only) |
| `library/translations/<lang>/<work>/<BOOK>.json` | Translations of excerpts, once they start (see `library/translations/README.md`) |
| `sources/` | The source text each excerpt was copied from, and `manifest.json` listing where each came from |
| `bible/owb/` | The Bible text: Open Word Bible chapters, imported at a pinned commit |
| `i18n/en.json` | Every word of the interface, so a language can be added by adding a catalog |
| `web/` | The stylesheets, scripts and fonts the pages use (see "The site" below) |
| `scripts/` | Import, validate, verify and build |
| `docs/` | How to add a work, the editorial rules, the reference scheme (`references.md`), the roadmap (`roadmap.md`), and how the site is deployed |

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
| `/<book>/<chapter>/` | The reader: the Open Word Bible text, and the panel of commentary, Greek words, translation notes and cross-references for the chosen verse. `#calvin.JHN.1.1.1` opens one excerpt; each has Cite, How this was copied and Report a mistake |
| `/commentators/`, `/commentators/<author>/` | Every commentator by era; one commentator's biography, works and comments |
| `/works/<work>/` | One commentary: edition, rights, source, and every excerpt front to back |
| `/works/<work>/<n>/` | A whole homily or tractate, read straight through, marking the passages Logia sets beside a verse |
| `/library/` | The catalogue: every work by genre and era, what it covers, its versions, and what is still to come |
| `/search/` | Search every excerpt and whole text, narrowed by kind, era, tradition and commentator (`web/search.js` over `/data/search.json`) |
| `/topics/`, `/topics/<id>/` | Topics: the excerpts a topic's verses and terms gather, from every tradition |
| `/about/` | What Logia is and how excerpts are checked |

It looks and works like [openwordbible.org](https://openwordbible.org), its
sister site: `web/style.css` and `web/fonts/` are the Open Word Bible's own
(copied from its repository at the pinned commit; refresh them together with
the Bible text), and `web/site.js` is taken from its site script: the header's
menus and the settings menu (theme, text size, typeface, line spacing, motion,
and Logia's own: the translation level and how much of each excerpt to show).
`web/logia.css` and `web/reader.js` are Logia's own.

### Accounts, saving, liking and sharing

Logia has no sign-in of its own: readers use their Open Word Bible account.

1. "Sign in" goes to `openwordbible.org/handoff/?site=logia&to=<page>`, which
   signs the reader in there (email, password, Google or passkey) and asks
   them to continue to Logia.
2. Open Word Bible sends them back to `/signed-in/#code=…&to=…` with a
   single-use code that lasts five minutes; `web/account.js` trades it for an
   API token of Logia's own and keeps it in `localStorage`.
3. Likes and saves are kept by Open Word Bible's API against the same
   account (`backend/logia/` in the open-word-bible repository):
   `/api/logia/me`, `/api/logia/saved/<key>`, `/api/logia/likes/<key>`, and
   the public like counts at `/api/logia/likes?chapter=JHN.1`. A comment's key
   is `<work>.<BOOK>.<chapter>.<verse>`, for example `calvin.JHN.1.14`.
4. Sharing needs no account: a card's link (`/jhn/1/#v14-calvin`) opens the
   verse at that comment, through the device's share sheet or copied.

`/saved/` lists a reader's saved comments, with their text from the chapter
data files the build writes to `/data/<BOOK>.<chapter>.json`. A local build
can point at a local API and site with `LOGIA_API_URL` and `LOGIA_OWB_URL`.

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
  reads where each excerpt sits in its work, the Scripture it cites and, in
  the Catena, which Father's passage it quotes; each stays `detected` until
  a person checks it.
- **Rights are recorded per version**: the edition, the translator, the
  year, and what is still to confirm for worldwide use.
- **Nothing is marked reviewed by an AI.** Works and translations stay
  `ai_draft` until a named human reviewer approves them.

## Commands

    python3 scripts/find_refs.py --check      # loci, citations, quotations up to date
    python3 scripts/extract_texts.py --check  # whole texts up to date
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
