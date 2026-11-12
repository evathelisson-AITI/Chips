"""Offline tests for the watcher, story grouping, the pending merge and the site data.
Standard library only. Run from the repo root:  python3 -m unittest discover tests
"""
import copy
import datetime
import json
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["OBS_CONFIG"] = os.path.join(ROOT, "config.json")
import merge_pending  # noqa: E402
import stories  # noqa: E402
import watch  # noqa: E402

with open(os.path.join(ROOT, "tests", "relevance_sample.json"), encoding="utf-8") as _f:
    SAMPLE = json.load(_f)["items"]


def accepted(title, summary=""):
    return not watch.blocked(title) and watch.relevant(title, summary) is not None


def days_ago(n):
    return str(datetime.date.today() - datetime.timedelta(days=n))


class RelevanceSample(unittest.TestCase):
    """Labelled headlines in tests/relevance_sample.json."""

    def by(self, label):
        return [i["title"] for i in SAMPLE if i["label"] == label]

    def test_every_deal_passes(self):
        missed = [t for t in self.by("deal") if not accepted(t)]
        self.assertEqual(missed, [], "deal headlines rejected by the filter")

    def test_spam_outlets_blocked(self):
        leaked = [t for t in self.by("spam") if accepted(t)]
        self.assertEqual(leaked, [])

    def test_most_noise_rejected(self):
        noise = self.by("noise")
        leaked = [t for t in noise if accepted(t)]
        rate = 1 - len(leaked) / len(noise)
        self.assertGreaterEqual(rate, 0.8, f"noise rejection {rate:.0%}; leaked: {leaked}")


class Matching(unittest.TestCase):
    def test_word_boundaries(self):
        for title in ["Chipotle beats on credit card sales",
                      "Labs report absolute gains, footnotes show debt",
                      "Nvidia sales growth forecast"]:
            self.assertIsNone(watch.relevant(title), title)

    def test_plural_and_prefix(self):
        self.assertTrue(watch.relevant("Startup leases GPUs to labs"))
        self.assertTrue(watch.relevant("Banks syndicating a chip loan"))

    def test_strong_phrase_in_summary(self):
        self.assertEqual(watch.relevant("Market wrap", "a new GPU-backed facility closed"), "strong")

    def test_exclude_beats_strong(self):
        self.assertIsNone(watch.relevant("Tokenized Nvidia stock as GPU collateral"))

    def test_clean_text(self):
        self.assertEqual(watch.clean_text("<b>A</b>&nbsp;&nbsp;B &amp; C"), "A B & C")

    def test_amounts(self):
        self.assertIsNone(stories.amount_musd("Investors bet 100 billion won on DRAM"))
        self.assertEqual(stories.amount_musd("Nvidia's $500 Billion plan won't age well"), 500000)
        self.assertEqual(stories.amount_musd("Lambda raises $1B"), 1000)

    def test_md_safe(self):
        self.assertNotIn("@octocat", stories.md_safe("ping @octocat\nnow"))
        self.assertNotIn("\n", stories.md_safe("a\nb"))


class StoryGrouping(unittest.TestCase):
    """Story labels in the sample: duplicates must group, distinct stories must not."""

    @classmethod
    def setUpClass(cls):
        items = [{"name": i["title"], "date": "", "story": i.get("story") or f"single-{n}"}
                 for n, i in enumerate(SAMPLE)]
        cls.groups = stories.group(items)

    def test_no_wrong_merges(self):
        mixed = [sorted({i["story"] for i in g}) for g in self.groups if len({i["story"] for i in g}) > 1]
        self.assertEqual(mixed, [], "groups that mix different stories")

    def test_duplicates_collapse(self):
        labels = {i["story"] for g in self.groups for i in g if not i["story"].startswith("single-")}
        for s in labels:
            sizes = [sum(1 for i in g if i["story"] == s) for g in self.groups]
            total = sum(sizes)
            self.assertGreaterEqual(max(sizes) / total, 2 / 3, f"story {s} split into {[x for x in sizes if x]}")

    def test_reworded_headline_same_company(self):
        a = {"name": "CoreWeave plans multibillion-dollar chip-backed debt deal - Financial Times", "date": "2026-11-11"}
        b = {"name": "CoreWeave turns to chip-backed loans as AI debt mounts - CryptoRank", "date": "2026-11-11"}
        self.assertTrue(stories.same_story(a, b))
        self.assertFalse(stories.same_story(a, dict(b, date="2026-11-01")), "relaxed rule needs close dates")
        n1 = {"name": "Nvidia turns to insurers to de-risk AI chip loans", "date": "2026-11-11"}
        n2 = {"name": "Nvidia chip loans face scrutiny from banks", "date": "2026-11-11"}
        self.assertFalse(stories.same_story(n1, n2), "generic Nvidia is not enough")

    def test_date_window(self):
        a = {"name": "Lambda raises $1B in debt", "date": "2026-01-01"}
        b = {"name": "Lambda raises $1B in debt", "date": "2026-03-01"}
        self.assertFalse(stories.same_story(a, b))

    def test_best_source_leads(self):
        g = stories.group([
            {"name": "Acme $2B GPU loan - Blog", "date": "2026-01-01", "outlet": "Some Blog", "url": "https://b/1"},
            {"name": "Acme $2B GPU loan - Reuters", "date": "2026-01-02", "outlet": "Reuters", "url": "https://r/1"},
        ])
        self.assertEqual(len(g), 1)
        head, _ = stories.merge_group(g[0])
        self.assertEqual(head["outlet"], "Reuters")
        self.assertEqual([s["outlet"] for s in head["sources"]], ["Some Blog"])


