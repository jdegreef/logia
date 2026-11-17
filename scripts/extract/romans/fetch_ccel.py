"""fetch_ccel.py WORK URLBASE ID... : save each CCEL page's book-content block
under sources/WORK/<name>.html and add manifest rows."""
import hashlib, json, os, re, subprocess, sys, time
ROOT = os.environ.get("LOGIA", "/home/user/logia")
work, base, ids = sys.argv[1], sys.argv[2], sys.argv[3:]
man_path = os.path.join(ROOT, "sources", "manifest.json")
man = json.load(open(man_path, encoding="utf-8"))
have = {f["path"] for f in man["files"]}
os.makedirs(os.path.join(ROOT, "sources", work), exist_ok=True)
for pid in ids:
    name = f"{pid}.html"
    url = f"{base}{name}"
    rel = f"sources/{work}/{name}"
    for attempt in range(4):
        r = subprocess.run(["curl", "-sSf", url], capture_output=True)
        if r.returncode == 0 and r.stdout:
            break
        time.sleep(2 ** attempt)
    else:
        sys.exit(f"failed {url}")
    raw = r.stdout
    t = raw.decode("utf-8")
    start = t.find('<div xmlns="http://www.w3.org/1999/xhtml" class="book-content"')
    assert start >= 0, url
    depth, pos = 0, start
    for m in re.compile(r"<(/?)div\b[^>]*?(/?)>").finditer(t, start):
        if m[2]:
            continue
        depth += -1 if m[1] else 1
        if depth == 0:
            end = m.end(); break
    block = t[start:end]
    open(os.path.join(ROOT, rel), "w", encoding="utf-8").write(block)
    row = {"path": rel, "work": work, "url": url, "retrieved": time.strftime("%Y-%m-%d"), "kind": "digital",
           "download_sha256": hashlib.sha256(raw).hexdigest(),
           "extract": "The page's book-content block (CCEL site chrome left out); footnote text is inline in mnote spans."}
    if rel in have:
        man["files"] = [row if f["path"] == rel else f for f in man["files"]]
    else:
        man["files"].append(row)
    print(rel, len(block))
with open(man_path, "w", encoding="utf-8") as f:
    f.write(json.dumps(man, ensure_ascii=False, indent=1))
