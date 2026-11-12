# Security policy

## Scope
- The website (`index.html`, `app.js`, `observatory-data.json`, `vercel.json`), deployed from this repository's `main` branch.
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
- `vercel.json` sets a Content-Security-Policy that allows scripts only from the site itself. Do not add inline scripts or `on*=` handlers to `index.html`.
- Code never sets `ver` to `VERIFIED` or `REPORTED`.
