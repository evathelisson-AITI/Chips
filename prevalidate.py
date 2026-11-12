#!/usr/bin/env python3
"""
Observatory pre-validation (assistive). Reads observatory-data.json, never modifies it.
(To merge duplicate pending rows in the data file, use merge_pending.py.)
For every entry with ver == "PENDING REVIEW" it:
  - rejects obvious noise (spam outlets, tokenized-stock lending, macro/earnings news)
  - extracts entity and USD amount from the title
  - clusters duplicates (same entity + same amount) into ONE deal candidate
  - grades the best source per cluster (primary / rating / press1 / press2 / other)
  - matches clusters against existing deals and a seed list of known primary sources
  - writes SUGGESTIONS only: prevalidation.json + PREVALIDATION.md
The machine never writes ver / VERIFIED / REPORTED. The curator decides.

Usage: python prevalidate.py [--db observatory-data.json] [--hints primary_hints.json] [--online]
"""
import json, re, hashlib, argparse, datetime, urllib.parse, sys

from stories import (ENTITIES, ENTITY_RX, RANK, amount_musd, entity_of,  # noqa: F401
                     outlet_of, tier_of, url_of, md_safe, safe_http_url)

LINKS = {"Kamino/sUSDai": "Bullish/USD.AI"}       # derivative markets point to the parent deal
CRYPTO = {"Bullish/USD.AI", "Kamino/sUSDai"}

NOT_GPU = re.compile(r"tokenized|\baave\b|morpho", re.I)
MACRO = re.compile(r"chip stocks slide|borrowing costs|bond sell-?off|sales growth|forecasts \d+%", re.I)
COMMENT = re.compile(r"explained|gamble|blind spots|won.t age|reality check|can a leasing model|"
                     r"central bank of ai|ai harvest|wall street decided|top .{0,20}stocks|faces .{0,40}risk", re.I)
DEAL = re.compile(r"\b(secur\w*|raises?|inks?|leads?|led|provides?|commits?|closes?|closed|backs?|"
                  r"financing|facility|loan|debt|notes|lease)\b", re.I)
CHIP = re.compile(r"gpu|chip|nvidia|compute", re.I)


def existing_amount(s):
    m = re.search(r"([\d,]+\.?\d*)\s*M", s or "")
    return float(m.group(1).replace(",", "")) if m else None


def uid(d):
    return hashlib.sha1(f"{d.get('date')}|{d.get('name')}".encode()).hexdigest()[:12]


def classify(d):
    name = d["name"]
    outlet = outlet_of(d)
    tier = tier_of(outlet)
    info = {"id": uid(d), "date": d.get("date"), "name": name, "outlet": outlet, "tier": tier,
            "entity": entity_of(name), "amount_musd": amount_musd(name)}
    if tier == "spam":
        info.update(kind="reject", reason="templated SEO outlet")
    elif NOT_GPU.search(name):
        info.update(kind="reject", reason="crypto lending against equities, not chip collateral")
    elif MACRO.search(name):
        info.update(kind="reject", reason="macro / earnings news, not a financing")
    elif COMMENT.search(name):
        info.update(kind="commentary")
    elif info["amount_musd"] and DEAL.search(name) and CHIP.search(name):
        info.update(kind="deal-signal")
    else:
        info.update(kind="other")
    return info


