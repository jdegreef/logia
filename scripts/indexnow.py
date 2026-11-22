"""IndexNow: tell Bing (and Yandex, Seznam, Naver) which pages changed in a
deploy, so they fetch them within hours. Bing's index is the one ChatGPT
search and Copilot read from. No account is needed: the key below is public
by design, and the build serves it at /<key>.txt to prove the site is ours.

The build writes /indexnow.json: the commit it was built from, and for each
page in the sitemaps a short digest of its title, description and <main>
(not the header and footer, which change with every asset). After a push to
main, .github/workflows/indexnow.yml runs

    python3 scripts/indexnow.py snapshot old.json    # the live manifest, before the deploy
    python3 scripts/indexnow.py submit old.json      # waits for the deploy, sends what changed

and only the pages whose digest changed (or are new) are sent.
"""

import hashlib
import json
import os
import re
import sys
import time
import urllib.request

SITE_URL = "https://logia.faith"
KEY = "fee9a037ef50b35ae81725853a831707"
ENDPOINT = "https://api.indexnow.org/indexnow"
BATCH = 10000                     # the most URLs IndexNow takes in one request


def digest(html):
    """A short digest of what a search engine indexes on a page."""
    head = html.split("</head>", 1)[0]
    keep = re.findall(r"<title>.*?</title>|<meta name=\"description\"[^>]*>", head)
    m = re.search(r"<main\b.*?</main>", html, re.S)
    text = "".join(keep) + (m[0] if m else html)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def manifest(site, paths, commit):
    """{"commit": ..., "pages": {path: digest}} for the pages given."""
    pages = {}
    for p in paths:
        f = os.path.join(site, p.strip("/"), "index.html")
        if os.path.exists(f):
            with open(f, encoding="utf-8") as fh:
                pages[p] = digest(fh.read())
    return {"commit": commit, "pages": pages}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "logia-indexnow"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def changed(old, new):
    """The paths whose page is new or different."""
    before = old.get("pages", {})
    return sorted(p for p, d in new["pages"].items() if before.get(p) != d)


def submit(urls):
    for i in range(0, len(urls), BATCH):
        body = json.dumps({"host": SITE_URL.split("//")[1], "key": KEY, "keyLocation": f"{SITE_URL}/{KEY}.txt",
                           "urlList": urls[i:i + BATCH]}).encode()
        req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"IndexNow: sent {len(urls[i:i + BATCH])} URLs, HTTP {r.status}")


def main():
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "snapshot":
        try:
            old = fetch(SITE_URL + "/indexnow.json")
        except Exception as err:                # the first deploy with IndexNow: nothing to compare with
            print(f"no live manifest ({err}); every page will be sent")
            old = {}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(old, f)
        return
    with open(path, encoding="utf-8") as f:
        old = json.load(f)
    want = os.environ.get("GITHUB_SHA", "")
    for _ in range(60):                         # Render deploys once CI passes: wait up to 40 minutes
        new = fetch(f"{SITE_URL}/indexnow.json?t={int(time.time())}")
        # This push's build, or a later one if pushes came close together.
        if not want or new.get("commit") == want or (old.get("commit") and new.get("commit") != old["commit"]):
            break
        time.sleep(40)
    else:
        sys.exit(f"the live site never reached {want}; nothing sent")
    urls = [SITE_URL + p for p in changed(old, new)]
    if not urls:
        print("IndexNow: no page changed")
        return
    submit(urls)


if __name__ == "__main__":
    main()
