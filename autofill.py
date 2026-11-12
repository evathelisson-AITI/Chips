"""
First-guess values for the curator's deal form, so a lead opens filled in and the
curator only checks it against the source and picks VERIFIED or REPORTED.

Guesses come from what the watch already collected: the lead's headline, the
headlines of the other articles in its story ("sources"), the feed excerpt
(`_summary`, read for facts but never copied), and notes in primary_hints.json.
Nothing here is published by itself: the values only prefill the form, every
guessed field is reported in "_auto" so the page can mark it, and `ver` is never
guessed (AGENTS.md: only a human curator sets it). The generated `terms` text is
composed from the extracted facts, not copied from feed text.

Standard library only.
"""
import json
import os
import re
from collections import Counter

import stories

ROOT = os.path.dirname(os.path.abspath(__file__))

DEFAULT_LENDERS = [
    "Blackstone", "Magnetar", "Blue Owl", "Apollo", "Macquarie", "Goldman Sachs", "GSAM", "JPMorgan",
    "J.P. Morgan", "Morgan Stanley", "MUFG", "Brookfield", "KKR", "BlackRock", "Carlyle", "Ares", "PIMCO",
    "Citi", "Citigroup", "Bank of America", "Wells Fargo", "Deutsche Bank", "Barclays", "BNP Paribas",
    "Mizuho", "SMBC", "HSBC", "Natixis", "Fortress", "Upper90", "Hercules", "TFC", "Bullish", "Oaktree",
    "Sixth Street", "HPS", "Antares", "Golub", "MidCap", "Silver Point", "PGIM", "Athene", "Valor", "NBSF",
]
GPU_RX = re.compile(r"\b(Vera Rubin|GB300|GB200|B300|B200|H200|H100|H20|MI355X|MI325X|MI300X|Blackwell|Hopper|Rubin|TPU)s?\b",
                    re.I)
COLLATERAL_RX = re.compile(r"gpu-backed|chip-backed|gpu-collateralized|collateral|gpu financing|gpu loans?"
                           r"|secured by (?:nvidia )?(?:gpus|chips)"
                           r"|against (?:nvidia )?(?:gpus|chips)|(?:gpus|chips) as collateral", re.I)
NEGATED_RX = re.compile(r"collateral not confirmed|not (?:secured|collateralized|collateralised)|unconfirmed", re.I)
# Not "Tencent leases 100,000 chips from Oracle": renting cloud capacity is not a chip-lease vehicle.
SPV_RX = re.compile(r"\bspv\b|leaseback|lease back|lease (?:the )?chips back|chip-lease|special purpose vehicle", re.I)
ABS_RX = re.compile(r"securiti[sz]ation|\babs\b|asset-backed", re.I)
VENDOR_RX = re.compile(r"letter of intent|\bloi\b|\bmous?\b|intent to invest|invests? up to", re.I)
NOTES_RX = re.compile(r"\bnotes\b|\bbonds?\b", re.I)
LOAN_RX = re.compile(r"\bloans?\b|facility|\bdebt\b|financing|credit|\bddtl\b|delayed draw|borrow", re.I)
PLANNED_RX = re.compile(r"\b(?:plans?|planning|eyes|eyeing|explores?|exploring|in talks|seeks?|seeking|considers?|weighs?|"
                        r"mulls?|nears|lines up|lining up|prepares?|preparing|marketing|to raise|to borrow|in preparation|"
                        r"not closed|reportedly|begins)\b", re.I)
CLOSED_RX = re.compile(r"\b(?:closes|closed|completes|completed|secures|secured|raises|raised|lands|landed|inks|inked|"
                       r"obtains|obtained|borrows|borrowed|upsizes|upsized|refinances|refinanced)\b", re.I)
ANNOUNCED_RX = re.compile(r"\b(?:announces|enters into|signs|agrees|provides|leads|led|backs|commits|launches|prices|priced)\b",
                          re.I)
