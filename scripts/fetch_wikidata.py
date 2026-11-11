"""Find each commentator's Wikidata item and English Wikipedia article.

    python3 scripts/fetch_wikidata.py            # the commentators not yet in library/identifiers.json
    python3 scripts/fetch_wikidata.py augustine  # just these

Searches Wikidata for the commentator's name and accepts a match only when
exactly one result is a human (P31 = Q5) whose year of death (P570) is the
year in library/authors/<id>.json. Anything else is reported and left out,
for a person to look up. Writes library/identifiers.json; never guesses.

Wikimedia limits automated requests: the script waits between them, names
itself in its User-Agent, and stops at the first refusal (HTTP 429) rather
than retry. Run it again later to carry on.
"""
import glob
import json
import os
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
    todo = argv or [a for a in authors if a not in data["authors"]]
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
    except Refused as err:
        print(err)
    data["authors"] = dict(sorted(data["authors"].items()))
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{len(data['authors'])} of {len(authors)} commentators have identifiers; {len(unresolved)} unresolved")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
