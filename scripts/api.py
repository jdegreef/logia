"""Logia's public, read-only API: static JSON written into site/api/v1/.

    python3 scripts/build_site.py      # writes the API with the site

Called by build_site.build() with the loaded library. Everything here is
data the site already shows, in a stable shape for other programs: authors,
works and their versions, every excerpt (as the reader shows it, with scan
corrections applied) on every verse, citations, topics and whole texts, and
the Open Word Bible's English text of every chapter, so a chapter file is
enough to show a verse with what the church has said about it.
docs/api.md describes every file. The shape only changes in a new version
(/api/v2/); fields may be added within a version, never removed or renamed.

Logia's data is CC0. The Bible text is the Open Word Bible (CC0). The Greek
and Hebrew word data (MACULA, CC BY) and the cross-references (OpenBible.info,
CC BY) are not in the API.
"""
import json
import os

import scripture

VERSION = 1


def _dump(site, rel, data):
    path = os.path.join(site, "api", f"v{VERSION}", rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def write(lib, site, site_url, h):
    """Write the API. h holds the build's helpers: ref_parts, chapter_url,
    default_wording, locus_label."""
    base = f"{site_url}/api/v{VERSION}"
    page = lambda path: site_url + path            # noqa: E731

    def author(a):
        return {"id": a["id"], "name": a["name"], "dates": a["dates"], "died": a["died"], "era": a["era"],
                "tradition": a["tradition"], "family": a["family"], "bio": a["bio"], "bio_status": a["bio_status"],
                "url": page(f"/commentators/{a['id']}/")}

    def excerpt(c):
        b, ch, v = h.ref_parts(c["start"])
        w = lib.works[c["work"]]
        return {"id": c["id"], "work": c["work"], "author": w["author"],
                "author_name": lib.author_of(c["work"])["name"],
                "title": w["title"], "version": lib.edition(c["work"])["id"],
                "start": c["start"], "end": c["end"], "heading": c["heading"], "locus": c.get("locus"),
                "place": h.locus_label(w, c["locus"]) if c.get("locus") else None,
                "text": c["text"], "corrections": [{"from": a, "to": z} for a, z in c["fixed"]],
                "source": c["source_url"], "status": w["status"],
                "cites": [{k: x[k] for k in ("at", "text", "start", "end", "found", "status")} for x in c["cites"]],
                "url": page(h.chapter_url(b, ch) + "#" + c["id"])}

    # Which excerpts are on, and which cite, each verse.
    on, cited = {}, {}
    for c in lib.comments:
        b, ch, v = h.ref_parts(c["start"])
        eb, ech, ev = h.ref_parts(c["end"])
        for chap in range(ch, ech + 1):
            for verse in range(v if chap == ch else 1, (ev if chap == ech else 200) + 1):
                on.setdefault((b, chap, verse), []).append(c["id"])
        for x in c["cites"]:
            sb, sc, sv = scripture.parse(scripture.to_source(x["start"]))      # citations are English-numbered
            _, ec, evv = scripture.parse(scripture.to_source(x["end"]))
            for chap in range(sc, ec + 1):
                for verse in range(sv if chap == sc else 1, (evv if chap == ec else 200) + 1):
                    if c["id"] not in on.get((sb, chap, verse), []):
                        cited.setdefault((sb, chap, verse), [])
                        if c["id"] not in cited[(sb, chap, verse)]:
                            cited[(sb, chap, verse)].append(c["id"])
    topics_on = {}
    for tp in lib.topics:
        for ref in tp["verses"]:
            topics_on.setdefault(scripture.parse(ref), []).append(tp["id"])
    by_id = {c["id"]: c for c in lib.comments}

    for b, ch in lib.chapters:
        bible = lib.bible(b, ch)
        text = {}
        for r in bible["records"]:
            for p in r["pieces"]:
                text[p[0]] = text.get(p[0], "") + h.default_wording(p[1])
        verses, ids = [], []
        for v in bible["verses"]:
            here = on.get((b, ch, v), [])
            ids += [x for x in here if x not in ids]
            verses.append({"verse": v, "ref": f"{b}.{ch}.{v}", "text": " ".join(text.get(v, "").split()),
                           "excerpts": here, "cited_by": cited.get((b, ch, v), []),
                           "topics": topics_on.get((b, ch, v), []),
                           "url": page(h.chapter_url(b, ch) + f"#v{v}")})
        _dump(site, f"chapters/{b}.{ch}.json", {
            "book": b, "chapter": ch, "name": f"{lib.books[b]['en']} {ch}", "url": page(h.chapter_url(b, ch)),
            "bible": {"text": "Open Word Bible", "level": "Balanced", "licence": "CC0 1.0",
                      "url": f"https://openwordbible.org{h.chapter_url(b, ch)}"},
            "verses": verses, "excerpts": {x: excerpt(by_id[x]) for x in ids}})

    works = []
    for wid in lib.ordered_works():
        w = lib.works[wid]
        versions = lib.versions_of(wid)
        mine = sorted((c for c in lib.comments if c["work"] == wid), key=lambda c: (h.ref_parts(c["start"]), c["id"]))
        texts = lib.texts.get(wid, [])
        works.append({"id": wid, "title": w["title"], "author": w["author"], "genre": w["genre"],
                      "divisions": w["divisions"], "original_language": w["original_language"], "status": w["status"],
                      "versions": [v["id"] for v in versions], "excerpts": len(mine),
                      "url": page(f"/works/{wid}/"), "api": f"{base}/works/{wid}.json"})
        _dump(site, f"works/{wid}.json", {
            **works[-1], "author": author(lib.author_of(wid)), "versions": versions,
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

    topics = []
    for tp in lib.topics:
        members = lib.topic_members(tp)
        topics.append({k: tp[k] for k in ("id", "title", "note", "verses", "terms", "status")}
                      | {"excerpts": len(members), "url": page(f"/topics/{tp['id']}/"),
                         "api": f"{base}/topics/{tp['id']}.json"})
        _dump(site, f"topics/{tp['id']}.json", {**topics[-1], "excerpts": [
            {"id": c["id"], "why": why, "start": c["start"]} for c, why in members]})
    _dump(site, "topics.json", topics)

    counts = {"authors": len(lib.authors), "works": len(lib.works), "versions": len(lib.versions),
              "excerpts": len(lib.comments), "chapters": len(lib.chapters), "topics": len(lib.topics),
              "texts": sum(len(ts) for ts in lib.texts.values())}
    _dump(site, "index.json", {
        "name": "Logia", "api_version": VERSION, "site": site_url,
        "docs": "https://github.com/jdegreef/logia/blob/main/docs/api.md",
        "licence": "Logia's data: CC0 1.0. Commentary texts: public domain. Bible text: Open Word Bible, CC0 1.0.",
        "counts": counts,
        "endpoints": {
            "authors": f"{base}/authors.json", "works": f"{base}/works.json", "work": f"{base}/works/{{work}}.json",
            "chapter": f"{base}/chapters/{{BOOK}}.{{chapter}}.json", "topics": f"{base}/topics.json",
            "topic": f"{base}/topics/{{topic}}.json", "text": f"{base}/texts/{{work}}/{{n}}.json",
            "search": f"{site_url}/data/search.json"}})
    return counts
