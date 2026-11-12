"""Find each commentator's Wikidata item and English Wikipedia article, and
each Father's work's item and its number in the Clavis Patrum.

    python3 scripts/fetch_wikidata.py            # the commentators and works not yet in library/identifiers.json
    python3 scripts/fetch_wikidata.py augustine  # just these (author or work ids)

Searches Wikidata for the commentator's name and accepts a match only when
exactly one result is a human (P31 = Q5) whose year of death (P570) is the
year in library/authors/<id>.json. Anything else is reported and left out,
for a person to look up. Writes library/identifiers.json; never guesses.

A work of the early church (era "Early church") is found among the items
whose author (P50) is the commentator's item already found: the one whose
English label shares the most words with the work's title, at least two,
and more than any other. Its number in the Clavis
Patrum Graecorum or Latinorum is read from that item, under the properties
whose English labels say so (looked up by label, not typed); an item with
no number gets none.

Wikimedia limits automated requests: the script waits between them, names
itself in its User-Agent, and stops at the first refusal (HTTP 429) rather
than retry. Run it again later to carry on.
"""
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "library", "identifiers.json")
API = "https://www.wikidata.org/w/api.php"
AGENT = "LogiaBuild/1.0 (https://logia.faith; https://github.com/jdegreef/logia)"
PAUSE = float(os.environ.get("LOGIA_WIKIDATA_PAUSE", "1.5"))   # seconds between requests


class Refused(Exception):
    pass


