# How the Matthew commentaries were cut from their sources

The scripts that made `library/comments/<work>/MAT.json` for jfb-matthew,
wesley-matthew and haydock-matthew, kept as a record, like `../romans/`. They
use the helpers in `../romans/` (`fetch_ccel.py` saved the CCEL pages,
`ccelparas.py` reads them, `chunk.py` packs entries) and are run from the
repository root. They are not part of the site build or CI. Each work's
`notes` in `library/works/` describes in words what its script does.

- `build_jfb.py`: Brown's notes by their verse numbers and the section
  summaries and headings that name verses; his notes on Luke inside Matthew
  are left out.
- `build_wesley.py`: one excerpt per verse note, whole.
- `build_haydock.py`: one excerpt per `Ver.` note, up to about 350 words; the
  garbled Greek it leaves out is listed in `GREEK`.

The Haydock source was saved with the same steps as `../romans/fetch_scan.py`
(the full text of the `/stream/` view, Matthew with a 2,000-character margin),
by hand, because that transcription's file name is not `<id>_djvu.txt`.
