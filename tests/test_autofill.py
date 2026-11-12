"""
Tests for autofill.py (first-guess values for the curator's deal form).
Run from the repo root:  python3 -m unittest discover tests
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import autofill  # noqa: E402
import curate  # noqa: E402
import stories  # noqa: E402

IREN_HINT = {"entity": "IREN", "amount_musd": 2400, "tier": "primary",
             "url": "https://www.prnewswire.com/news-releases/blue-owl-iren-302863057.html",
             "note": "Blue Owl press release, 2026-08-28"}


def lead(name, date="2026-09-04", outlet="24/7 Wall St.", url="https://news.google.com/rss/articles/x", **kw):
    return {"name": name, "date": date, "outlet": outlet, "url": url, "ver": "PENDING REVIEW",
            "type": "To classify", "terms": stories.NEUTRAL_TERMS, "status": "Auto-added - awaiting human verification",
            **kw}


class Guess(unittest.TestCase):
    def test_full_lead_with_known_primary_source(self):
        g = autofill.guess(lead("IREN Climbs 4% on $2.4B Blue Owl-Led GPU Financing - 24/7 Wall St."), [IREN_HINT])
        self.assertEqual(g["name"], "IREN — USD 2.4bn GPU-backed loan (Blue Owl)")
        self.assertEqual((g["type"], g["amount"], g["amount_musd"]), ("GPU-backed loan", "2,400 M", "2400"))
        self.assertEqual(g["url"], IREN_HINT["url"], "a known primary source replaces the news link")
        self.assertEqual(g["src"], "Blue Owl press release, 28/08/2026")
        self.assertEqual((g["lenders"], g["collateral"]), ("Blue Owl", "gpu-lien"))
        self.assertEqual((g["date"], g["announced"]), ("2026-08-28", "2026-08-28"), "the release predates the article")

    def test_status(self):
        self.assertEqual(autofill.guess(lead("GSAM eyes $6.6bn GPU-backed private financing for OpenAI"))["status"],
                         "In preparation")
        closed = autofill.guess(lead("Lambda secures $1B in debt to buy more chips", date="2026-08-28"))
        self.assertEqual((closed["status"], closed["closed"], closed["amount_kind"]), ("Closed", "2026-08-28", "committed"))
        planned = autofill.guess(lead("Nebius plans $5B debt raise"))
        self.assertNotIn("amount_kind", planned, "a planned amount is not a commitment")
        quiet = autofill.guess(lead("Sharon AI Enters Into GPU-Backed Debt Facility"))
        self.assertEqual((quiet["status"], quiet["amount"]), ("Announced", "Undisclosed"))
        self.assertEqual(autofill.guess(lead("Banks weigh GPU loan market"))["status"], "In preparation")
        self.assertEqual(autofill.guess(lead("A GPU loan for Acme"))["status"], "Reported")

    def test_borrower_when_headline_names_the_lender(self):
        g = autofill.guess(lead("GSAM eyes $6.6bn GPU-backed private financing for OpenAI"))
        self.assertIn("for OpenAI", g["terms"])
        self.assertEqual(g["lenders"], "Goldman Sachs")
        g = autofill.guess(lead("Bullish Provides USD.AI $100 Million Facility for GPU-Backed Loans"))
        self.assertTrue(g["name"].startswith("USD.AI — USD 100m"), g["name"])

    def test_collateral_not_guessed_when_a_note_says_unconfirmed(self):
        hint = {"entity": "Lambda", "amount_musd": 1000, "tier": "press1", "url": "https://finance.yahoo.com/x",
                "note": "Bloomberg via Yahoo syndication. Collateral NOT confirmed"}
        g = autofill.guess(lead("Lambda raises $1B in GPU-backed debt"), [hint])
        self.assertNotIn("collateral", g)
        self.assertEqual(g["src"].split(",")[0], "Bloomberg")

    def test_capacity_rental_is_not_a_chip_lease_vehicle(self):
        g = autofill.guess(lead("Tencent leases 100,000 chips from Oracle to accelerate AI push"))
        self.assertNotEqual(g.get("type"), "Chip-lease SPV")
        self.assertNotIn("collateral", g)

    def test_hints_need_matching_amounts(self):
        nvidia = {"entity": "Nvidia", "amount_musd": 500000, "tier": "primary", "url": "https://nvidianews.nvidia.com/x"}
        g = autofill.guess(lead("Nvidia turns to insurers to de-risk AI chip loans"), [nvidia])
        self.assertNotEqual(g.get("url"), nvidia["url"], "an unrelated Nvidia release must not be linked")

    def test_terms_are_composed_not_copied(self):
        excerpt = "The neocloud operator said the facility carries a coupon tied to SOFR plus a spread"
        g = autofill.guess(lead("Acme secures $300 million GPU-backed loan at SOFR+4.5% from Blackstone",
                                _summary=excerpt))
        self.assertNotIn(excerpt[:40], g["terms"])
        self.assertIn("rate SOFR+4.5%", g["terms"])
        self.assertIn("lenders: Blackstone", g["terms"])

    def test_rating_and_gpus(self):
        g = autofill.guess(lead("Moody's assigns A3 rating to CoreWeave's $8.5bn GB200-backed DDTL"))
        self.assertEqual((g["rating"], g["gpu_generation"]), ("A3 (Moody's)", "GB200"))
        self.assertEqual(autofill.guess(lead("x", terms="Ba2/BB+; JPMorgan & MUFG"))["rating"], "Ba2 / BB+")

    def test_edgar_filing_lead(self):
        g = autofill.guess(lead("CoreWeave, Inc. - 8-K (1.01 material agreement, 2.03 new financial obligation)",
                                outlet="sec.gov", url="https://www.sec.gov/Archives/edgar/data/1/2/3-index.htm"))
        self.assertEqual(g["name"], "CoreWeave 8-K: 1.01 material agreement, 2.03 new financial obligation")
        self.assertEqual((g["type"], g["status"]), ("Bond / Loan", "Announced"))
        self.assertTrue(g["src"].startswith("CoreWeave 8-K, "))


class Fill(unittest.TestCase):
    def test_lead_form_is_filled_and_marked(self):
        d = lead("IREN Climbs 4% on $2.4B Blue Owl-Led GPU Financing - 24/7 Wall St.")
        form, auto = autofill.fill(curate.draft(d), d, [IREN_HINT])
        self.assertEqual(form["ver"], "", "ver is never filled")
        self.assertNotIn("ver", auto)
        self.assertTrue({"name", "type", "amount", "terms", "status", "src", "url", "collateral"} <= set(auto))
        clean = curate.clean({**form, "ver": "REPORTED"})   # the curator only picks the flag
        self.assertEqual(clean["collateral"], "gpu-lien")

    def test_published_values_are_never_changed(self):
        d = {"id": "x", "date": "2026-08", "name": "CoreWeave DDTL 5.5", "type": "GPU-backed loan", "amount": "2,600 M",
             "terms": "SOFR+5.50%; Ba2/BB+; JPMorgan & MUFG", "status": "Closed", "ver": "VERIFIED", "src": "PR",
             "url": "https://example.com", "lenders": "JPMorgan (lead)"}
        before = dict(d)
        form, auto = autofill.fill(curate.draft(d), d, [], published=True)
        self.assertEqual(d, before)
        for k in ("name", "type", "amount", "terms", "status", "src", "url", "ver", "lenders"):
            self.assertEqual(form[k], curate.draft(d)[k], k)
            self.assertNotIn(k, auto)
        self.assertEqual((form["rate"], form["rating"]), ("SOFR+5.50%", "Ba2 / BB+"))

    def test_real_leads_validate_once_a_flag_is_picked(self):
        """The prefilled drafts for the leads in the repo pass the curator's checks
        (where a type and status could be guessed) after only choosing REPORTED."""
        state = curate.state()
        self.assertTrue(state["leads"])
        ok = 0
        for v in state["leads"]:
            f = v["draft"]
            if f.get("type") and f.get("status"):
                curate.clean({**f, "ver": "REPORTED"})
                ok += 1
            self.assertTrue(v["auto"], v["name"])
        self.assertGreaterEqual(ok / len(state["leads"]), 0.6, "most leads should need no typing")


if __name__ == "__main__":
    unittest.main()
