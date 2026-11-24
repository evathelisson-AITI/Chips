"""
Tests for curator_web.py (the password-protected curator page on the live site).
GitHub is replaced by an in-memory fake, so nothing touches the network.
  python3 -m unittest discover tests
"""
import http.client
import json
import os
import sys
import threading
import unittest
from http.server import HTTPServer
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import curate  # noqa: E402
import curator_web  # noqa: E402
import update_seed  # noqa: E402

FORM = {"date": "2026-09", "name": "Test deal", "type": "GPU-backed loan", "amount": "100 M",
        "terms": "Lender X, SOFR+5%", "status": "Closed", "src": "Issuer press release, 09/2026",
        "url": "https://example.com/pr", "ver": "REPORTED"}
ENV = {"CURATOR_PASSWORD": "correct horse battery staple", "SESSION_SECRET": "s" * 40,
       "GITHUB_TOKEN": "test-token", "GITHUB_REPO": "owner/repo"}


class FakeGitHub:
    """Commits, trees and one branch, answering the calls GitHubStore makes."""

    def __init__(self, files):
        self.commits = {"c0": {"files": dict(files), "message": "initial", "parents": []}}
        self.ref = "c0"
        self.n = 0
        self.trees = {}
        self.before_patch = None  # called once before the next ref update (simulates a concurrent push)

    def _new(self, files, message, parent):
        self.n += 1
        sha = f"c{self.n}"
        self.commits[sha] = {"files": files, "message": message, "parents": [parent]}
        return sha

    def push(self, changes, message="watch: 2026-11-30"):
        files = {**self.commits[self.ref]["files"], **changes}
        self.ref = self._new(files, message, self.ref)

    def call(self, method, path, body=None, raw=False):
        path, _, query = path.partition("?")
        if method == "GET" and path == "git/ref/heads/main":
            return {"object": {"sha": self.ref}}
        if method == "GET" and path.startswith("contents/"):
            sha = query.split("ref=")[1]
            return self.commits[sha]["files"].get(path[len("contents/"):].replace("%2F", "/"))
        if method == "GET" and path.startswith("git/commits/"):
            c = self.commits[path.rsplit("/", 1)[1]]
            return {"tree": {"sha": "t-" + path.rsplit("/", 1)[1]}, "message": c["message"],
                    "parents": [{"sha": p} for p in c["parents"]]}
        if method == "POST" and path == "git/trees":
            files = dict(self.commits[body["base_tree"][2:]]["files"])
            for e in body["tree"]:
                if e.get("content") is not None:
                    files[e["path"]] = e["content"]
                else:
                    files.pop(e["path"], None)
            self.n += 1
            self.trees[f"t{self.n}"] = files
            return {"sha": f"t{self.n}"}
        if method == "POST" and path == "git/commits":
            return {"sha": self._new(self.trees[body["tree"]], body["message"], body["parents"][0])}
        if method == "PATCH" and path == "git/refs/heads/main":
            if self.before_patch:
                hook, self.before_patch = self.before_patch, None
                hook()
            if self.commits[body["sha"]]["parents"][0] != self.ref:
                raise curator_web.Conflict()
            self.ref = body["sha"]
            return {}
        raise AssertionError(f"unexpected call {method} {path}")

    def file(self, rel):
        return self.commits[self.ref]["files"].get(rel)

    def db(self):
        return json.loads(self.file(curate.DATA))


def repo_files():
    out = {}
    for rel in (curate.DATA, curate.CANDIDATES, curate.PREVALIDATION, curate.HINTS, curate.CONFIG, curate.APP):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            out[rel] = f.read()
    out[curate.REVIEWED] = "[]\n"
    return out


