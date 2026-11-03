# Translations of excerpts

None yet: Logia starts in English. When a language starts, its translations go
here, one file per work and book:

    library/translations/<lang>/<work>/<BOOK>.json

```json
{"language": "es", "work": "calvin", "book": "JHN",
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
