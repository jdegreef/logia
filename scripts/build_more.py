"""More of Logia's pages and data, built by scripts/build_site.py's build():

- reading plans: Advent, a book in so many days, and their calendar feeds
  (/plans/, /advent/, /<book>/plan/, *.ics);
- a feed for each commentator and each book (/feeds/);
- each work's Scripture index and scan corrections, and its review progress
  (/works/<work>/scripture/, /works/<work>/corrections/);
- who made the English (/translators/);
- how to help, with live counts (/about/help/), and the citation review tool
  (/review/citations/, its data under /review/data/);
- the most-cited verses (/explore/most-cited/) and a random excerpt (/random/);
- the parish widget (/widget/, /widget.js, /widget/sundays.json);
- the pieces build_site.py prints on verse and work pages: the verse grid,
  excerpts that cite the same verses, corrections applied, the scan page.

Every word on these pages comes from i18n/<lang>.json through t(); every
excerpt, date and count from the library. Nothing here writes commentary.
The functions take build_site as B (set by setup), so the two files share
one set of helpers without importing each other at load time.
"""
import datetime
import json
import os
import re
from collections import Counter

B = None

# Advent's plan runs from 1 December to Christmas Eve, as Advent calendars
# do, whatever day Advent's first Sunday falls on.
ADVENT_YEAR = 2026


def setup(module):
    global B
    B = module


def t(key, **values):
    return B.t(key, **values)


def e(text):
    return B.e(text)


def plans_data():
    return B.load(os.path.join(B.ROOT, "library", "plans.json"))


# --- Reading plans --------------------------------------------------------------

def span_of(ref):
    """'LUK.1.5-LUK.1.17' -> (book, (1, 5), (1, 17))."""
    lo, _, hi = ref.partition("-")
    b, c, v = B.ref_parts(lo)
    _b, ec, ev = B.ref_parts(hi or lo)
    return b, (c, v), (ec, ev)


def passage_href(lib, book, start, end):
    """A passage's page where it has one, else its first verse's page, else the chapter."""
    url = B.passage_url(book, start, end)
    if any(B.passage_url(book, s, x) == url for _h, s, x, _v in B.passages_with_commentary(lib, book)):
        return url
    if (book, *start) in lib.voices_on:
        return B.verse_url(book, *start)
    return f"{B.chapter_url(book, start[0])}#v{start[1]}"


def passage_label(lib, book, start, end):
    name = lib.books[book]["en"]
    if start == end:
        return f"{name} {start[0]}:{start[1]}"
    return B.passage_ref(lib, book, start, end)


def advent_days(lib, year=ADVENT_YEAR):
    """[(date, book, start, end, excerpts)] for 1 to 24 December."""
    out = []
    for i, ref in enumerate(plans_data()["advent"]["readings"]):
        book, start, end = span_of(ref)
        n = sum(len(cs) for _w, cs in B.in_passage(lib, book, start, end))
        out.append((datetime.date(year, 12, 1 + i), book, start, end, n))
    return out


def date_label(d):
    return t("plan.date", weekday=t("plan.weekdays")[d.weekday()], day=d.day, month=t("plan.months")[d.month - 1], year=d.year)


def advent_page(lib):
    days = advent_days(lib)
    rows = []
    for i, (d, book, start, end, n) in enumerate(days, 1):
        badge = f' <span class="lg-badge">{e(t("plans.christmas_eve"))}</span>' if (d.month, d.day) == (12, 24) else ""
        rows.append(f'<li><p class="lg-plan-day"><b>{e(t("plan.day", n=i))}</b> <span class="lg-quiet">{e(date_label(d))}</span>{badge}</p>'
                    f'<p><a href="{e(passage_href(lib, book, start, end))}">{e(passage_label(lib, book, start, end))}</a> '
                    f'<span class="lg-quiet">{e(t("passage.n_excerpts", n=n))}</span></p></li>')
    body = f"""
<article class="lg-verse lg-plan">
<header class="page-head"><p class="eyebrow"><a href="/plans/">{e(t("plans.eyebrow"))}</a> · <a href="/readings/">{e(t("occasions.eyebrow"))}</a></p>
<h1>{e(t("plans.advent_heading"))}</h1><p class="dek">{e(t("plans.advent_dek", year=ADVENT_YEAR))}</p>
{calendar_link("/advent.ics")}</header>
<ol class="lg-plan-days">{"".join(rows)}</ol>
<p class="lg-quiet">{e(t("plans.advent_note"))} <a href="{e(t("occasions.christmas.path"))}">{e(t("plans.christmas_link"))}</a></p>
</article>"""
    return B.page(lib, t("plans.advent_heading"), body, "/advent/", current="/read/",
                  head_title=t("plans.advent_title", year=ADVENT_YEAR) + " · Logia",
                  description=t("plans.advent_description", year=ADVENT_YEAR),
                  ld=(B.breadcrumbs((t("plans.eyebrow"), "/plans/"), (t("plans.advent_heading"), "/advent/")),))


def book_plan_days(lib, book, n_days):
    """A book's chapters shared out over n_days in order, about the same
    number of verses each day, never splitting a chapter."""
    chapters = list(range(1, lib.books[book]["chapters"] + 1))
    sizes = [len(B.chapter_verses(book, c)) for c in chapters]
    total, days, run, done = sum(sizes), [], [], 0
    for i, (c, size) in enumerate(zip(chapters, sizes)):
        run.append(c)
        done += size
        left, to_fill = len(chapters) - i - 1, n_days - len(days) - 1
        if to_fill and left >= to_fill and (done >= total * (len(days) + 1) / n_days or left == to_fill):
            days.append(run)
            run = []
    return days + [run] if run else days


