"""
Shared helpers for the watcher, pre-validation and the pending-entry merge:
who reported a headline, what story it is about, and how to group duplicates.
Standard library only.
"""
import datetime
import hashlib
import re
import urllib.parse

# Order matters: specific names first, generic "Nvidia" last.
ENTITIES = [
    ("IREN", r"\biren\b"), ("Lambda", r"\blambda\b"), ("CoreWeave", r"coreweave"),
    ("Nebius", r"nebius"), ("Crusoe", r"\bcrusoe\b"), ("TeraWulf", r"terawulf"),
    ("Cipher", r"\bcipher (?:mining|digital)\b"), ("Fluidstack", r"fluidstack"),
    ("Applied Digital", r"applied digital"), ("Hut 8", r"\bhut 8\b"),
    ("WhiteFiber", r"whitefiber"), ("Sharon AI", r"sharon ai"),
    ("Bullish/USD.AI", r"usd\.ai|bullish"), ("Kamino/sUSDai", r"kamino|susdai"),
    ("Goldman/GSAM", r"gsam|goldman"), ("Blue Owl", r"blue owl"), ("Broadcom", r"broadcom"),
    ("xAI", r"\bxai\b"), ("Apollo", r"apollo"), ("Tencent/Oracle", r"tencent"),
    ("Nvidia", r"nvidia"),
]
ENTITY_RX = dict(ENTITIES)


def add_entities(issuers):
    """Add watched issuers from config.json ("issuers": [{name, aliases}]) that are
    not in ENTITIES yet, ahead of the generic "Nvidia". Idempotent."""
    known = {n.lower() for n, _ in ENTITIES}
    for i in issuers or []:
        name = str((i or {}).get("name", "")).strip()
        if not name or name.lower() in known:
            continue
        alts = [name] + [str(a) for a in (i.get("aliases") or []) if str(a).strip()]
        rx = r"(?<!\w)(?:" + "|".join(re.escape(a.lower()) for a in alts) + r")(?!\w)"
        ENTITIES.insert(len(ENTITIES) - 1 if ENTITIES[-1][0] == "Nvidia" else len(ENTITIES), (name, rx))
        ENTITY_RX[name] = rx
        known.add(name.lower())

SPAM = ["vinanet"]
PRIMARY = ["sec.gov", "sec edgar", "prnewswire", "pr newswire", "businesswire", "business wire",
           "globenewswire", "nvidianews", "blueowl.com", "coreweave.com", "apollo.com", "iren.com"]
RATING = ["moody", "s&p global", "fitch"]
PRESS1 = ["reuters", "bloomberg", "financial times", "ft.com", "wsj", "wall street journal"]
PRESS2 = ["techcrunch", "datacenterdynamics", "dcd", "the information", "9fin", "nikkei",
          "the register", "afr", "cnbc", "forbes"]
RANK = {"primary": 0, "rating": 0, "press1": 1, "press2": 2, "other": 3, "spam": 9}

NEUTRAL_TERMS = "Auto-detected; details to be completed after reading the source"
WINDOW_DAYS = 14


# ------------------------------------------------------------ facts in a title
def amount_musd(text):
    """Largest USD amount in the text, in millions; None if there is none."""
    # Korean won amounts ("100 billion won") are not USD; don't guess. Only a number
    # before "won" counts, so "Won't" in a headline is not mistaken for the currency.
    if re.search(r"\d[\d,.]*\s*(?:trillion|billion|million)?\s+won\b", text, re.I):
        return None
    mult = {"trillion": 1e6, "t": 1e6, "billion": 1e3, "bn": 1e3, "b": 1e3,
            "million": 1, "mm": 1, "mn": 1, "m": 1}
    vals = [float(m.group(1).replace(",", "")) * mult[m.group(2).lower()]
            for m in re.finditer(r"(?:\$\s?|\busd\s?)(\d[\d,]*\.?\d*)\s?(trillion|billion|million|bn|mm|mn|b|m|t)\b",
                                 text, re.I)]
    return max(vals) if vals else None


def entity_of(text):
    t = text.lower()
    for name, rx in ENTITIES:
        if re.search(rx, t):
            return name
    return None


# ------------------------------------------------------------ sources
def url_of(d):
    if d.get("url"):
        return d["url"]
    m = re.search(r"\[source link: (\S+?)\]", d.get("terms", ""))
    return m.group(1) if m else ""


def headline(title):
    """Title without the trailing " - Outlet" that Google News appends."""
    parts = title.rsplit(" - ", 1)
    return parts[0].strip() if len(parts) == 2 and len(parts[1]) <= 60 else title.strip()


def outlet_of(d):
    if d.get("outlet"):
        return d["outlet"]
    url, src, name = url_of(d), d.get("src", ""), d.get("name", "")
    if "ft.com" in url or src.lower().startswith("financial times"):
        return "Financial Times"
    if src.startswith("SEC EDGAR"):
        return "sec.gov"
    if "news.google.com" in url or not url:
        return name.rsplit(" - ", 1)[-1].strip() if " - " in name else src.split(",")[0]
    return urllib.parse.urlparse(url).netloc.replace("www.", "")