class FakeFeed:
    def __init__(self, entries, title="Fixture feed"):
        self.feed = {"title": title}
        self.entries = entries


def tm(days):
    return (datetime.date.today() - datetime.timedelta(days=days)).timetuple()


class FeedProcessing(unittest.TestCase):
    def test_fixture_feed(self):
        feed = FakeFeed([
            {"title": "Acme secures $1bn GPU-backed loan", "link": "https://a.example/1",
             "summary": "<p>Acme&nbsp;closed</p>", "published_parsed": tm(1),
             "source": {"title": "Reuters", "href": "https://www.reuters.com"}},
            {"title": "Acme secures $1bn GPU-backed loan", "link": "https://a.example/1",
             "published_parsed": tm(1)},                                    # same URL: dedupe
            {"title": "Old GPU-backed loan", "link": "https://a.example/2", "published_parsed": tm(400)},
            {"title": "Undated GPU-backed loan", "link": "https://a.example/3"},
            {"title": "GPU-backed loan spin - Vinanet", "link": "https://a.example/4", "published_parsed": tm(1)},
            {"title": "Weather report", "link": "https://a.example/5", "published_parsed": tm(1)},
        ])
        w = watch.Watch(seen=[])
        w.process_feed(feed, "https://feed.example/rss", 2)
        self.assertEqual([c["url"] for c in w.candidates], ["https://a.example/1"])
        c = w.candidates[0]
        self.assertEqual(c["ver"], "PENDING REVIEW")
        self.assertEqual(c["outlet"], "Reuters")
        self.assertEqual(c["terms"], stories.NEUTRAL_TERMS, "feed text must not be republished")
        self.assertEqual(c["_summary"], "Acme closed")
        self.assertEqual(w.stats["https://feed.example/rss"], [6, 1, None])

        again = watch.Watch(seen=w.seen)
        again.process_feed(feed, "https://feed.example/rss", 2)
        self.assertEqual(again.candidates, [], "seen state must suppress repeats")

    def test_edgar_one_candidate_per_filing(self):
        def hit(adsh, doc, form="8-K"):
            return {"_id": f"{adsh}:{doc}", "_source": {"adsh": adsh, "ciks": ["0000012345"], "form": form,
                                                        "root_forms": [form], "display_names": ["Acme Corp"],
                                                        "file_date": days_ago(1)}}
        w = watch.Watch(seen=[])
        w.process_edgar({
            '"GPU" "collateral"': [hit("0001-26-000001", "a.htm"), hit("0001-26-000001", "ex10.htm"),
                                   hit("0002-26-000002", "fund.htm", form="485BPOS")],
            '"GPU-backed"': [hit("0001-26-000001", "a.htm")],
        })
        self.assertEqual(len(w.candidates), 1)
        c = w.candidates[0]
        self.assertEqual(c["url"], "https://www.sec.gov/Archives/edgar/data/12345/000126000001/0001-26-000001-index.htm")
        self.assertIn('"GPU" "collateral" + "GPU-backed"', c["name"])

    def test_grouping_and_followups(self):
        w = watch.Watch(seen=[])
        for n, outlet in enumerate(["Blog", "Reuters", "TechCrunch"]):
            w.add(2, f"Lambda raises $1B in private debt - {outlet}", f"https://x/{n}", "GN", days_ago(1),
                  outlet=outlet)
        w.add(2, "Unrelated: Crusoe leases chips to labs", "https://x/9", "GN", days_ago(1), outlet="FT")
        grouped = watch.group_candidates(w.candidates)
        self.assertEqual(len(grouped), 2)
        lam = next(c for c in grouped if "Lambda" in c["name"])
        self.assertEqual(lam["outlet"], "Reuters")
        self.assertEqual(len(lam["sources"]), 2)
        memory = [{"date": days_ago(5), "name": "Lambda secures $1B debt to buy chips", "id": "dold"}]
        memory = watch.mark_followups(grouped, memory)
        self.assertEqual(lam["_followup_of"]["id"], "dold")
        self.assertEqual(len(memory), 2, "only the new story is remembered")
        digest = "\n".join(watch.digest_lines(grouped))
        self.assertIn("1 new story, 1 follow-up", digest)
        self.assertIn("(+2 more:", digest)

    def test_direct_publish_never_curates_and_attaches(self):
        w = watch.Watch(seen=[])
        w.add(1, "<img src=x onerror=alert(1)> GPU-backed loan $5B", "https://a.example/x", "Test", None)
        w.candidates[0]["ver"] = "VERIFIED"  # even if something upstream tampered with it
        w.add(1, "Second outlet: GPU-backed loan $5B for Acme", "https://b.example/y", "Test", None)
        w.candidates[1]["name"] = "<img src=x onerror=alert(1)> GPU-backed loan $5B - Other"
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "data.json")
            with open(path, "w") as f:
                json.dump({"updated": "", "deals": []}, f)
            self.assertEqual(watch.publish_direct(w.candidates[:1], path, {1}), 1)
            self.assertEqual(watch.publish_direct(w.candidates[:1], path, {1}), 0, "no duplicate rows")
            self.assertEqual(watch.publish_direct(w.candidates[1:], path, {1}), 0, "same story attaches")
            with open(path) as f:
                deals = json.load(f)["deals"]
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0]["ver"], "PENDING REVIEW")
        self.assertEqual(len(deals[0]["sources"]), 1)
        self.assertTrue(deals[0]["id"])