def book_plans(lib):
    """[(book, days)] for the plans in library/plans.json whose book has commentary."""
    cov = {b for b, _c in lib.coverage()}
    return [(p["book"], p["days"]) for p in plans_data()["books"] if p["book"] in cov]


def plan_url(book):
    return f"/{book.lower()}/plan/"


def book_plan_page(lib, book, n_days):
    name = lib.books[book]["en"]
    days = book_plan_days(lib, book, n_days)
    rows = []
    for i, chs in enumerate(days, 1):
        n = sum(len(lib.comments_in(book, c)) for c in chs)
        links = " · ".join(f'<a href="{B.chapter_url(book, c)}">{e(name)} {c}</a>' for c in chs)
        rows.append(f'<li><p class="lg-plan-day"><b>{e(t("plan.day", n=i))}</b> <span class="lg-quiet">{e(t("passage.n_excerpts", n=n))}</span></p>'
                    f'<p>{links}</p></li>')
    heading = t("plans.book_heading", book=name, n=len(days))
    body = f"""
<article class="lg-verse lg-plan">
<header class="page-head"><p class="eyebrow"><a href="/plans/">{e(t("plans.eyebrow"))}</a> · <a href="/{book.lower()}/">{e(name)}</a></p>
<h1>{e(heading)}</h1><p class="dek">{e(t("plans.book_dek", book=name, n=len(days), chapters=lib.books[book]["chapters"]))}</p></header>
<ol class="lg-plan-days">{"".join(rows)}</ol>
<p class="lg-quiet">{e(t("plans.book_note"))}</p>
</article>"""
    return B.page(lib, heading, body, plan_url(book), current="/read/", description=t("plans.book_description", book=name, n=len(days)),
                  ld=(B.breadcrumbs((t("plans.eyebrow"), "/plans/"), (heading, plan_url(book))),))


def lent_books(lib):
    return list(dict.fromkeys(b for b, _c, _v in lib.voices_on))


def calendar_link(href):
    return (f'<p class="lg-cal-feed"><a href="{href}" download>{B.icon("star", 15)} {e(t("plans.calendar"))}</a> '
            f'<span class="lg-quiet">{e(t("plans.calendar_note"))}</span></p>')


def plans_page(lib):
    advent = (f'<li><a href="/advent/"><b>{e(t("plans.advent_heading"))}</b> <span>{e(t("plans.advent_row"))}</span></a>'
              f'<span class="lg-quiet"><a href="/advent.ics">{e(t("plans.calendar_short"))}</a></span></li>')
    lent = "".join(f'<li><a href="/{b.lower()}/lent/"><b>{e(t("plan.heading", book=lib.books[b]["en"], n=40))}</b> '
                   f'<span>{e(t("plans.lent_row", year=B.LENT_YEAR))}</span></a>'
                   f'<span class="lg-quiet"><a href="/{b.lower()}/lent.ics">{e(t("plans.calendar_short"))}</a></span></li>'
                   for b in lent_books(lib) if b == "JHN")
    books = "".join(f'<li><a href="{plan_url(b)}"><b>{e(t("plans.book_heading", book=lib.books[b]["en"], n=len(book_plan_days(lib, b, n))))}</b> '
                    f'<span>{e(t("plans.book_row", chapters=lib.books[b]["chapters"]))}</span></a></li>' for b, n in book_plans(lib))
    body = f"""
<header class="page-head"><p class="eyebrow">{e(t("occasions.eyebrow"))}</p>
<h1>{e(t("plans.heading"))}</h1><p class="dek">{e(t("plans.dek"))}</p></header>
<section class="lg-block"><h2>{e(t("plans.seasons"))}</h2><ul class="lg-people lg-wide">{advent}{lent}</ul></section>
<section class="lg-block"><h2>{e(t("plans.books"))}</h2><ul class="lg-people lg-wide">{books}</ul></section>
<section class="lg-block"><h2>{e(t("plans.sundays"))}</h2><p>{e(t("plans.sundays_note"))}</p>{calendar_link("/readings/sundays.ics")}</section>"""
    return B.page(lib, t("plans.heading"), body, "/plans/", current="/read/", description=t("plans.description"),
                  ld=(B.breadcrumbs((t("plans.heading"), "/plans/")),))


# --- Calendar feeds (.ics) ---------------------------------------------------------

def ics_text(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_fold(line):
    """RFC 5545 lines: at most 75 octets, continued with a space."""
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode("utf-8")) > 74:
            out.append(cur)
            cur = " " + ch
        else:
            cur += ch
    return "\r\n".join(out + [cur])


def ics(name, events):
    """A calendar of all-day events: (date, uid, summary, url, description)."""
    stamp = "20260101T000000Z"
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Logia//logia.faith//EN", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:{ics_text(name)}"]
    for day, uid, summary, url, description in events:
        nxt = day + datetime.timedelta(days=1)
        lines += ["BEGIN:VEVENT", f"UID:{uid}@logia.faith", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{nxt:%Y%m%d}",
                  f"SUMMARY:{ics_text(summary)}", f"URL:{url}", f"DESCRIPTION:{ics_text(description + chr(10) + url)}",
                  "TRANSP:TRANSPARENT", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(x) for x in lines) + "\r\n"


def advent_ics(lib):
    events = []
    for i, (d, book, start, end, n) in enumerate(advent_days(lib), 1):
        label = passage_label(lib, book, start, end)
        events.append((d, f"advent-{d:%Y%m%d}", t("plans.ics_day", plan=t("plans.advent_short"), n=i, ref=label),
                       B.SITE_URL + passage_href(lib, book, start, end), t("passage.n_excerpts", n=n)))
    return ics(t("plans.advent_heading"), events)


