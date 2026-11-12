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


def _max_age_days():
    """config max_age_days, or OBS_MAX_AGE_DAYS for a one-off backfill run
    (e.g. after the watch was paused). Clamped to 1..365."""
    raw = os.environ.get("OBS_MAX_AGE_DAYS", "").strip()
    try:
        days = int(raw) if raw else int(CONFIG.get("max_age_days", 10))
    except ValueError:
        print(f"[warn] OBS_MAX_AGE_DAYS={raw!r} is not a number; using config", file=sys.stderr)
        days = int(CONFIG.get("max_age_days", 10))
    return max(1, min(days, 365))


MAX_AGE = datetime.timedelta(days=_max_age_days())
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
MARKET = _term_rx(CONFIG.get("market_terms", []))
DEAL_VERB = _term_rx(CONFIG.get("deal_verbs", []))
STRESS = _term_rx(CONFIG.get("stress_terms", []))


def _issuer_rx(issuers, case_sensitive):
    """Names and aliases of watched issuers ("generic" ones such as Nvidia excluded:
    Nvidia headlines go through the narrower context-term rule)."""
    names = [n for i in issuers if not i.get("generic") and bool(i.get("match_case")) == case_sensitive
             for n in [i.get("name", "")] + list(i.get("aliases") or []) if n and "/" not in n]
    if not names:
        return re.compile(r"(?!x)x")
    alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return re.compile(r"(?<!\w)(?:" + alt + r")(?:'s|’s)?(?!\w)", 0 if case_sensitive else re.I)


ISSUERS = [i for i in CONFIG.get("issuers", []) if isinstance(i, dict)]
_ISSUER_I, _ISSUER_CS = _issuer_rx(ISSUERS, False), _issuer_rx(ISSUERS, True)
stories.add_entities(ISSUERS)


def issuer_in(text):
    return bool(_ISSUER_I.search(text) or _ISSUER_CS.search(text))


# A money amount: "$2.4B", "EUR 500m", "¥50bn", "Rs 4,000 crore", "100 million".
# (Not "100,000 chips" or "58%".)
AMOUNT = re.compile(r"[$€£¥₹]\s?\d|\b(?:usd|us\$|eur|gbp|jpy|inr|rs\.?)\s?\d"
                    r"|\d[\d,.]*\s?(?:bn|billion|million|mn|trillion|crore)\b", re.I)
BLOCK = [b.lower() for b in CONFIG.get("blocked_sources", ["vinanet"])]


def has_deal_signal(text):
    """An amount or a deal verb (secures, closes, provides, leases, ...): what a
    report of a transaction has and an essay about GPU financing usually lacks."""
    return bool(AMOUNT.search(text) or DEAL_VERB.search(text))


def is_stress(title):
    """A stress term (default, seized, downgrade, covenant, ...) next to a chip or
    watched-issuer term and a finance term, all in the title."""
    chipish = TECH.search(title) or issuer_in(title) or STRONG.search(title)
    finance = FIN.search(title) or STRONG.search(title)
    return bool(STRESS.search(title) and chipish and finance)


