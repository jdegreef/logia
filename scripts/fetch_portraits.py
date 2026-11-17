"""Find a public-domain portrait of each commentator on Wikimedia Commons and
save a small copy of it in web/portraits/, with its record in
library/portraits.json.

    python3 scripts/fetch_portraits.py           # every commentator without one
    python3 scripts/fetch_portraits.py calvin    # just these

The commentator's Wikidata item is found with one SPARQL query, accepted only
when exactly one item is a human (P31 = Q5) whose English label or alias is
the commentator's name and whose year of death (P570) is the year in
library/authors/<id>.json, as scripts/fetch_wikidata.py does. Its image
(P18) is then looked up on Commons, and kept only when Commons gives its
licence as public domain or CC0: the file, the artist and date as Commons
records them, the licence and the address of the file's page are written to
library/portraits.json, and a 320-pixel copy to web/portraits/<id>.jpg.
Anything else is reported and left out, for a person to look at. Nothing is
typed: every value comes from Wikidata or Commons.

Wikimedia asks automated clients to name themselves and go slowly: each
request carries a User-Agent and waits between requests, and a refusal
(HTTP 429) stops the run.
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
PATH = os.path.join(ROOT, "library", "portraits.json")
OUT = os.path.join(ROOT, "web", "portraits")
AGENT = "LogiaBuild/1.0 (https://logia.faith; https://github.com/jdegreef/logia)"
SPARQL = "https://query.wikidata.org/sparql"
COMMONS = "https://en.wikipedia.org/w/api.php"     # answers for Commons files too
PAUSE = 2.0
WIDTH = 320
FREE = re.compile(r"^(public domain|pd\b|pd-|cc0)", re.I)


class Refused(Exception):
    pass


def fetch(url, accept="*/*"):
    # Without an Accept header, Wikimedia answers urllib's requests with HTTP 429.
    req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
    except urllib.error.HTTPError as err:
        if err.code in (429, 503):
            raise Refused(f"Wikimedia refused the request (HTTP {err.code}); try again later") from err
        raise
    time.sleep(PAUSE)
    return body


def authors(ids):
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "library", "authors", "*.json"))):
        a = json.load(open(p, encoding="utf-8"))
        if not ids or a["id"] in ids:
            out.append(a)
    return out


def items(people):
    """{author id: [(item, image file or None)]}: the humans named so who died that year."""
    rows = " ".join(f'("{a["id"]}" "{a["name"]}"@en {a["died"]})' for a in people)
    query = f"""SELECT ?id ?item ?image WHERE {{
  VALUES (?id ?name ?died) {{ {rows} }}
  {{ ?item rdfs:label ?name }} UNION {{ ?item skos:altLabel ?name }}
  ?item wdt:P31 wd:Q5; wdt:P570 ?death.
  FILTER(YEAR(?death) = ?died)
  OPTIONAL {{ ?item wdt:P18 ?image }}
}}"""
    data = json.loads(fetch(SPARQL + "?" + urllib.parse.urlencode({"query": query, "format": "json"})))
    out = {}
    for b in data["results"]["bindings"]:
        item = b["item"]["value"].rsplit("/", 1)[1]
        image = urllib.parse.unquote(b["image"]["value"].rsplit("/", 1)[1]) if "image" in b else None
        hits = out.setdefault(b["id"]["value"], {})
        hits.setdefault(item, image or hits.get(item))
    return {k: list(v.items()) for k, v in out.items()}


def plain(html_text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html_text or "")).strip()


def file_info(files):
    """{file name: Commons' record of it}, for up to 50 files at a time."""
    out = {}
    names = list(files)
    for i in range(0, len(names), 50):
        params = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|extmetadata",
                  "iiurlwidth": WIDTH, "titles": "|".join("File:" + n for n in names[i:i + 50])}
        data = json.loads(fetch(COMMONS + "?" + urllib.parse.urlencode(params)))
        norm = {x["to"]: x["from"] for x in data["query"].get("normalized", [])}
        for page in data["query"]["pages"].values():
            if not page.get("imageinfo"):
                continue
            title = norm.get(page["title"], page["title"])
            out[title.split(":", 1)[1]] = page["imageinfo"][0]
    return out


def main(argv):
    ids = argv[1:]
    record = json.load(open(PATH, encoding="utf-8")) if os.path.exists(PATH) else {
        "about": ("A public-domain portrait of each commentator from Wikimedia Commons, found by "
                  "scripts/fetch_portraits.py: the Wikidata item, the file, its artist and date as Commons "
                  "records them, its licence and its page. Never typed."), "portraits": {}}
    people = [a for a in authors(ids) if ids or a["id"] not in record["portraits"]]
    if not people:
        print("every commentator has a portrait record")
        return 0
    try:
        found = items(people)
        images = {}
        for a in people:
            hits = found.get(a["id"], [])
            if len(hits) != 1:
                print(f"{a['id']}: {len(hits)} Wikidata items match the name and year of death; left out")
                continue
            item, image = hits[0]
            if not image:
                print(f"{a['id']}: {item} has no image; left out")
                continue
            images[image] = (a, item)
        info = file_info(images)
    except Refused as err:
        print(err)
        return 1
    os.makedirs(OUT, exist_ok=True)
    for image, (a, item) in images.items():
        ii = info.get(image)
        meta = (ii or {}).get("extmetadata", {})
        licence = plain(meta.get("LicenseShortName", {}).get("value"))
        if not ii or not FREE.match(licence):
            given = licence or "no licence given"
            print(f"{a['id']}: {image} is not marked public domain on Commons ({given}); left out")
            continue
        try:
            body = fetch(ii["thumburl"])
        except Refused as err:
            print(err)
            break
        with open(os.path.join(OUT, f"{a['id']}.jpg"), "wb") as f:
            f.write(body)
        record["portraits"][a["id"]] = {
            "wikidata": item, "file": image, "page": ii["descriptionurl"],
            "artist": plain(meta.get("Artist", {}).get("value")) or None,
            "date": plain(meta.get("DateTimeOriginal", {}).get("value")) or None,
            "licence": licence, "width": ii.get("thumbwidth"), "height": ii.get("thumbheight")}
        print(f"{a['id']}: {image} ({licence})")
    record["portraits"] = dict(sorted(record["portraits"].items()))
    with open(PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(record['portraits'])} of {len(authors([]))} commentators have a portrait")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