def lent_ics(lib, book):
    name = lib.books[book]["en"]
    dates = B.lent_days(B.LENT_YEAR)
    days = B.plan_days(lib, book, len(dates))
    events = []
    for i, (d, secs) in enumerate(zip(dates, days), 1):
        refs = "; ".join(B.passage_ref(lib, book, s, x) for _h, s, x in secs)
        _h, s, x = secs[0]
        events.append((d, f"lent-{book.lower()}-{d:%Y%m%d}", t("plans.ics_day", plan=t("plans.lent_short", book=name), n=i, ref=refs),
                       B.SITE_URL + passage_href(lib, book, s, x), " · ".join(h for h, _s, _x in secs)))
    return ics(t("plan.heading", book=name, n=len(dates)), events)


def sundays_ics(lib):
    data = B.sundays()
    if not data:
        return None
    events = []
    for d in data["days"]:
        gospel = d["readings"]["gospel"]
        got = B.parse_reading(gospel[0]) if gospel else None
        url = B.SITE_URL + "/readings/"
        if got and (got[0], got[1][0]) in lib.coverage():
            url = B.SITE_URL + passage_href(lib, *got)
        others = "; ".join(dict.fromkeys(d["readings"]["epistle"] + d["readings"]["first_and_psalm"]))
        events.append((datetime.date.fromisoformat(d["date"]), f"rcl-{d['date']}", f'{d["name"]}: {" · ".join(gospel) or "–"}', url,
                       t("plans.ics_sunday", others=others)))
    return ics(t("sundays.heading"), events)


# --- A feed for each commentator and each book ------------------------------------

def atom(lib, title, self_path, home_path, works):
    added = B.works_added()
    items = sorted(((added[w], w) for w in works if w in added), reverse=True)
    updated = items[0][0] if items else datetime.date.today().isoformat()
    count = Counter(c["work"] for c in lib.comments if c["work"] in works)
    entries = "".join(
        f"""<entry><title>{e(lib.author_of(w)["name"])}: {e(t("about.recent_row", title=lib.works[w]["title"], year=lib.works[w]["published"]))}</title>
<link href="{B.SITE_URL}/works/{w}/"/><id>{B.SITE_URL}/works/{w}/</id><updated>{day}T00:00:00Z</updated>
<summary>{e(t("new.row_note", books=B.name_list(B.work_books(lib, w)), n=f"{count[w]:,}"))}</summary></entry>
""" for day, w in items)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="{B.LANG}">
<title>{e(title)}</title>
<link href="{B.SITE_URL}{self_path}" rel="self"/><link href="{B.SITE_URL}{home_path}"/><id>{B.SITE_URL}{self_path}</id>
<updated>{updated}T00:00:00Z</updated><author><name>Logia</name></author>
{entries}</feed>
"""


def feeds(lib):
    """{path: Atom text} for each commentator and each book with commentary."""
    out = {}
    for a in lib.ordered_authors():
        works = [w for w in lib.works if lib.works[w]["author"] == a["id"]]
        out[f'/feeds/{a["id"]}.xml'] = atom(lib, t("feeds.author_title", name=a["name"]), f'/feeds/{a["id"]}.xml', f'/commentators/{a["id"]}/', works)
    books = {}
    for c in lib.comments:
        books.setdefault(B.ref_parts(c["start"])[0], set()).add(c["work"])
    for b in lib.books:
        if b in books:
            out[f"/feeds/{b.lower()}.xml"] = atom(lib, t("feeds.book_title", book=lib.books[b]["en"]), f"/feeds/{b.lower()}.xml", f"/{b.lower()}/", books[b])
    return out


def feeds_page(lib):
    people = "".join(f'<li><a href="/feeds/{a["id"]}.xml"><b>{e(a["name"])}</b> <span>{e(a["dates"])}</span></a></li>'
                     for a in lib.ordered_authors())
    books = "".join(f'<li><a href="/feeds/{b.lower()}.xml"><b>{e(lib.books[b]["en"])}</b></a></li>'
                    for b in lib.books if any(x == b for x, _c in lib.coverage()))
    body = f"""
<header class="page-head"><p class="eyebrow"><a href="/new/">{e(t("new.title"))}</a></p>
<h1>{e(t("feeds.heading"))}</h1><p class="dek">{e(t("feeds.dek"))}</p></header>
<p><a href="/new.xml">{e(t("feeds.all"))}</a></p>
<section class="lg-block"><h2>{e(t("feeds.by_book"))}</h2><ul class="lg-people">{books}</ul></section>
<section class="lg-block"><h2>{e(t("feeds.by_author"))}</h2><ul class="lg-people lg-wide">{people}</ul></section>"""
    return B.page(lib, t("feeds.heading"), body, "/feeds/", current="/about/", description=t("feeds.dek"),
                  ld=(B.breadcrumbs((t("new.title"), "/new/"), (t("feeds.heading"), "/feeds/")),))


# --- Each work's Scripture index, corrections and review progress -------------

def work_citations(wid):
    out = []
    for path in sorted(B.glob.glob(os.path.join(B.ROOT, "library", "citations", wid, "*.json"))):
        out.extend(B.load(path)["citations"])
    return out


def scripture_index_page(lib, wid):
    """Every verse a work cites, by book and chapter, as the index at the back of a printed volume."""
    w, a = lib.works[wid], lib.author_of(wid)
    cites = [x for x in work_citations(wid) if x["status"] != "rejected" and x["start"].split(".")[0] in lib.books]
    order = list(lib.books)
    by_ref = {}
    for x in cites:
        by_ref.setdefault((x["start"], x["end"]), []).append(x)

    def key(se):
        bk, c, v = B.ref_parts(se[0])
        return order.index(bk), c, v, se[1]
    groups, current = [], None
    rows = []
    for se in sorted(by_ref, key=key):
        bk = se[0].split(".")[0]
        if bk != current:
            if rows:
                groups.append((current, rows))
            current, rows = bk, []
        places = []
        for x in by_ref[se]:
            c = lib.by_id.get(x["in"])
            if c:
                places.append(f'<a href="{e(B.excerpt_href(lib, c))}">{e(B.scripture.label(c["start"], c["end"]))}</a>')
        label = B.scripture.label(*se)
        href = lib.verse_link(se[0])
        name = f'<a href="{e(href)}">{e(label)}</a>' if href else e(label)
        rows.append(f'<li><b>{name}</b> <span class="lg-quiet">{e(t("scripture_index.in"))}</span> {", ".join(dict.fromkeys(places))}</li>')
    if rows:
        groups.append((current, rows))
    jump = " · ".join(f'<a href="#b-{bk.lower()}">{e(lib.books[bk]["en"])}</a>' for bk, _r in groups)
    body = "".join(f'<section class="lg-block" id="b-{bk.lower()}"><h2>{e(lib.books[bk]["en"])}</h2>'
                   f'<ul class="lg-scripture-index">{"".join(r)}</ul></section>' for bk, r in groups)
    html_body = f"""
