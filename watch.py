#!/usr/bin/env python3
"""
Chip-Backed Finance Observatory - source watch.
AI Transparency Institute - contact@aitransparencyinstitute.com

Every run:
  1. Scans three tiers of sources (EDGAR / press-release wires / FT + Google News).
  2. Groups articles about the same story into one candidate (other articles go
     into its "sources"), and flags stories already seen in an earlier run as
     follow-ups (state/stories.json).
  3. Writes candidates.json and DIGEST.md, and updates state/seen.json.
  4. Depending on config "auto_publish_mode":
       off    -> stops there. The workflow opens a GitHub issue for the curator,
                 who adds real deals to observatory-data.json by hand. (Default.)
       direct -> also adds candidates to observatory-data.json as PENDING REVIEW,
                 attaching them to an existing pending row about the same story.
     Any other value (including the old "pr") is treated as "off".
The machine NEVER assigns VERIFIED or REPORTED. Only a human curator does.

This is the only copy of the watcher: .github/workflows/watch.yml runs this file.
Edit config.json, not this file, to change terms, feeds or the publishing mode.
"""

import datetime
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse

import stories

CONFIG_PATH = os.environ.get("OBS_CONFIG", "config.json")
with open(CONFIG_PATH, encoding="utf-8") as _f:
    CONFIG = json.load(_f)
TODAY = datetime.date.today()
MAX_AGE = datetime.timedelta(days=CONFIG.get("max_age_days", 10))
STORY_MEMORY_DAYS = 60
# Feeds are untrusted: cap what one response may cost (bytes after decompression,
# and total seconds; requests' own timeout applies per read, not per response).
MAX_RESPONSE_BYTES = CONFIG.get("max_response_bytes", 5_000_000)
MAX_RESPONSE_SECONDS = 60
EDGAR_ADSH = re.compile(r"^\d{1,10}-\d{2}-\d{1,6}$")


# ---------------------------------------------------------------- relevance
def _term_rx(terms):
    """Whole-word, case-insensitive matcher. A plural "s"/"es" is allowed after
    each term; a trailing "*" in the config makes the term a prefix."""
    parts = []
    for t in terms:
        t = t.lower().strip()
        if t.endswith("*"):
            parts.append(re.escape(t[:-1]) + r"\w*")
        else:
            parts.append(re.escape(t) + r"(?:e?s)?")
    if not parts:
        return re.compile(r"(?!x)x")  # matches nothing
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)", re.I)


STRONG = _term_rx(CONFIG.get("strong_phrases", []))
TECH = _term_rx(CONFIG.get("tech_terms", []))
CONTEXT = _term_rx(CONFIG.get("context_terms", []))
FIN = _term_rx(CONFIG.get("finance_terms", []))
FIN_STRONG = _term_rx(CONFIG.get("strong_finance_terms", []))
EXCLUDE = _term_rx(CONFIG.get("exclude_terms", []))
DEAL_VERB = _term_rx(CONFIG.get("deal_verbs", []))
# A money amount: "$2.4B", "EUR 500m", "100 million". (Not "100,000 chips" or "58%".)
AMOUNT = re.compile(r"[$€£]\s?\d|\b(?:usd|eur|gbp)\s?\d|\d[\d,.]*\s?(?:bn|billion|million|mn)\b", re.I)
BLOCK = [b.lower() for b in CONFIG.get("blocked_sources", ["vinanet"])]


def has_deal_signal(text):
    """An amount or a deal verb (secures, closes, provides, leases, ...): what a
    report of a transaction has and an essay about GPU financing usually lacks."""
    return bool(AMOUNT.search(text) or DEAL_VERB.search(text))


def relevant(title, summary=""):
    """Return "strong", "combo" or None.

    strong: a strong phrase (e.g. "gpu-backed") in the title or summary.
    combo:  judged on the TITLE only, because feed summaries are long and noisy:
            a chip/GPU term plus any finance term, or a context term
            (nvidia, data center, ...) plus a collateral-type finance term.
    Either way the title must also carry a deal signal (has_deal_signal); for a
    strong match the summary may carry it instead.
    Titles matching an exclude term (e.g. "tokenized") are always dropped.
    """
    if EXCLUDE.search(title):
        return None
    if STRONG.search(title) or STRONG.search(summary):
        kind = "strong"
    elif TECH.search(title) and FIN.search(title):
        kind = "combo"
    elif CONTEXT.search(title) and FIN_STRONG.search(title):
        kind = "combo"
    else:
        return None
    if has_deal_signal(title) or (kind == "strong" and has_deal_signal(summary)):
        return kind
    return None


