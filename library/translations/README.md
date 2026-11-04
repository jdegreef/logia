# Translations of excerpts

None yet: Logia starts in English. When a language starts, its translations go
here, one file per work and book:

    library/translations/<lang>/<work>/<BOOK>.json

Each is a version of the work, so it first gets a version record,
`library/versions/<work>/<lang>-logia.json` (docs/references.md,
"Versions"): `"kind": "translation"`, `"made_by": "logia"`, `published` and
`source_kind` null, its `rights` (Logia's own work, CC0), and the version's
`status` and `reviewer`. The translation file names it:

```json
{"language": "es", "work": "calvin", "book": "JHN", "version": "calvin.es-logia",
 "entries": [
   {"of": "calvin.JHN.1.1.1", "text": "...", "from_language": "la",
    "status": "ai_draft", "reviewer": null}
 ]}
```

- `of` is the id of the excerpt translated; `validate.py` checks it exists.
- `from_language` is what it was translated from: the edition's English, or
  the original (Greek, Latin, German) where that is the better source.
- `status` is `ai_draft` until a named, native-speaking reviewer approves it;
  only that person sets `reviewed` and their name in `reviewer`.
- Translate the most-read passages first, across several commentators,
  rather than one commentary end to end.