<header class="page-head"><p class="eyebrow"><a href="/commentators/{a["id"]}/">{e(a["name"])}</a> · <a href="/works/{wid}/">{e(w["title"])}</a></p>
<h1>{e(t("scripture_index.heading"))}</h1><p class="dek">{e(t("scripture_index.dek", n=f"{len(cites):,}", verses=f"{len(by_ref):,}", title=w["title"]))}</p>
<p class="lg-quiet">{e(t("scripture_index.note"))}</p><p class="lg-index-jump">{jump}</p></header>
{body or f'<p class="lg-quiet">{e(t("scripture_index.none"))}</p>'}"""
    path = f"/works/{wid}/scripture/"
    return B.page(lib, f'{t("scripture_index.heading")}: {a["name"]}, {w["title"]}', html_body, path, current="/commentators/",
                  description=t("scripture_index.description", name=a["name"], title=w["title"], n=f"{len(by_ref):,}"),
                  ld=(B.breadcrumbs((a["name"], f'/commentators/{a["id"]}/'), (w["title"], f"/works/{wid}/"),
                                    (t("scripture_index.heading"), path)),))


def raw_texts(wid):
    """{excerpt id: its text as the source file has it, before corrections}."""
    out = {}
    for path in B.glob.glob(os.path.join(B.ROOT, "library", "comments", wid, "*.json")):
        for x in B.load(path)["entries"]:
            out[x["id"]] = x["text"]
    return out


def corrections_used(lib):
    """{excerpt id: [(from, to)]}: the scan corrections that change each excerpt."""
    out = {}
    for wid, pairs in lib.fixes.items():
        if wid not in lib.works:
            continue
        for cid, text in raw_texts(wid).items():
            for a, b in pairs:
                if a in text:
                    out.setdefault(cid, []).append((a, b))
                    text = text.replace(a, b)
    return out


def corrections_page(lib, wid, used):
    w, a = lib.works[wid], lib.author_of(wid)
    where = {}
    for cid, pairs in used.items():
        if cid.split(".")[0] == wid or lib.by_id.get(cid, {}).get("work") == wid:
            for p in pairs:
                where.setdefault(p, []).append(cid)
    rows = []
    for x in lib.fixes[wid]:
        p = (x[0], x[1])
        ids = where.get(p, [])
        links = ", ".join(f'<a href="{e(B.excerpt_href(lib, lib.by_id[cid]))}">{e(B.scripture.label(lib.by_id[cid]["start"]))}</a>'
                          for cid in ids[:6] if cid in lib.by_id)
        more = f' <span class="lg-quiet">{e(t("corrections.more", n=len(ids) - 6))}</span>' if len(ids) > 6 else ""
        rows.append(f'<tr><td><s>{e(p[0])}</s></td><td aria-hidden="true">→</td><td>{e(p[1])}</td>'
                    f'<td class="lg-quiet">{e(t("corrections.n", n=len(ids)))}</td><td>{links}{more}</td></tr>')
    path = f"/works/{wid}/corrections/"
    body = f"""
<header class="page-head"><p class="eyebrow"><a href="/commentators/{a["id"]}/">{e(a["name"])}</a> · <a href="/works/{wid}/">{e(w["title"])}</a></p>
<h1>{e(t("corrections.heading"))}</h1><p class="dek">{e(t("corrections.dek", n=len(rows), title=w["title"]))}</p>
<p class="lg-quiet">{e(t("corrections.note"))} <a href="{B.GITHUB_URL}/blob/main/library/corrections/{wid}.json" rel="noopener">{e(t("corrections.file"))} ↗</a></p></header>
<div class="lg-table-wrap"><table class="lg-corrections"><thead><tr><th>{e(t("corrections.scan"))}</th><th></th><th>{e(t("corrections.page"))}</th>
<th>{e(t("corrections.excerpts"))}</th><th>{e(t("corrections.where"))}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>"""
    return B.page(lib, f'{t("corrections.heading")}: {w["title"]}', body, path, current="/commentators/",
                  description=t("corrections.description", title=w["title"], n=len(rows)),
                  ld=(B.breadcrumbs((a["name"], f'/commentators/{a["id"]}/'), (w["title"], f"/works/{wid}/"),
                                    (t("corrections.heading"), path)),))


def review_counts(wid):
    """{status: n} for a work's citations."""
    return Counter(x["status"] for x in work_citations(wid))


