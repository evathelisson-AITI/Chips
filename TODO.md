# TODO

Reviewed and reprioritized on 2026-11-12. Everything that code can do was implemented the same day. What remains needs a human: **(curator)** marks data decisions that code must not make (see AGENTS.md), and **(owner)** marks repo or organisation decisions.

## Open
- [ ] **(curator) Triage the 28 pending rows.** Duplicates are already merged (69 headlines → 28 rows, each with its other sources listed). `PREVALIDATION.md` has suggestions: 7 deal clusters (IREN $2.4bn, Lambda $1bn, Bullish/USD.AI $100M, GSAM $6.6bn, …) and 4 suggested rejects. Promote real deals to `VERIFIED`/`REPORTED` entries and delete the rest.
- [ ] **(curator) Check the draft labels** in `tests/relevance_sample.json` (`label` and `story`). The filter and grouping tests rely on them.
- [ ] **(curator) New lead from the 2026-11-12 test run:** the FT reported on 2026-11-11 that CoreWeave plans a multibillion-dollar chip-backed debt deal. CoreWeave's 10-Q, filed the same day, is also in that run's EDGAR results.
- [ ] **(owner) Push to `main`.** That starts the twice-weekly schedule and redeploys the site with the new headers. Make sure the repo's Actions setting "Workflow permissions" allows read and write, or the commit step fails.
- [ ] **(owner) Choose a code license.** `LICENSE` covers data and content (CC BY 4.0). The code license is undecided.
- [ ] **(owner) Confirm the response times in `SECURITY.md`** (acknowledge within 5 business days, plan within 30 days).
- [ ] **(owner) Decide whether EDGAR should include 10-Q/10-K.** In the test run, the `"GPU" "collateral"` query alone returned 49 filings, mostly quarterly reports. Some are relevant (IREN, CoreWeave, TeraWulf, WhiteFiber), many are not. To cut noise, add `"10-Q"` and `"10-K"` to `edgar_exclude_forms`, at the cost of missing financings disclosed only in periodic reports.

## Not possible as specified
- **Resolving Google News links to publisher URLs.** Following the redirect lands on Google's consent page. Decoding the links would need Google's undocumented internal API. Instead, the publisher name is taken from each item's `<source>` element and stored as `outlet`, which is enough for source ranking and duplicate grouping. Links still go through Google News.
- **GlobeNewswire RSS.** It refuses automated clients (HTTP 403) and we don't spoof a browser. The feed is replaced by Google News searches limited to prnewswire, businesswire and globenewswire.

## Done (2026-11-12, security pass)
- [x] CSP without `'unsafe-inline'`: CSS moved to `styles.css`, inline `style=` replaced by classes. `default-src 'none'`, `upgrade-insecure-requests`. Added HSTS, COOP, CORP; Permissions-Policy uses `browsing-topics` instead of the obsolete `interest-cohort`. Checked in a browser under the headers.
- [x] `app.js` ignores malformed parts of the data file (non-array lists, non-object rows, non-numeric series) instead of failing.
- [x] Review issue: feed text is escaped for markdown/HTML, `#` references neutralised like `@` mentions, link targets http(s) only and percent-encoded. Non-http(s) feed links are dropped at collection.
- [x] Feed and EDGAR downloads capped at 5 MB and 60 s. EDGAR accession numbers and CIKs validated before they go into URLs. `prevalidate.py --online` only follows http(s) links and does not download bodies.
- [x] Workflow split into `watch` (read-only) and `publish` (write) jobs; `persist-credentials: false`; push with hooks disabled; actions pinned to SHAs; dependencies hash-pinned (`requirements-watch.in` → `.txt`); `.github/dependabot.yml`.

## Done (2026-11-12)
Site
- [x] Registry table and stats show curated deals only. Pending leads are listed apart and not counted. Removed the hardcoded "≈ USD 7bn" stat.
- [x] All data escaped (`esc()`). Links only to http(s) (`safeUrl()`). No inline handlers.
- [x] JS moved to `app.js`. `vercel.json` adds CSP (same-origin scripts only), X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy. Checked in a browser under the CSP.
- [x] Source links rendered from a `url` field, plus a "+N more sources" list per row. Feed excerpts are no longer republished.
- [x] Dates displayed consistently ("Aug 2023", "1 Oct 2026").
- [x] Fallback: the embedded snapshot is generated from the data (`update_seed.py`, run by the workflow), holds curated deals only, and shows a visible notice when used.
- [x] Methodology text describes the watcher and the review step.

Data
- [x] Decoded HTML entities. Every deal has a unique `id`. Source links moved from `terms` into `url`.
- [x] Duplicate pending rows merged into stories (`merge_pending.py`): 69 → 28. The 18 Vinanet spam copies were dropped from their group, which keeps its Forbes, Memeburn and Gundlach coverage.

Watcher
- [x] One copy of each script, run by `.github/workflows/watch.yml` (FTP step removed). Mode `off` + review issue. The fake `pr` mode is removed.
- [x] Relevance filter: whole-word matching, title-only combination rule, narrowed Nvidia/data-center rule, exclude terms, blocklist on title, link and outlet.
- [x] Story grouping (`stories.py`): same company + amount, or similar titles, within 14 days, plus a narrower rule for reworded headlines. The best source leads. `state/stories.json` marks follow-ups across runs. `direct` mode attaches to existing rows.
- [x] EDGAR: one candidate per filing (multiple matching documents and queries are folded in), form filter, paging (the old 20-hit limit was our own slice), "TRUNCATED" note when `edgar_max_hits` is reached. Replaced the noisy `"graphics processing units" "lease"` query.
- [x] Undated items rejected. `@` neutralised in issue text. Entity list extended (Crusoe, TeraWulf, Cipher, Fluidstack, Applied Digital, Hut 8, WhiteFiber). Fixed "Won't" being read as Korean won.

Repo
- [x] `README.md`, `SECURITY.md`, `LICENSE` (data), `.gitignore`. Stale root `seen.json` deleted.
- [x] Tests: `python3 -m unittest discover tests` (filter, grouping, EDGAR, merge, direct mode, data shape, seed freshness) and `node tests/test_render.mjs` (escaping, links, counts, dates, fallback, no inline script). Both run in the workflow before the watcher.
