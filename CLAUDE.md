# Logia — conventions for Claude

Logia (logia.faith) is a free, open library of public-domain Christian
commentary tied verse by verse to Scripture, in the spirit of Sefaria. It is a
separate site from openwordbible.org: the Open Word Bible is only its Bible
text. README.md describes the data layout; docs/adding-a-work.md is the
procedure for a new commentary.

## Rules that are easy to break

- **Never write commentary text.** An excerpt is copied from its source,
  exactly, and its source text is saved under `sources/` and listed in
  `sources/manifest.json`. Fetch with curl and extract with a script; never
  paraphrase, summarise, modernise or fill a gap from memory.
  `scripts/verify_sources.py` must pass.
- **Only public-domain editions.** Text and translation published in 1930 or
  earlier (US); record the edition, translator and year in the work's
  `rights`, and what is still to confirm for worldwide use. Use scans and open
  transcriptions (CCEL, archive.org, Project Gutenberg). Don't copy from sites
  that claim rights in their typed editions (BibleHub, StudyLight,
  newadvent.org).
- **Never type Greek or Hebrew.** Original-language words in an excerpt are
  copied from the source as it reads. Where a scan turns Greek into noise,
  leave the Greek out (mark a broken sentence with " ... ") rather than retype
  it. `validate.py` refuses a correction that adds Greek or Hebrew.
- **Scan fixes are data, not edits.** Excerpts keep the scan's text; a
  misreading is fixed by a pair in `library/corrections/<work>.json`, applied
  in order at build time. Fix only what the printed page plainly says ("Let
  ns" → "Let us"); leave anything uncertain alone.
- **Nothing is marked reviewed by Claude.** Works and translations stay
  `ai_draft` until a named human reviewer approves them.
- **The Bible text is imported, never edited.** `bible/owb/` comes from
  `scripts/import_owb.py` at the commit pinned in `bible/owb/SOURCE.json`.
  A wording problem belongs in the open-word-bible repository.
- **Present the traditions fairly.** Keep a commentator's words whole, even
  when they are harsh or dated; a context note may explain, nothing is cut
  silently. Logia takes no side where Catholic, Orthodox and Protestant
  readings differ.
- Don't use or redistribute MACULA's `ln` / `domain` fields; the import
  leaves them out.

## The site

- **Look like openwordbible.org.** `web/style.css`, `web/fonts/` and the
  menus in `web/site.js` are the Open Word Bible's; don't restyle them here.
  Logia's own styles go in `web/logia.css` with `lg-` / `cx-` class names
  (style.css styles many plain names such as `.verse`, `.card`, `.panel`).
- **Every interface word goes in `i18n/en.json`**, read through `t()` in
  `scripts/build_site.py` (and the chapter data's `ui` for `web/reader.js`),
  so a language is a new catalog, not a code change.
- **Accounts are shared with openwordbible.org.** Don't build a separate
  sign-in for Logia.

## Languages

English first. Interface text and translations of excerpts will be added per
language (`library/translations/<lang>/`); a translation is made from the best
public-domain source (the Greek, Latin or German original where the English
is weak), ships as `ai_draft`, and is approved by a native-speaking reviewer.

## Before pushing

    python3 scripts/validate.py
    python3 scripts/verify_sources.py
    python3 -m unittest discover -s tests -t .
    python3 scripts/build_site.py
    uvx ruff@0.16.9 check .
    node --check web/site.js && node --check web/reader.js && node --check web/account.js
