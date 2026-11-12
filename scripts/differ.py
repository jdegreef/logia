"""The passages the churches read differently (library/differ/), and the
check that each page holds voices from enough traditions to be fair.

A page in library/differ/<id>.json is either its own record (title, start,
end, focus, note, status, reviewed_by) or points to a topic of a guide
({"guide": "traditions", "topic": 2}), whose title, passage and note it
takes. Its note is Logia's own short framing, a draft until a named person
reviews it; everything else on the page is the commentators' own words,
every work Logia holds on the passage, never a choice of them.

A page is published only when those works come from enough families of
tradition (library/families.json): as many families as its rule asks, and
among them the early church, a Catholic or Orthodox voice, and a Protestant
one. Otherwise it is held back, and validate.py says what it lacks.
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def families():
    return load(os.path.join(ROOT, "library", "families.json"))


def family(tradition, fam=None):
    """The family id of a tradition ("Reformed (Presbyterian)" -> "reformed"), or None."""
    for f in (fam or families())["families"]:
        if any(word in tradition for word in f["match"]):
            return f["id"]
    return None


def pages():
    """Every page, resolved: [{id, path, title, start, end, focus, note, status, reviewed_by, guide}]."""
    guides = {g["id"]: g for g in (load(p) for p in glob.glob(os.path.join(ROOT, "library", "guides", "en", "*.json")))}
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "library", "differ", "*.json"))):
        d = load(p)
        if "guide" in d:
            g = guides.get(d["guide"])
            topic = g["topics"][d["topic"] - 1] if g and 0 < d["topic"] <= len(g.get("topics", [])) else None
            if not topic:
                out.append({"id": d["id"], "missing": f"guide {d['guide']!r} has no topic {d['topic']}"})
                continue
            d = {**d, **{k: topic[k] for k in ("title", "start", "end", "focus", "note")},
                 "status": g["status"], "reviewed_by": g.get("reviewed_by"), "guide_path": g["path"]}
        out.append({**d, "path": f"/differ/{d['id']}/"})
    return out


def _key(ref):
    b, c, v = ref.split(".")
    return b, int(c), int(v)


def works_on(page, comments):
    """{work: [its excerpts that overlap the passage]}, from (work, start, end, entry) rows."""
    s, e = _key(page["start"]), _key(page["end"])
    out = {}
    for work, start, end, entry in comments:
        a, b = _key(start), _key(end)
        if a[0] == s[0] and a <= e and s <= b:
            out.setdefault(work, []).append(entry)
    return out


def balance(present, fam=None):
    """(fair, what is missing) for the set of family ids present."""
    fam = fam or families()
    kind = {f["id"]: f["kind"] for f in fam["families"]}
    kinds = {kind[f] for f in present if f in kind}
    rule = fam["rule"]
    names = {"shared": "the early church", "catholic": "Catholic", "orthodox": "Orthodox", "protestant": "Protestant"}
    missing = []
    for need in rule["need"]:
        if not kinds & set(need.split("|")):
            missing.append(" or ".join(names.get(k, k) for k in need.split("|")))
    if len(present) < rule["families"]:
        n = rule["families"] - len(present)
        missing.append(f"{n} more tradition{'s' if n > 1 else ''}")
    return not missing, missing
