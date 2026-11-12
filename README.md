# Chip-Backed Finance Observatory

An open research database of debt secured by AI chips, from the AI Transparency Institute: hand-collected deal terms, a GPU collateral price index, an announcement-event calendar and a holdings map.

Live site: https://chips-sigma.vercel.app/

## How it works

```
 sources ──► watch.py ──► candidates.json / DIGEST.md ──► GitHub issue ──► curator ──► observatory-data.json ──► site
 (EDGAR, press wires,     (filters, groups duplicates     (prevalidate.py adds         (adds real deals by hand,
  FT, Google News)         into stories)                   suggestions)                 VERIFIED or REPORTED)
```

- **Site**: `index.html` + `app.js`, static, no build step. Vercel deploys from `main`. The page loads `observatory-data.json` at every visit. If that fails, it shows an embedded snapshot with a notice.
- **Registry**: only entries a curator marked `VERIFIED` (primary source) or `REPORTED` (press only) are counted and shown in the deal table. Older machine-collected `PENDING REVIEW` leads are listed apart, uncounted, until the curator reviews them.
- **Source watch**: `.github/workflows/watch.yml` runs Monday and Thursday at 07:00 UTC, or by hand from the Actions tab. It does not change the site data (`auto_publish_mode: "off"` in `config.json`). It opens an issue that lists one line per story, with duplicates folded in.

## Curation routine
1. Open the latest "Observatory watch" issue (or `DIGEST.md` and `PREVALIDATION.md`).
2. For each story worth recording, open the source. Prefer the primary source (filing or issuer press release).
3. Add an entry to `deals` in `observatory-data.json`:
   ```json
   {"id": "d-coreweave-ddtl6", "date": "2026-11", "name": "…", "type": "GPU-backed loan",
    "amount": "2,000 M", "terms": "…", "status": "Closed", "ver": "VERIFIED",
    "src": "CoreWeave press release, 11/2026", "url": "https://…"}
   ```
   `ver` is `VERIFIED` for a primary source and `REPORTED` for press only. `url` is optional. Each `id` must be unique.
4. For `PENDING REVIEW` rows: promote them into a proper entry as above, or delete them.
5. Run the checks and commit:
   ```
   python3 update_seed.py                      # refresh the page's fallback snapshot
   python3 -m unittest discover tests && node tests/test_render.mjs
   ```

## Configuration (`config.json`)
- Terms: `strong_phrases`, `tech_terms`, `context_terms`, `finance_terms`, `strong_finance_terms`, `exclude_terms`. Matching is whole-word, plurals are automatic, and a trailing `*` makes a prefix. After changing terms, run the tests: every real deal in `tests/relevance_sample.json` must still pass.
- Sources: `tier1_edgar_queries` (+ `edgar_exclude_forms`, `edgar_max_hits`), `tier1_google_news_queries` (press-release wires), `tier2_ft_feeds`, `tier2_google_news_queries`, `tier3_extra_rss`. Outlets in `blocked_sources` are skipped.
- `auto_publish_mode`: `off` (recommended) or `direct` (adds `PENDING REVIEW` rows to the site data, attaching duplicates to existing rows).

## Files
| File | Purpose |
|---|---|
| `index.html`, `app.js`, `styles.css` | the site; `app.js` escapes all data and holds the fallback snapshot |
| `observatory-data.json` | the data: `updated`, `deals`, `resale`, `rental`, `events` |
| `vercel.json` | security headers (CSP allows only same-origin scripts and styles, HSTS, COOP/CORP) |
| `requirements-watch.in`, `requirements-watch.txt` | watcher dependencies; `.txt` is the hash-pinned lock |
| `watch.py` | source watch |
| `stories.py` | shared helpers: outlet, source tier, story grouping |
| `prevalidate.py`, `primary_hints.json` | suggestions for the curator (never changes data) |
| `merge_pending.py` | folds duplicate `PENDING REVIEW` rows into one row with a `sources` list |
| `update_seed.py` | regenerates the fallback snapshot in `app.js` |
| `state/seen.json`, `state/stories.json` | watcher memory: articles seen, stories seen (60 days) |
| `tests/` | offline tests (Python stdlib, Node) |

## Run locally
```
python3 -m http.server 8000            # http://localhost:8000
pip install --require-hashes -r requirements-watch.txt
python3 watch.py                       # network; updates state/ and the digest
```
Running `watch.py` locally marks articles as seen, so the scheduled run won't report them again. To experiment, run it in a copy of the repo.

## License
Data and site content: CC BY 4.0 (see `LICENSE`). Code: license not yet chosen.
Security reports: see `SECURITY.md`.
