# AGENTS.md

Chip-Backed Finance Observatory (AI Transparency Institute): a static site plus a Python feed watcher. Deployed at https://chips-sigma.vercel.app/ (Vercel deploys from git, static, no build step). See README.md for the pipeline, curation routine and file list.

## Key facts
- `index.html` has no inline script or style; all JS is in `app.js`, all CSS in `styles.css`. `vercel.json` sets a CSP that allows only same-origin scripts and styles, so never add inline `<script>`, `<style>`, `style=` or `on*=` handlers (also not in markup that `app.js` generates).
- `app.js` holds a generated `SEED` snapshot (between `SEED:BEGIN`/`SEED:END`). Regenerate it with `python3 update_seed.py`; never edit it by hand. A test fails when it is stale.
- Only `VERIFIED`/`REPORTED` deals are counted and shown in the registry. `PENDING REVIEW` rows are listed apart.
- Deal fields: `id` (unique), `date` (`YYYY-MM` or `YYYY-MM-DD`), `name`, `type`, `amount`, `terms`, `status`, `ver`, `src`; optional `url`, `outlet`, `sources: [{outlet, url, date, title}]`.
- `curate.py` serves a local review page (`curator/`, 127.0.0.1 only) where the curator approves or rejects leads. It writes `observatory-data.json`, `state/reviewed.json` and the `app.js` seed. It sets `ver` only to the value the curator picked in the form. `curator/` and `curate.py` are excluded from the Vercel deploy (`.vercelignore`).
- `watch.py` (mode `off` by default) writes `candidates.json`, `DIGEST.md`, `state/seen.json`, `state/stories.json`. Story grouping and source tiers live in `stories.py`, which `prevalidate.py` and `merge_pending.py` also use. EDGAR filings are one candidate per filing and are kept out of headline grouping.
- `.github/workflows/watch.yml` has two jobs: `watch` (read-only token, runs third-party code on untrusted feeds) and `publish` (write token, copies only the listed data files, rebuilds `app.js` itself, pushes). Keep that split. Actions are pinned to commit SHAs.
- `requirements-watch.txt` is hash-pinned and generated from `requirements-watch.in` (command in its header). Don't hand-edit it.
- Feed fetches go through `watch.http_get` (size and time caps). Feed text in the issue/digest goes through `stories.md_safe`, links through `stories.md_url`.
- GlobeNewswire's RSS returns 403 to automated clients. Press-release wires are searched through Google News instead. Do not spoof a browser User-Agent.

## Checks
```
python3 -m unittest discover tests && node tests/test_render.mjs
```

## Rules
- Never set `ver` to `VERIFIED` or `REPORTED` from code. Only a human curator does that. Machine entries are `PENDING REVIEW`.
- `watch.py` modifies tracked files (`state/`, digest, and the site data in `direct` mode). Running it locally consumes dedupe state; experiment in a copy of the repo.
- Treat feed content as untrusted: pass every value through `esc()` and link only via `link()`/`safeUrl()` in `app.js`.
- Do not republish feed excerpts on the site. `terms` for machine entries is a neutral note; excerpts stay in `candidates.json` (`_summary`).
- After changing terms in `config.json`, run the tests: every `deal` in the labelled sample must still pass, and no story group may mix two labelled stories.
