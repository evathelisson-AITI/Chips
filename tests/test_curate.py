"""
Tests for curate.py (the local review page's server). Each test works on a copy of
the data in a temporary directory. Run from the repo root:
  python3 -m unittest discover tests
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import curate  # noqa: E402
import update_seed  # noqa: E402

FORM = {"date": "2026-09", "name": "Test deal", "type": "GPU-backed loan", "amount": "100 M",
        "terms": "Lender X, SOFR+5%", "status": "Closed", "src": "Issuer press release, 09/2026",
        "url": "https://example.com/pr", "ver": "REPORTED"}


class Curate(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for f in ("observatory-data.json", "candidates.json", "prevalidation.json", "app.js"):
            shutil.copy(os.path.join(ROOT, f), self.dir)
        self.saved = {k: getattr(curate, k) for k in ("DATA", "CANDIDATES", "PREVALIDATION", "REVIEWED", "APP")}
        curate.DATA = os.path.join(self.dir, "observatory-data.json")
        curate.CANDIDATES = os.path.join(self.dir, "candidates.json")
        curate.PREVALIDATION = os.path.join(self.dir, "prevalidation.json")
        curate.REVIEWED = os.path.join(self.dir, "state", "reviewed.json")
        curate.APP = os.path.join(self.dir, "app.js")
        curate.UNDO.clear()

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(curate, k, v)
        curate.UNDO.clear()
        shutil.rmtree(self.dir)

    def db(self):
        with open(curate.DATA, encoding="utf-8") as f:
            return json.load(f)

    def test_form_validation(self):
        for bad, msg in ((dict(ver=""), "VERIFIED"), (dict(ver="PENDING REVIEW"), "VERIFIED"),
                         (dict(url="javascript:alert(1)"), "http"), (dict(date="Sept 2026"), "YYYY"),
                         (dict(terms=""), "terms"), (dict(type="To classify"), "type")):
            with self.assertRaisesRegex(curate.Invalid, msg):
                curate.clean({**FORM, **bad})

    def test_approve_pending_keeps_sources_and_refreshes_seed(self):
        pending = [d for d in self.db()["deals"] if d["ver"] == "PENDING REVIEW" and d.get("sources")][0]
        curate.act("approve", {"kind": "pending", "ref": pending["id"], "form": FORM})
        row = next(d for d in self.db()["deals"] if d["id"] == pending["id"])
        self.assertEqual(row["ver"], "REPORTED")
        self.assertEqual(row["sources"], pending["sources"])
        with open(curate.APP, encoding="utf-8") as f:
            seed = update_seed.current_payload(f.read())
        self.assertIn(pending["id"], [d["id"] for d in seed["deals"]])

    def test_reject_and_undo(self):
        before = self.db()
        pending = next(d for d in before["deals"] if d["ver"] == "PENDING REVIEW")
        curate.act("reject", {"kind": "pending", "ref": pending["id"]})
        self.assertNotIn(pending["id"], [d["id"] for d in self.db()["deals"]])
        curate.act("undo", {})
        self.assertEqual(self.db(), before)

    def test_new_deal_and_candidate(self):
        curate.act("approve", {"kind": "new", "ref": "", "form": FORM})
        ids = [d["id"] for d in self.db()["deals"]]
        self.assertEqual(len(ids), len(set(ids)))
        with open(curate.CANDIDATES, "w", encoding="utf-8") as f:
            json.dump([{"_tier": 1, "_summary": "x", "date": "2026-11-11", "name": "Fresh lead - FT",
                        "url": "https://example.com/fresh", "ver": "PENDING REVIEW"}], f)
        lead = next(l for l in curate.state()["leads"] if l["kind"] == "candidate")
        curate.act("reject", {"kind": "candidate", "ref": lead["ref"]})
        self.assertFalse([l for l in curate.state()["leads"] if l["kind"] == "candidate"])
        curate.act("undo", {})
        lead = next(l for l in curate.state()["leads"] if l["kind"] == "candidate")
        curate.act("approve", {"kind": "candidate", "ref": lead["ref"], "form": FORM})
        row = next(d for d in self.db()["deals"] if d["name"] == "Test deal" and d.get("url") == FORM["url"]
                   and d["id"] not in ids)
        self.assertFalse([k for k in row if k.startswith("_")], "feed excerpts must not reach the site data")
        self.assertFalse([l for l in curate.state()["leads"] if l["kind"] == "candidate"])


if __name__ == "__main__":
    unittest.main()
