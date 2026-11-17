"""Draw the link-preview picture (og:image, 1200 x 630) for each commentator,
book, topic and creed, in web/cards/, from the library's own records: names,
dates, traditions and titles, never a line of commentary. The build copies
web/cards/ to the site and points each page's og:image at its card
(card_for in scripts/build_site.py); a page without one keeps web/card.png.

    python3 scripts/make_cards.py           # every card
    python3 scripts/make_cards.py --check   # fail if a card is missing

Needs Pillow (pip install pillow), which the site's build does not: the
cards are made here and committed. Run it again after adding a commentator,
a book, a topic or a creed.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_site as B  # noqa: E402

OUT = os.path.join(ROOT, "web", "cards")
FONTS = os.path.join(ROOT, "web", "fonts")
W, H = 1200, 630
INK, MUTED = (33, 29, 24), (110, 103, 94)


def font(name, size, weight=None):
    f = ImageFont.truetype(os.path.join(FONTS, name), size)
    if weight:
        try:
            f.set_variation_by_axes([weight])
        except (OSError, ValueError):
            pass
    return f


def wrap(draw, text, f, width, lines):
    """text in at most lines lines of width, the last cut with … if it must be."""
    words, out, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=f) <= width:
            cur = trial
        else:
            out.append(cur)
            cur = w
    out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        while draw.textlength(out[-1] + "…", font=f) > width:
            out[-1] = out[-1].rsplit(" ", 1)[0]
        out[-1] += "…"
    return out


def card(path, eyebrow, title, sub):
    base = Image.open(os.path.join(ROOT, "web", "card.png")).convert("RGB")
    paper, gold = base.getpixel((10, 10)), base.getpixel((600, H - 4))   # web/card.png's own colours
    img = Image.new("RGB", (W, H), paper)
    logo = base.crop((80, 68, 300, 140))
    img.paste(logo, (80, 68))
    d = ImageDraw.Draw(img)
    d.text((84, 190), eyebrow.upper(), font=font("hanken-grotesk-latin-wght-normal.woff2", 26, 600), fill=gold)
    size = 76
    while True:
        tf = font("fraunces-latin-wght-normal.woff2", size, 600)
        lines = wrap(d, title, tf, W - 168, 3)
        if len(lines) <= 2 or size <= 56:
            break
        size -= 6
    y = 240
    for line in lines:
        d.text((84, y), line, font=tf, fill=INK)
        y += int(size * 1.18)
    sf = font("hanken-grotesk-latin-wght-normal.woff2", 30, 400)
    for line in wrap(d, sub, sf, W - 168, 2):
        y += 8
        d.text((84, y + 16), line, font=sf, fill=MUTED)
        y += 40
    d.rectangle((0, H - 14, W, H), fill=gold)
    img.save(path, optimize=True)


def cards(lib):
    """{file name: (eyebrow, title, line)} for every card."""
    out = {}
    for a in lib.ordered_authors():
        out[f"commentator-{a['id']}.png"] = (B.t("cards.commentator", era=B.t("eras." + a["era"])), a["name"],
                                             f'{a["dates"]} · {a["tradition"]}')
    for b in dict.fromkeys(bk for bk, _c in lib.chapters):
        out[f"book-{b.lower()}.png"] = (B.t("cards.book"), lib.books[b]["en"], B.t("cards.book_line"))
    for tp in B.topics(lib):
        key = f"topics.{tp['id']}"
        out[f"topic-{tp['id']}.png"] = (B.t("cards.topic"), B.t(key + ".heading"), B.t(key + ".dek"))
    for c in lib.creeds:
        out[f"creed-{c['id']}.png"] = (B.t("cards.creed"), c["title"], B.creed_when(c))
    return out


def main(argv):
    lib = B.Library()
    want = cards(lib)
    if "--check" in argv:
        missing = [n for n in want if not os.path.exists(os.path.join(OUT, n))]
        if missing:
            print(f"{len(missing)} cards missing (python3 scripts/make_cards.py): {', '.join(missing[:8])}")
            return 1
        print(f"{len(want)} cards")
        return 0
    os.makedirs(OUT, exist_ok=True)
    for name, (eyebrow, title, line) in want.items():
        card(os.path.join(OUT, name), eyebrow, title, line)
    print(f"{len(want)} cards in web/cards/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
