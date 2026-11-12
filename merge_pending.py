#!/usr/bin/env python3
"""
Tidy the PENDING REVIEW entries in observatory-data.json. Safe to run repeatedly.

  1. Every deal gets a stable "id" (curated deals too; nothing else about them changes).
  2. Pending entries: the "[source link: ...]" text moves into a "url" field, the
     verbatim feed excerpt in "terms" is replaced by a neutral note (we do not
     republish publishers' text), and the "outlet" is recorded.
  3. Pending entries about the same story are merged into one row: the best source
     (primary > Reuters/Bloomberg/FT > other press, then earliest) stays as the row,
     and the other articles move into its "sources" list. Articles from
     config "blocked_sources" are dropped from a group that has other outlets.

It never changes "ver" and never touches VERIFIED or REPORTED entries.
Usage: python merge_pending.py [--db observatory-data.json] [--dry-run]
"""
import argparse
import json
import re

import stories

PENDING = "PENDING REVIEW"


def normalise(d):
    """Step 1-2 for one entry (in place)."""
    d.setdefault("id", stories.deal_id(d))
    if d.get("ver") != PENDING:
        return
    m = re.search(r"\s*\[source link: (\S+?)\]", d.get("terms", ""))
    if m:
        d.setdefault("url", m.group(1))
        d["terms"] = d["terms"][:m.start()] + d["terms"][m.end():]
    d["terms"] = stories.NEUTRAL_TERMS
    d.setdefault("outlet", stories.outlet_of(d))


def merge(db, blocked=()):
    """Steps 1-3 on a loaded data file. Returns a summary dict."""
    deals = db["deals"]

    def curated_view(ds):  # everything about curated entries except the added id
        return sorted(json.dumps({k: v for k, v in d.items() if k != "id"}, sort_keys=True)
                      for d in ds if d.get("ver") != PENDING)

    before = curated_view(deals)
    for d in deals:
        normalise(d)
    curated = [d for d in deals if d.get("ver") != PENDING]
    pending = [d for d in deals if d.get("ver") == PENDING]
    merged, dropped = [], 0
    for g in stories.group(pending):
        head, n = stories.merge_group(g, blocked)
        head["ver"] = PENDING
        merged.append(head)
        dropped += n
    db["deals"] = sorted(curated + merged, key=lambda d: d["date"])
    assert curated_view(db["deals"]) == before, "curated entries must not change"
    return {"pending_before": len(pending), "pending_after": len(merged), "blocked_dropped": dropped}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="observatory-data.json")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    with open(a.db, encoding="utf-8") as f:
        db = json.load(f)
    try:
        with open(a.config, encoding="utf-8") as f:
            blocked = [b.lower() for b in json.load(f).get("blocked_sources", [])]
    except OSError:
        blocked = []
    s = merge(db, blocked)
    n = s["pending_after"]
    if n:
        db["updated"] = re.sub(r"\d+ entr(y|ies) PENDING", f"{n} entr{'y' if n == 1 else 'ies'} PENDING",
                               db.get("updated", ""))
    print(f"pending rows {s['pending_before']} -> {n}; "
          f"{s['blocked_dropped']} blocked-outlet articles dropped from merged groups")
    if not a.dry_run:
        with open(a.db, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
