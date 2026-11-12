# TODO

Reviewed and reprioritized on 2026-11-12. Everything that code can do was implemented the same day. What remains needs a human: **(curator)** marks data decisions that code must not make (see AGENTS.md), and **(owner)** marks repo or organisation decisions.

## Open
Red-team findings from 2026-11-13. Items that need a human:
- [ ] **(owner) Run the backfill once.** The watch didn't run from 2026-10-01 to now, and its 14-day window means those weeks are never picked up. Run the workflow by hand with `max_age_days` = 60. A test run in a copy found big deals missing from the registry: SpaceX's $40bn GPU debt (Reuters, 26 Oct), Lambda's $1bn senior secured financing (Business Wire, 1 Oct), Amazon's ~$8bn Grace Blackwell SPV leaseback, Nebius borrowing $3.5bn, CoreWeave's ≥$4bn high-grade loan (Bloomberg, 12 Nov), NexGen Cloud / QumulusAI / USD.AI facilities, plus 8-Ks from SharonAI, Cipher, TeraWulf, WhiteFiber and Hut 8 (items 1.01/2.03).
- [ ] **(curator) Classify `collateral` for the 10 published deals.** Until then the overview says "10 collateral not yet classified". Candidates for "related, not counted": the Nvidia–OpenAI LOI (equity) and the Nvidia "$500bn" row (per `primary_hints.json`, MOUs for platforms raising third-party capital, not Nvidia money). Also check whether the xAI notes are secured by GPUs.
- [ ] **(curator) Add a source `url` to every published deal.** None has one today, although the site says every entry lists its source. New `VERIFIED` rows can't be saved without one.
- [ ] **(curator) Re-flag rows whose flag doesn't fit the definition.** xAI is `VERIFIED` on Reuters/PitchBook (press). The Nvidia $500bn row is `REPORTED` "unconfirmed by primary source", but a primary Nvidia release is in `primary_hints.json`.
- [ ] **(curator) Fix the Lambda row and the ~50% residual claim.** `primary_hints.json` says the 2024 Lambda/Macquarie deal was a loan, not an ABS. The overview stat "~50% residual value… in early GPU-backed securitizations" and the Price Index note ("fell to ~27%… vs ~50%") rest on it. That note also measures from the 2023 peak, not from the deal date.
- [ ] **(curator) Check the Price Index caption.** With points now on a real time axis, the resale line is a fairly steady decline. "Note the step behavior around new-generation availability" was partly an effect of the even spacing.
- [ ] **(curator) Record sources for each price point** (`[label, value, {src, url, sku}]`), and say which unit is meant (PCIe/SXM, card/server, new/used). Better sources: Vast.ai's public API, list prices, dated broker quotes; commercial rental indices need a licence.
- [ ] **(curator) Check CoreWeave's DDTL history against its 10-K/10-Q debt note.** DDTL 2.0 (~$7.5bn, May 2024) and 3.0 (~$2.6bn, Jul 2025) seem to be missing, and "DDTL 5.5" ($2.6bn, MUFG) looks like 3.0.
- [ ] **(curator) Quarterly recall audit.** List every GPU-secured facility in the debt notes of the `issuers` with a CIK, and publish "N of M known public-company facilities in the registry".
- [ ] **(curator) Replace the paraphrased `recall_items`** in `tests/relevance_sample.json` with verbatim headlines.
- [ ] **(owner) Decide on cadence.** PR Newswire's financing feed only holds about a day of items, so it is useless weekly. A daily watch (with a weekly issue) would let wire feeds be added.
- [ ] **(owner) Holdings Map sources to pursue.** BDC schedules of investments (Blue Owl, Ares, BXSL…; the full-text query already finds Blue Owl BDC 10-Qs), N-PORT fund holdings, rating-agency presales, and UCC-1 lien searches (paid).