class MergePending(unittest.TestCase):
    def test_merge(self):
        curated = {"date": "2026-01", "name": "Curated deal $1B", "type": "Loan", "amount": "1,000 M",
                   "terms": "t", "status": "Closed", "ver": "VERIFIED", "src": "PR"}
        def pend(name, outlet, url):
            return {"date": "2026-08-28", "name": f"{name} - {outlet}", "type": "To classify", "amount": "-",
                    "terms": f"verbatim feed text [source link: {url}]", "status": "s",
                    "ver": "PENDING REVIEW", "src": "GN"}
        db = {"updated": "x", "deals": [
            copy.deepcopy(curated),
            pend("Lambda raises $1B debt", "Crypto Briefing", "https://news.google.com/1"),
            pend("Lambda raises $1B debt", "TechCrunch", "https://news.google.com/2"),
            pend("Lambda raises $1B debt spin", "Vinanet", "https://news.google.com/3"),
        ]}
        s = merge_pending.merge(db, blocked=["vinanet"])
        self.assertEqual(s, {"pending_before": 3, "pending_after": 1, "blocked_dropped": 1})
        cur = [d for d in db["deals"] if d["ver"] == "VERIFIED"][0]
        self.assertEqual({k: v for k, v in cur.items() if k != "id"}, curated, "curated entry unchanged")
        row = [d for d in db["deals"] if d["ver"] == "PENDING REVIEW"][0]
        self.assertEqual(row["outlet"], "TechCrunch")
        self.assertEqual(row["url"], "https://news.google.com/2")
        self.assertEqual(row["terms"], stories.NEUTRAL_TERMS)
        self.assertEqual([x["outlet"] for x in row["sources"]], ["Crypto Briefing"])
        before = json.dumps(db, sort_keys=True)
        merge_pending.merge(db, blocked=["vinanet"])
        self.assertEqual(json.dumps(db, sort_keys=True), before, "idempotent")


class SiteData(unittest.TestCase):
    """Shape of observatory-data.json, which app.js renders."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "observatory-data.json"), encoding="utf-8") as f:
            cls.db = json.load(f)

    def test_shape(self):
        self.assertIsInstance(self.db["updated"], str)
        fields = ["id", "date", "name", "type", "amount", "terms", "status", "ver", "src"]
        for d in self.db["deals"]:
            for k in fields:
                self.assertIsInstance(d.get(k), str, f"{k} in {d.get('name')}")
            self.assertIn(d["ver"], {"VERIFIED", "REPORTED", "PENDING REVIEW"}, d["name"])
            self.assertRegex(d["date"], r"^\d{4}-\d{2}(-\d{2})?$", d["name"])
            self.assertNotRegex(d["terms"], r"&#?\w+;|\[source link:", d["name"])
            if "url" in d:
                self.assertRegex(d["url"], r"^https?://", d["name"])
            for s in d.get("sources", []):
                self.assertRegex(s.get("url", ""), r"^https?://", d["name"])
                self.assertIsInstance(s.get("outlet"), str)
        ids = [d["id"] for d in self.db["deals"]]
        self.assertEqual(len(ids), len(set(ids)), "deal ids must be unique")
        for e in self.db["events"]:
            for k in "dtxk":
                self.assertIsInstance(e.get(k), str)
        for series in ("resale", "rental"):
            for label, value in self.db[series]:
                self.assertIsInstance(label, str)
                self.assertIsInstance(value, (int, float))

    def test_seed_snapshot_current(self):
        import update_seed
        with open(os.path.join(ROOT, "app.js"), encoding="utf-8") as f:
            seed = update_seed.current_payload(f.read())
        self.assertEqual({k: seed[k] for k in ("deals", "resale", "rental", "events")},
                         update_seed.payload(self.db), "run: python3 update_seed.py")


class Config(unittest.TestCase):
    def test_mode_is_supported(self):
        self.assertIn(watch.CONFIG.get("auto_publish_mode", "off"), {"off", "direct"})


if __name__ == "__main__":
    unittest.main()
