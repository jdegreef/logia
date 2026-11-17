"""Check that the pages Logia's excerpts were copied from still answer: each
CCEL (and Tertullian Project) page an excerpt or work names, and each
scanned book on archive.org once (its many page links all lead into it).
It only reports; nothing in the library is changed.

    python3 scripts/check_sources_live.py              # all of them, politely (an hour or so)
    python3 scripts/check_sources_live.py --sample 20  # a few, chosen at random, to try it

It names itself in its User-Agent, waits between requests to the same site,
and stops at the first refusal (HTTP 429). It exits 1 when any page is
missing (HTTP 404 or 410, or no answer at all), and lists them.
"""
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
AGENT = "LogiaBuild/1.0 (https://logia.faith; https://github.com/jdegreef/logia)"
PAUSE = 1.5


def addresses():
    """{address to check: [where it is used]}, one per archive.org book."""
    import build_site as B
    lib = B.Library()
    out = {}

    def add(url, where):
        if not url:
            return
        url = url.split("#")[0]
        m = re.match(r"(https?://archive\.org/details/[^/?]+)", url)
        out.setdefault(m[1] if m else url, []).append(where)
    for c in lib.comments:
        add(c.get("source_url"), c["id"])
        add((c.get("scan") or {}).get("url"), c["id"])
    for wid, w in lib.works.items():
        add(w.get("full_text_url"), wid)
    for path in sorted(os.listdir(os.path.join(ROOT, "library", "creeds"))):
        if path.endswith(".json") and not path.startswith("_"):
            d = json.load(open(os.path.join(ROOT, "library", "creeds", path), encoding="utf-8"))
            add(d.get("full_text_url"), d["id"])
    return out


def status(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as err:
        if err.code == 405:     # HEAD not allowed: ask for the page itself
            page = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "*/*"})
            with urllib.request.urlopen(page, timeout=30) as r:
                return r.status
        return err.code
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None


def main(argv):
    found = addresses()
    urls = sorted(found)
    if "--sample" in argv:
        n = int(argv[argv.index("--sample") + 1])
        urls = random.sample(urls, min(n, len(urls)))
    print(f"checking {len(urls)} of {len(found)} addresses")
    last, bad = {}, []
    for i, url in enumerate(urls, 1):
        host = urllib.parse.urlparse(url).netloc
        wait = PAUSE - (time.time() - last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        code = status(url)
        last[host] = time.time()
        if code == 429:
            print(f"{host} asked us to slow down (HTTP 429); stopped after {i - 1}")
            break
        if code is None or code in (404, 410):
            bad.append((url, code))
            users = ", ".join(found[url][:3]) + ("…" if len(found[url]) > 3 else "")
            print(f"MISSING {code or 'no answer'} {url} (used by {users})")
    print(f"{len(bad)} missing" if bad else "every address checked answers")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