def work_extras(lib, wid):
    """On a work's page: its Scripture index, its corrections and how far the
    review of its citations has come."""
    n = review_counts(wid)
    total = sum(n.values())
    links = []
    if total:
        links.append(f'<a href="/works/{wid}/scripture/">{e(t("scripture_index.heading"))}</a>')
    if lib.fixes.get(wid):
        links.append(f'<a href="/works/{wid}/corrections/">{e(t("corrections.link", n=len(lib.fixes[wid])))}</a>')
    meter = ""
    if total:
        done = n.get("reviewed", 0) + n.get("rejected", 0)
        pct = done / total * 100
        meter = (f'<p class="lg-review-meter"><span class="lg-meter" role="img" aria-label="{e(t("review.meter_label", done=f"{done:,}", n=f"{total:,}"))}">'
                 f'<span style="width:{max(pct, .5):.1f}%"></span></span> {e(t("review.meter", done=f"{done:,}", n=f"{total:,}"))} '
                 f'<a href="/review/citations/?work={wid}">{e(t("review.help_link"))}</a></p>')
    if not links and not meter:
        return ""
    return (f'<section class="lg-block" id="checking"><h2>{e(t("review.work_heading"))}</h2>'
            f'<p>{" · ".join(links)}</p>{meter}</section>')


# --- Who made the English (/translators/) --------------------------------------

SERIES = (("npnf", ("Nicene and Post-Nicene",)), ("anf", ("Ante-Nicene",)), ("lf", ("Library of the Fathers", "Oxford translation")),
          ("cts", ("Calvin Translation Society",)), ("clark", ("T. & T. Clark", "T&T Clark", "Clark")))


def series_of(text):
    for key, names in SERIES:
        if any(n in text for n in names):
            return key
    return "other"


def translators_page(lib):
    groups = {}
    for wid in lib.ordered_works():
        w = lib.works[wid]
        if w.get("translation") and w.get("original_language", "").lower() != "english":
            groups.setdefault(series_of(w["translation"]), []).append(wid)
    sections = []
    for key in [k for k, _n in SERIES] + ["other"]:
        if key not in groups:
            continue
        rows = "".join(f'<li><p><a href="/works/{wid}/"><b>{e(lib.author_of(wid)["name"])}</b>, <i>{e(lib.works[wid]["title"])}</i></a> '
                       f'<span class="lg-quiet">({e(lib.works[wid]["original_language"])})</span></p>'
                       f'<p class="lg-quiet">{e(lib.works[wid]["translation"])}</p></li>' for wid in groups[key])
        sections.append(f'<section class="lg-block"><h2>{e(t("translators.series." + key))}</h2><ul class="lg-translators">{rows}</ul></section>')
    n = sum(len(v) for v in groups.values())
    body = f"""
<header class="page-head"><p class="eyebrow"><a href="/about/">{e(t("about.title"))}</a></p>
<h1>{e(t("translators.heading"))}</h1><p class="dek">{e(t("translators.dek", n=n))}</p></header>
{"".join(sections)}
<p class="lg-quiet">{e(t("translators.note"))}</p>"""
    return B.page(lib, t("translators.heading"), body, "/translators/", current="/about/", description=t("translators.description"),
                  ld=(B.breadcrumbs((t("about.title"), "/about/"), (t("translators.heading"), "/translators/")),))


# --- How to help, and the citation review tool ---------------------------------

def all_citation_counts():
    n = Counter()
    for path in B.glob.glob(os.path.join(B.ROOT, "library", "citations", "*", "*.json")):
        n.update(x["status"] for x in B.load(path)["citations"])
    return n


def other_counts(folder, key):
    n = Counter()
    for path in B.glob.glob(os.path.join(B.ROOT, "library", folder, "*", "*.json")):
        n.update(x["status"] for x in B.load(path)[key])
    return n


def help_page(lib):
    cites = all_citation_counts()
    quotes = other_counts("quotations", "quotations")
    names = other_counts("mentions", "mentions")
    drafts = sum(1 for w in lib.works.values() if w.get("status") == "ai_draft")
    tasks = [
        ("cite", cites.get("detected", 0), "/review/citations/"),
        ("quote", quotes.get("detected", 0), B.GITHUB_URL + "/blob/main/docs/references.md"),
        ("name", names.get("detected", 0), B.GITHUB_URL + "/blob/main/docs/references.md"),
        ("work", drafts, "/about/rules/"),
        ("misreading", sum(len(v) for v in lib.fixes.values()), B.GITHUB_URL + "/issues/new?template=misreading.yml"),
        ("edition", len(lib.works), B.GITHUB_URL + "/issues/new?template=commentary.yml"),
        ("translate", 0, B.GITHUB_URL + "/issues/new?template=translation.yml"),
    ]
    rows = "".join(f'<li><a href="{e(href)}"{" rel=noopener" if href.startswith("http") else ""}><b>{e(t("help.tasks." + k + ".title"))}</b>'
                   f'<span>{e(t("help.tasks." + k + ".text", n=f"{n:,}"))}</span></a></li>' for k, n, href in tasks)
    body = f"""
<header class="page-head"><p class="eyebrow"><a href="/about/">{e(t("about.title"))}</a></p>
<h1>{e(t("help.heading"))}</h1><p class="dek">{e(t("help.dek"))}</p></header>
<ul class="lg-ab-tiles lg-ab-help lg-help-tasks">{rows}</ul>
<p class="lg-quiet">{e(t("help.note"))}</p>"""
    return B.page(lib, t("help.heading"), body, "/about/help/", current="/about/", description=t("help.description"),
                  ld=(B.breadcrumbs((t("about.title"), "/about/"), (t("help.heading"), "/about/help/")),))