def relevant(title, summary=""):
    """Return "stress", "strong", "combo" or None.

    stress: see is_stress(). Kept without a deal signal: defaults, seizures and
            downgrades are what the observatory exists to catch.
    strong: a strong phrase (e.g. "gpu-backed") in the title or summary.
    combo:  judged on the TITLE only, because feed summaries are long and noisy:
            a chip/GPU term or a watched issuer (config "issuers") plus any finance
            term, or a context term (nvidia, data center, ...) plus a
            collateral-type finance term.
    strong and combo also need a deal signal in the title (has_deal_signal); for
    a strong match the summary may carry it instead.
    Titles matching an exclude term (e.g. "tokenized") are always dropped;
    combo titles matching a market term (stock, shares, earnings, ...) too.
    """
    if EXCLUDE.search(title):
        return None
    if is_stress(title):
        return "stress"
    if STRONG.search(title) or STRONG.search(summary):
        kind = "strong"
    elif (TECH.search(title) or issuer_in(title)) and FIN.search(title):
        kind = "combo"
    elif CONTEXT.search(title) and FIN_STRONG.search(title):
        kind = "combo"
    else:
        return None
    if kind == "combo" and MARKET.search(title):
        return None   # stock-market chatter, not a financing
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
        self.filings = {}  # accession number -> candidate added this run

    def add(self, tier, title, url, source, date, summary="", outlet=None, signal=None):
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
        if signal == "stress":
            self.candidates[-1]["_signal"] = "stress"
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
            kind = relevant(title, summary)
            if not kind:
                continue
            ok, d = entry_date(e)
            if not ok:
                continue
            if self.add(tier, title, link, src, d, summary, outlet, signal=kind):
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
        allow = {f.upper() for f in CONFIG.get("edgar_fulltext_forms", [])}
        min_other = int(CONFIG.get("edgar_min_queries_other_forms", 1))
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
        if allow:   # other forms need several distinct query matches
            filings = {a: f for a, f in filings.items()
                       if str(f["s"].get("form", "")).upper() in allow or len(f["queries"]) >= min_other}
        new = 0
        for adsh, f in sorted(filings.items(), key=lambda kv: kv[1]["s"].get("file_date", "")):
            s = f["s"]
            if adsh in self.filings:   # already listed by the issuer scan: note the match
                c = self.filings[adsh]
                c["name"] = (c["name"] + " - full text matches " + " + ".join(f["queries"]))[:180]
                continue
            cik = str((s.get("ciks") or [""])[0]).lstrip("0")
            cik = cik if cik.isdigit() else ""
            url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{adsh}-index.htm"
                   if cik else "https://www.sec.gov/edgar/search/#/q=" + urllib.parse.quote(adsh))
            filer = (s.get("display_names") or ["Unknown filer"])[0]
            name = f"{filer} - {s.get('form', '')} matching {' + '.join(f['queries'])}"
            if self.add(1, name, url, "SEC EDGAR", s.get("file_date"),
                        "EDGAR full-text match", outlet="sec.gov"):
                self.filings[adsh] = self.candidates[-1]
                new += 1
        self.stats["EDGAR filings (after form filter, one per filing)"] = [len(filings), new, None]

    # ---- EDGAR, per watched issuer
    ITEM_NAMES = {"1.01": "material agreement", "1.02": "agreement terminated",
                  "2.03": "new financial obligation", "2.04": "acceleration / default",
                  "2.06": "impairment"}
    STRESS_ITEMS = {"2.04", "2.06"}

    def process_issuer_filings(self, issuer, data):
        """data: the company's https://data.sec.gov/submissions/CIK##########.json.
        Adds one candidate per filing in the window that is an 8-K with an item in
        config "edgar_8k_items" (financing agreements, defaults, impairments) or a
        periodic report (its debt note lists every facility). Skips the company if
        EDGAR's name for the CIK does not match the configured name (a wrong cik)."""
        label = "EDGAR filings: " + issuer.get("name", "?")
        flat = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
        names = [issuer.get("name", "")] + list(issuer.get("aliases") or [])
        edgar_name = str(data.get("name", ""))
        if not any(flat(n) and flat(n) in flat(edgar_name) for n in names):
            self.stats[label] = [0, 0, f"cik name mismatch: EDGAR says {edgar_name[:40]!r}; check config"]
            return
        cik = str(data.get("cik") or issuer.get("cik") or "").lstrip("0")
        if not cik.isdigit():
            self.stats[label] = [0, 0, "bad cik"]
            return
        items_wanted = set(CONFIG.get("edgar_8k_items", ["1.01", "2.03", "2.04"]))
        periodic = {f.upper() for f in CONFIG.get("edgar_periodic_forms", ["10-K", "10-Q"])}
        registration = {f.upper() for f in CONFIG.get("edgar_registration_forms", [])}
        recent = (data.get("filings") or {}).get("recent") or {}
        col = lambda k: list(recent.get(k) or [])
        rows = zip(col("accessionNumber"), col("filingDate"), col("form"),
                   col("items") or [""] * len(col("form")))
        cutoff = str(TODAY - MAX_AGE)
        n_window = new = 0
        for adsh, fdate, form, items in rows:
            adsh, fdate, form = str(adsh), str(fdate)[:10], str(form).upper()
            if fdate < cutoff or not EDGAR_ADSH.match(adsh):
                continue
            item_set = {i.strip() for i in str(items or "").split(",") if i.strip()}
            if form in ("8-K", "8-K/A"):
                hit = sorted(item_set & items_wanted)
                if not hit:
                    continue
                what = ", ".join(f"{i} {self.ITEM_NAMES.get(i, '')}".strip() for i in hit)
            elif form in periodic:
                what = "periodic report: check the debt note" if form != "6-K" else "foreign issuer report"
            elif form in registration:
                what = "registration statement: check the debt section"
            else:
                continue
            n_window += 1
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{adsh}-index.htm"
            name = f"{edgar_name} - {form} ({what})"
            signal = "stress" if item_set & self.STRESS_ITEMS else None
            if self.add(1, name, url, "SEC EDGAR", fdate, "EDGAR filing list", outlet="sec.gov", signal=signal):
                self.filings[adsh] = self.candidates[-1]
                new += 1
        self.stats[label] = [n_window, new, None]

    def scan_edgar_issuers(self):
        for issuer in ISSUERS:
            cik = issuer.get("cik")
            if not isinstance(cik, int) or cik <= 0:
                continue
            try:
                data = json.loads(http_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"))
            except Exception as e:
                print(f"[warn] EDGAR filing list failed: {issuer.get('name')} ({e})", file=sys.stderr)
                self.stats["EDGAR filings: " + str(issuer.get("name"))] = [0, 0, str(e)[:80]]
                continue
            self.process_issuer_filings(issuer, data)
            time.sleep(0.2)   # SEC fair access: well under 10 requests per second

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
        self.scan_edgar_issuers()   # first, so its clearer titles lead for shared filings
        self.scan_edgar()
        for u in CONFIG.get("tier1_press_release_feeds", []):
            self.scan_feed(u, 1)
        for q in CONFIG.get("tier1_google_news_queries", []):
            self.scan_feed(google_news_url(q), 1)
        for u in CONFIG.get("tier2_ft_feeds", []):
            self.scan_feed(u, 2, "Financial Times")
        for ed in google_news_editions():
            for q in CONFIG.get("tier2_google_news_queries", []):
                self.scan_feed(google_news_url(q, ed), 2)
                time.sleep(1)   # be gentle with Google News
        for u in CONFIG.get("tier3_extra_rss", []):
            self.scan_feed(u, 3)


US_EDITION = {"hl": "en-US", "gl": "US", "ceid": "US:en"}
_EDITION_OK = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z]{2,4})?(?::[A-Za-z-]{2,8})?$")


