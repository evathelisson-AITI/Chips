# Security policy

## Scope
- The website (`index.html`, `app.js`, `styles.css`, `observatory-data.json`, `vercel.json`), deployed from this repository's `main` branch.
- The source watch (`watch.py`, `prevalidate.py`, `merge_pending.py`, `stories.py`, `update_seed.py`) and its GitHub Actions workflow (`.github/workflows/watch.yml`).

Only the current `main` branch is supported. There are no versioned releases.

## Reporting a vulnerability
Email **contact@aitransparencyinstitute.com** with "Security" in the subject. Please include the affected file or URL, steps to reproduce, and the impact you expect. Please do not open a public issue for an unfixed vulnerability.

What to expect:
- An acknowledgement within 5 business days.
- An assessment, and a fix or mitigation plan, within 30 days for confirmed issues.
- Credit in the commit message if you want it.

## Data-integrity reports
Wrong or misleading data, for example an unverified headline shown as a fact, is also treated as a security-relevant report. Use the same address.

## Design notes for contributors
- All feed content is untrusted. `app.js` escapes every value (`esc()`) and links only to `http(s)` URLs. `tests/test_render.mjs` checks this.
- `vercel.json` sets a Content-Security-Policy that allows scripts and styles only from the site itself (no `unsafe-inline`). Do not add inline scripts, inline styles or `on*=` handlers, in `index.html` or in markup `app.js` generates.
- Feed text that reaches the GitHub review issue is escaped (`stories.md_safe`: no injected links, HTML, @mentions or issue references) and feed links must be http(s) (`stories.safe_http_url`, `stories.md_url`). Feed downloads are capped in size and time (`watch.http_get`).
- The workflow runs the watcher (third-party packages, untrusted feeds) in a job with a read-only token. A separate job with write access takes only the expected data files from it, rebuilds `app.js` itself and pushes. Actions are pinned to commit SHAs and Python packages to hashes; Dependabot proposes updates.
- Code never sets `ver` to `VERIFIED` or `REPORTED`.
