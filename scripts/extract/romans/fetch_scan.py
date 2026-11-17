"""fetch_scan.py WORK ID START_MARK [END_MARK] : save the OCR text (archive.org's text view, as served)
from a margin before START_MARK to a margin after END_MARK (or the end) under sources/WORK/ID.txt."""
import hashlib, json, os, subprocess, sys, time
ROOT = os.environ.get("LOGIA", "/home/user/logia")
work, ident, a_mark = sys.argv[1:4]; b_mark = sys.argv[4] if len(sys.argv) > 4 else None
url = f"https://archive.org/stream/{ident}/{ident}_djvu.txt"
for attempt in range(4):
    r = subprocess.run(["curl", "-sSf", url], capture_output=True)
    if r.returncode == 0 and r.stdout: break
    time.sleep(2 ** attempt)
else: sys.exit("failed " + url)
raw = r.stdout; t = raw.decode("utf-8")
i = t.find("<pre"); i = t.find(">", i) + 1; j = t.find("</pre>", i)
full = t[i:j]
a = full.find(a_mark); assert a >= 0, a_mark
b = full.find(b_mark, a) + len(b_mark) if b_mark else len(full)
assert b > a
a = max(0, a - 2000); b = min(len(full), b + 2000)
rel = f"sources/{work}/{ident}.txt"
os.makedirs(os.path.join(ROOT, "sources", work), exist_ok=True)
open(os.path.join(ROOT, rel), "w", encoding="utf-8").write(full[a:b])
man_path = os.path.join(ROOT, "sources", "manifest.json")
man = json.load(open(man_path, encoding="utf-8"))
row = {"path": rel, "work": work, "url": url, "retrieved": time.strftime("%Y-%m-%d"), "kind": "scan",
       "download_sha256": hashlib.sha256(raw).hexdigest(),
       "extract": f"Characters {a}-{b} of the scan's full text (the pages quoted, with a margin)."}
man["files"] = [f for f in man["files"] if f["path"] != rel] + [row]
open(man_path, "w", encoding="utf-8").write(json.dumps(man, ensure_ascii=False, indent=1))
print(rel, a, b, len(full))