def blocked(*fields):
    text = " ".join(f or "" for f in fields).lower()
    return any(b in text for b in BLOCK)


def clean_text(s):
    """Strip tags, decode entities (&nbsp; etc.) and collapse whitespace.
    The site escapes every value, so decoded text is safe to store."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def entry_date(entry):
    """(is_recent, 'YYYY-MM-DD'). Undated entries are rejected: we cannot tell
    whether they are new, and old stories resurfacing was a source of noise."""
    for f in ("published_parsed", "updated_parsed"):
        tm = entry.get(f)
        if tm:
            d = datetime.date(tm.tm_year, tm.tm_mon, tm.tm_mday)
            return (TODAY - d) <= MAX_AGE, str(d)
    return False, None


# ---------------------------------------------------------------- collection
def http_get(url, params=None):
    """GET with the watcher's User-Agent, refusing responses larger than
    MAX_RESPONSE_BYTES or slower than MAX_RESPONSE_SECONDS. Returns bytes."""
    import requests
    deadline = time.monotonic() + MAX_RESPONSE_SECONDS
    with requests.get(url, params=params, headers={"User-Agent": CONFIG["user_agent"]},
                      timeout=30, stream=True) as r:
        r.raise_for_status()
        if int(r.headers.get("Content-Length") or 0) > MAX_RESPONSE_BYTES:
            raise ValueError("response too large")
        buf = bytearray()
        for chunk in r.iter_content(64 * 1024):
            buf += chunk
            if len(buf) > MAX_RESPONSE_BYTES:
                raise ValueError("response too large")
            if time.monotonic() > deadline:
                raise TimeoutError("response too slow")
        return bytes(buf)


def key(url, title):
    return hashlib.sha1((url or title).encode()).hexdigest()[:16]


class Watch:
    def __init__(self, seen):
        self.seen = set(seen)
        self.candidates = []
        self.stats = {}  # source -> [fetched, new, error]

    def add(self, tier, title, url, source, date, summary="", outlet=None):
        url = stories.safe_http_url(url)   # feed links are untrusted
        k = key(url, title)
        if k in self.seen:
            return False
        self.seen.add(k)
        date = (date or str(TODAY))[:10]
        self.candidates.append({
            "_tier": tier,
            "_summary": summary[:260],   # for the curator only; never published
            "date": date,
            "name": clean_text(title)[:180],
            "type": "To classify",
            "amount": "-",
            "terms": stories.NEUTRAL_TERMS,
            "status": "Auto-added - awaiting human verification",
            "ver": "PENDING REVIEW",
            "src": f"{source}, {date}",
            "url": url,
            "outlet": outlet or source,
        })
        return True

    def process_feed(self, feed, url, tier, source_label=None):
        """Filter parsed feed entries into candidates. Separate from the network
        fetch so it can be tested on fixture feeds."""
        new = 0
        src = source_label or feed.feed.get("title", urllib.parse.urlparse(url).netloc)
        for e in feed.entries[:60]:
            title = clean_text(e.get("title", ""))
            summary = clean_text(e.get("summary", ""))
            link = e.get("link", "")
            # Google News names the publisher in <source>; other feeds are the publisher.
            outlet = (e.get("source") or {}).get("title") or source_label or src
            if blocked(title, link, outlet):
                continue
            if not relevant(title, summary):
                continue
            ok, d = entry_date(e)
            if not ok:
                continue
            if self.add(tier, title, link, src, d, summary, outlet):
                new += 1
        self.stats[url] = [min(len(feed.entries), 60), new, None]

    def scan_feed(self, url, tier, source_label=None):
        import feedparser
        try:
            feed = feedparser.parse(http_get(url))
        except Exception as e:
            print(f"[warn] feed unreachable: {url} ({e})", file=sys.stderr)
            self.stats[url] = [0, 0, str(e)[:80]]
            return
        self.process_feed(feed, url, tier, source_label)

    # ---- EDGAR
    def process_edgar(self, results):
        """results: {query: [hits]}. One candidate per filing (accession number),
        whichever queries and documents matched it. Forms in
        config "edgar_exclude_forms" (fund prospectuses, merger filings, ...) are skipped."""
        exclude = {f.upper() for f in CONFIG.get("edgar_exclude_forms", [])}
        filings = {}
        for q, hits in results.items():
            for h in hits:
                s = h.get("_source", {})
                forms = {str(f).upper() for f in [s.get("form", "")] + list(s.get("root_forms") or [])}
                if forms & exclude:
                    continue
                adsh = str(s.get("adsh", ""))
                if not EDGAR_ADSH.match(adsh):   # it becomes part of a URL
                    continue
                f = filings.setdefault(adsh, {"s": s, "queries": []})
                if q not in f["queries"]:
                    f["queries"].append(q)
        new = 0
        for adsh, f in sorted(filings.items(), key=lambda kv: kv[1]["s"].get("file_date", "")):
            s = f["s"]
            cik = str((s.get("ciks") or [""])[0]).lstrip("0")
            cik = cik if cik.isdigit() else ""
            url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{adsh}-index.htm"
                   if cik else "https://www.sec.gov/edgar/search/#/q=" + urllib.parse.quote(adsh))
            filer = (s.get("display_names") or ["Unknown filer"])[0]
            name = f"{filer} - {s.get('form', '')} matching {' + '.join(f['queries'])}"
            if self.add(1, name, url, "SEC EDGAR", s.get("file_date"),
                        "EDGAR full-text match", outlet="sec.gov"):
                new += 1
        self.stats["EDGAR filings (after form filter, one per filing)"] = [len(filings), new, None]

    def scan_edgar(self):
        max_hits = CONFIG.get("edgar_max_hits", 200)
        results = {}
        for q in CONFIG.get("tier1_edgar_queries", []):
            label = "EDGAR: " + q
            hits, total = [], 0
            try:
                while len(hits) < max_hits:
                    r = http_get("https://efts.sec.gov/LATEST/search-index",
                                 params={"q": q, "dateRange": "custom", "from": len(hits),
                                         "startdt": str(TODAY - MAX_AGE), "enddt": str(TODAY)})
                    page = json.loads(r).get("hits", {})
                    total = (page.get("total") or {}).get("value", 0)
                    batch = page.get("hits", [])
                    hits += batch
                    if not batch or len(hits) >= total:
                        break
            except Exception as e:
                print(f"[warn] EDGAR query failed: {q} ({e})", file=sys.stderr)
                self.stats[label] = [len(hits), "-", str(e)[:80]]
            else:
                note = f"TRUNCATED at {len(hits)} of {total}" if total > len(hits) else None
                self.stats[label] = [len(hits), "-", note]
            results[q] = hits
        self.process_edgar(results)

    def run_sources(self):
        self.scan_edgar()
        gn = "https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en"
        for u in CONFIG.get("tier1_press_release_feeds", []):
            self.scan_feed(u, 1)
        for q in CONFIG.get("tier1_google_news_queries", []):
            self.scan_feed(gn.format(urllib.parse.quote(q)), 1)
        for u in CONFIG.get("tier2_ft_feeds", []):
            self.scan_feed(u, 2, "Financial Times")
        for q in CONFIG.get("tier2_google_news_queries", []):
            self.scan_feed(gn.format(urllib.parse.quote(q)), 2)
        for u in CONFIG.get("tier3_extra_rss", []):
            self.scan_feed(u, 3)


# ---------------------------------------------------------------- story grouping
def _is_filing(c):
    # EDGAR candidates are already one per filing, and their generated titles
    # look alike, so they are kept out of headline-based story grouping.
    return c.get("outlet") == "sec.gov"


def group_candidates(candidates):
    """One candidate per story. The best-sourced article leads; the others
    move into its "sources". The lead keeps the best tier of its group."""
    out = [c for c in candidates if _is_filing(c)]
    for g in stories.group([c for c in candidates if not _is_filing(c)]):
        head, _ = stories.merge_group(g)
        head["_tier"] = min(c["_tier"] for c in g)
        out.append(head)
    return sorted(out, key=lambda c: (c["_tier"], c["date"]))


def mark_followups(candidates, memory):
    """Flag candidates that continue a story from an earlier run (within the
    story window). Returns the updated memory to save in state/stories.json."""
    news = [c for c in candidates if not _is_filing(c)]
    for c in news:
        for m in memory:
            if stories.same_story(c, m):
                c["_followup_of"] = m
                break
    memory = memory + [{"date": c["date"], "name": c["name"], "id": stories.deal_id(c)}
                       for c in news if "_followup_of" not in c]
    cutoff = str(TODAY - datetime.timedelta(days=STORY_MEMORY_DAYS))
    return [m for m in memory if m.get("date", "") >= cutoff]


# ---------------------------------------------------------------- outputs
def _line(c):
    md = stories.md_safe
    url = stories.md_url(c.get("url"))
    title = f"[{md(c['name'])}]({url})" if url else md(c["name"])
    s = f"- **{md(c['date'])}** {title} - {md(c['outlet'])}"
    more = c.get("sources") or []
    if more:
        outlets = ", ".join(md(r["outlet"]) for r in more[:6]) + (" …" if len(more) > 6 else "")
        s += f" (+{len(more)} more: {outlets})"
    return s


def digest_lines(candidates):
    fresh = [c for c in candidates if "_followup_of" not in c]
    follow = [c for c in candidates if "_followup_of" in c]
    n_articles = sum(1 + len(c.get("sources") or []) for c in candidates)
    lines = [f"# Observatory watch digest - {TODAY}",
             f"{len(fresh)} new stor{'y' if len(fresh) == 1 else 'ies'}, {len(follow)} follow-up(s) "
             f"({n_articles} article(s)).", ""]
    names = {1: "Tier 1 - primary sources", 2: "Tier 2 - quality press", 3: "Tier 3 - alerts"}
    cur = None
    for c in fresh:
        if c["_tier"] != cur:
            cur = c["_tier"]
            lines += [f"## {names[cur]}", ""]
        lines += [_line(c)]
    if follow:
        lines += ["", "## Follow-ups to stories from earlier runs", ""]
        lines += [_line(c) + f" - continues: {stories.md_safe(c['_followup_of']['name'][:90])}" for c in follow]
    if not candidates:
        lines += ["_No new candidates this run._"]
    return lines


def publish_direct(candidates, path, tiers):
    """Add candidates to the site data as PENDING REVIEW. A candidate about the
    same story as an existing pending row is attached to that row's sources
    instead of becoming a new row. Returns the number of rows added."""
    try:
        with open(path, encoding="utf-8") as f:
            db = json.load(f)
    except Exception as e:
        print(f"[error] cannot read {path}: {e}", file=sys.stderr)
        return 0
    pending = [d for d in db.get("deals", []) if d.get("ver") == "PENDING REVIEW"]
    existing = {(d.get("name"), d.get("date")) for d in db.get("deals", [])}
    published = changed = 0
    for c in candidates:
        if c["_tier"] not in tiers or (c["name"], c["date"]) in existing:
            continue
        entry = {k: v for k, v in c.items() if not k.startswith("_")}
        entry["ver"] = "PENDING REVIEW"  # never anything else from code
        match = next((d for d in pending if stories.same_story(entry, d)), None)
        if match is not None:
            merged, _ = stories.merge_group(sorted([match, entry], key=stories.rank))
            merged["ver"] = "PENDING REVIEW"
            merged["id"] = match.get("id") or stories.deal_id(match)
            match.clear()
            match.update(merged)
            changed += 1
        else:
            entry["id"] = stories.deal_id(entry)
            db["deals"].append(entry)
            pending.append(entry)
            published += 1
        existing.add((c["name"], c["date"]))
    if published or changed:
        db["deals"].sort(key=lambda d: d["date"])
        pending_total = sum(1 for d in db["deals"] if d.get("ver") == "PENDING REVIEW")
        db["updated"] = (f"{TODAY} - auto-update by source watch - "
                         f"{pending_total} entr{'y' if pending_total == 1 else 'ies'} PENDING human review")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    return published


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def main():
    w = Watch(_load("state/seen.json", []))
    w.run_sources()
    candidates = group_candidates(w.candidates)
    memory = mark_followups(candidates, _load("state/stories.json", []))

    os.makedirs("state", exist_ok=True)
    with open("state/seen.json", "w") as f:
        json.dump(sorted(w.seen), f, indent=0)
    with open("state/stories.json", "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=1, ensure_ascii=False)
    with open("candidates.json", "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2, ensure_ascii=False)

    lines = digest_lines(candidates)
    mode = CONFIG.get("auto_publish_mode", "off")
    if mode not in ("off", "direct"):
        print(f"[warn] auto_publish_mode={mode!r} is not supported; treating it as 'off'", file=sys.stderr)
        mode = "off"
    published = 0
    if mode == "direct" and candidates:
        path = CONFIG["observatory_json_path"]
        published = publish_direct(candidates, path, set(CONFIG.get("auto_publish_tiers", [1])))
        lines += ["", f"**Direct mode: {published} new row(s) added to {path} as PENDING REVIEW. "
                      f"Verify each source, then set ver to VERIFIED or REPORTED, or delete the entry.**"]

    lines += ["", "## Source health (fetched / new / note)"]
    for u, (n_fetched, n_new, err) in w.stats.items():
        lines += [f"- {stories.md_safe(u[:90])}: {n_fetched} / {n_new}" + (f" / {stories.md_safe(err)}" if err else "")]
    with open("DIGEST.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{len(candidates)} stor(ies) from {len(w.candidates)} article(s); "
          f"{published} added to the site data (mode={mode})")


if __name__ == "__main__":
    main()
