# GIF Perfect — Project Knowledge

## Workflow Rules
- **Verify deploy target before deploying**: Before running any deploy command, confirm which Netlify site ID / project it will deploy to. Check `.netlify/state.json` or use `--site` flag explicitly. Deploying to the wrong site is a silent failure — the correct site gets nothing.
- **Git push on every change**: After any code change is made and approved, immediately commit and `git push` to GitHub. This applies to this project and all other projects in the stack. No exceptions.
- **Cost rule — free first**: Before recommending any paid tool, service, or subscription, always check whether a free alternative already exists in the current stack or is provided natively by an existing provider. Example: Namecheap and Cloudflare both include free email forwarding — ImprovMX was unnecessary. Always ask: "does a service Adam already pays for cover this?"
- **Verify before confirming anything**: Never confirm that something is true, done, or working without first checking proof. This applies to mid-conversation statements ("yes, X is now the case", "that's already in place", "it's working") as well as task completion. Assume the statement is FALSE until you have verified it with a direct check (read the file, query the state, check the log, hit the endpoint). A successful CLI command is not proof of the outcome. If you haven't checked, don't confirm.
- **Trust the user — search harder before contradicting**: If the user says something has been solved or exists in another workflow, do not contradict them based on a single failed search. Search again more thoroughly (different terms, subagents, broader scope) before saying it cannot be found. The user is usually right.

---


## Market
🌍 **UNIVERSAL** — Desktop app for video → GIF chunking at target file size.
100% content-agnostic — the tool processes video containers, never reads content. Wedding videographers, gaming YouTubers, OF creators, TikTok agencies all have the same problem.
Stripe-native. App Store / ProductHunt / ProductHunt eligible. Zero adult compliance risk.

## Stack Context
- **Business**: Registered in Spain, EU VAT OSS via Stripe. One-time purchase (not subscription).
- **App**: Python 3.12 + CustomTkinter desktop app. Must run with `/opt/homebrew/bin/python3.12 app.py` (system Python has incompatible Tk 8.5.9; Homebrew 3.12 has Tk 9.0.3).
- **Packaging**: PyInstaller + static-ffmpeg. Mac .dmg (local build via `build_mac.sh`). Windows .exe (GitHub Actions `build.yml` on `windows-latest`).
- **Licence/webhook backend**: `/gifperfect/webhook` on the Acaption API server (`https://api.acaption.com`) — generates and emails GIFP- or GIFB- keys after Stripe purchase.
- **Email**: Resend via new dedicated account for `gifperfect.com`. DNS complete. `hello@gifperfect.com` forwards to `adam@translatea.com` via Namecheap Email Forwarding.
- **Sales page**: `site/` folder → deployed to Netlify at `gifperfect.com`.

## Pricing
| Tier | Price | Limit | Notes |
|---|---|---|---|
| Free | $0 | 3 conversions/day | Full-image 9-position watermark |
| Creator | $29 one-time | Unlimited | 1 licence key (GIFP-) |
| Studio | $99 one-time | Unlimited | 5 licence keys (GIFP-) |
| Studio Batch | $199 one-time | Unlimited + batch mode | 5 licence keys (GIFB-) |

## Stripe Payment Links
- Creator ($29): `https://buy.stripe.com/bJe28r3wd61A5Xv9p16Ri04`
- Studio ($99): `https://buy.stripe.com/14A9AT2s92Po99HdFh6Ri03`
- Studio Batch ($199): `https://buy.stripe.com/aFaaEX7Mtey60DbeJl6Ri05`
- Live webhook secret: `whsec_hAvhVSpcGeVcKZtwRCq8KIaaj10NUI6R`
- Test webhook secret: `whsec_9LR9ICUmDoCkBKtDxjxz7XOzNkHQb8Ph`
- Tier detection: `amount_total` cents → 2900=Creator (1 key), 9900=Studio (5 keys), 19900=Studio Batch (5 GIFB- keys)
- ⚠️ Ucaption test webhook also fires on GifPerfect test purchases (same Stripe account) — expected, harmless in production (live webhooks are separate)

## File Locations
- Main app: `/Users/mac/Desktop/GifPerfect/app.py`
- PyInstaller spec: `gifperfect.spec`
- Icon generator: `generate_icon.py` (purple "G", outputs `icon.icns` + `icon.ico`)
- Sales page: `site/index.html`
- Platform reference: `site/platforms/index.html`
- Mac build script: `build_mac.sh`
- CI: `.github/workflows/build.yml` (Mac + Windows)

## App Features
- **GIF Chunks mode**: test segment → estimate MB/s → calculate chunk duration → split video into GIF chunks at target size
- **Frames Only mode**: standalone JPG frame extraction without GIF generation
- **Batch mode**: Studio Batch (GIFB- key) only — queue multiple videos, process sequentially, per-video output subdirs
- **Watermark**: Free tier — full-image 9-position tiled `drawtext` overlay via FFmpeg
- **Target size presets**: 15 MB (X/Twitter) / 25 MB (Discord) / 99 MB (OF) / custom
- **Resolution**: 480p / 640p / 1080p / original
- **FPS**: 15 / 24 / 30
- **Frame extraction**: optional, saves JPGs alongside GIFs every N seconds
- **Output naming**: `originalfilename_chunk_001.gif`, `originalfilename_frame_001.jpg` (prefixed with source filename stem)
- **Code signing**: NOT done — Apple Developer Program ($99/yr) and Windows cert (~€100/yr) pending budget. Users must right-click → Open on Mac; More info → Run anyway on Windows.

