# How the Romans commentaries were cut from their sources

These are the scripts that made `library/comments/<work>/ROM.json` for the six
Romans works (calvin-romans, chrysostom-romans, henry-romans, bengel-romans,
hodge-romans, godet-romans), kept as they were run, as a record of how the
excerpts were made and so that a work can be cut again. They are not part of
the site build or CI, and they are not linted (`pyproject.toml` excludes this
folder): they were written for one session's machine, and the paths in them
(`/home/user/logia`, a scratch folder under `/tmp/claude-0/...`) must be
changed before they are run again. Each work's `notes` in `library/works/`
describes in words what its script does.

## Shared helpers

- `fetch_ccel.py` saves a CCEL page's book-content block under `sources/<work>/`
  and adds its row to `sources/manifest.json`; `fetch_scan.py` does the same
  for an archive.org OCR text (the `/stream/` view, as served).
- `ccelparas.py` reads a CCEL page's paragraphs (footnotes skipped, as
  `scripts/verify_sources.py` does), with the `Commentary` mark each is under.
- `scanclean.py` turns OCR text into paragraphs: running heads and page
  numbers dropped, hyphenated line ends joined, footnotes left out.
- `garble.py` finds OCR noise that was Greek, using a vocabulary built from
  the CCEL pages in `sources/` (so its results drift a little as the library
  grows: re-cutting Hodge today changes a few early entries).
- `chunk.py` packs a unit's paragraphs into entries of at most about 350 words,
  cutting long paragraphs at sentence ends with ' ... ', and numbers the ids.

## One script per work

- `build_calvin.py`: one entry per lemma, placed by Calvin's verse numbers and
  CCEL's `Commentary` marks; the doxology comment is its own unit on 16:25-27.
- `build_chrys.py` with `chrys_cut.py`: each homily's verse marks; the closing
  exhortation is cut at the first sentence after the last mark that exhorts
  the hearers.
- `build_henry.py`: each point on the verse it names, or its section.
- `build_hodge.py`: the Commentary section of each chapter, by Hodge's verse marks.
- `bengel/`: run `clean.py OUT1`, `verses.py OUT1 OUT2`, `lemmas.py OUT2 OUT3`,
  `build.py OUT3`. `greek.py` and `vocab.py` need a plain English word list
  (`web2.txt`, from the `english-words` package on PyPI), not committed here.
- `godet/`: `build.py` (with `marks.py`, `clean.py`, `greek.py`, its own
  `chunk.py` and the hand-set verse numbers in `override.json`); `greek.py`
  needs the same kind of word list (`words.txt`).

## Changes made by hand after a script ran

Published excerpts never change id, so these are not in the scripts:

- bengel-romans: the note on 16:25 is its own entry (`bengel-romans.ROM.16.25.1`);
  the script would join it to the published 16:23-24 entry.
- hodge-romans and godet-romans: footnotes the OCR ran into excerpts at a
  page turn were cut out afterwards, by exact start and end, and each cut
  marked ' ... ' (see the commit "Hodge and Godet on Romans: footnotes the OCR
  ran into the text are cut out").
- The 16:25-27 entries of every work were added after the Open Word Bible had
  the verses, by re-running each script and keeping only the new entries.
