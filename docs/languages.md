# Logia in other languages: addresses and search engines

Logia is English first (CLAUDE.md, "Languages"). This note fixes where the
other languages will live, so that the first translation does not have to
decide it and nothing built for English has to move.

## Addresses

- Each language has its own folder under the root, named by its code:
  `/es/rom/8/28/`, `/fr/commentators/calvin/`. English stays at the root
  (`/rom/8/28/`), so no English address changes.
- A language is never chosen by a query string, a cookie or the browser's
  language: search engines index one page per address, so each language needs
  its own address. A reader can switch language with a link; nothing
  redirects them.
- The same path follows the language code: `/es/` + the English path. Book
  codes, commentator ids and work ids are the same in every language.

## Search engines

- Each page names its versions in other languages with
  `<link rel="alternate" hreflang>`, its own included, and English as
  `x-default`. `page()` in `scripts/build_site.py` writes these from its
  `alternates` argument ({language: path}); no page passes one yet.
- Each language has its own sitemap (`sitemap-es.xml`, or one per book as
  English has), listed in `sitemap.xml`.
- `<html lang>` and the JSON-LD `inLanguage` are the page's language.
- A translation of an excerpt ships as `ai_draft` until a native-speaking
  reviewer approves it. Until then its page is built for readers but marked
  `noindex` (and so left out of the sitemaps, as `indexed()` already does for
  every noindex page), so an unreviewed translation is never what a search
  engine shows. Interface text alone (`i18n/<lang>.json`) does not hold a
  page back.