## FFmpeg
- Dev: resolved via `static_ffmpeg.add_paths()` + `shutil.which('ffmpeg')`
- Packaged: static-ffmpeg binaries bundled by PyInstaller spec into `.app`/`.exe`

## Licence Key Format
- `GIFP-XXXX-XXXX-XXXX` — Creator / Studio (standard, no batch mode)
- `GIFB-XXXX-XXXX-XXXX` — Studio Batch (unlocks batch mode via prefix detection)
Generated by webhook on Acaption API server. Keys stored in `/opt/acaption-api/gifperfect_keys.txt` (append-only log).
Licence file on client: `~/.gifperfect_licence` — JSON `{"key": "...", "batch": true/false}`.

## Resend DNS (gifperfect.com) — Complete
All records added to Namecheap Advanced DNS:
- ✅ DKIM TXT: `resend._domainkey`
- ✅ TXT: `send` → `v=spf1 include:amazonses.com ~all`
- ✅ TXT: `_dmarc` → `v=DMARC1; p=none;`
- ✅ MX: `send` → `feedback-smtp.eu-west-1.amazonses.com` — added via Namecheap custom MX; required to get domain to Verified status on Resend.

## Run Locally
```bash
/opt/homebrew/bin/python3.12 app.py
```

## Build Mac .dmg
```bash
bash build_mac.sh
```

## Deploy Sales Page
```bash
# Netlify does NOT auto-deploy from GitHub — must deploy manually every time:
export PATH="/opt/homebrew/Cellar/node/25.8.1_1/bin:/opt/homebrew/bin:$PATH"
cd site && netlify deploy --prod --dir .
```

## Acaption API Webhook Env Vars (Hetzner VPS)
- `STRIPE_GIFPERFECT_SECRET` — live Stripe webhook signing secret (`whsec_hAvh...`)
- `STRIPE_GIFPERFECT_TEST_SECRET` — test Stripe webhook signing secret (`whsec_9LR9...`) — both live and test are supported simultaneously
- `RESEND_GIFPERFECT_API_KEY` — dedicated Resend account key for gifperfect.com (`re_YMh8...`) — separate from `RESEND_API_KEY`
- `GIFPERFECT_FROM_EMAIL` — `hello@gifperfect.com`
- `RESEND_API_KEY` — belongs to a different Resend account; NOT used for GifPerfect emails

## Other Projects in the Stack
| Project | Market | Folder |
|---|---|---|
| Ucaption (universal sister) | 🌍 Universal | `~/Desktop/Ucaption` |
| Acaption API (webhook host) | 🔞 Adult | `~/Desktop/AcaptionAPI` |
| Acaption | 🔞 Adult | `~/Desktop/Acaption` |
| OF AutoPoster | 🔞 Adult | `~/Desktop/OFAutoPosting` |
| OF GG AutoPoster | 🔞 Adult | `~/Desktop/OFGGAutoPosting` |
| OF Messaging | 🔞 Adult | `~/Desktop/OFMessaging` |
| X AutoPoster | 🔞/🌍 Both | `~/Desktop/XAutoPosting` |

---

## Active Skills

These skills are pre-loaded for this project. Use them automatically when the trigger condition is met — no need to invoke manually.

### Research & Planning
| Skill | Auto-trigger |
|---|---|
| `omc-deep-interview` | Before any significant feature addition or pivot |
| `jobs-to-be-done` | When making any significant product decision |
| `working-backwards` | When planning a new version — start from user outcome |
| `prd-reviewer` | Before building any new feature |
| `pricing` | Any discussion of pricing tiers or one-time vs subscription |
| `premortem` | Before any launch |
| `competitor-analysis` | When reviewing Ezgif, Giphy, CloudConvert, VEED |

### Build
| Skill | Auto-trigger |
|---|---|
| `omc-ralph` | Starting any non-trivial feature build |
| `architecture-advisor` | Any discussion of FFmpeg bundling, PyInstaller, or licence server |
| `frontend-design` | Any UI changes to the CustomTkinter interface |
| `developer-tool-ux-review` | When reviewing the desktop app UX |
| `debugging-partner` | Any error in the GIF generation or chunking pipeline |
| `omc-ai-slop-cleaner` | Before any release build |
| `code-reviewer` | Before packaging any installer |

### Launch & Growth
| Skill | Auto-trigger |
|---|---|
| `launch-checklist` | Before releasing any version (Mac .dmg / Windows .exe) |
| `copywriting` | When writing sales page copy |
| `hook-engineer` | When writing the main headline for the sales page |
| `feature-launch-copywriter` | When launching a new version or feature |
| `page-cro` | When optimising the Netlify sales page |
| `paid-ads` | When planning OF community or Reddit promotion |
