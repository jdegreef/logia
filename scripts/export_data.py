"""Build a release of Logia's data: one zip of the library, for others to use.

    python3 scripts/export_data.py 1.0.0        # writes dist/logia-data-1.0.0.zip

The zip holds everything a program needs to use the library without this
repository's code: library/ (authors, works, excerpts, corrections,
citations, quotations, mentions, whole texts, scan pages, creeds, topics,
readings, guides, translations), sources/manifest.json (where every text was
copied from), the docs that describe the data (docs/data.md,
docs/references.md, docs/api.md), the licences, and logia-data.json: the
release's version, the data format version (FORMAT below), and counts.

The zip is reproducible: the same data gives the same bytes, so a release
can be checked against a build of its tag. .github/workflows/release.yml
builds it when a tag data-v<version> is pushed and attaches it to the
GitHub release. docs/data.md says how versions are numbered.
"""
import glob
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The shape of the library's files (docs/data.md). Raise it, and the release's
# major version, when a file loses or renames a field or changes its meaning.
FORMAT = 1
DOCS = ("docs/data.md", "docs/references.md", "docs/api.md", "LICENSE", "LICENSE-CODE", "README.md")
STAMP = (2026, 1, 1, 0, 0, 0)          # every file's time in the zip, so builds match byte for byte


def files():
    out = sorted(p for p in glob.glob(os.path.join(ROOT, "library", "**", "*"), recursive=True) if os.path.isfile(p))
    out.append(os.path.join(ROOT, "sources", "manifest.json"))
    out += [os.path.join(ROOT, d) for d in DOCS]
    return [os.path.relpath(p, ROOT).replace(os.sep, "/") for p in out]


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def counts():
    def n(pattern, key=None):
        paths = glob.glob(os.path.join(ROOT, pattern))
        return len(paths) if not key else sum(len(load(p)[key]) for p in paths)
    return {"authors": n("library/authors/*.json"), "works": n("library/works/*.json"),
            "excerpts": n("library/comments/*/*.json", "entries"),
            "citations": n("library/citations/*/*.json", "citations"),
            "quotations": n("library/quotations/*/*.json", "quotations"),
            "texts": n("library/texts/*/*.json"), "creeds": n("library/creeds/*.json"),
            "topics": len(load(os.path.join(ROOT, "library", "topics.json"))["topics"])}


def build(version, out):
    meta = {"name": "Logia data", "version": version, "format": FORMAT,
            "licence": "Logia's data: CC0 1.0. Commentary texts: public domain (see each work's rights).",
            "site": "https://logia.faith", "repository": "https://github.com/jdegreef/logia",
            "docs": "docs/data.md", "counts": counts()}
    prefix = f"logia-data-{version}/"
    names = files()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        def add(name, data):
            info = zipfile.ZipInfo(prefix + name, STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
        add("logia-data.json", json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
        for rel in names:
            with open(os.path.join(ROOT, rel), "rb") as f:
                add(rel, f.read())
    return meta, len(names) + 1


def main(argv):
    if len(argv) != 1 or not re.fullmatch(r"\d+\.\d+\.\d+", argv[0]):
        sys.exit("usage: export_data.py <version>, e.g. 1.0.0 (docs/data.md, \"Releases\")")
    version = argv[0]
    if int(version.split(".")[0]) != FORMAT:
        sys.exit(f"version {version}: its major number must be the data format, {FORMAT}")
    out = os.path.join(ROOT, "dist", f"logia-data-{version}.zip")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    meta, n = build(version, out)
    print(f"{os.path.relpath(out, ROOT)}: {n} files; " + ", ".join(f"{v} {k}" for k, v in meta["counts"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
