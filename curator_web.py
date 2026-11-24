"""
The curator page on the live site (https://<site>/curator/), behind a password.

The Vercel function api/curator.py serves the same API as the local tool
(curate.py), but reads the repo files from GitHub and saves every change as one
commit on main, which Vercel then deploys. Standard library only.

Settings (Vercel -> Project -> Settings -> Environment Variables):
  CURATOR_PASSWORD  the passphrase the curator types (at least 16 characters)
  SESSION_SECRET    random text, at least 32 characters; changing it logs everyone out
  GITHUB_TOKEN      fine-grained token for this one repository, "Contents: read and write"
  GITHUB_REPO       owner/name, default evathelisson-AITI/Chips
  GITHUB_BRANCH     default main

The token's owner is the commit author, so it must be an account Vercel deploys for.
`ver` is still only ever the value the curator picked (curate.clean enforces it).
"""
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler

import curate

COOKIE = "__Host-curator"
SESSION_SECONDS = 12 * 3600
COMMIT_PREFIX = "Curator: "
WRITTEN = (curate.DATA, curate.REVIEWED, curate.APP)  # what a curator commit may change
READ_AHEAD = (curate.DATA, curate.REVIEWED, curate.CANDIDATES, curate.PREVALIDATION, curate.HINTS, curate.CONFIG)
WEB_NOTE = " The public site updates in about a minute."


class Conflict(Exception):
    """main moved while we were saving."""


class GitHubError(Exception):
    pass


