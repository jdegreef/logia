"""Scripture references: book codes, the names commentators use, and limits.

A Logia reference is BOOK.chapter.verse with a USFM book code (JHN.1.14),
as in bible/owb. The 66 books, their English names and chapter counts come
from the Open Word Bible (bible/owb/books.en.json, bible/owb/chapters.json).
The deuterocanonical books, which the Catholic and Orthodox churches read as
Scripture and the Fathers quote as such, are not in the Open Word Bible: they
are listed here so that a citation of them is kept like any other.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OWB = os.path.join(ROOT, "bible", "owb")

DEUTEROCANON = {
    "TOB": ("Tobit", 14), "JDT": ("Judith", 16), "WIS": ("Wisdom", 19), "SIR": ("Sirach", 51),
    "BAR": ("Baruch", 6), "1MA": ("1 Maccabees", 16), "2MA": ("2 Maccabees", 15),
}

# Old Testament chapter counts follow the Hebrew text (Open Word Bible);
# English Bibles, which the commentators cite, divide these books otherwise.
ENGLISH_CHAPTERS = {"MAL": 4}

# CCEL marks each Scripture reference in its transcriptions with
# goBible(testament, book, chapter, verse, chapter, verse); its book names:
CCEL_BOOKS = {
    "Gen": "GEN", "Exod": "EXO", "Lev": "LEV", "Num": "NUM", "Deut": "DEU", "Josh": "JOS", "Judg": "JDG",
    "Ruth": "RUT", "iSam": "1SA", "iiSam": "2SA", "iKgs": "1KI", "iiKgs": "2KI", "iChr": "1CH", "iiChr": "2CH",
    "Ezra": "EZR", "Neh": "NEH", "Esth": "EST", "Job": "JOB", "Ps": "PSA", "Prov": "PRO", "Eccl": "ECC",
    "Song": "SNG", "Isa": "ISA", "Jer": "JER", "Lam": "LAM", "Ezek": "EZK", "Dan": "DAN", "Hos": "HOS",
    "Joel": "JOL", "Amos": "AMO", "Obad": "OBA", "Jonah": "JON", "Mic": "MIC", "Nah": "NAM", "Hab": "HAB",
    "Zeph": "ZEP", "Hag": "HAG", "Zech": "ZEC", "Mal": "MAL", "Matt": "MAT", "Mark": "MRK", "Luke": "LUK",
    "John": "JHN", "Acts": "ACT", "Rom": "ROM", "iCor": "1CO", "iiCor": "2CO", "Gal": "GAL", "Eph": "EPH",
    "Phil": "PHP", "Col": "COL", "iThess": "1TH", "iiThess": "2TH", "iTim": "1TI", "iiTim": "2TI",
    "Titus": "TIT", "Phlm": "PHM", "Heb": "HEB", "Jas": "JAS", "iPet": "1PE", "iiPet": "2PE", "iJohn": "1JN",
    "iiJohn": "2JN", "iiiJohn": "3JN", "Jude": "JUD", "Rev": "REV",
    "Tob": "TOB", "Jdt": "JDT", "Wis": "WIS", "Sir": "SIR", "Bar": "BAR", "iMacc": "1MA", "iiMacc": "2MA",
}

# The names and abbreviations 19th-century English commentaries print, for
# books with one name. Numbered books (1 Cor.) are in NUMBERED.
NAMES = {
    "GEN": "Gen Genesis", "EXO": "Ex Exod Exodus", "LEV": "Lev Levit Leviticus", "NUM": "Num Numb Numbers",
    "DEU": "Deut Deuteronomy", "JOS": "Josh Joshua", "JDG": "Judg Judges", "RUT": "Ruth", "EZR": "Ezra",
    "NEH": "Neh Nehemiah", "EST": "Esth Esther", "JOB": "Job", "PSA": "Ps Psa Psal Psalm Psalms",
    "PRO": "Prov Proverbs", "ECC": "Eccl Eccles Ecclesiastes", "SNG": "Cant Canticles", "ISA": "Isa Isai Isaiah",
    "JER": "Jer Jerem Jeremiah", "LAM": "Lam Lamentations", "EZK": "Ezek Ezekiel", "DAN": "Dan Daniel",
    "HOS": "Hos Hosea", "JOL": "Joel", "AMO": "Amos", "OBA": "Obad Obadiah", "JON": "Jonah", "MIC": "Mic Micah",
    "NAM": "Nah Nahum", "HAB": "Hab Habakkuk", "ZEP": "Zeph Zephaniah", "HAG": "Hag Haggai",
    "ZEC": "Zech Zechariah", "MAL": "Mal Malachi", "MAT": "Matt Matthew", "MRK": "Mark", "LUK": "Luke",
    "JHN": "John", "ACT": "Acts", "ROM": "Rom Romans", "GAL": "Gal Galatians", "EPH": "Eph Ephes Ephesians",
    "PHP": "Phil Philip Philippians", "COL": "Col Coloss Colossians", "TIT": "Tit Titus",
    "PHM": "Philem Philemon", "HEB": "Heb Hebrews", "JAS": "Jas James", "JUD": "Jude",
    "REV": "Rev Revelation Apoc Apocalypse",
}
NUMBERED = {
    "Sam Samuel": ("1SA", "2SA"), "Kings Kgs": ("1KI", "2KI"), "Chron Chr Chronicles": ("1CH", "2CH"),
    "Cor Corinthians": ("1CO", "2CO"), "Thess Thessalonians": ("1TH", "2TH"), "Tim Timothy": ("1TI", "2TI"),
    "Pet Peter": ("1PE", "2PE"), "John": ("1JN", "2JN", "3JN"),
}


def _load(name):
    with open(os.path.join(OWB, name), encoding="utf-8") as f:
        return json.load(f)


BOOK_NAMES = {**_load("books.en.json"), **{k: v[0] for k, v in DEUTEROCANON.items()}}
CHAPTERS = {**_load("chapters.json"), **{k: v[1] for k, v in DEUTEROCANON.items()}, **ENGLISH_CHAPTERS}
REF = re.compile(r"^([1-3]?[A-Z]{2,3})\.(\d+)\.(\d+)$")


def parse(ref):
    """'JHN.1.14' -> ('JHN', 1, 14), or None if it is not a reference to a
    chapter that exists."""
    m = REF.match(ref or "")
    if not m or m[1] not in CHAPTERS:
        return None
    book, chapter, verse = m[1], int(m[2]), int(m[3])
    if not (1 <= chapter <= CHAPTERS[book] and 1 <= verse <= 200):
        return None
    return book, chapter, verse


def label(start, end=None):
    """'JHN.1.14', 'JHN.1.18' -> 'John 1:14–18'."""
    b, c, v = parse(start)
    out = f"{BOOK_NAMES[b]} {c}:{v}"
    if end and end != start:
        eb, ec, ev = parse(end)
        out += f"–{ev}" if (eb, ec) == (b, c) else f"–{ec}:{ev}"
    return out


_ROMAN = re.compile(r"^(c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$")
_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}


def roman(s):
    """A lower-case Roman numeral as an int, or None. OCR reads a leading
    'l' as 'I' ('Ixxxix' for 'lxxxix'), so that is tried too."""
    for t in (s.lower(), "l" + s[1:].lower() if s[:1] == "I" else None):
        if t and _ROMAN.match(t):
            total, prev = 0, 0
            for ch in reversed(t):
                n = _VALUES[ch]
                total, prev = (total - n, prev) if n < prev else (total + n, n)
            return total
    return None