def review_data(lib):
    """{(work, book): [[excerpt, at, printed, start, end, before, after, verse text]]}
    for every citation still "detected"."""
    out = {}
    plain = {}
    for path in sorted(B.glob.glob(os.path.join(B.ROOT, "library", "citations", "*", "*.json"))):
        data = B.load(path)
        rows = []
        for x in data["citations"]:
            if x["status"] != "detected":
                continue
            c = lib.by_id.get(x["in"])
            if not c:
                continue
            at, n = x["at"], len(x["text"])
            before = c["text"][max(0, at - 160):at].split("\n")[-1]
            after = c["text"][at + n:at + n + 80].split("\n")[0]
            bk, ch, v = B.ref_parts(x["start"])
            _b, ech, ev = B.ref_parts(x["end"])
            words = ""
            if bk in lib.books and B.scripture.CHAPTERS.get(bk, 0) >= ch:
                key = (bk, ch)
                if key not in plain:
                    try:
                        plain[key] = B.chapter_plain(bk, ch)
                    except OSError:
                        plain[key] = {}
                last = ev if ech == ch else max(plain[key], default=v)
                words = " ".join(plain[key].get(i, "") for i in range(v, min(last, v + 2) + 1)).strip()
            rows.append([x["in"], at, x["text"], x["start"], x["end"], before, after, words])
        if rows:
            out[(data["work"], data["book"])] = rows
    return out


def review_page(lib, data):
    works = {}
    for (wid, book), rows in data.items():
        works.setdefault(wid, []).append([book, lib.books[book]["en"] if book in lib.books else book, len(rows)])
    index = [{"w": wid, "a": lib.author_of(wid)["name"], "t": lib.works[wid]["title"], "b": bs}
             for wid in lib.ordered_works() if wid in works for bs in [works[wid]]]
    ui = json.dumps({**B.CATALOG["review"]["ui"], "github": B.GITHUB_URL}, ensure_ascii=False).replace("</", "<\\/")
    names = {code: x["en"] for code, x in lib.books.items()}
    left = sum(len(r) for r in data.values())
    body = f"""
<header class="page-head"><p class="eyebrow"><a href="/about/help/">{e(t("help.heading"))}</a></p>
<h1>{e(t("review.heading"))}</h1><p class="dek">{e(t("review.dek", n=f"{left:,}"))}</p></header>
<div class="lg-review" id="review-app" data-index="{e(json.dumps(index, ensure_ascii=False))}" data-books="{e(json.dumps(names, ensure_ascii=False))}">
<noscript><p>{e(t("review.noscript"))}</p></noscript></div>
<section class="lg-block"><h2>{e(t("review.how_heading"))}</h2>{"".join(f"<p>{e(p)}</p>" for p in t("review.how"))}</section>
<script type="application/json" id="review-text">{ui}</script>"""
    return B.page(lib, t("review.heading"), body, "/review/citations/", current="/about/", description=t("review.description"),
                  scripts=("review.js",), noindex=True)


# --- The most-cited verses, and a random excerpt -------------------------------------

def most_cited(lib, top=60):
    """[(verse, n, works)] most cited from outside the verse's own book."""
    n, works = Counter(), {}
    for path in B.glob.glob(os.path.join(B.ROOT, "library", "citations", "*", "*.json")):
        data = B.load(path)
        for x in data["citations"]:
            if x["status"] == "rejected" or x["start"] != x["end"] or x["start"].split(".")[0] == data["book"]:
                continue
            if x["start"].split(".")[0] not in lib.books:
                continue
            n[x["start"]] += 1
            works.setdefault(x["start"], set()).add(lib.works[data["work"]]["author"])
    return [(r, k, len(works[r])) for r, k in sorted(n.items(), key=lambda kv: (-kv[1], kv[0]))[:top]]


def most_cited_page(lib):
    rows = most_cited(lib)
    peak = rows[0][1] if rows else 1
    items = []
    for ref, n, k in rows:
        bk, ch, v = B.ref_parts(ref)
        href = lib.verse_link(ref) or f"{B.OWB_SITE}{B.chapter_url(bk, ch)}#v{v}"
        try:
            words = B.snippet(B.chapter_plain(bk, ch).get(v, ""), 14)
        except OSError:
            words = ""
        items.append(f'<li><a href="{e(href)}"><span class="lg-bar-label"><b>{e(B.scripture.label(ref))}</b></span>'
                     f'<span class="lg-bar"><span style="width:{n / peak * 100:.1f}%"></span></span>'
                     f'<span class="lg-bar-n">{n}</span></a><p class="lg-quiet">{e(t("most_cited.row", k=k))} · {e(words)}</p></li>')
    body = f"""
<header class="page-head"><p class="eyebrow"><a href="/explore/">{e(t("nav.explore"))}</a></p>
<h1>{e(t("most_cited.heading"))}</h1><p class="dek">{e(t("most_cited.dek"))}</p>
<p class="lg-quiet">{e(t("most_cited.note"))}</p></header>
<ol class="lg-xbars lg-most-cited">{"".join(items)}</ol>"""
    return B.page(lib, t("most_cited.heading"), body, "/explore/most-cited/", current="/explore/", description=t("most_cited.description"),
                  ld=(B.breadcrumbs((t("nav.explore"), "/explore/"), (t("most_cited.heading"), "/explore/most-cited/")),))


def random_json(lib):
    """{"jhn/1": [verses with a page]} for /random/ to choose from."""
    out = {}
    for b, c, v in sorted(lib.voices_on):
        out.setdefault(f"{b.lower()}/{c}", []).append(v)
    return json.dumps(out, separators=(",", ":"))


