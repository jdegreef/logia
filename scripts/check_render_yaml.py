"""Check that render.yaml, the Render Blueprint, is valid YAML of the right shape.

An unquoted ": " in a command once broke the Blueprint sync on Render
("mapping values are not allowed in this context"), so CI parses it.
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main():
    path = ROOT / "render.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as err:
        sys.exit(f"render.yaml is not valid YAML:\n{err}")
    problems = []
    services = data.get("services") if isinstance(data, dict) else None
    if not isinstance(services, list) or not services:
        problems.append("no services list")
    for i, svc in enumerate(services or []):
        if not isinstance(svc, dict):
            problems.append(f"service {i} is not a mapping")
            continue
        for key in ("type", "name", "runtime", "buildCommand", "staticPublishPath"):
            if not isinstance(svc.get(key), str) or not svc[key].strip():
                problems.append(f"service {i}: {key} missing or not a string")
        for j, r in enumerate(svc.get("routes") or []):
            if not (isinstance(r, dict) and r.get("type") in ("redirect", "rewrite")
                    and all(isinstance(r.get(k), str) and r[k].startswith("/") for k in ("source", "destination"))):
                problems.append(f"service {i}: route {j} needs a type and / paths for source and destination")
        for j, h in enumerate(svc.get("headers") or []):
            if not (isinstance(h, dict) and all(isinstance(h.get(k), str) for k in ("path", "name", "value"))):
                problems.append(f"service {i}: header {j} needs string path, name and value")
    sys.path.insert(0, str(ROOT / "scripts"))
    import redirects
    if redirects.block() not in path.read_text(encoding="utf-8"):
        problems.append("the book redirects are stale; run python3 scripts/redirects.py")
    site = ROOT / "site"
    if site.is_dir():
        taken = sorted(s for s in redirects.sources() if (site / s).exists())
        if taken:
            problems.append("book redirects would shadow site paths: " + ", ".join(taken))
    if problems:
        sys.exit("render.yaml: " + "; ".join(problems))
    print(f"render.yaml OK ({len(services)} service)")


if __name__ == "__main__":
    main()
