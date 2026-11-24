# Setting up the curator page (one time, about 10 minutes)

After this, reviewing deals works like this: open **https://chips-sigma.vercel.app/curator/**, type the password, and click **Approve…** or **Reject**. Every click saves right away, and the public site shows the change about a minute later. Nothing to install.

This needs the GitHub and Vercel accounts that own the site (evathelisson-AITI). It's all clicking.

## 1. Create a GitHub key for the page
1. Go to https://github.com/settings/personal-access-tokens/new (GitHub → your picture → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token).
2. **Token name:** `Chips curator page`. **Expiration:** 1 year (put a reminder in your calendar to renew it).
3. **Repository access:** "Only select repositories" → choose **Chips**.
4. **Permissions** → Repository permissions → **Contents: Read and write**. Leave everything else as it is.
5. Click **Generate token** and copy it (it starts with `github_pat_`). You'll paste it in step 2. GitHub shows it only once.

## 2. Give the page its settings in Vercel
1. Go to https://vercel.com → project **chips-sigma** → **Settings** → **Environment Variables**.
2. Add these four, each for the **Production** environment:

| Name | Value |
|---|---|
| `GITHUB_TOKEN` | the token from step 1 |
| `CURATOR_PASSWORD` | a passphrase you'll remember, at least 16 characters, e.g. four random words |
| `SESSION_SECRET` | any long random text, at least 32 characters (Kirtan can generate one for you) |
| `GITHUB_REPO` | `evathelisson-AITI/Chips` |

3. Save.

## 3. Turn it on
Merge the pull request that adds the curator page (your merge is the one Vercel deploys). After that, open https://chips-sigma.vercel.app/curator/ and log in.

If you added the settings after the last deploy: Vercel → Deployments → the top one → ⋯ → **Redeploy**.

## Everyday use
- **To review:** new leads from the weekly watch (Mondays). Open the source, then **Approve…** (check the pre-filled form, choose VERIFIED or REPORTED, click **Publish to site**) or **Reject**.
- **Published:** deals on the site. **Edit** fixes details, **Remove** takes a deal off.
- **Undo** appears in the message at the bottom after each save.
- **Log out** at the top right, or it logs you out by itself after 12 hours.

## If something goes wrong
- *"The curator page is not set up yet…"*: a setting from step 2 is missing or too short. Fix it in Vercel and redeploy.
- *"GitHub answered 401/403"*: the token expired or lacks Contents: Read and write. Make a new one (step 1) and replace `GITHUB_TOKEN`.
- *"Someone else saved at the same moment"*: reload the page and do it again.
- **Change the password:** edit `CURATOR_PASSWORD` in Vercel and redeploy. Everyone gets logged out.
