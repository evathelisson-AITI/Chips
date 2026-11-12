# AGENTS.md

Chip-Backed Finance Observatory (AI Transparency Institute): a static site plus a Python feed watcher. Deployed at https://chips-sigma.vercel.app/ (Vercel deploys from git, static, no build step). See README.md for the pipeline, curation routine and file list.

## Key facts
- `index.html` has no inline script; all JS is in `app.js`. `vercel.json` sets a CSP that allows only same-origin scripts, so never add inline `<script>` or `on*=` handlers.
- `app.js` holds a generated `SEED` snapshot (between `SEED:BEGIN`/`SEED:END`). Regenerate it with `python3 update_seed.py`; never edit it by hand. A test fails when it is stale.
- Only `VERIFIED`/`REPORTED` deals are counted and shown in the registry. `PENDING REVIEW` rows are listed apart.
- Deal fields: `id` (unique), `date` (`YYYY-MM` or `YYYY-MM-DD`), `name`, `type`, `amount`, `terms`, `status`, `ver`, `src`; optional `url`, `outlet`, `sources: [{outlet, url, date, title}]`.
- `watch.py` (mode `off` by default) writes `candidates.json`, `DIGEST.md`, `state/seen.json`, `state/stories.json`. Story grouping and source tiers live in `stories.py`, which `prevalidate.py` and `merge_pending.py` also use. EDGAR filings are one candidate per filing and are kept out of headline grouping.
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