# ------------------------------------------------------------ GitHub
class GitHub:
    def __init__(self, repo, token, opener=None):
        self.repo, self.token = repo, token
        self.open = opener or urllib.request.urlopen

    def call(self, method, path, body=None, raw=False):
        req = urllib.request.Request(
            f"https://api.github.com/repos/{self.repo}/{path}", method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.token}", "User-Agent": "chips-curator",
                     "X-GitHub-Api-Version": "2022-11-28",
                     "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
                     **({"Content-Type": "application/json"} if body is not None else {})})
        try:
            with self.open(req, timeout=20) as r:
                data = r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404 and raw:
                return None
            if e.code == 422 and method == "PATCH":
                raise Conflict() from None
            raise GitHubError(f"GitHub answered {e.code} for {method} {path.split('?')[0]}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise GitHubError("GitHub could not be reached. Try again in a minute.") from None
        return data.decode("utf-8") if raw else json.loads(data or b"{}")


class GitHubStore:
    """The repo files at the head of a branch. write() makes one commit and moves
    the branch without force, so a concurrent push makes it raise Conflict."""
    mode = "web"

    def __init__(self, gh, branch="main"):
        self.gh, self.branch = gh, branch
        self.head = gh.call("GET", f"git/ref/heads/{branch}")["object"]["sha"]
        self.cache = {}

    def _get(self, rel, sha):
        return self.gh.call("GET", f"contents/{urllib.parse.quote(rel)}?ref={sha}", raw=True)

    def prefetch(self, rels):
        todo = [r for r in rels if r not in self.cache]
        with ThreadPoolExecutor(max_workers=6) as ex:
            for rel, text in zip(todo, ex.map(lambda r: self._get(r, self.head), todo)):
                self.cache[rel] = text

    def text(self, rel):
        if rel not in self.cache:
            self.cache[rel] = self._get(rel, self.head)
        return self.cache[rel]

    def write(self, files, label):
        base = self.gh.call("GET", f"git/commits/{self.head}")["tree"]["sha"]
        tree = self.gh.call("POST", "git/trees", {"base_tree": base, "tree": [
            {"path": rel, "mode": "100644", "type": "blob", "content": text} if text is not None
            else {"path": rel, "mode": "100644", "type": "blob", "sha": None}
            for rel, text in files.items()]})["sha"]
        commit = self.gh.call("POST", "git/commits", {
            "message": COMMIT_PREFIX + label[:200], "tree": tree, "parents": [self.head]})["sha"]
        self.gh.call("PATCH", f"git/refs/heads/{self.branch}", {"sha": commit, "force": False})
        self.head = commit
        self.cache.update(files)
        return commit

    def undo(self, token=None):
        """Reverts the curator commit `token`, if nothing was committed after it."""
        if not token:
            raise curate.Invalid("Nothing to undo.")
        if token != self.head:
            raise curate.Invalid("Can't undo any more: the data changed after that save. "
                                 "Fix the entry on this page instead.")
        commit = self.gh.call("GET", f"git/commits/{token}")
        message, parents = commit.get("message", ""), commit.get("parents") or []
        if not message.startswith(COMMIT_PREFIX) or len(parents) != 1:
            raise curate.Invalid("That change can't be undone here.")
        old = {rel: self._get(rel, parents[0]["sha"]) for rel in WRITTEN}
        label = message[len(COMMIT_PREFIX):].split("\n")[0]
        self.write(old, f"undo {label}")
        return label

    def undo_label(self):
        return None  # the page keeps the token of the last save


# ------------------------------------------------------------ settings and sessions
def settings():
    env = os.environ
    s = {"password": env.get("CURATOR_PASSWORD", ""), "secret": env.get("SESSION_SECRET", ""),
         "token": env.get("GITHUB_TOKEN", ""), "repo": env.get("GITHUB_REPO", "evathelisson-AITI/Chips"),
         "branch": env.get("GITHUB_BRANCH", "main")}
    problems = []
    if len(s["password"]) < 16:
        problems.append("CURATOR_PASSWORD (at least 16 characters)")
    if len(s["secret"]) < 32:
        problems.append("SESSION_SECRET (at least 32 characters)")
    if not s["token"]:
        problems.append("GITHUB_TOKEN")
    s["problem"] = ("The curator page is not set up yet. Missing in Vercel's environment variables: "
                    + ", ".join(problems) + ".") if problems else None
    return s


def _mac(s, expires):
    # The password's hash is part of the signature, so changing the password logs everyone out.
    pw = hashlib.sha256(s["password"].encode()).hexdigest()
    return hmac.new(s["secret"].encode(), f"curator|{expires}|{pw}".encode(), hashlib.sha256).hexdigest()


def make_session(s, now=None):
    expires = int(now if now is not None else time.time()) + SESSION_SECONDS
    return f"{expires}.{_mac(s, expires)}"


def session_ok(s, value, now=None):
    try:
        expires, mac = value.split(".", 1)
        expires = int(expires)
    except (AttributeError, ValueError):
        return False
    now = now if now is not None else time.time()
    return expires > now and expires - now <= SESSION_SECONDS and hmac.compare_digest(mac, _mac(s, expires))


def password_ok(s, given):
    a = hashlib.sha256(str(given).encode()).digest()
    b = hashlib.sha256(s["password"].encode()).digest()
    return hmac.compare_digest(a, b)


def run(action, body, s, gh=None):
    """One change against GitHub. If main moved meanwhile (the weekly watch pushed,
    or a second tab saved), it re-reads and tries once more."""
    gh = gh or GitHub(s["repo"], s["token"])
    for attempt in (1, 2):
        store = GitHubStore(gh, s["branch"])
        store.prefetch(READ_AHEAD)
        try:
            result = curate.act(action, body, store)
        except Conflict:
            if action == "undo" or attempt == 2:
                raise curate.Invalid("Someone else saved at the same moment. Reload the page and try again.")
            continue
        result["message"] = result["message"].rstrip(".") + "." + WEB_NOTE
        result["state"] = curate.state(store)
        return result


def load_state(s, gh=None):
    store = GitHubStore(gh or GitHub(s["repo"], s["token"]), s["branch"])
    store.prefetch(READ_AHEAD)
    return curate.state(store)


# ------------------------------------------------------------ HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "curator"
    gh = None  # tests put a fake GitHub here

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, cookie=None):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex")
        self.send_header("Content-Security-Policy", curate.CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def _cookie(self):
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == COOKIE:
                return v
        return None

    def _route(self):
        return (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("a") or [""])[0]

    def _same_origin(self):
        origin = self.headers.get("Origin")
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "")
        return origin is None or origin == f"https://{host}"

    def do_GET(self):
        s = settings()
        if s["problem"]:
            return self._send(503, {"error": s["problem"]})
        if self._route() != "state":
            return self._send(404, {"error": "not found"})
        if not session_ok(s, self._cookie()):
            return self._send(401, {"error": "Please log in."})
        try:
            self._send(200, load_state(s, self.gh))
        except GitHubError as e:
            self._send(502, {"error": str(e)})

    def do_POST(self):
        s = settings()
        if s["problem"]:
            return self._send(503, {"error": s["problem"]})
        # A cross-site page cannot send X-Curator without a CORS preflight, which we never answer.
        if (self.headers.get("X-Curator") != "1" or not self._same_origin()
                or not self.headers.get("Content-Type", "").startswith("application/json")):
            return self._send(403, {"error": "forbidden"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(min(n, 100_000)) or b"{}")
        except ValueError:
            return self._send(400, {"error": "bad request"})
        body = body if isinstance(body, dict) else {}
        action = self._route()

        if action == "login":
            if not password_ok(s, body.get("password", "")):
                time.sleep(1)  # slows guessing
                return self._send(401, {"error": "Wrong password."})
            return self._send(200, {"ok": True}, cookie=(
                f"{COOKIE}={make_session(s)}; Path=/; Max-Age={SESSION_SECONDS}; Secure; HttpOnly; SameSite=Strict"))
        if action == "logout":
            return self._send(200, {"ok": True}, cookie=f"{COOKIE}=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Strict")
        if not session_ok(s, self._cookie()):
            return self._send(401, {"error": "Please log in."})
        if action not in ("approve", "reject", "undo"):
            return self._send(404, {"error": "not found"})
        try:
            self._send(200, run(action, body, s, self.gh))
        except curate.Invalid as e:
            self._send(400, {"error": str(e)})
        except GitHubError as e:
            self._send(502, {"error": str(e)})


__all__ = ["Handler", "GitHub", "GitHubStore", "settings", "make_session", "session_ok", "password_ok", "run"]
