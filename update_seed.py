#!/usr/bin/env python3
"""
Regenerate the SEED snapshot in app.js from observatory-data.json.
The snapshot is what the page shows when the JSON cannot be loaded. It holds
curated deals only (VERIFIED / REPORTED), plus the series and events.
Usage: python update_seed.py [--check]   (--check: exit 1 if app.js is out of date)
"""
import datetime
import json
import re
import sys

APP, DATA = "app.js", "observatory-data.json"
BLOCK = re.compile(r"/\* SEED:BEGIN \*/\n.*?\n/\* SEED:END \*/", re.S)


def payload(db):
    return {
        "deals": [d for d in db.get("deals", []) if d.get("ver") in ("VERIFIED", "REPORTED")],
        "resale": db.get("resale", []),
        "rental": db.get("rental", []),
        "events": db.get("events", []),
    }


def build(db, snapshot):
    seed = {"snapshot": snapshot, **payload(db)}
    body = json.dumps(seed, ensure_ascii=False, indent=1)
    # JSON is valid JS; "</" is escaped so the data can never close a script tag.
    return "/* SEED:BEGIN */\nconst SEED = " + body.replace("</", "<\\/") + ";\n/* SEED:END */"


def current_payload(js):
    m = re.search(r"const SEED = (.*?);\n/\* SEED:END \*/", js, re.S)
    return json.loads(m.group(1).replace("<\\/", "</")) if m else None


def main():
    with open(DATA, encoding="utf-8") as f:
        db = json.load(f)
    with open(APP, encoding="utf-8") as f:
        js = f.read()
    old = current_payload(js) or {}
    fresh = payload(db)
    same = all(old.get(k) == v for k, v in fresh.items())
    if "--check" in sys.argv:
        print("seed up to date" if same else "seed OUT OF DATE: run python update_seed.py")
        sys.exit(0 if same else 1)
    if same:
        print("seed already up to date")
        return
    snapshot = str(datetime.date.today())
    js = BLOCK.sub(lambda _: build(db, snapshot), js, count=1)
    with open(APP, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"seed updated: {len(fresh['deals'])} curated deals, snapshot {snapshot}")


if __name__ == "__main__":
    main()
