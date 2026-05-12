# GIF Perfect — Project Knowledge

## Workflow Rules
- **Verify deploy target before deploying**: Before running any deploy command, confirm which Netlify site ID / project it will deploy to. Check `.netlify/state.json` or use `--site` flag explicitly. Deploying to the wrong site is a silent failure — the correct site gets nothing.
- **Update CLAUDE.md after every push**: After every git push, update the project's CLAUDE.md to reflect any changes made.
- **⛔ Before EVERY new build, assume a bug exists and find it — whether or not one has been reported.** This is a default-on rule, not a conditional. Re-scan the entire pipeline end-to-end — front-end (UI / IPC / renderer) AND back-end (main process, business logic, pipeline, bundling) — actively hunting for the bug you've assumed is there. If you find one, fix it and re-scan. If after a thorough double-check you're 100% sure no bug exists, build a standalone repro of the **full production chain** (every post-processing step — watermarks, composites, encoders, format conversions, IPC envelope) and prove the path produces the expected output. Only at that point do you tag / commit / trigger the build. Burned 2026-05-12 on PerfectStudio v1.2.2: standalone test omitted the trailing watermark composite, missing that sharp's `.composite()` overwrites prior overlays when chained — v1.2.3 was the real fix. Cost of skipping: 2 wasted ~20-min CI builds + user-visible repeat failure + credibility hit.
- **⛔ Windows Electron installers: always hide the in-window menu bar before shipping.** Electron defaults to showing a `File / Edit / View / Help` strip across the top of every BrowserWindow on Windows (and Linux), which looks unprofessional for a focused desktop app. Required fix: call `win.setMenuBarVisibility(false)` once per window right after `win.loadFile(...)`, with NO platform guard. macOS treats it as a no-op (menu lives in the system menu bar at the top); Windows hides the strip. The menu can stay registered via `Menu.setApplicationMenu(...)` — visibility and registration are independent, so keyboard accelerators still fire and Alt brings the bar back when needed. Always re-verify on a fresh Windows install before shipping a new desktop-app version. Burned 2026-05-12 on PerfectStudio v1.2.3: `main.js` had `if (process.platform === 'darwin') win.setMenuBarVisibility(false)` — macOS-only guard, so Windows users saw the strip; fixed in v1.2.4 by removing the guard.


## Run Locally
```bash
/opt/homebrew/bin/python3.12 app.py
```

## Build Mac .dmg
```bash
bash build_mac.sh
```

## Deploy Sales Page
GitHub → Netlify auto-deploy connected — every push to `main` deploys `site/` automatically.
```bash
# Manual deploy (fallback only):
export PATH="/opt/homebrew/Cellar/node/25.8.1_1/bin:/opt/homebrew/bin:$PATH"
cd site && netlify deploy --prod --dir .
```

## Stripe Payment Links
- Creator ($29): `https://buy.stripe.com/bJe28r3wd61A5Xv9p16Ri04`
- Studio ($99): `https://buy.stripe.com/14A9AT2s92Po99HdFh6Ri03`
- Studio Batch ($199): `https://buy.stripe.com/aFaaEX7Mtey60DbeJl6Ri05`
- Live webhook secret: `whsec_hAvhVSpcGeVcKZtwRCq8KIaaj10NUI6R`
- Test webhook secret: `whsec_9LR9ICUmDoCkBKtDxjxz7XOzNkHQb8Ph`
- Tier detection: `amount_total` cents → 2900=Creator (1 key), 9900=Studio (5 keys), 19900=Studio Batch (5 GIFB- keys)

## Acaption API Webhook Env Vars (Hetzner VPS)
- `STRIPE_GIFPERFECT_SECRET` — live webhook signing secret
- `STRIPE_GIFPERFECT_TEST_SECRET` — test webhook signing secret (both live and test supported simultaneously)
- `RESEND_GIFPERFECT_API_KEY` — dedicated Resend account key for gifperfect.com (`re_YMh8...`)
- `GIFPERFECT_FROM_EMAIL` — `hello@gifperfect.com`

## Resend — Verified Domain
**`gifperfect.com` is the only verified Resend sender domain across the entire stack.**
All products (GifPerfect, SlomoPerfect, UTagger) send licence emails from `hello@gifperfect.com`.
Do NOT change any product's `FROM_EMAIL` to another domain without first verifying that domain in Resend — emails will silently fail.

## Known Bug Fixed (April 2026)
`send_gifperfect_keys()` was guarding on `RESEND_API_KEY` instead of `RESEND_GIFPERFECT_API_KEY`.
Fixed in commit `2510078` — now correctly guards on its own key.

## Install Guide Page (2026-05-03)
`site/install/windows/index.html` — 60-second SmartScreen walkthrough mirroring the ClaudSkills pattern. Hero notice on the homepage links to it instead of the old inline blurb. Page is in `sitemap.xml` (priority 0.7). Update the file-name/size copy in step 1 when shipping a new Windows installer (currently references `GIF Perfect Setup .exe` ~110 MB).

## Netlify Site ID
`d86e96c2-e459-4d9d-b6f6-8c8e9441455a` — `.netlify/state.json` previously held a stale ID (`77bddcb6-...` was a different site that doesn't serve `gifperfect.com`); fixed 2026-05-03. Always pass `--site d86e96c2-...` explicitly when deploying via CLI.

## File Overwrite Policy

- **⛔ Never silently overwrite a local file.** Before any operation that would replace an existing file on the local machine (image/format conversion, codegen, downloads, copies, moves to an occupied path, save-as targets, batch processing), check whether a same-named file already exists at the destination. If it does, **stop and ask the user**: overwrite, or pick a new name? Do not decide on your own based on file size, content similarity, timestamps, single-frame-vs-animated checks, or any other heuristic. The user has to choose. This applies even when the existing file looks redundant, auto-generated, or "obviously" derived from the same source. **Burned 2026-05-12**: silently overwrote 33 single-frame `.gif` files in `/Volumes/All/Gifs/1-25 MB/` during a batch JPG→GIF conversion after self-deciding it was safe.
