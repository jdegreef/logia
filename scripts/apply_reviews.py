"""Add a person's answers from the reference checker (/review/citations/,
web/review.js) to library/citations/.

    python3 scripts/apply_reviews.py answers.json [more.json ...]

Each file is what the checker downloads or puts in a GitHub issue:

    {"reviewer": "Their name",
     "answers": [{"in": "calvin.JHN.1.1.1", "at": 184, "start": "1TI.3.16", "end": "1TI.3.16", "ok": true}, ...]}

"ok": true sets the citation's status to "reviewed", false to "rejected"
(docs/references.md). A citation is found by its excerpt, its place in the
excerpt and the verse it points to, so an answer to a citation that has since
changed is left out and counted. Only a person runs this, after reading the
answers: the checker's answers are a person's, and this script never
answers anything itself.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def citations_path(excerpt):
    work, book = excerpt.split(".")[:2]
    return os.path.join(ROOT, "library", "citations", work, f"{book}.json")


def apply(answers):
    """Set the status of each answered citation. Returns (changed, unchanged, not found)."""
    files, changed, same, missing = {}, 0, 0, 0
    for a in answers:
        path = citations_path(a["in"])
        if path not in files:
            if not os.path.exists(path):
                missing += 1
                continue
            with open(path, encoding="utf-8") as f:
                files[path] = json.load(f)
        key = (a["in"], a["at"], a["start"], a.get("end", a["start"]))
        hit = [c for c in files[path]["citations"] if (c["in"], c["at"], c["start"], c["end"]) == key]
        if not hit:
            missing += 1
            continue
        status = "reviewed" if a["ok"] else "rejected"
        for c in hit:
            if c["status"] == status:
                same += 1
            else:
                c["status"] = status
                changed += 1
    for path, data in files.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, indent=1))
    return changed, same, missing


def main(paths):
    if not paths:
        raise SystemExit(__doc__)
    answers, people = [], []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        people.append(data.get("reviewer") or "(no name)")
        answers += [a for a in data["answers"] if isinstance(a.get("ok"), bool)]
    changed, same, missing = apply(answers)
    print(f"{changed} citations changed, {same} already so, {missing} not found; answers by {', '.join(people)}")


if __name__ == "__main__":
    main(sys.argv[1:])