- [ ] **(curator) Triage the 9 pending rows.** 19 clear non-deals (commentary, explainers, stock and earnings news, tokenized-stock DeFi) were removed on 2026-11-12. Left: 5 likely deals (GSAM $6.6bn for OpenAI, Bullish/USD.AI $100M, Lambda $1bn, IREN $2.4bn, Sharon AI) and 4 borderline (Nebius $5bn debt raise, Broadcom "$60B" from an aggregator, Tencent leasing Oracle capacity, Nvidia insuring chip loans). `PREVALIDATION.md` has suggestions. Promote real deals to `VERIFIED`/`REPORTED` and delete the rest.
- [ ] **(curator) Check the draft labels** in `tests/relevance_sample.json` (`label` and `story`). The filter and grouping tests rely on them.
- [ ] **(curator) New lead from the 2026-11-12 test run:** the FT reported on 2026-11-11 that CoreWeave plans a multibillion-dollar chip-backed debt deal. CoreWeave's 10-Q, filed the same day, is also in that run's EDGAR results.
- [ ] **(owner) Push to `main`.** That starts the weekly schedule and redeploys the site with the new headers. Make sure the repo's Actions setting "Workflow permissions" allows read and write, or the commit step fails.
- [ ] **(owner) Choose a code license.** `LICENSE` covers data and content (CC BY 4.0). The code license is undecided.
- [ ] **(owner) Confirm the response times in `SECURITY.md`** (acknowledge within 5 business days, plan within 30 days).
- [ ] **(owner) Decide whether EDGAR should include 10-Q/10-K.** In the test run, the `"GPU" "collateral"` query alone returned 49 filings, mostly quarterly reports. Some are relevant (IREN, CoreWeave, TeraWulf, WhiteFiber), many are not. To cut noise, add `"10-Q"` and `"10-K"` to `edgar_exclude_forms`, at the cost of missing financings disclosed only in periodic reports.

## Not possible as specified
- **Resolving Google News links to publisher URLs.** Following the redirect lands on Google's consent page. Decoding the links would need Google's undocumented internal API. Instead, the publisher name is taken from each item's `<source>` element and stored as `outlet`, which is enough for source ranking and duplicate grouping. Links still go through Google News.
- **GlobeNewswire RSS.** It refuses automated clients (HTTP 403) and we don't spoof a browser. The feed is replaced by Google News searches limited to prnewswire, businesswire and globenewswire.

## Done (2026-11-13, red-team pass)
- [x] Recall: watched `issuers` count as chip terms; more finance terms (facility, notes, DDTL, ABS, lender…); non-USD amounts (¥, yen, Rs, crore, USD prefix). Before: the filter rejected "CoreWeave Closes $2.6 Billion Delayed Draw Term Loan Facility". New `recall_items` test set from outside the watcher's output (the old sample could only check precision).
- [x] Stress lane: defaults, seizures, downgrades, covenant waivers are kept without a deal signal and listed apart in the digest. 8-K items 2.04/2.06 are flagged too.
- [x] Per-company EDGAR scan from `issuers` CIKs (8-K items 1.01/1.02/2.03/2.04/2.06, periodic reports, IPO registration statements); all CIKs checked against sec.gov. Full-text search limited to current/periodic reports (other forms need two query matches). This cut a 60-day test run from 179 to 94 filings.
- [x] Nvidia newsroom feed, a rating-agency query, issuer and stress queries, en-IN Google News edition; `market_terms` drop stock chatter; near-equal amounts from one company group as one story.
- [x] Backfill: `OBS_MAX_AGE_DAYS` / workflow input `max_age_days`.
- [x] Schema: optional structured fields (`collateral`, `amount_musd`, lenders, rate, maturity, rating, events…) in the data, the curator page and the site; related financings listed apart; total computed from numeric amounts only; resale stat computed from the series; charts on a real time axis; point sources shown or stated as missing; "What is counted" in Methodology. `VERIFIED` requires a link.
- [x] `candidates.json`: legacy feed excerpts moved out of `terms`.

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