def get(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json", "maxlag": "5"})
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except urllib.error.HTTPError as err:
        if err.code in (429, 503):
            raise Refused(f"Wikidata refused the request (HTTP {err.code}); try again later") from err
        raise
    time.sleep(PAUSE)
    if "error" in data:
        raise Refused(f"Wikidata: {data['error'].get('info', data['error'])}")
    return data


def death_years(entity):
    """The years of death an item gives (P570), as ints."""
    out = set()
    for claim in entity.get("claims", {}).get("P570", []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        t = value.get("time", "")
        if t:
            sign = -1 if t.startswith("-") else 1
            out.add(sign * int(t.lstrip("+-").split("-")[0]))
    return out


def is_human(entity):
    return any(c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") == "Q5"
               for c in entity.get("claims", {}).get("P31", []))


def pick(author, entities):
    """The one item that is a human who died in the author's year, or None."""
    hits = [x for x in entities if is_human(x) and author["died"] in death_years(x)]
    if len(hits) != 1:
        return None
    x = hits[0]
    article = x.get("sitelinks", {}).get("enwiki", {}).get("title")
    return {"wikidata": x["id"], "wikipedia": article.replace(" ", "_") if article else None}


CLAVIS = {"cpg": "Clavis Patrum Graecorum ID", "cpl": "Clavis Patrum Latinorum ID"}


def claim_ids(entity, prop):
    return [c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            for c in entity.get("claims", {}).get(prop, [])]


def claim_strings(entity, prop):
    out = []
    for c in entity.get("claims", {}).get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, str):
            out.append(v)
    return out


WORDS = re.compile(r"[a-z]+")
COMMON = set("the of on and or to in a st s saint according book gospel".split())


def title_words(text):
    return {w for w in WORDS.findall(text.lower()) if w not in COMMON}


def pick_work(title, author_item, entities, props):
    """Among items whose author (P50) is `author_item`, the one whose English
    label shares the most words with `title`, at least two and more than any
    other; with its Clavis numbers under `props` ({"cpg": "P..."}). Or None."""
    want = title_words(title)
    scored = sorted(((len(want & title_words(x.get("labels", {}).get("en", {}).get("value", ""))), x)
                     for x in entities if author_item in claim_ids(x, "P50")), key=lambda p: -p[0])
    if not scored or scored[0][0] < 2 or (len(scored) > 1 and scored[1][0] == scored[0][0]):
        return None
    x = scored[0][1]
    out = {"wikidata": x["id"], "label": x["labels"]["en"]["value"]}
    for key, prop in props.items():
        numbers = claim_strings(x, prop)
        if len(numbers) == 1:
            out[key] = numbers[0]
    return out


def clavis_properties():
    """{"cpg": property id, "cpl": property id}, found by their exact English labels."""
    out = {}
    for key, label in CLAVIS.items():
        found = get({"action": "wbsearchentities", "search": label, "language": "en", "type": "property", "limit": 5})
        exact = [x["id"] for x in found.get("search", []) if x.get("label") == label]
        if len(exact) == 1:
            out[key] = exact[0]
    return out


def lookup_work(work, author_item, props):
    """The author's works on Wikidata (items with P50 = the author), then pick_work."""
    found = get({"action": "query", "list": "search", "srsearch": f"haswbstatement:P50={author_item}",
                 "srlimit": 50, "srnamespace": 0})
    ids = [x["title"] for x in found.get("query", {}).get("search", [])]
    entities = []
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        data = get({"action": "wbgetentities", "ids": "|".join(batch), "props": "claims|labels", "languages": "en"})
        entities += [data["entities"][x] for x in batch if x in data.get("entities", {})]
    return pick_work(work["title"], author_item, entities, props)


def lookup(author):
    found = get({"action": "wbsearchentities", "search": author["name"], "language": "en", "type": "item", "limit": 7})
    ids = [x["id"] for x in found.get("search", [])]
    if not ids:
        return None
    data = get({"action": "wbgetentities", "ids": "|".join(ids), "props": "claims|sitelinks", "sitefilter": "enwiki"})
    return pick(author, [data["entities"][i] for i in ids if i in data.get("entities", {})])


def main(argv):
    authors = {a["id"]: a for a in (json.load(open(p, encoding="utf-8"))
                                    for p in sorted(glob.glob(os.path.join(ROOT, "library", "authors", "*.json"))))}
    with open(PATH, encoding="utf-8") as f:
        data = json.load(f)
    works = {w["id"]: w for w in (json.load(open(p, encoding="utf-8"))
                                  for p in sorted(glob.glob(os.path.join(ROOT, "library", "works", "*.json"))))}
    fathers = [w for w in works if authors[works[w]["author"]]["era"] == "Early church"]
    data.setdefault("works", {})
    todo = [x for x in argv if x in authors] if argv else [a for a in authors if a not in data["authors"]]
    todo_works = [x for x in argv if x in fathers] if argv else [w for w in fathers if w not in data["works"]]
    unresolved = []
    try:
        for aid in todo:
            hit = lookup(authors[aid])
            if hit:
                data["authors"][aid] = hit
                print(f"{aid}: {hit['wikidata']} {hit['wikipedia'] or '(no English article)'}")
            else:
                unresolved.append(aid)
                print(f"{aid}: no single match; look it up by hand")
        props = clavis_properties() if todo_works else {}
        for wid in todo_works:
            author_item = data["authors"].get(works[wid]["author"], {}).get("wikidata")
            if not author_item:
                unresolved.append(wid)
                print(f"{wid}: its author has no Wikidata item yet")
                continue
            hit = lookup_work(works[wid], author_item, props)
            if hit:
                data["works"][wid] = hit
                numbers = ", ".join(f"{k.upper()} {hit[k]}" for k in CLAVIS if k in hit) or "no Clavis number"
                print(f"{wid}: {hit['wikidata']} ({numbers})")
            else:
                unresolved.append(wid)
                print(f"{wid}: no item by {author_item} clearly has this title; look it up by hand")
    except Refused as err:
        print(err)
    data["authors"] = dict(sorted(data["authors"].items()))
    data["works"] = dict(sorted(data["works"].items()))
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{len(data['authors'])} of {len(authors)} commentators and {len(data['works'])} of {len(fathers)} "
          f"works of the Fathers have identifiers; {len(unresolved)} unresolved")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