UP_TO_RX = re.compile(r"\bup to\b", re.I)
RATE_RX = re.compile(r"\bSOFR\s*\+\s*\d+(?:\.\d+)?\s*(?:%|bps)?|\b\d{1,2}(?:\.\d{1,3})?%(?=\s+(?:senior |secured |fixed )*"
                     r"(?:notes|coupon|interest|bonds?|loan))", re.I)
MATURITY_RX = re.compile(r"\b(\d{1,2})-year\b|\bdue (20\d\d)\b", re.I)
AGENCY_RX = re.compile(r"moody|s&p|fitch|kbra|dbrs", re.I)
MOODYS_RX = re.compile(r"\b(Aaa|Aa[1-3]|A[1-3]|Baa[1-3]|Ba[1-3]|B[1-3]|Caa[1-3])\b")
SPLIT_RATING_RX = re.compile(r"\b(Aaa|Aa[1-3]|A[1-3]|Baa[1-3]|Ba[1-3]|B[1-3])\s*/\s*(AAA|AA[+-]?|A[+-]?|BBB[+-]?|BB[+-]?|B[+-]?)"
                             r"(?!\w)")
SP_RX = re.compile(r"(?<![\w-])(AAA|AA[+-]?|BBB[+-]?|BB[+-]?|A[+-]|B[+-]|CCC[+-]?)(?![\w])")
EDGAR_NAME_RX = re.compile(r"^(?P<filer>.+?)(?: \([^)]*\))* - (?P<form>[\w/-]+)(?: \((?P<what>[^)]*)\))?")
OUTLET_NAMES = {"prnewswire.com": "PR Newswire", "businesswire.com": "Business Wire",
                "globenewswire.com": "GlobeNewswire", "sec.gov": "SEC filing", "nvidianews.nvidia.com": "Nvidia newsroom"}
NAME_PHRASE = {"Securitization": "GPU-backed securitization", "Chip-lease SPV": "chip-lease vehicle",
               "GPU-backed loan": "GPU-backed loan", "Bond / Loan": "debt financing",
               "Vendor commitment": "vendor commitment"}
TYPE_PHRASE = {"Securitization": "GPU-backed securitization", "Chip-lease SPV": "Chip-lease vehicle",
               "GPU-backed loan": "GPU-backed debt facility", "Bond / Loan": "Debt financing",
               "Vendor commitment": "Vendor commitment"}