def random_page(lib):
    body = f"""
<header class="page-head"><p class="eyebrow"><a href="/explore/">{e(t("nav.explore"))}</a></p>
<h1>{e(t("random.heading"))}</h1><p class="dek" id="random-status">{e(t("random.dek"))}</p></header>
<p><a class="button" id="random-go" href="/jhn/1/1/">{e(t("random.again"))}</a></p>
<noscript><p>{e(t("random.noscript"))}</p></noscript>"""
    return B.page(lib, t("random.heading"), body, "/random/", current="/explore/", description=t("random.description"), noindex=True)


def quiz_page(lib):
    eras = [[x, t("eras." + x)] for x in B.ERAS if any(a["era"] == x for a in lib.authors.values())]
    ui = {**B.CATALOG["quiz"]["ui"], "eras": eras}
    chapters = [f"{bk}.{ch}" for bk, ch in sorted(lib.coverage())]
    body = f"""
<header class="page-head"><p class="eyebrow"><a href="/explore/">{e(t("nav.explore"))}</a></p>
<h1>{e(t("quiz.heading"))}</h1><p class="dek">{e(t("quiz.dek"))}</p></header>
<div class="lg-quiz" id="quiz-app" data-ui="{e(json.dumps(ui, ensure_ascii=False))}" data-chapters="{e(json.dumps(chapters))}">
<noscript><p>{e(t("quiz.noscript"))}</p></noscript></div>"""
    return B.page(lib, t("quiz.heading"), body, "/quiz/", current="/explore/", description=t("quiz.description"),
                  ld=(B.breadcrumbs((t("nav.explore"), "/explore/"), (t("quiz.heading"), "/quiz/")),))


# --- The parish widget ------------------------------------------------------------

WIDGET_VOICES = 3


def widget_sundays(lib, today=None):
    """The Sundays from a week ago on, each with its Gospel, a link and up to
    three opening lines from different traditions."""
    data = B.sundays()
    if not data:
        return []
    since = ((today or datetime.date.today()) - datetime.timedelta(days=7)).isoformat()
    out = []
    for d in data["days"]:
        if d["date"] < since or not d["readings"]["gospel"]:
            continue
        g = d["readings"]["gospel"][0]
        got = B.parse_reading(g)
        row = {"d": d["date"], "n": d["name"], "g": g, "h": B.SITE_URL + "/readings/", "v": []}
        if got and (got[0], got[1][0]) in lib.coverage():
            book, start, end = got
            row["h"] = B.SITE_URL + passage_href(lib, book, start, end)
            seen = set()
            for wid, cs in B.in_passage(lib, book, start, end):
                a = lib.author_of(wid)
                kind = B.tradition_kind(a)
                if kind in seen or not cs:
                    continue
                seen.add(kind)
                c = cs[0]
                row["v"].append({"a": a["name"], "x": B.opening_words(c, 32), "h": B.SITE_URL + B.excerpt_href(lib, c)})
                if len(row["v"]) == WIDGET_VOICES:
                    break
        out.append(row)
    return out


def widget_page(lib):
    code = f'<div data-logia-sunday></div>\n<script src="{B.SITE_URL}/widget.js" defer></script>'
    body = f"""
<header class="page-head"><p class="eyebrow"><a href="/linker/">{e(t("nav.linker"))}</a></p>
<h1>{e(t("widget.heading"))}</h1><p class="dek">{e(t("widget.dek"))}</p></header>
<section class="lg-block"><h2>{e(t("widget.preview"))}</h2><div data-logia-sunday></div></section>
<section class="lg-block"><h2>{e(t("widget.install"))}</h2><p>{e(t("widget.install_note"))}</p>
<pre class="lg-cite-text lg-cite-code">{e(code)}</pre>
<button type="button" class="button ghost lg-copy" data-copy="{e(code)}" data-done="{e(t("work.cite_copied"))}">{e(t("work.cite_copy_short"))}</button>
{"".join(f"<p>{e(p)}</p>" for p in t("widget.details"))}</section>
<script src="/widget.js" defer></script>"""
    return B.page(lib, t("widget.heading"), body, "/widget/", current="/about/", description=t("widget.description"),
                  ld=(B.breadcrumbs((t("widget.heading"), "/widget/")),))


def widget_js():
    with open(os.path.join(B.WEB, "widget.js"), encoding="utf-8") as f:
        text = f.read()
    ui = json.dumps(B.CATALOG["widget"]["ui"], ensure_ascii=False)
    return text.replace("/*UI*/{}", ui).replace("https://logia.faith", B.SITE_URL)


# --- Pieces of the verse and work pages -----------------------------------------------

GRID_KINDS = ("catholic", "orthodox", "protestant", "shared")


def verse_grid(lib, voices, book, chapter, verse):
    """Every voice on a verse in a table, eras across and traditions down,
    each with its first words; empty cells stay, to show where the library is thin."""
    if len(voices) < 3:
        return ""
    cells = {}
    for wid, cs in voices:
        a = lib.author_of(wid)
        c = next((x for x in cs if B.ref_parts(x["start"])[2] == verse), cs[0])
        cells.setdefault((B.tradition_kind(a), a["era"]), []).append(
            f'<li><a href="#{e(wid)}"><b>{e(B.short_name(a))}</b></a> <span>{e(B.snippet(c["text"], 9))}</span></li>')
    eras = [x for x in B.ERAS if any(k[1] == x for k in cells)]
    kinds = [k for k in GRID_KINDS if any(x[0] == k for x in cells)]
    head = "".join(f"<th scope=col>{e(t('eras.' + x))}</th>" for x in eras)
    rows = "".join(f"<tr><th scope=row>{e(t('kinds.' + k))}</th>"
                   + "".join(f'<td><ul>{"".join(cells[(k, x)])}</ul></td>' if (k, x) in cells else '<td class="lg-grid-empty">–</td>' for x in eras)
                   + "</tr>" for k in kinds)
    return (f'<details class="lg-block lg-vgrid" id="grid"><summary>{e(t("grid.summary", n=len(voices)))}</summary>'
            f'<p class="lg-quiet">{e(t("grid.note"))}</p><div class="lg-table-wrap"><table><thead><tr><td></td>{head}</tr></thead>'
            f'<tbody>{rows}</tbody></table></div></details>')


