#!/usr/bin/env python3
"""
Local review page for the curator: approve or reject leads without editing JSON.

  python3 curate.py            # opens http://127.0.0.1:8765 in your browser
  python3 curate.py --port 9000 --no-browser

It lists
  - PENDING REVIEW rows in observatory-data.json,
  - leads from the latest watch run (candidates.json) that are not in the data yet,
  - the published (VERIFIED / REPORTED) deals, which you can edit or remove,
with the prevalidate.py suggestions next to each lead.

Approve writes the deal into observatory-data.json with the ver you pick. Reject
deletes a pending row, or hides a watch lead (remembered in state/reviewed.json).
Every change also refreshes the fallback snapshot in app.js (update_seed.py), so
afterwards you only run the checks and commit. "Undo" reverts the last change.

The page is for the human curator: code never picks VERIFIED/REPORTED on its own;
the server only writes the ver you clicked. It listens on 127.0.0.1 only.
Standard library only.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import stories
import update_seed

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "observatory-data.json")
CANDIDATES = os.path.join(ROOT, "candidates.json")
PREVALIDATION = os.path.join(ROOT, "prevalidation.json")
REVIEWED = os.path.join(ROOT, "state", "reviewed.json")
APP = os.path.join(ROOT, "app.js")
STATIC = os.path.join(ROOT, "curator")
FILES = {"/": ("index.html", "text/html"), "/curate.js": ("curate.js", "text/javascript"),
         "/curate.css": ("curate.css", "text/css")}

PENDING = "PENDING REVIEW"
CURATED = ("VERIFIED", "REPORTED")
FIELDS = ("date", "name", "type", "amount", "terms", "status", "src")
DEFAULT_TYPES = ["GPU-backed loan", "Chip-lease SPV", "Securitization", "Bond / Loan", "Vendor commitment"]
DEFAULT_STATUSES = ["Announced", "Reported", "Closed", "Outstanding", "Repaid"]
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
       "img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")

LOCK = threading.Lock()
UNDO = []  # snapshots (data text, reviewed text, label) taken before each change


class Invalid(ValueError):
    pass


# ------------------------------------------------------------ files
def _read(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def refresh_seed():
    with open(DATA, encoding="utf-8") as f:
        db = json.load(f)
    js = _text(APP)
    if js is None:
        return
    old = update_seed.current_payload(js) or {}
    if all(old.get(k) == v for k, v in update_seed.payload(db).items()):
        return
    js = update_seed.BLOCK.sub(lambda _: update_seed.build(db, str(datetime.date.today())), js, count=1)
    _write_text(APP, js)


def save(db, reviewed, label):
    UNDO.append((_text(DATA), _text(REVIEWED), label))
    del UNDO[:-50]
    n = sum(1 for d in db["deals"] if d.get("ver") == PENDING)
    db["updated"] = f"{datetime.date.today()} - reviewed by curator" + (
        f" - {n} entr{'y' if n == 1 else 'ies'} PENDING human review" if n else "")
    db["deals"].sort(key=lambda d: d.get("date", ""))
    _write_text(DATA, _dump(db))
    _write_text(REVIEWED, _dump(sorted(set(reviewed))))
    refresh_seed()


def undo():
    if not UNDO:
        raise Invalid("Nothing to undo.")
    data, reviewed, label = UNDO.pop()
    _write_text(DATA, data)
    if reviewed is None:
        if os.path.exists(REVIEWED):
            os.remove(REVIEWED)
    else:
        _write_text(REVIEWED, reviewed)
    refresh_seed()
    return label


# ------------------------------------------------------------ leads
def lead_key(c):
    return hashlib.sha1((c.get("url") or c.get("name", "")).encode()).hexdigest()[:16]


def suggestions():
    """prevalidate.py output, keyed by its item id (sha1 of date|name)."""
    pv = _read(PREVALIDATION, {})
    items = pv.get("items") if isinstance(pv.get("items"), dict) else {}
    clusters = {}
    for c in pv.get("clusters") or []:
        for m in c.get("member_ids") or []:
            clusters[m] = c
    return items, clusters


def hint(d, items, clusters):
    uid = hashlib.sha1(f"{d.get('date')}|{d.get('name')}".encode()).hexdigest()[:12]
    it = items.get(uid) or {}
    cl = clusters.get(uid) or {}
    text = cl.get("suggestion") or it.get("suggestion") or ""
    if text == "SEE-CLUSTER":
        text = ""
    return {
        "suggestion": text,
        "tier": it.get("tier") or stories.tier_of(stories.outlet_of(d)),
        "entity": cl.get("entity") or it.get("entity"),
        "primary_links": [u for u in (cl.get("known_primary") or []) if stories.safe_http_url(u)],
        "search_links": [u for u in (cl.get("find_primary") or []) if stories.safe_http_url(u)],
    }


def draft(d):
    """Prefilled form values. A published deal opens with its stored values; a lead
    gets a first guess from its headline, which the curator edits before saving."""
    if d.get("ver") in CURATED:
        return {k: d.get(k, "") for k in FIELDS + ("url", "ver")}
    name = stories.headline(d.get("name", ""))
    musd = stories.amount_musd(d.get("name", ""))
    date = d.get("date", "")
    outlet = stories.outlet_of(d)
    m = re.match(r"(\d{4})-(\d{2})", date)
    return {
        "date": date,
        "name": name,
        "type": "" if d.get("type") == "To classify" else d.get("type", ""),
        "amount": f"{musd:,.0f} M" if musd else "",
        "terms": "" if d.get("terms") == stories.NEUTRAL_TERMS else d.get("terms", ""),
        "status": "" if str(d.get("status", "")).startswith("Auto-added") else d.get("status", ""),
        "src": f"{outlet}, {m.group(2)}/{m.group(1)}" if outlet and m else d.get("src", ""),
        "url": d.get("url", ""),
        "ver": d.get("ver") if d.get("ver") in CURATED else "",
    }


def view(d, kind, ref, items, clusters):
    h = hint(d, items, clusters)
    form = draft(d)
    if kind != "published" and h["primary_links"]:
        form["url"] = h["primary_links"][0]   # a known issuer release / filing beats a news link
    srcs = [s for s in (d.get("sources") or []) if isinstance(s, dict) and stories.safe_http_url(s.get("url", ""))]
    return {
        "kind": kind, "ref": ref, "date": d.get("date", ""), "name": d.get("name", ""),
        "outlet": stories.outlet_of(d), "url": stories.safe_http_url(d.get("url", "")),
        "ver": d.get("ver", ""), "type": d.get("type", ""), "amount": d.get("amount", ""),
        "status": d.get("status", ""), "terms": d.get("terms", ""), "src": d.get("src", ""),
        "excerpt": d.get("_summary", ""), "followup": bool(d.get("_followup_of")),
        "sources": [{"outlet": s.get("outlet", ""), "url": s["url"], "date": s.get("date", ""),
                     "title": s.get("title", "")} for s in srcs],
        "hint": h, "draft": form,
    }


def state():
    db = _read(DATA, {"deals": []})
    deals = db.get("deals", [])
    reviewed = set(_read(REVIEWED, []))
    items, clusters = suggestions()
    known_urls = {d.get("url") for d in deals if d.get("url")}
    known_urls |= {s.get("url") for d in deals for s in d.get("sources") or [] if isinstance(s, dict)}
    known_names = {(d.get("name"), d.get("date")) for d in deals}
    leads = []
    for c in _read(CANDIDATES, []):
        if not isinstance(c, dict):
            continue
        k = lead_key(c)
        if k in reviewed or c.get("url") in known_urls or (c.get("name"), c.get("date")) in known_names:
            continue
        leads.append(view(c, "candidate", k, items, clusters))
    leads += [view(d, "pending", d["id"], items, clusters) for d in deals if d.get("ver") == PENDING]
    leads.sort(key=lambda v: v["date"], reverse=True)
    published = [view(d, "published", d["id"], items, clusters) for d in deals if d.get("ver") in CURATED]
    published.sort(key=lambda v: v["date"], reverse=True)
    types = list(dict.fromkeys(DEFAULT_TYPES + [d["type"] for d in deals
                                                if d.get("ver") in CURATED and d.get("type")]))
    statuses = list(dict.fromkeys(DEFAULT_STATUSES + [d["status"] for d in deals
                                                      if d.get("ver") in CURATED and d.get("status")]))
    return {"leads": leads, "published": published, "types": types, "statuses": statuses,
            "undo": UNDO[-1][2] if UNDO else None, "updated": db.get("updated", "")}


# ------------------------------------------------------------ actions
def clean(form):
    out = {}
    for k in FIELDS + ("url", "ver"):
        v = form.get(k, "")
        if not isinstance(v, str):
            raise Invalid(f"{k} must be text")
        out[k] = " ".join(v.split()) if k != "terms" else v.strip()
    missing = [k for k in FIELDS if not out[k]]
    if missing:
        raise Invalid("Please fill in: " + ", ".join(missing))
    if out["ver"] not in CURATED:
        raise Invalid("Choose VERIFIED (primary source) or REPORTED (press only).")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?", out["date"]):
        raise Invalid("Date must be YYYY-MM or YYYY-MM-DD.")
    if out["url"] and not stories.safe_http_url(out["url"]):
        raise Invalid("Link must start with http:// or https://")
    if out["type"] == "To classify":
        raise Invalid("Pick a deal type.")
    if out["terms"] == stories.NEUTRAL_TERMS:
        raise Invalid("Write the deal terms (the placeholder note is not shown on the site).")
    if len(out["terms"]) > 1000 or any(len(out[k]) > 300 for k in FIELDS if k != "terms"):
        raise Invalid("A field is too long.")
    return out


def apply_form(deal, form):
    for k in FIELDS + ("ver",):
        deal[k] = form[k]
    if form["url"]:
        deal["url"] = form["url"]
        if "news.google.com" not in form["url"]:
            deal["outlet"] = stories.outlet_of({"url": form["url"], "src": form["src"]})
    else:
        deal.pop("url", None)


def find(deals, ref):
    for d in deals:
        if d.get("id") == ref:
            return d
    raise Invalid("That entry no longer exists. Reload the page.")


def act(action, body):
    db = _read(DATA, None)
    if not isinstance(db, dict) or not isinstance(db.get("deals"), list):
        raise Invalid("observatory-data.json could not be read.")
    deals = db["deals"]
    reviewed = list(_read(REVIEWED, []))
    kind, ref = body.get("kind"), body.get("ref")

    if action == "undo":
        return {"message": f"Undone: {undo()}"}

    if action == "approve":
        form = clean(body.get("form") or {})
        if kind == "pending":
            d = find(deals, ref)
            if d.get("ver") != PENDING:
                raise Invalid("That row is already published.")
            apply_form(d, form)
        elif kind == "published":
            d = find(deals, ref)
            apply_form(d, form)
        elif kind in ("candidate", "new"):
            src = {}
            if kind == "candidate":
                src = next((c for c in _read(CANDIDATES, []) if isinstance(c, dict) and lead_key(c) == ref), None)
                if src is None:
                    raise Invalid("That lead is no longer in candidates.json. Reload the page.")
                reviewed.append(ref)
            d = {k: v for k, v in src.items() if not k.startswith("_")}
            apply_form(d, form)
            d["id"] = stories.deal_id(d)
            while any(x.get("id") == d["id"] for x in deals):
                d["id"] = "d" + hashlib.sha1(d["id"].encode()).hexdigest()[:10]
            deals.append(d)
        else:
            raise Invalid("Unknown entry type.")
        label = f"{'saved' if kind == 'published' else 'published'} \"{form['name'][:60]}\" as {form['ver']}"
        save(db, reviewed, label)
        return {"message": label[0].upper() + label[1:]}

    if action == "reject":
        if kind == "candidate":
            if ref not in {lead_key(c) for c in _read(CANDIDATES, []) if isinstance(c, dict)}:
                raise Invalid("That lead is no longer in candidates.json. Reload the page.")
            reviewed.append(ref)
            name = next(c.get("name", "") for c in _read(CANDIDATES, []) if isinstance(c, dict) and lead_key(c) == ref)
        elif kind in ("pending", "published"):
            d = find(deals, ref)
            name = d.get("name", "")
            deals.remove(d)
        else:
            raise Invalid("Unknown entry type.")
        label = f"removed \"{stories.headline(name)[:60]}\""
        save(db, reviewed, label)
        return {"message": label[0].upper() + label[1:]}

    raise Invalid("Unknown action.")


# ------------------------------------------------------------ server
class Handler(BaseHTTPRequestHandler):
    server_version = "curate"

    def log_message(self, fmt, *args):
        pass

    def _host_ok(self):
        # Blocks DNS-rebinding: only our own loopback host names are accepted.
        port = self.server.server_address[1]
        return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/state":
            with LOCK:
                return self._send(200, state())
        if path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        if path in FILES:
            name, ctype = FILES[path]
            with open(os.path.join(STATIC, name), "rb") as f:
                return self._send(200, f.read(), ctype)
        self._send(404, {"error": "not found"})

    def do_POST(self):
        port = self.server.server_address[1]
        origin = self.headers.get("Origin")
        # Cross-site pages cannot send this header without a CORS preflight, which
        # we never answer, so only our own page can make changes.
        if (not self._host_ok() or self.headers.get("X-Curator") != "1"
                or origin not in (None, f"http://127.0.0.1:{port}", f"http://localhost:{port}")
                or not self.headers.get("Content-Type", "").startswith("application/json")):
            return self._send(403, {"error": "forbidden"})
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/"):
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(min(n, 100_000)) or b"{}")
            with LOCK:
                result = act(path[5:], body if isinstance(body, dict) else {})
                result["state"] = state()
            self._send(200, result)
        except Invalid as e:
            self._send(400, {"error": str(e)})
        except ValueError:
            self._send(400, {"error": "bad request"})


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    httpd = HTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}/"
    print(f"Deal review running at {url}  (Ctrl+C to stop)")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. Next: run the checks, then commit observatory-data.json, app.js, state/reviewed.json.")


if __name__ == "__main__":
    main()