class Store(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGitHub(repo_files())
        self.s = {**curator_web.settings(), "repo": "owner/repo", "branch": "main"}

    def test_approve_is_one_commit_with_data_reviewed_and_seed(self):
        pending = next(d for d in self.gh.db()["deals"] if d["ver"] == "PENDING REVIEW")
        r = curator_web.run("approve", {"kind": "pending", "ref": pending["id"], "form": FORM}, self.s, self.gh)
        self.assertEqual(r["undo"], self.gh.ref)
        self.assertIn("about a minute", r["message"])
        c = self.gh.commits[self.gh.ref]
        self.assertTrue(c["message"].startswith("Curator: published"))
        self.assertEqual(self.gh.n, 2, "one tree and one commit")
        row = next(d for d in self.gh.db()["deals"] if d["id"] == pending["id"])
        self.assertEqual(row["ver"], "REPORTED")
        seed = update_seed.current_payload(self.gh.file(curate.APP))
        self.assertIn(pending["id"], [d["id"] for d in seed["deals"]])
        self.assertEqual(r["state"]["mode"], "web")

    def test_undo_restores_the_files(self):
        before = {rel: self.gh.file(rel) for rel in curator_web.WRITTEN}
        pending = next(d for d in self.gh.db()["deals"] if d["ver"] == "PENDING REVIEW")
        r = curator_web.run("reject", {"kind": "pending", "ref": pending["id"]}, self.s, self.gh)
        curator_web.run("undo", {"token": r["undo"]}, self.s, self.gh)
        self.assertEqual({rel: self.gh.file(rel) for rel in curator_web.WRITTEN}, before)
        self.assertTrue(self.gh.commits[self.gh.ref]["message"].startswith("Curator: undo removed"))

    def test_undo_refused_after_a_later_commit(self):
        pending = next(d for d in self.gh.db()["deals"] if d["ver"] == "PENDING REVIEW")
        r = curator_web.run("reject", {"kind": "pending", "ref": pending["id"]}, self.s, self.gh)
        self.gh.push({"DIGEST.md": "x"})
        with self.assertRaisesRegex(curate.Invalid, "changed after"):
            curator_web.run("undo", {"token": r["undo"]}, self.s, self.gh)
        with self.assertRaisesRegex(curate.Invalid, "Nothing to undo"):
            curator_web.run("undo", {}, self.s, self.gh)

    def test_undo_only_reverts_curator_commits(self):
        self.gh.push({"DIGEST.md": "x"})
        with self.assertRaisesRegex(curate.Invalid, "can't be undone"):
            curator_web.run("undo", {"token": self.gh.ref}, self.s, self.gh)

    def test_concurrent_push_is_retried_and_kept(self):
        self.gh.before_patch = lambda: self.gh.push({"DIGEST.md": "from the watch"})
        curator_web.run("approve", {"kind": "new", "ref": "", "form": FORM}, self.s, self.gh)
        self.assertEqual(self.gh.file("DIGEST.md"), "from the watch")
        self.assertIn("Test deal", [d["name"] for d in self.gh.db()["deals"]])

    def test_validation_still_applies(self):
        with self.assertRaisesRegex(curate.Invalid, "VERIFIED"):
            curator_web.run("approve", {"kind": "new", "ref": "", "form": {**FORM, "ver": "PENDING REVIEW"}},
                            self.s, self.gh)
        self.assertEqual(self.gh.ref, "c0", "nothing committed")


class Sessions(unittest.TestCase):
    def setUp(self):
        with mock.patch.dict(os.environ, ENV):
            self.s = curator_web.settings()

    def test_round_trip_and_expiry(self):
        v = curator_web.make_session(self.s, now=1000)
        self.assertTrue(curator_web.session_ok(self.s, v, now=1001))
        self.assertFalse(curator_web.session_ok(self.s, v, now=1000 + curator_web.SESSION_SECONDS + 1))
        self.assertFalse(curator_web.session_ok(self.s, v[:-1] + ("0" if v[-1] != "0" else "1"), now=1001))
        far = str(10**12) + "." + v.split(".")[1]
        self.assertFalse(curator_web.session_ok(self.s, far, now=1001))
        for junk in (None, "", "abc", "1.2.3"):
            self.assertFalse(curator_web.session_ok(self.s, junk))

    def test_new_password_or_secret_logs_out(self):
        v = curator_web.make_session(self.s, now=1000)
        self.assertFalse(curator_web.session_ok({**self.s, "password": "another long passphrase"}, v, now=1001))
        self.assertFalse(curator_web.session_ok({**self.s, "secret": "t" * 40}, v, now=1001))

    def test_password(self):
        self.assertTrue(curator_web.password_ok(self.s, ENV["CURATOR_PASSWORD"]))
        self.assertFalse(curator_web.password_ok(self.s, "wrong"))

    def test_settings_refuse_weak_setup(self):
        with mock.patch.dict(os.environ, {**ENV, "CURATOR_PASSWORD": "short"}):
            self.assertIn("CURATOR_PASSWORD", curator_web.settings()["problem"])
        with mock.patch.dict(os.environ, {k: "" for k in ENV}):
            p = curator_web.settings()["problem"]
            self.assertTrue(all(k in p for k in ("CURATOR_PASSWORD", "SESSION_SECRET", "GITHUB_TOKEN")))
        self.assertIsNone(self.s["problem"])


class Http(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, ENV)
        self.env.start()
        self.gh = FakeGitHub(repo_files())
        handler = type("H", (curator_web.Handler,), {"gh": self.gh})
        self.httpd = HTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.sleep = mock.patch.object(curator_web.time, "sleep")
        self.sleep.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.env.stop()
        self.sleep.stop()

    def req(self, method, action, body=None, cookie=None, origin="same", headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        hdrs = {}
        if method == "POST":
            hdrs = {"Content-Type": "application/json", "X-Curator": "1"}
        if origin == "same":
            hdrs["Origin"] = f"https://127.0.0.1:{self.port}"
        elif origin:
            hdrs["Origin"] = origin
        if cookie:
            hdrs["Cookie"] = f"{curator_web.COOKIE}={cookie}"
        hdrs.update(headers or {})
        c.request(method, f"/api/curator?a={action}", body=None if body is None else json.dumps(body), headers=hdrs)
        r = c.getresponse()
        out = (r.status, json.loads(r.read() or b"{}"), r.getheader("Set-Cookie"))
        c.close()
        return out

    def login(self):
        code, _, cookie = self.req("POST", "login", {"password": ENV["CURATOR_PASSWORD"]})
        self.assertEqual(code, 200)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertIn("Secure", cookie)
        return cookie.split(";")[0].split("=", 1)[1]

    def test_needs_login(self):
        self.assertEqual(self.req("GET", "state")[0], 401)
        self.assertEqual(self.req("POST", "approve", {"kind": "new", "form": FORM})[0], 401)
        self.assertEqual(self.req("POST", "login", {"password": "nope"})[0], 401)
        self.assertEqual(self.gh.ref, "c0")

    def test_login_then_approve(self):
        cookie = self.login()
        code, st, _ = self.req("GET", "state", cookie=cookie)
        self.assertEqual((code, st["mode"]), (200, "web"))
        code, r, _ = self.req("POST", "approve", {"kind": "new", "ref": "", "form": FORM}, cookie=cookie)
        self.assertEqual(code, 200, r)
        self.assertIn("Test deal", [d["name"] for d in self.gh.db()["deals"]])
        code, r, _ = self.req("POST", "approve", {"kind": "new", "ref": "", "form": {**FORM, "date": "x"}},
                              cookie=cookie)
        self.assertEqual(code, 400)

    def test_cross_site_requests_refused(self):
        cookie = self.login()
        for kw in ({"origin": "https://evil.example"},
                   {"headers": {"X-Curator": "0"}},
                   {"headers": {"Content-Type": "text/plain"}}):
            self.assertEqual(self.req("POST", "approve", {"kind": "new", "form": FORM}, cookie=cookie, **kw)[0], 403)
        self.assertEqual(self.gh.ref, "c0")

    def test_logout_clears_cookie(self):
        _, _, cookie = self.req("POST", "logout", {})
        self.assertIn("Max-Age=0", cookie)

    def test_not_configured(self):
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": ""}):
            code, r, _ = self.req("GET", "state")
        self.assertEqual(code, 503)
        self.assertIn("GITHUB_TOKEN", r["error"])


if __name__ == "__main__":
    unittest.main()

