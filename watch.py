#!/usr/bin/env python3
"""
Chip-Backed Finance Observatory - source watch with supervised auto-publication.
AI Transparency Institute - contact@aitransparencyinstitute.com

What it does, every run:
  1. Scans three tiers of sources (EDGAR / press-release wires / FT + Google News).
  2. Writes new findings to candidates.json and DIGEST.md.
  3. Depending on config "auto_publish_mode":
       off    -> stops there (human copies entries manually)
       pr     -> the workflow opens a Pull Request; one human click publishes
       direct -> merges entries into observatory-data.json NOW, but every
                 auto-added entry carries ver = "PENDING REVIEW", which the
                 website displays as a red badge plus a warning banner.
The badge is the human-supervision warning: a curator must later open the
source, verify, and change the badge to VERIFIED or REPORTED, or delete the
entry. The machine NEVER assigns VERIFIED or REPORTED itself.
"""

import json, re, sys, html, hashlib, datetime, urllib.parse
import requests, feedparser

CONFIG = json.load(open("config.json", encoding="utf-8"))
UA = {"User-Agent": CONFIG["user_agent"]}
TODAY = datetime.date.today()
MAX_AGE = datetime.timedelta(days=CONFIG.get("max_age_days", 10))

TECH = [t.lower() for t in CONFIG["tech_terms"]]
FIN = [t.lower() for t in CONFIG["finance_terms"]]
STRONG = [t.lower() for t in CONFIG["strong_phrases"]]

def relevant(text):
    t = text.lower()
    if any(p in t for p in STRONG):
        return "strong"
    if any(a in t for a in TECH) and any(b in t for b in FIN):
        return "combo"
    return None

try:
    SEEN = set(json.load(open("state/seen.json", encoding="utf-8")))
except Exception:
    SEEN = set()

def key(url, title):
    return hashlib.sha1((url or title).encode()).hexdigest()[:16]

candidates = []

def add(tier, title, url, source, date, note=""):
    k = key(url, title)
    if k in SEEN:
        return
    SEEN.add(k)
    candidates.append({
        "_tier": tier,
        "date": (date or str(TODAY))[:10],
        "name": html.unescape(title)[:180],
        "type": "To classify",
        "amount": "-",
        "terms": (note or "Auto-detected; details to be completed after reading the source")[:280],
        "status": "Auto-added - awaiting human verification",
        "ver": "PENDING REVIEW",
        "src": f"{source}, {(date or str(TODAY))[:10]}",
        "url": url,
    })

def recent(entry):
    for f in ("published_parsed", "updated_parsed"):
        tm = entry.get(f)
        if tm:
            d = datetime.date(tm.tm_year, tm.tm_mon, tm.tm_mday)
            return (TODAY - d) <= MAX_AGE, str(d)
    return True, None

def scan_feed(url, tier, source_label=None):
    try:
        raw = requests.get(url, headers=UA, timeout=30)
        feed = feedparser.parse(raw.content)
    except Exception as e:
        print(f"[warn] feed unreachable: {url} ({e})", file=sys.stderr)
        return
    for e in feed.entries[:60]:
        title = e.get("title", "")
        summary = re.sub(r"<[^>]+>", " ", e.get("summary", ""))
        if not relevant(title + " " + summary):
            continue
        ok, d = recent(e)
        if not ok:
            continue
        src = source_label or feed.feed.get("title", urllib.parse.urlparse(url).netloc)
        add(tier, title, e.get("link", ""), src, d, summary.strip()[:260])

def scan_edgar():
    for q in CONFIG["tier1_edgar_queries"]:
        try:
            r = requests.get("https://efts.sec.gov/LATEST/search-index",
                             params={"q": q, "startdt": str(TODAY - MAX_AGE), "enddt": str(TODAY)},
                             headers=UA, timeout=30)
            hits = r.json().get("hits", {}).get("hits", [])
        except Exception as e:
            print(f"[warn] EDGAR query failed: {q} ({e})", file=sys.stderr)
            continue
        for h in hits[:20]:
            s = h.get("_source", {})
            name = f"{(s.get('display_names') or ['Unknown filer'])[0]} - {s.get('form','')} filing matching {q}"
            url = "https://efts.sec.gov/LATEST/search-index?q=" + urllib.parse.quote(q)
            add(1, name, url, "SEC EDGAR", s.get("file_date"), f"EDGAR full-text match on {q}")

# ---- run tiers ----
scan_edgar()
for u in CONFIG["tier1_press_release_feeds"]:
    scan_feed(u, 1)
for u in CONFIG["tier2_ft_feeds"]:
    scan_feed(u, 2, "Financial Times")
for q in CONFIG["tier2_google_news_queries"]:
    g = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=en-US&gl=US&ceid=US:en"
    scan_feed(g, 2)
for u in CONFIG["tier3_extra_rss"]:
    scan_feed(u, 3)

candidates.sort(key=lambda c: (c["_tier"], c["date"]))

# ---- outputs: state, candidates, digest ----
json.dump(sorted(SEEN), open("state/seen.json", "w"), indent=0)
json.dump(candidates, open("candidates.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

lines = [f"# Observatory watch digest - {TODAY}",
         f"{len(candidates)} new candidate(s).", ""]
names = {1: "Tier 1 - primary sources", 2: "Tier 2 - quality press", 3: "Tier 3 - alerts"}
cur = None
for c in candidates:
    if c["_tier"] != cur:
        cur = c["_tier"]; lines += [f"## {names[cur]}", ""]
    lines += [f"- **{c['date']}** [{c['name']}]({c['url']}) - {c['src']}"]
if not candidates:
    lines += ["_No new candidates this run._"]

# ---- supervised auto-publication ----
mode = CONFIG.get("auto_publish_mode", "off")
tiers = set(CONFIG.get("auto_publish_tiers", [1]))
published = 0
if mode in ("direct", "pr") and candidates:
    path = CONFIG["observatory_json_path"]
    try:
        db = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"[error] cannot read {path}: {e}", file=sys.stderr)
        db = None
    if db is not None:
        existing = {(d.get("name"), d.get("date")) for d in db.get("deals", [])}
        for c in candidates:
            if c["_tier"] not in tiers:
                continue
            entry = {k: v for k, v in c.items() if not k.startswith("_") and k != "url"}
            entry["terms"] += f" [source link: {c['url']}]"
            if (entry["name"], entry["date"]) not in existing:
                db["deals"].append(entry)
                published += 1
        if published:
            db["deals"].sort(key=lambda d: d["date"])
            pending_total = sum(1 for d in db["deals"] if d.get("ver") == "PENDING REVIEW")
            db["updated"] = (f"{TODAY} - auto-update by source watch - "
                             f"{pending_total} entr{'y' if pending_total==1 else 'ies'} PENDING human review")
            json.dump(db, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
            lines += ["", f"**Auto-publication ({mode} mode): {published} entry(ies) merged into {path} "
                          f"with badge PENDING REVIEW. Human curation required: verify each source, "
                          f"then change the badge to VERIFIED or REPORTED, or delete the entry.**"]

open("DIGEST.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(f"{len(candidates)} candidate(s); {published} auto-published as PENDING REVIEW (mode={mode})")
