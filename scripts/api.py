"""Logia's public, read-only API: static JSON written into site/api/v1/.

    python3 scripts/build_site.py      # writes the API with the site

Called by build_site.build() with the loaded library. Everything here is
data the site already shows, in a stable shape for other programs: the
commentators, the works with their edition, rights and scan corrections,
every excerpt (as the site shows it, corrections applied) on every verse,
the Scripture it cites, the topics, the whole homilies and tractates, and
the Open Word Bible's English text of every chapter, so one chapter file is
enough to show a verse with what the church has said about it.
docs/api.md describes every file. The shape only changes in a new version
(/api/v2/); fields may be added within a version, never removed or renamed.

Logia's data is CC0. The Bible text is the Open Word Bible (CC0). The Greek
and Hebrew word data (MACULA, CC BY) and the cross-references (OpenBible.info,
CC BY) are not in the API.
"""
import json
import os

VERSION = 1
DOCS = "https://github.com/jdegreef/logia/blob/main/docs/api.md"
WORK_FIELDS = ("title", "author", "divisions", "original_language", "edition", "translation", "published",
               "full_text_url", "source_kind", "rights", "status")


def _dump(site, rel, data):
    path = os.path.join(site, "api", f"v{VERSION}", rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def write(lib, site, site_url, h):
    """Write the API. h holds the build's helpers: ref_parts, chapter_url,
    verse_url, chapter_plain, locus_label, topics, topic_span, t. Returns
    the counts in index.json."""
    base = f"{site_url}/api/v{VERSION}"

    def page(path):
        return site_url + path

    def author(a):
        return {"id": a["id"], "name": a["name"], "dates": a["dates"], "died": a["died"], "era": a["era"],
                "tradition": a["tradition"], "bio": a["bio"], "bio_status": a["bio_status"],
                "url": page(f"/commentators/{a['id']}/")}

    def excerpt(c):
        b, ch, _v = h.ref_parts(c["start"])
        w = lib.works[c["work"]]
        return {"id": c["id"], "work": c["work"], "author": w["author"],
                "author_name": lib.author_of(c["work"])["name"], "title": w["title"],
                "start": c["start"], "end": c["end"], "heading": c["heading"], "locus": c.get("locus"),
                "place": h.locus_label(w, c["locus"]) if c.get("locus") else None,
                "text": c["text"], "source": c["source_url"], "scan": c.get("scan"), "status": w["status"],
                "cites": [{k: x[k] for k in ("at", "text", "start", "end", "found", "status")} for x in c["cites"]],
                "url": page(h.chapter_url(b, ch) + f"#v{h.ref_parts(c['start'])[2]}-{c['work']}")}

    topics = h.topics(lib)
    topics_on = {}
    for tp in topics:
        for item in tp["items"]:
            book, (sc, sv), (ec, ev) = h.topic_span(item)
            topics_on.setdefault(book, []).append(((sc, sv), (ec, ev), tp["id"]))

    for b, ch in lib.chapters:
        text = h.chapter_plain(b, ch)
        verses_n = sorted(text)
        if not verses_n:
            continue
        cited = lib.cited_by(b, ch, verses_n)
        on = {}
        for c in lib.comments_in(b, ch):
            _b, sc, sv = h.ref_parts(c["start"])
            _b, ec, ev = h.ref_parts(c["end"])
            for v in verses_n:
                if (sc, sv) <= (ch, v) <= (ec, ev):
                    on.setdefault(v, []).append(c["id"])
        ids, verses = [], []
        for v in verses_n:
            here = on.get(v, [])
            ids += [x for x in here if x not in ids]
            tps = list(dict.fromkeys(tid for lo, hi, tid in topics_on.get(b, []) if lo <= (ch, v) <= hi))
            where = h.verse_url(b, ch, v) if (b, ch, v) in lib.voices_on else h.chapter_url(b, ch) + f"#v{v}"
            verses.append({"verse": v, "ref": f"{b}.{ch}.{v}", "text": text[v], "excerpts": here,
                           "cited_by": [r["id"] for r in cited.get(str(v), [])], "topics": tps, "url": page(where)})
        _dump(site, f"chapters/{b}.{ch}.json", {
            "book": b, "chapter": ch, "name": f"{lib.books[b]['en']} {ch}", "url": page(h.chapter_url(b, ch)),
            "bible": {"text": "Open Word Bible", "level": "Balanced", "licence": "CC0 1.0",
                      "url": f"https://openwordbible.org{h.chapter_url(b, ch)}"},
            "verses": verses, "excerpts": {x: excerpt(lib.by_id[x]) for x in ids}})

    works = []
    for wid in lib.ordered_works():
        w = lib.works[wid]
        mine = sorted((c for c in lib.comments if c["work"] == wid), key=lambda c: (h.ref_parts(c["start"]), c["id"]))
        texts = lib.texts.get(wid, [])
        works.append({"id": wid, **{k: w.get(k) for k in WORK_FIELDS}, "excerpts": len(mine),
                      "url": page(f"/works/{wid}/"), "api": f"{base}/works/{wid}.json"})
        _dump(site, f"works/{wid}.json", {
            **works[-1], "author": author(lib.author_of(wid)),
            "corrections": [{"from": a, "to": z} for a, z in lib.fixes.get(wid, [])],
            "excerpts": [{"id": c["id"], "start": c["start"], "end": c["end"], "locus": c.get("locus"),
                          "chapter": f"{base}/chapters/{h.ref_parts(c['start'])[0]}.{h.ref_parts(c['start'])[1]}.json"}
                         for c in mine],
            "texts": [{"locus": x["locus"], "title": x["title"], "verses": x["verses"],
                       "url": page(f"/works/{wid}/{x['locus']}/"), "api": f"{base}/texts/{wid}/{x['locus']}.json"}
                      for x in texts]})
        for x in texts:
            _dump(site, f"texts/{wid}/{x['locus']}.json", {**x, "url": page(f"/works/{wid}/{x['locus']}/")})
    _dump(site, "works.json", works)
    _dump(site, "authors.json", [author(a) for a in lib.ordered_authors()])

    rows = []
    for tp in topics:
        key = f"topics.{tp['id']}"
        rows.append({"id": tp["id"], "heading": h.t(key + ".heading"), "dek": h.t(key + ".dek"),
                     "passages": [{"start": x["start"], "end": x["end"]} for x in tp["items"]],
                     "url": page(f"/topics/{tp['id']}/"), "api": f"{base}/topics/{tp['id']}.json"})
        _dump(site, f"topics/{tp['id']}.json", rows[-1])
    _dump(site, "topics.json", rows)

    counts = {"authors": len(lib.authors), "works": len(lib.works), "excerpts": len(lib.comments),
              "chapters": len(lib.chapters), "topics": len(rows),
              "texts": sum(len(ts) for ts in lib.texts.values())}
    _dump(site, "index.json", {
        "name": "Logia", "api_version": VERSION, "site": site_url, "docs": DOCS,
        "licence": "Logia's data: CC0 1.0. Commentary texts: public domain. Bible text: Open Word Bible, CC0 1.0.",
        "counts": counts,
        "endpoints": {
            "authors": f"{base}/authors.json", "works": f"{base}/works.json", "work": f"{base}/works/{{work}}.json",
            "chapter": f"{base}/chapters/{{BOOK}}.{{chapter}}.json", "topics": f"{base}/topics.json",
            "topic": f"{base}/topics/{{topic}}.json", "text": f"{base}/texts/{{work}}/{{n}}.json"}})
    return counts