def tier_of(outlet):
    o = (outlet or "").lower()
    for tier, names in (("spam", SPAM), ("primary", PRIMARY), ("rating", RATING),
                        ("press1", PRESS1), ("press2", PRESS2)):
        if any(n in o for n in names):
            return tier
    return "other"


def source_ref(d):
    """Compact reference to one article, as stored in an entry's "sources" list."""
    return {"outlet": outlet_of(d), "url": url_of(d), "date": d.get("date", ""),
            "title": headline(d.get("name", ""))}


def deal_id(d):
    return "d" + hashlib.sha1(f"{d.get('date')}|{d.get('name')}".encode()).hexdigest()[:10]


# ------------------------------------------------------------ story grouping
STOP = set("the a an of for to in on as and with by is its it from at into via after amid "
           "new says say report reports reportedly".split())


def tokens(title):
    return {w for w in re.findall(r"[a-z0-9$.]+", headline(title).lower().replace("’", "'"))
            if w not in STOP and len(w) > 1}


def story_key(d):
    name = d.get("name", "")
    e, a = entity_of(name), amount_musd(name)
    return (e, round(a)) if e and a else None


def _date(s):
    m = re.match(r"(\d{4})-(\d{2})(?:-(\d{2}))?", s or "")
    if not m:
        return None
    return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3) or 1))


def same_story(a, b, window_days=WINDOW_DAYS):
    """Dated within the window of each other, and one of:
    - same company and same USD amount (within 2%; not for the generic "Nvidia");
    - titles sharing at least half their words;
    - same named company (not the generic "Nvidia"), dated within 3 days,
      and titles sharing at least 30% of their words (reworded headlines)."""
    da, db = _date(a.get("date")), _date(b.get("date"))
    if da and db and abs((da - db).days) > window_days:
        return False
    ka, kb = story_key(a), story_key(b)
    if ka and ka == kb:
        return True
    if ka and kb and ka[0] == kb[0] and ka[0] != "Nvidia" and abs(ka[1] - kb[1]) <= 0.02 * max(ka[1], kb[1]):
        return True   # "$1 billion" and "$1.008 billion" from the same company
    ta, tb = tokens(a.get("name", "")), tokens(b.get("name", ""))
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / len(ta | tb)
    if overlap >= 0.5:
        return True
    ea = entity_of(a.get("name", ""))
    return (overlap >= 0.3 and ea not in (None, "Nvidia") and ea == entity_of(b.get("name", ""))
            and da is not None and db is not None and abs((da - db).days) <= 3)


def rank(d):
    """Sort key: best source tier first, then earliest date."""
    return (RANK[tier_of(outlet_of(d))], d.get("date", ""))


def group(items, window_days=WINDOW_DAYS):
    """Group items into stories. An item joins the first group that has any
    member it matches. Each group is returned sorted best source first."""
    groups = []
    for it in items:
        for g in groups:
            if any(same_story(it, m, window_days) for m in g):
                g.append(it)
                break
        else:
            groups.append([it])
    return [sorted(g, key=rank) for g in groups]


def merge_group(g, blocked=()):
    """Collapse a group (best first) into its first item, moving the others into
    its "sources" list. Articles from blocked outlets are dropped when the group
    has any other outlet. Returns (entry, n_dropped)."""
    def is_blocked(d):
        o = (outlet_of(d) + " " + d.get("name", "")).lower()
        return any(b in o for b in blocked)

    keep = [d for d in g if not is_blocked(d)] or g
    dropped = len(g) - len(keep)
    head = dict(keep[0])
    refs = list(head.get("sources") or [])
    for d in keep[1:]:
        refs += [source_ref(d)] + list(d.get("sources") or [])
    seen, uniq = {url_of(head)}, []
    for r in sorted(refs, key=lambda r: r.get("date", "")):
        if r.get("url") and r["url"] not in seen:
            seen.add(r["url"])
            uniq.append(r)
    if uniq:
        head["sources"] = uniq
    return head, dropped


_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]<>()!|~])")


def md_safe(s):
    """Text for GitHub markdown (issue bodies). Feed headlines are untrusted, so:
    no line breaks, markdown and HTML characters backslash-escaped (no injected
    links, images or tags), and a zero-width space after "@" and "#" so a
    headline cannot @mention people or cross-reference other issues."""
    s = _MD_SPECIAL.sub(r"\\\1", re.sub(r"\s+", " ", str(s)))
    return s.replace("@", "@\u200b").replace("#", "#\u200b")


def safe_http_url(u):
    """The URL if it is an absolute http(s) URL without whitespace or control
    characters, else "". Applied to every link taken from a feed."""
    u = str(u or "").strip()
    if not re.match(r"https?://[^/\s]", u, re.I) or re.search(r"[\x00-\x20\x7f]", u):
        return ""
    return u


def md_url(u):
    """A link destination for GitHub markdown, or "" if the URL is not http(s).
    Characters that could end the destination or start markup are percent-encoded."""
    u = safe_http_url(u)
    return urllib.parse.quote(u, safe="/:?&=#%~+,;$'*@![]-._") if u else ""
