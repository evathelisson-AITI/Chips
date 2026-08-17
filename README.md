# Observatory Source Watch — Setup (one page)

Automated monitoring + supervised auto-publication for the Chip-Backed Finance Observatory.
**The machine detects and publishes with a red PENDING REVIEW warning; only a human ever assigns VERIFIED or REPORTED.**

## What runs, twice a week (Mon & Thu, or on demand)
1. Scans SEC EDGAR, press-release wires, FT headline RSS, Google News (Reuters/Bloomberg/FT indexed).
2. New relevant items → `candidates.json` + `DIGEST.md`.
3. **Auto-publication (config `auto_publish_mode`)**: `direct` = merges entries into `observatory-data.json` with badge `PENDING REVIEW` (site shows red badge + warning banner) · `pr` = opens a Pull Request instead, one human click publishes · `off` = detection only.
4. Opens a GitHub **issue titled "PENDING REVIEW: N entries await human verification"** → this is your notification (watch the repo to get it by email).
5. If FTP secrets are set, uploads the updated `observatory-data.json` to the website automatically.

## Setup (once, ~15 minutes)
1. Create a GitHub repository (free account is fine, e.g. `aiti/observatory-watch`) and upload these files: `watch.py`, `config.json`, `requirements.txt`, `observatory-data.json`, `state/seen.json`, `.github/workflows/watch.yml`, this README.
2. In the repo: **Settings → Secrets and variables → Actions → New repository secret**, add:
   - `FTP_HOST` (e.g. `ftp.aitransparencyinstitute.com`)
   - `FTP_USER`, `FTP_PASS`
   - `FTP_DIR` — the folder holding the observatory files, e.g. `/wp-content/uploads/2026/08/`
   *(Skip this step to disable website deployment; the JSON then updates only in the repo.)*
3. Tab **Actions** → enable workflows → select "Observatory source watch" → **Run workflow** to test.
4. Click **Watch → All activity** on the repo so the PENDING REVIEW issues reach your inbox.

## Your curation routine (a few minutes, after each digest)
1. Open the issue / `DIGEST.md`, click each source link, read.
2. Edit `observatory-data.json` (directly on GitHub — pencil icon): for each PENDING entry, either
   - complete `type`, `amount`, `terms`, `status`, set `"ver"` to `"VERIFIED"` (primary source) or `"REPORTED"` (press), **or**
   - delete the block if irrelevant.
3. Commit. The next scheduled run (or a manual run) redeploys the cleaned file. Close the issue.

## Tuning
Everything lives in `config.json`: keywords, feeds, EDGAR queries, `auto_publish_tiers` (default `[1,2]`; set `[1]` to auto-publish primary sources only), `auto_publish_mode`, scan frequency in `watch.yml` (cron line).

## Guarantees built in
- Deduplication: an item is never surfaced twice (`state/seen.json`).
- Idempotence: re-running adds nothing new.
- The machine never sets VERIFIED/REPORTED; the site banners all PENDING entries; the "Data as of" badge announces how many entries await review.
- If anything fails, the website keeps serving the last good JSON (and, failing that, the seed data inside the HTML).