def also_cites_index(lib):
    """{excerpt id: [other excerpts that cite at least two of the same verses]}, best first, up to three."""
    targets = {}
    for c in lib.comments:
        s = {x["start"] for x in c["cites"]}
        if len(s) >= 2:
            targets[c["id"]] = s
    by_target = {}
    for cid, s in targets.items():
        for r in s:
            by_target.setdefault(r, []).append(cid)
    out = {}
    for cid, s in targets.items():
        shared = Counter()
        for r in s:
            group = by_target[r]
            if len(group) > 400:
                continue        # a verse cited everywhere says little about likeness
            for other in group:
                if other != cid:
                    shared[other] += 1
        mine = lib.by_id[cid]
        best = [o for o, k in sorted(shared.items(), key=lambda kv: (-kv[1], kv[0]))
                if k >= 2 and lib.by_id[o]["start"] != mine["start"]][:3]
        if best:
            out[cid] = best
    return out


def also_rows(lib, c):
    """The <li>s under an excerpt for those that cite the same verses."""
    rows = []
    for oid in getattr(lib, "also_cites", {}).get(c["id"], []):
        o = lib.by_id[oid]
        a = lib.author_of(o["work"])
        rows.append(f'<li><a href="{e(B.excerpt_href(lib, o))}">{e(t("verse.also_cites", name=a["name"], ref=B.scripture.label(o["start"], o["end"])))}</a></li>')
    return rows


def fixed_link(lib, c):
    """"2 scan corrections", linked to the work's list, where any changed this excerpt."""
    n = len(getattr(lib, "fixes_used", {}).get(c["id"], []))
    if not n:
        return ""
    return f'<a href="/works/{c["work"]}/corrections/" title="{e(t("verse.fixed_title"))}">{e(t("verse.fixed", n=n))}</a>'


def scan_button(c):
    """"See the printed page": the scan's page image, which web/study.js loads only when asked."""
    s = c.get("scan")
    if not s or not s.get("img"):
        return ""
    return (f'<button type="button" class="lg-linkish lg-scan-show" data-img="{e(s["img"])}" data-href="{e(s["url"])}" '
            f'data-alt="{e(t("verse.scan_alt", page=s["page"] or "?"))}" data-hide="{e(t("verse.scan_hide"))}" hidden>{e(t("verse.scan_show"))}</button>')


# --- Writing it all ---------------------------------------------------------------------

def build(lib, write, pages):
    """Write every page and file above; add the pages' addresses to pages."""
    def page_at(path, text):
        write(path, text)
        pages.append(path)

    def file_at(path, text):
        """A file by its own name (write() makes any name it doesn't know a folder)."""
        full = os.path.join(B.SITE, path.strip("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="") as f:
            f.write(text)

    page_at("/plans/", plans_page(lib))
    page_at("/advent/", advent_page(lib))
    file_at("/advent.ics", advent_ics(lib))
    for b in lent_books(lib):
        file_at(f"/{b.lower()}/lent.ics", lent_ics(lib, b))
    for b, n in book_plans(lib):
        page_at(plan_url(b), book_plan_page(lib, b, n))
    sun = sundays_ics(lib)
    if sun:
        file_at("/readings/sundays.ics", sun)
    for path, text in feeds(lib).items():
        write(path, text)
    page_at("/feeds/", feeds_page(lib))
    used = lib.fixes_used
    for wid in lib.ordered_works():
        if work_citations(wid):
            page_at(f"/works/{wid}/scripture/", scripture_index_page(lib, wid))
        if lib.fixes.get(wid):
            page_at(f"/works/{wid}/corrections/", corrections_page(lib, wid, used))
    page_at("/translators/", translators_page(lib))
    page_at("/about/help/", help_page(lib))
    data = review_data(lib)
    for (wid, book), rows in data.items():
        write(f"/review/data/{wid}.{book}.json", json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
    write("/review/citations/", review_page(lib, data))
    page_at("/explore/most-cited/", most_cited_page(lib))
    write("/random.json", random_json(lib))
    write("/random/", random_page(lib))
    page_at("/quiz/", quiz_page(lib))
    page_at("/widget/", widget_page(lib))
    write("/widget.js", widget_js())
    write("/widget/sundays.json", json.dumps(widget_sundays(lib), ensure_ascii=False, separators=(",", ":")))


def prepare(lib):
    """What verse and work pages need from here, worked out once before they are built."""
    lib.fixes_used = corrections_used(lib)
    lib.also_cites = also_cites_index(lib)


def sitemaps(lib, pages, rows_for):
    """{file name: sitemap text}: one per book of the Bible with commentary
    (its chapters, verses and passages) and one for everything else, and the
    index that lists them. rows_for(pages) gives the <url> rows."""
    groups = {}
    for p in pages:
        m = re.match(r"/([0-9a-z]{3})/", p)
        key = m[1] if m and m[1].upper() in lib.books else "site"
        groups.setdefault(key, []).append(p)
    out = {}
    for key, ps in groups.items():
        rows = rows_for(ps)
        if rows:                 # a book with no commentary has no page for search engines
            out[f"sitemap-{key}.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                         + rows + "</urlset>\n")
    index = "".join(f"<sitemap><loc>{B.SITE_URL}/{name}</loc></sitemap>\n" for name in sorted(out))
    out["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                          + index + "</sitemapindex>\n")
    return out