def known_lenders(config_path=None):
    """config.json "known_lenders" if set, else the default list."""
    path = config_path or os.environ.get("OBS_CONFIG") or os.path.join(ROOT, "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            names = json.load(f).get("known_lenders")
        if isinstance(names, list) and names:
            return [str(n) for n in names if str(n).strip()]
    except Exception:
        pass
    return DEFAULT_LENDERS


def matching_hints(d, hints):
    """primary_hints.json entries about the same company and (if both have one) amount."""
    name = d.get("name", "")
    ent, amt = stories.entity_of(name), stories.amount_musd(name)
    out = []
    for h in hints or []:
        if not isinstance(h, dict) or not ent or h.get("entity") != ent:
            continue
        ha = h.get("amount_musd")
        if amt and ha:
            if abs(ha - amt) / max(ha, amt) > 0.05:
                continue
        elif ent == "Nvidia" or ha:   # without an amount, only a company-specific, amount-free hint fits
            continue
        out.append(h)
    return out


def _titles(d):
    return [stories.headline(d.get("name", ""))] + [str(s.get("title", "")) for s in d.get("sources") or []
                                                   if isinstance(s, dict)]


def _entity_display(ent):
    if not ent:
        return ent
    return "USD.AI" if ent == "Bullish/USD.AI" else ent.split("/")[0]


def _pick_amount(titles):
    """The amount most headlines agree on (ties: the lead headline's)."""
    vals = [round(a, 1) for a in (stories.amount_musd(t) for t in titles) if a]
    if not vals:
        return None
    best = Counter(vals).most_common()
    top = [v for v, n in best if n == best[0][1]]
    lead = stories.amount_musd(titles[0])
    return round(lead, 1) if lead and round(lead, 1) in top else top[0]


def _fmt_m(musd):
    return f"{musd:,.0f} M" if musd >= 10 else f"{musd:,.1f} M"


def _fmt_usd(musd):
    if musd >= 1000:
        return f"USD {round(musd / 1000, 3):,g}bn"
    return f"USD {musd:,.0f}m"


def _dates(d):
    ds = [d.get("date", "")] + [str(s.get("date", "")) for s in d.get("sources") or [] if isinstance(s, dict)]
    return sorted(x for x in ds if re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", x))


def _lenders(text, lenders, borrower):
    found = []
    for name in lenders:
        if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.I) and name.lower() != (borrower or "").lower():
            canon = "Goldman Sachs" if name in ("GSAM",) else name
            if canon not in found:
                found.append(canon)
    for m in re.finditer(r"\bled by ([A-Z][\w&.]*(?: [A-Z][\w&.]*){0,2})|\b([A-Z][\w&.]*(?: [A-Z][\w&.]*){0,2})-led\b", text):
        name = (m.group(1) or m.group(2)).strip()
        if name.lower() != (borrower or "").lower() and not any(name.lower() in f.lower() or f.lower() in name.lower()
                                                                for f in found):
            found.append(name)
    return found[:4]


def _borrower(headline, lenders):
    """The company that borrows: the watched issuer in the headline, unless that is a
    lender (then whoever the money is "for" / "provided" to)."""
    ent = stories.entity_of(headline)
    lender_hit = ent and any(l.lower() in ent.lower() for l in lenders)
    if ent and not lender_hit:
        return _entity_display(ent)
    name = r"([A-Z][\w.&-]*(?: [A-Z][\w.&-]*)?)"
    for verb in (r"(?i:provides?|backs?|lends? to)", r"(?i:for)", r"(?i:to)"):
        m = re.search(r"\b" + verb + " " + name, headline)
        if m and not re.match(r"(?i)gpu|chip|ai\b|loans?\b", m.group(1)):
            return m.group(1)
    return _entity_display(ent)


def _rating(text):
    m = SPLIT_RATING_RX.search(text)
    if m:
        return f"{m.group(1)} / {m.group(2)}"
    if not AGENCY_RX.search(text):
        return "investment grade (reported)" if re.search(r"investment[- ]grade", text, re.I) else ""
    agency = AGENCY_RX.search(text).group(0)
    m = MOODYS_RX.search(text) if agency.lower() == "moody" else None
    if m:
        return f"{m.group(1)} (Moody's)"
    m = SP_RX.search(text)
    if m:
        return f"{m.group(1)} ({ {'s&p': 'S&P', 'fitch': 'Fitch', 'kbra': 'KBRA', 'dbrs': 'DBRS'}.get(agency.lower(), agency) })"
    return ""


def _domain(url):
    return re.sub(r"^www\.", "", re.sub(r"^https?://([^/?#]+).*", r"\1", url))


def _source_and_url(d, hint_list):
    """Best link and its "Source" label and date. Known sources (primary_hints.json)
    and primary-tier articles in the story replace the lead's own link when they
    rank higher (primary > rating > Reuters/Bloomberg/FT > trade press > other)."""
    lead_url = stories.safe_http_url(stories.url_of(d))
    best = (stories.RANK[stories.tier_of(stories.outlet_of(d))], lead_url, stories.outlet_of(d), None)
    options = []
    for h in hint_list:
        u = stories.safe_http_url(h.get("url", ""))
        if u and h.get("tier") in stories.RANK:
            note = str(h.get("note", ""))
            m = re.search(r"\d{4}-\d{2}-\d{2}", note)
            first = re.split(r"[,;:]| via ", note)[0].strip()
            label = first if ("press release" in note.lower() or stories.tier_of(first) != "other") and first \
                else OUTLET_NAMES.get(_domain(u), _domain(u))
            options.append((stories.RANK[h["tier"]], u, label, m.group(0) if m else None))
    for s in d.get("sources") or []:
        u = stories.safe_http_url(s.get("url", "")) if isinstance(s, dict) else ""
        if u and "news.google.com" not in u:
            options.append((stories.RANK[stories.tier_of(stories.outlet_of(s))], u, stories.outlet_of(s), s.get("date")))
    for opt in sorted(options, key=lambda o: o[0]):
        if opt[0] < best[0]:
            best = opt
        break
    return best[1], best[2], best[3]


def _src_date(date):
    m = re.fullmatch(r"(\d{4})-(\d{2})(?:-(\d{2}))?", date or "")
    if not m:
        return date or ""
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m.group(3) else f"{m.group(2)}/{m.group(1)}"


def guess_filing(d):
    """A lead from the EDGAR scan ("Filer - 8-K (1.01 material agreement, ...)")."""
    m = EDGAR_NAME_RX.match(d.get("name", ""))
    if not m:
        return {}
    filer = re.sub(r",? (?:Inc\.?|Corp\.?|Ltd\.?|plc|N\.V\.|Holdings Inc\.?)(?:/\w+)?$", "", m.group("filer")).strip()
    form, what = m.group("form"), (m.group("what") or "").strip()
    date = d.get("date", "")
    out = {
        "name": f"{filer} {form}: {what}" if what else f"{filer} {form}",
        "date": date,
        "status": "Announced" if form.startswith("8-K") else "Outstanding",
        "terms": f"Disclosed in {filer}'s {form}" + (f" ({what})" if what else "") +
                 ". Amount, lenders and collateral to be read from the filing.",
        "src": f"{filer} {form}, {_src_date(date)}",
        "url": stories.safe_http_url(stories.url_of(d)),
    }
    if re.search(r"2\.03|financial obligation", what):
        out["type"] = "Bond / Loan"
    if len(date) == 10:
        out["announced"] = date
    return out


def guess(d, hints=(), lenders=None):
    """Field -> guessed value, for every field we have evidence for."""
    if stories.outlet_of(d) == "sec.gov":
        return guess_filing(d)
    lenders = lenders or known_lenders()
    titles = _titles(d)
    hint_list = matching_hints(d, hints)
    notes = " ".join(str(h.get("note", "")) for h in hint_list)
    own_terms = "" if d.get("terms") == stories.NEUTRAL_TERMS else str(d.get("terms", ""))
    text = " ".join(titles + [str(d.get("_summary", "")), notes, own_terms])
    head = titles[0]
    out = {"name": head}

    dates = _dates(d)
    if dates:
        out["date"] = dates[0]
        if len(dates[0]) == 10:
            out["announced"] = dates[0]

    musd = _pick_amount(titles)
    up_to = bool(UP_TO_RX.search(head))
    if musd:
        out["amount"] = ("up to " if up_to else "") + _fmt_m(musd)
        out["amount_musd"] = f"{musd:g}"

    if ABS_RX.search(text):
        typ = "Securitization"
    elif SPV_RX.search(text):
        typ = "Chip-lease SPV"
    elif VENDOR_RX.search(text) and not LOAN_RX.search(head):
        typ = "Vendor commitment"
    elif COLLATERAL_RX.search(text) and not NEGATED_RX.search(text):
        typ = "GPU-backed loan"
    elif NOTES_RX.search(head) or LOAN_RX.search(text):
        typ = "Bond / Loan"
    else:
        typ = ""
    if typ:
        out["type"] = typ

    if NEGATED_RX.search(text):
        collateral = ""
    elif typ == "Chip-lease SPV":
        collateral = "spv-owned-leased"
    elif typ == "Vendor commitment":
        collateral = "none-or-unclear"
    elif COLLATERAL_RX.search(text):
        collateral = "gpu-lien"
    else:
        collateral = ""
    if collateral:
        out["collateral"] = collateral

    status_text = head + " " + notes
    if PLANNED_RX.search(status_text):
        out["status"] = "In preparation"
    elif CLOSED_RX.search(status_text):
        out["status"] = "Closed"
        if out.get("announced"):
            out["closed"] = out["announced"]
    elif ANNOUNCED_RX.search(status_text):
        out["status"] = "Announced"
    else:
        out["status"] = "Reported"   # press coverage without a clear verb
    if not musd:
        out["amount"] = "Undisclosed"
    if musd and (up_to or out.get("status") in ("Closed", "Announced")):
        out["amount_kind"] = "up-to" if up_to else "committed"

    found_lenders = _lenders(text, lenders, None)
    borrower = _borrower(head, lenders)
    found_lenders = [l for l in found_lenders if l.lower() != (borrower or "").lower()]
    if found_lenders:
        out["lenders"] = ", ".join(found_lenders)
    gpus = list(dict.fromkeys(g.group(1) for g in GPU_RX.finditer(text)))
    if gpus:
        out["gpu_generation"] = ", ".join(gpus)
    m = RATE_RX.search(text)
    if m:
        out["rate"] = re.sub(r"\s+", "", m.group(0)) if m.group(0).upper().startswith("SOFR") else m.group(0)
    m = MATURITY_RX.search(text)
    if m:
        out["maturity"] = f"{m.group(1)}y" if m.group(1) else m.group(2)
    rating = _rating(text)
    if rating:
        out["rating"] = rating
    if re.search(r"nvidia", text, re.I):
        if re.search(r"nvidia[- ](?:as )?anchor|anchor(?:ed)? by nvidia", text, re.I):
            out["vendor_role"] = "Nvidia anchor investor"
        elif re.search(r"nvidia.{0,40}(?:backstop|guarantee)|(?:backstop|guarantee).{0,40}nvidia", text, re.I):
            out["vendor_role"] = "Nvidia backstop / guarantee reported"
        elif re.search(r"nvidia-backed", text, re.I):
            out["vendor_role"] = "Nvidia-backed borrower"

    url, outlet, src_date = _source_and_url(d, hint_list)
    if src_date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(src_date)) and src_date < out.get("date", "9999"):
        out["date"] = out["announced"] = src_date   # the source itself is earlier than the article
        if out.get("closed"):
            out["closed"] = src_date
    if url:
        out["url"] = url
    if outlet:
        out["src"] = f"{outlet}, {_src_date(src_date or out.get('date', d.get('date', '')))}"

    # A consistent deal name when the facts allow it ("IREN — USD 2.4bn GPU financing
    # (Blue Owl)"); otherwise the headline.
    if borrower and musd and typ:
        out["name"] = (f"{borrower} — {_fmt_usd(musd)} {NAME_PHRASE[typ]}"
                       + (f" ({', '.join(found_lenders)})" if found_lenders else ""))

    # Terms in our own words, from the facts above.
    parts = [TYPE_PHRASE.get(typ, "Financing")]
    if musd:
        parts[0] += f" of {'up to ' if up_to else ''}{_fmt_usd(musd)}"
    if borrower:
        parts[0] += f" for {borrower}"
    if found_lenders:
        parts.append("lenders: " + ", ".join(found_lenders))
    if gpus:
        parts.append("collateral GPUs: " + ", ".join(gpus))
    for k, label in (("rate", "rate"), ("maturity", "maturity"), ("rating", "rating")):
        if out.get(k):
            parts.append(f"{label} {out[k]}")
    if out.get("status") == "In preparation":
        parts.append("reported as in preparation, not closed")
    out["terms"] = "; ".join(parts) + "."
    return out


CORE = ("date", "name", "type", "amount", "terms", "status", "src", "url")


def fill(draft, d, hints=(), published=False, lenders=None):
    """Merge guesses into a form draft and return (draft, auto_fields).
    Leads: the whole form is a guess, so guesses replace the plain defaults and
    every filled field is listed as auto. Published deals: only empty optional
    fields get a suggestion; stored values are never changed. `ver` is never filled."""
    g = {k: v for k, v in guess(d, hints, lenders).items() if k in draft and k != "ver" and v}
    if published:
        auto = [k for k, v in g.items() if k not in CORE and not draft.get(k)]
        for k in auto:
            draft[k] = g[k]
        return draft, auto
    draft.update(g)
    return draft, [k for k, v in draft.items() if k != "ver" and v]