def google_news_editions():
    """Editions from config "google_news_editions" (well-formed ones only), else en-US."""
    eds = [e for e in CONFIG.get("google_news_editions") or [] if isinstance(e, dict)
           and all(_EDITION_OK.match(str(e.get(k, ""))) for k in ("hl", "gl", "ceid"))]
    return eds or [US_EDITION]


def google_news_url(query, edition=US_EDITION):
    return ("https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": edition["hl"], "gl": edition["gl"], "ceid": edition["ceid"]}))


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
        if any(c.get("_signal") == "stress" for c in g):
            head["_signal"] = "stress"
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
    stress = [c for c in candidates if c.get("_signal") == "stress"]
    fresh = [c for c in candidates if "_followup_of" not in c and c.get("_signal") != "stress"]
    follow = [c for c in candidates if "_followup_of" in c and c.get("_signal") != "stress"]
    n_articles = sum(1 + len(c.get("sources") or []) for c in candidates)
    lines = [f"# Observatory watch digest - {TODAY}",
             f"{len(fresh)} new stor{'y' if len(fresh) == 1 else 'ies'}, {len(follow)} follow-up(s), "
             f"{len(stress)} stress signal(s) ({n_articles} article(s)). Window: {MAX_AGE.days} days.", ""]
    if stress:
        lines += ["## Stress signals (defaults, seizures, downgrades, impairments)", ""]
        lines += [_line(c) for c in stress] + [""]
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