def close(a, b, tol=0.05):
    return a and b and abs(a - b) / max(a, b) <= tol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="observatory-data.json")
    ap.add_argument("--hints", default="primary_hints.json")
    ap.add_argument("--candidates", default="candidates.json", help="this run's new finds (optional)")
    ap.add_argument("--out", default="prevalidation.json")
    ap.add_argument("--md", default="PREVALIDATION.md")
    ap.add_argument("--online", action="store_true", help="try fetching non-Google URLs to confirm outlet/amount")
    a = ap.parse_args()

    db = json.load(open(a.db, encoding="utf-8"))
    try:
        hints = json.load(open(a.hints, encoding="utf-8"))
    except Exception:
        hints = []
    deals = db["deals"]
    try:
        extra = json.load(open(a.candidates, encoding="utf-8"))
    except Exception:
        extra = []
    seen_ids = {uid(d) for d in deals}
    pend_src = [d for d in deals if d.get("ver") == "PENDING REVIEW"] + \
               [dict(c, ver="PENDING REVIEW") for c in extra if uid(c) not in seen_ids]
    pending = [classify(d) | {"_raw": d} for d in pend_src]
    known = [d for d in deals if d.get("ver") != "PENDING REVIEW"]

    clusters, rejects, unclassified = {}, [], []
    for it in pending:
        if it["kind"] == "reject":
            rejects.append(it)
        elif it["entity"] and it["amount_musd"]:
            key = (it["entity"], round(it["amount_musd"]))
            clusters.setdefault(key, []).append(it)
        else:
            unclassified.append(it)

    out_clusters = []
    for (ent, amt), items in sorted(clusters.items()):
        best = min(items, key=lambda i: RANK[i["tier"]])
        tier = best["tier"]
        matched = [h for h in hints if h["entity"] == ent and (not h.get("amount_musd") or close(h["amount_musd"], amt))]
        if matched and min(RANK[h["tier"]] for h in matched) < RANK[tier]:
            tier = min((h["tier"] for h in matched), key=lambda t: RANK[t])
        dup = [k["name"] for k in known if re.search(ENTITY_RX[ent], k["name"].lower())
               and close(existing_amount(k.get("amount")), amt)]
        is_deal = any(i["kind"] == "deal-signal" for i in items) or bool(matched)
        if not is_deal:
            sugg = "COMMENTARY-ONLY (no deal evidence; attach as context)"
        elif tier in ("primary", "rating"):
            sugg = "VERIFIED-candidate (curator confirms issuer/filing in the source)"
        elif tier == "press1":
            sugg = "REPORTED-candidate (Reuters/Bloomberg/FT)"
        else:
            sugg = "NEEDS-PRIMARY-SOURCE (press/aggregator tier only)"
        q = urllib.parse.quote(f"{ent.replace('/', ' ')} {amt/1000:g} billion GPU financing" if amt >= 1000 else f"{ent.replace('/', ' ')} {amt:g} million GPU financing")
        c = {"entity": ent, "amount_musd": amt, "members": sum(1 + len(i["_raw"].get("sources") or []) for i in items), "best_tier": tier,
             "suggestion": sugg, "tags": (["crypto-funded"] if ent in CRYPTO else []),
             "possible_duplicate_of": dup, "known_primary": [h["url"] for h in matched],
             "member_ids": [i["id"] for i in items],
             "find_primary": ["https://www.sec.gov/edgar/search/#/q=" + urllib.parse.quote(f'"{ent}"'),
                              "https://www.google.com/search?q=" + q + "+site:prnewswire.com+OR+site:businesswire.com"],
             "outlets": sorted({i["outlet"] for i in items})}
        out_clusters.append(c)

    items_out = {}
    for it in pending:
        it = {k: v for k, v in it.items() if k != "_raw"}
        if it["kind"] == "reject":
            it["suggestion"] = f"REJECT-suggested ({it['reason']})"
        elif it["entity"] in LINKS and not it["amount_musd"]:
            it["suggestion"] = f"LINK-TO {LINKS[it['entity']]} (derivative, not a primary financing)"
        elif it["entity"] and it["amount_musd"]:
            it["suggestion"] = "SEE-CLUSTER"
        else:
            it["suggestion"] = "REVIEW-manually"
        items_out[it["id"]] = it

    if a.online:
        import requests
        for it in pending:
            u = safe_http_url(url_of(it["_raw"]))   # feed links are untrusted: http(s) only
            if not u or "news.google.com" in u:
                continue
            try:
                # Only the status and final domain are needed: never download the body.
                with requests.get(u, timeout=20, stream=True,
                                  headers={"User-Agent": "observatory-prevalidate"}) as r:
                    items_out[it["id"]]["online"] = {"status": r.status_code,
                                                     "final_domain": urllib.parse.urlparse(r.url).netloc}
            except Exception as e:
                items_out[it["id"]]["online"] = {"error": str(e)[:80]}

    json.dump({"generated": str(datetime.date.today()), "note": "suggestions only; ver is never modified",
               "clusters": out_clusters, "items": items_out},
              open(a.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    L = [f"# Pre-validation - {datetime.date.today()}",
         f"{len(pending)} pending -> {len(out_clusters)} deal/commentary clusters, "
         f"{len(rejects)} suggested rejects, {len(unclassified)} for manual review.", "",
         "_Suggestions only. The curator assigns VERIFIED / REPORTED._", "", "## Clusters (review these)"]
    for c in sorted(out_clusters, key=lambda c: RANK[c["best_tier"]]):
        L.append(f"- **{c['entity']} ~${c['amount_musd']:,.0f}M** x{c['members']} - {c['suggestion']}"
                 + (f" - possible duplicate of: {md_safe('; '.join(c['possible_duplicate_of']))}" if c["possible_duplicate_of"] else "")
                 + (f" - known source: {c['known_primary'][0]}" if c["known_primary"] else f" - find: {c['find_primary'][1]}")
                 + (f" [{', '.join(c['tags'])}]" if c["tags"] else ""))
    L += ["", "## Manual review"] + [f"- {i['date']} {md_safe(i['name'][:110])} ({md_safe(i['outlet'])}) -> "
                                     f"{items_out[i['id']]['suggestion']}" for i in unclassified]
    L += ["", f"## Suggested rejects ({len(rejects)})"]
    by = {}
    for r in rejects:
        by.setdefault(r["reason"], []).append(r)
    L += [f"- {reason}: {len(v)}" for reason, v in by.items()]
    open(a.md, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"{len(pending)} pending, {len(out_clusters)} clusters, {len(rejects)} rejects, {len(unclassified)} manual")


if __name__ == "__main__":
    sys.exit(main())
