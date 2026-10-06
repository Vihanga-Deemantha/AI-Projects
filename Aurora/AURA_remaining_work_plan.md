# AURA — Test Report & Plan for What's Left

> Written 2026-10-05 against branch `feature/phase_3` (commit `ca56c3b`). Status section added after the work was built.
> Frontend stays **JavaScript**, not TypeScript.

## Status — what has been built since this report

Everything in section 4 has been built, phase by phase, on branch `feature/phase_3` (**uncommitted**), and verified: **512 backend tests** (also green in a clean environment built from the pinned requirements), a clean frontend lint and production build, the Playwright journey, a built Docker image that was started and exercised for real, and live runs against the real Groq/Whisper/Piper stack. Sections 1–3 below are kept as written (the reasoning and evidence); where later work proved something in them wrong, it is marked **[Corrected]**. The day-to-day guide is now [README.md](README.md).

| Phase | Result | Notes |
|---|---|---|
| 3d Stabilise & harden | Done: F1–F13, F15–F21 | See the corrections to F3 and F14 below. (F17's inconsistent companion tags were missed here and fixed later: they are now one playful word each.) Test suite, CI workflow, email verification, rate limits, token revocation, account deletion, Alembic-only schema, CORS config, voice downloader, logging |
| 4 Fluency | Done | Pure `services/fluency.py`; `fluency_scores` / `fluency_events`; per-turn chips. Fillers are only counted with `STT_PROVIDER=groq` (local `base.en` drops them) |
| 5 Clarity | Done | `services/clarity.py`; hear-a-word endpoint. An *estimate* from recogniser confidence, labelled as such |
| 6 Naturalness | Done | Idiom/collocation/phrasal-verb subtypes, praise shown as celebration; live regression set (27 cases). **Known weak spot:** praise for phrasal verbs works only ~half the time (never flagged as mistakes) |
| 7 Reports | Done | Deterministic scores with a scoring version; the LLM only writes the short note |
| 8 Progress | Done | Weekly trends, streak, totals, milestones. **Deviation:** hand-written SVG chart instead of Recharts (no dependency) |
| 9 Weaknesses & today's practice | Done | Trend is mistakes *per session* so practising more never looks like getting worse; sessions can be silently steered to a focus |
| 10 Adaptive difficulty | Done | **Deviation:** the level is replayed from report history (one step per scored session) instead of being stored on the user, so it can't drift; only the manual override and the level each session ran at are stored |
| 11 Polish, eval, deployment | Done, except actually deploying | Dockerfile (built and exercised: `scripts/smoke_container.py`), health that answers 503 when degraded, production self-check at startup (also in `check_setup.py`), privacy-safe Sentry setup, README. Deploying to Vercel/Render/Neon needs your accounts and wasn't done. PDF export and WebSocket streaming (optional) not built |

**Still true / not verified** (also in the README's *Limitations*): the real Google sign-in success path, real Resend email and real Cloudinary uploads were only tested with fakes and validation; `local_client.py` wasn't re-run after the auth changes; the GitHub Actions workflow hasn't run on GitHub; recording was only exercised in Chrome.

**Bugs found only by running the real thing (the test suite fakes Whisper, Piper and Groq, so it could not see them):**

- **`av` 19 broke every local transcription.** `requirements.txt` had been frozen with `av==19.0.1`, but `faster-whisper` 1.2.1 passes an argument PyAV 19 removed, so a fresh install failed every turn with "Could not process that recording". Found by running the container; fixed by pinning `av==18.1.0`, with a test that decodes real WAV and WebM/Opus recordings through the real libraries (it fails on 19.x, passes on 18.1.0). The failure was also swallowed without a log line, so Whisper failures are now logged with their cause.
- **`npm audit`: a critical advisory in the pinned Next.js** (16.3.4, remote code execution in `next/og`, which AURA doesn't use). Upgraded to the patched 16.3.8: production dependencies now audit clean (5 high-severity findings remain, all in the lint toolchain and fixable only by a breaking downgrade).
- **Uncountable-noun mistakes ("informations", "equipments") were labelled as vocabulary/other about half the time** instead of grammar/countable_uncountable, which fragments the weakness profile. Found by re-running the live regression suite (it had passed 23/23 earlier; model output varies and the prompt's hints had been made less test-specific since). Fixed with a rule in the prompt, measured on held-out sentences that are not in the prompt: 10/18 labelled correctly before, 18/18 after. Three of those sentences are now regression cases. The regression suite's praise tests were also flaky (a single run is not a reliable measure of a nondeterministic model), so they now allow a few attempts while still failing if correct English is ever called a mistake.
- **Health endpoint** leaked exception text (`?full=true` could return a Groq organisation id when rate limited). It now reports only the error type.

**Follow-up (2026-10-06): speaking styles now bring a matching accent.** The pickers offered American, British, Australian, Irish, Scottish and Canadian English, but a style only changed the coach's *words*: everything was spoken in the companion's own American or British voice, so four of the six accents were promised and not delivered. A style now sets the words **and** the accent. A companion speaks a regional style with a real speaker of that accent and their own gender (two University of Edinburgh corpora, CC BY 4.0, served by two extra Piper models, about 140 MB), and where no voice exists the pair is not offered and the API refuses it: **Australian is available for Ryan and Alan only**, because the corpus's two Australian speakers are both men. Verified: 565 offline tests (53 of them new) and 22 deliberate breakages of the new code, each caught by a test; every companion × style pair through the real Whisper and Piper (spoken, then transcribed back); a live turn and the hear-a-word endpoint with a regional voice on the real stack; the browser journey plus two new browser tests; and the rebuilt container image (`scripts/smoke_container.py`, now also checking the accent voices). The full journey found a page that linted and built cleanly but crashed when opened (a child component read its parent's variable), so ESLint's `no-undef` is now on. **Not verified:** how convincing each accent sounds to a native speaker (that needs a human listener), and the new browser tests were not themselves mutation-tested. The accent models add about 100 MB and 125 MB of memory when first used, which puts the default container at about 1 GB (see the README's *Deploying*). Details in the README's *Companions, speaking styles and accents*.

**Load-test finding after this report (new):** Groq's free tier allows ~8,000 tokens/minute on `gpt-oss-120b`. Three learners talking at once exhausted it. The coach now says it is busy instead of failing generically and the background analysis retries, but real multi-user use needs a paid Groq tier or separate models for conversation and analysis.

## 1. Where the project stands *(at the time of the report)*

Phases 0–3c are built and working: auth (password, Google, OTP reset), profile + avatar, the full voice loop (STT → LLM → TTS, streamed), async grammar/vocab corrections, session end, and speech history. **Phases 4–11 of the master plan (fluency, pronunciation, idioms, reports, progress, weakness profiling, adaptive difficulty, polish/deploy) are not started.** There is no code or schema for them, and `Conversation.overall_score` is a column nothing writes to.

Before building Phase 4 on top, the testing below turned up bugs and gaps that would undermine it. So the plan is: **Phase 3d (stabilise & harden) first, then Phases 4–11.**

## 2. What was tested and how

| Layer | Method | Result |
|---|---|---|
| Backend API (70 checks, every route) | Python script against a live uvicorn on **real Postgres 16** (throwaway `aura_test` DB, since dropped). Real Groq, real Whisper, real Piper. | **68 pass, 2 fail** (identical on SQLite and Postgres) |
| Voice pipeline | Piper-synthesised speech → posted as WAV *and* as webm/opus (what browsers send) | Both transcribe exactly and stream back reply audio |
| Deeper probes (logic + security) | 2nd script: OTP lifecycle, Google-only accounts, account linking, timing, rate limits, upload size | 12 pass, **7 fail** (section 3). One "pass" (forgot-password resets the attempt counter) actually *confirms* weakness F5 |
| Performance | Time-to-first-audio, solo and 3 concurrent users | See section 3, F14 |
| Migrations | `alembic upgrade head` on empty Postgres + `alembic check` | Builds all 5 tables, **zero drift** from models. Your dev DB is at head (`20e0dbfaef7e`) |
| Frontend static | `npm run lint` | Clean |
| Frontend build | `npm run build` | **Fails** (F3). `next build --webpack` passes (11 routes) |
| Browser, real UI | Landing → route guards → signup form → practice (mic) → end session → history list → history detail → profile → mobile layout | All work. 0 console errors. No horizontal overflow at 375px |

**Not tested (be aware):**
- A **real microphone**. I injected a synthetic audio stream into `getUserMedia`; the actual `MediaRecorder` → backend path ran, but real mic quality, noise and permission prompts did not.
- A **real Google OAuth round-trip** (needs a human on the consent screen). Verified redirect URL, state cookie, and every failure branch; the success branch was only exercised by calling `_find_or_create_user` directly.
- **Real Resend email** and **real Cloudinary upload**. I deliberately blocked outbound mail (blanked `RESEND_API_KEY` for the test server) and only tested avatar *validation* (wrong type, >5 MB). Please test one real email + one real upload yourself.
- Firefox/Safari recording, light theme, more than 3 concurrent users, a >10-message session live (proved at query level instead, F2), any deployment.

> My own test noise, not project bugs: SQLite raised a naive-vs-aware datetime error in the OTP path (Postgres is fine, so this is only a reminder to test on Postgres), and the 2 "duplicate" corrections in my first run were me sending the same clip three times.

## 3. Findings

Severity: **P0** = fix before anything else; **P1** = fix in Phase 3d; **P2** = fix when convenient.

### Correctness

| ID | Sev | Finding | Evidence | Fix |
|---|---|---|---|---|
| F2 | **P0** | **AURA stops "hearing" the user after ~5 turns.** The LLM context query is `order_by(created_at.asc()).limit(10)` — the *oldest* 10 messages, not the newest. From turn 6 on, the model never sees the latest thing the user said. | [conversation.py:187-193](backend/routers/conversation.py:187) and [:325-331](backend/routers/conversation.py:325). Reproduced on a 14-message conversation: context = `msg0..msg9`, latest turn missing | Query newest N (`order_by(desc).limit(N)`) then reverse. Add a test with 14+ messages |
| F7 | **P0** | `word_timestamps_json` isn't JSON. It's `str()` of a Python list, so it contains single quotes and literal `np.float64(0.0)`. Neither `json.loads` nor `ast.literal_eval` can read it. **Blocks Phase 4.** | [conversation.py:179,308](backend/routers/conversation.py:308); sample row: `[{'word': ' Yesterday', 'start': np.float64(0.0)…` | `json.dumps` with plain `float()`. Existing rows are dev data; ignore or regex-backfill |
| F12 | P1 | **Corrections panel shows "0" until the *next* turn.** Analysis is a FastAPI `BackgroundTask`, which only starts *after* the stream ends; the frontend polls exactly once, at `done`. Analysis itself takes ~2.5s. | Browser run: 1 poll, 20ms after stream end, `0 this session` for 20s+. Corrections landed in DB 2.5s after the user message | Start analysis as soon as the user message is saved (`asyncio.create_task`) so it finishes while TTS runs, **and** make `CorrectionsPanel` retry (e.g. 1.5s / 3s / 6s) until new items arrive or it gives up |
| F10 | P2 | Ended sessions still accept messages. | `POST /message-stream` on an ended conversation returned 200 | 409 when `is_complete` |
| F11 | P2 | Two voice endpoints that behave differently: `/message` (batch) never runs corrections analysis; `/message-stream` does. | code + test | Delete `/message` (the web UI and `local_client.py` use the stream) or make it share one code path |
| F17 | P2 | UX nits: header badge says "NOT STARTED" while you're holding the mic on the first turn; History says "Time spoken" but shows session wall-clock length; companion tags are inconsistent (Introvert / Extrovert vs American); "Progress" nav is a disabled "Soon" item. | screenshots | Rename/derive properly; Progress arrives in Phase 8 |

### Security

| ID | Sev | Finding | Evidence | Fix |
|---|---|---|---|---|
| F1 | **P0** | **Account pre-hijack.** Signup doesn't verify the email. An attacker signs up as `victim@x.com` with their own password; when the victim later uses "Sign in with Google", `_find_or_create_user` links Google to *that* account — and the attacker's password keeps working. | Reproduced: after linking, the attacker's password still logs in | Email verification at signup (OTP via Resend, `email_verified` column). Until verified, don't link Google to the account: clear its `password_hash` or require verification first. A successful OTP reset can also mark the email verified |
| F4 | P1 | **Login and forgot-password leak which emails exist** via timing, undoing the generic-error design. | Known email **~375–390 ms** vs unknown **~10 ms** on both endpoints (bcrypt only runs for real users) | Always run a dummy bcrypt verify when the user is missing; move OTP generation/hashing into the background task |
| F5 | P1 | **No rate limiting anywhere.** 15 consecutive bad logins → all `401`. Calling forgot-password resets the 3-attempt OTP counter, so an attacker gets fresh guesses per request (and can spam email). | tested | Per-IP + per-email throttling on login/signup/forgot/verify-otp; cooldown (e.g. 60s) on forgot-password. `slowapi`, or a small DB counter |
| F6 | P1 | **No upload cap on audio.** A 30 MB junk file was accepted and read fully into memory. | HTTP 200 after 0.3s | Cap bytes (~2–3 MB) and duration; reject early |
| F15 | P2 | Google success redirect puts the **JWT and the full user JSON in the URL query string** (history, logs, referrers); `link_token` JWT also rides in a URL; the OAuth state cookie has no `Secure` flag. | [google.py:129](backend/routers/google.py:129), `:74` | Redirect with a short-lived one-time code the frontend exchanges via POST; `Secure` cookie when not on localhost |
| F21 | P2 | No account deletion; no way to revoke a JWT (changing your password doesn't log out other sessions; 7-day token in `localStorage`). | code | `token_version` on `User` baked into the JWT; delete-account endpoint (also `cloudinary.uploader.destroy`) |

### Build, deploy, ops

| ID | Sev | Finding | Evidence | Fix |
|---|---|---|---|---|
| F3 | **P0** | **`npm run build` fails** (Turbopack): `next/font/google queries have exactly one entry`. `next build --webpack` succeeds, so it's Turbopack-specific. Blocks a Vercel deploy. | build output | **[Corrected]** The suspected `Playfair_Display` style array was *not* the cause. The real cause was `Plus_Jakarta_Sans` being given a `weight` array: it is a variable font, so Turbopack wants no `weight` at all. Removing that one option fixed `npm run build` |
| F8 | **P0** (for deploy) | CORS is `[]` whenever `ENVIRONMENT != development`, so a deployed frontend is blocked. Also `127.0.0.1:3000` isn't allowed in dev. | [main.py:57-66](backend/main.py:57) preflight test | `CORS_ORIGINS` env var (comma list); always include `FRONTEND_URL` |
| F13 | **P0** (for deploy) | **Voice downloader is out of date.** `scripts/download_voices.py` and `check_setup.py` only know amy/ryan/alan/**lessac**; the app needs `kristin`, `hfc_female`, `norman` (3 of 6 voices). On a fresh machine or deploy those voices fail — and in the streaming path a TTS failure is *skipped silently*, so the user gets text and no audio. | grep: 0 mentions of the 3 voices in either script | Drive the download list from `VOICE_FILES`; on startup log missing voice files; make `/api/config/options` advertise only voices that load |
| F9 | P1 | SQLAlchemy `echo=True` is hard-coded, so every query (emails, transcripts) is logged forever; `LOG_LEVEL` is read but never used. | [database.py:12](backend/database.py:12) | `echo = ENVIRONMENT == "development" and LOG_LEVEL == "DEBUG"`; real `logging` config |
| F16 | P1 | `requirements.txt` pulls `torch`, `torchaudio`, `silero-vad`, `sounddevice` — used only by `local_client.py` / `main_prototype.py` / `check_setup.py`. Multi-GB image for nothing. | grep | Split into `requirements.txt` (server) + `requirements-local.txt` |
| F20 | P2 | Startup runs `Base.metadata.create_all` *and* Alembic exists; `create_all` never adds columns, so it can hide a missing migration. | main.py | Alembic-only outside local dev |
| F18 | P2 | Stale docs/comments: model comments list old styles (`scouse, caribbean, pirate`) and voices; no root README; Phase 3 plan says Next 14 (repo is 16). No `.env` setup walkthrough. | models/core.py:68-72 | Write `Aurora/README.md` (setup, env, voices, run, test) |
| F19 | **P0** | **Zero automated tests and no CI.** Everything above was found by hand. | `git ls-files` | Section 4, workstream D |

### Performance

| ID | Sev | Finding | Evidence |
|---|---|---|---|
| F14 | P1 | Warm, single user: **~2.2s to first audio** (STT 1.1s, LLM first sentence 0.7–0.9s) — inside your <2.5s target. With **3 simultaneous users: 4.5–5.1s** (STT 1.1s → 3.3s). Whisper on CPU is the bottleneck and doesn't scale. | `perf.py`: seq 2.24s / 2.14s; concurrent 5.08 / 4.55 / 4.65s |

Fix: make the STT backend switchable (`STT_PROVIDER=local|groq`). Groq hosts Whisper models; your own master plan flags this (suggestions #7 and #12). **Check that it returns word-level timestamps before committing**, since Phase 4 depends on them. Keep local faster-whisper as the offline/fallback path.

**[Outcome, measured]** Built, with word timestamps. `scripts/loadtest_voice.py`, same clip, same laptop, medians:

| | Local `base.en` | Groq `whisper-large-v3-turbo` |
|---|---|---|
| STT, 1 learner | 1.13 s | 0.82 s |
| STT, 3 at once | 3.05 s | 0.89 s |
| First audio, 1 learner | 2.19 s | 1.45 s |
| First audio, 3 at once | 4.24 s (worst 5.3 s) | 2.84 s (worst 7.6 s, includes one rate-limited turn) |

So the real gain is under concurrency: Groq's STT time stays flat while local STT triples. A single learner gains only ~0.3 s. The trade-offs are not about speed: Groq keeps filler words (needed for the fluency score) and handles accents better but gives no per-word confidence (so clarity is a rougher estimate with no "hard to catch" list), and the audio leaves your server. Recommendation and details: README, *Choosing a speech-to-text provider*. These are single runs on one machine.

### What works well (keep it)

Signup/login/me/profile/change-password/OTP flow (lockout after 3 attempts, expiry, single use); generic auth errors; ownership checks (every cross-user probe → 404); Google-only account rules (set password w/o current, can't disconnect first); input validation; idempotent `end`; history pagination and per-turn corrections; clean error + `done` on silence, garbage and empty audio; webm/opus works with no backend change; analysis output is accurate (caught past-tense, subject-verb and tense errors correctly); responsive UI; route guards; stream protocol is robust.

## 4. Implementation plan

### Phase 3d — Stabilise & harden (do this first; ~1 week)

Order matters: tests first, so every fix is locked in.

**D. Test foundation (start here)**
1. `backend/tests/` with pytest + `httpx` TestClient against a Postgres test DB (a `aura_test` DB in the existing compose service). Fixtures: user + token factory, `monkeypatch` for `llm`, `stt`, `tts`, `send_reset_email` (deterministic, no network).
2. Port the two scripts from this session into pytest: auth, ownership (404s), conversation, history, OTP (seed hash directly), Google-only accounts. The cases already exist, so this is mostly moving code.
3. **Analysis regression set** (master plan 11.2): ~15 transcripts with known errors, asserting `subtype`/`original`. Run manually (real LLM), not in CI.
4. Frontend: one Playwright smoke test — signup → hold-mic with a faked `getUserMedia` (the technique used in this session) → transcript + reply appear → end → history shows it. Plus `npm run lint` and `next build`.
5. GitHub Actions: backend pytest on Postgres service, frontend lint + build.

**A. Correctness** — F2 (+test), F7, F12, F10, F11, F17.
**B. Security** — F1 (email verification + safe linking), F4, F5, F6, then F15, F21.
**C. Build/deploy blockers** — F3, F8, F13, F9, F16, F20, F18 (README).
**Performance** — F14: STT provider switch; re-run `perf.py` (concurrent case).

*Exit criteria:* `pytest` green in CI; `npm run build` green; the 7 failing probes in section 3 pass; F2 covered by a test; a fresh clone + README gets all 6 voices working; time-to-first-audio with 3 users ≤ ~3s.

### Phase 4 — Fluency analysis (needs F7)
Follows master plan 4.x, with these specifics:
- `services/fluency.py`: pure function over the stored word timestamps → `wpm`, `pause_count` (gaps >0.5s), `long_pause_count` (>1.5s), `filler_count/breakdown`, `repetitions`, `word_count`. Pure Python, trivially unit-tested.
- Tables via Alembic: `fluency_scores` (per user message) and, as the plan suggests, `fluency_events` (each pause/filler with a timestamp) so trends are possible later.
- Compute at message-save time (cheap, no LLM) and return in the stream's `done` payload so the UI shows it instantly.
- **Known risk:** Whisper (and `vad_filter=True`) tends to drop "um/uh". Test with and without VAD, and with an `initial_prompt` containing disfluencies, before trusting filler counts. Consider relaxing VAD for fluency.
- UI: fluency tiles in `StatsRow`; per-turn chips in the transcript; filler breakdown in the panel.
- *Exit:* score + WPM + filler breakdown visible per turn.

### Phase 5 — Pronunciation ("clarity") estimate
- Use per-word `probability` and segment `avg_logprob` (already stored after F7). Flag words below ~0.7; show lowest-confidence words and an overall clarity %.
- Add the honesty label from the master plan ("clarity estimate based on speech-recognition confidence, not phoneme analysis"). This is a proxy, so name it **Clarity**, not Pronunciation.
- "Practice this word": `POST /api/tts/word` (uses existing Piper path, short text cap, auth + rate limit) with a play button on flagged words.
- *Exit:* low-confidence words shown with scores; stored in DB.

### Phase 6 — Idioms, collocations, naturalness
- Extend `ANALYSIS_SYSTEM_PROMPT` with `naturalness` subtypes: `idiom_used` (positive), `wrong_collocation`, `weak_vocabulary`, `phrasal_verb`. The `CorrectionItem` schema already supports `is_error=false` suggestions and the panel already renders them differently.
- Add positive-reinforcement rendering (the master plan's "celebrate correct use") — the model needs a `positive` flag/subtype so these aren't shown as corrections.
- Extend the regression set from 3d with idiom cases. Re-run it after every prompt change.

### Phase 7 — Session reports
- Table `session_reports` per the master plan 7.1. Generate in `POST /conversation/{id}/end` (it already exists): aggregate corrections + fluency, call the analysis model once for strengths/weaknesses text, write `Conversation.overall_score`.
- Wait for in-flight analysis before aggregating (this is the same race as F12 — solve it once, e.g. a short bounded wait or recompute lazily on first view).
- `GET /api/history/sessions/{id}/report`; a report view reachable from the end-of-session recap and from history detail. Define the scoring formulas in one file with tests (scores that change silently will break Phase 8/10).
- *Exit:* report appears after End session and in history.

### Phase 8 — Progress tracking
- Aggregation endpoints (weekly averages per score category, streak days, total practice time) over `session_reports`.
- New `/progress` page — this replaces the disabled "Soon" nav item. Recharts is fine (it's JS-compatible); keep charts simple (line per category, streak, totals).
- Backfill: only sessions with reports count. Decide whether to generate reports for existing completed sessions (a one-off script).

### Phase 9 — Weakness profiling & daily exercise
- `user_weaknesses` (subtype counts, last seen, trend), recomputed when a report is generated; trend = this-30-days vs previous-30-days rate per session.
- `GET /api/practice/today`: pick top weakness, return a steering prompt; add an optional `focus` field to session start that's appended to the system prompt in `personalities.build_system_prompt`.
- UI: "Today's practice" card on `/practice` with a one-click start.

### Phase 10 — Adaptive difficulty
- Tier table from the master plan 10.1; tier from rolling average of the last 3 report scores (10.2). Store the tier on the user and show "Difficulty: Intermediate ↑".
- Add a manual override on profile — adaptive systems that can't be overridden frustrate learners. Inject the tier's `prompt_modifier` via `build_system_prompt`.

### Phase 11 — Polish, eval, deployment
- Latency pass using the F14 numbers (decide STT provider with data).
- Deploy: Vercel (frontend) + Render/Railway (backend, ≥ 1 GB RAM — Whisper `base.en` plus six ~60–120 MB Piper voices loaded at startup is heavier than the master plan's 512 MB estimate; consider loading voices lazily, or only the 2–3 most used) + Neon/Supabase Postgres. Voices downloaded on boot from object storage (already fixed in F13 groundwork).
- Production checklist: `ENVIRONMENT=production`, `CORS_ORIGINS`, `Secure` cookies, no SQL echo, alembic-only schema, rotate `JWT_SECRET`, real Google redirect URI registered, Resend domain verified (currently `onboarding@resend.dev`, which can only email your own address), Cloudinary configured, error tracking (Sentry), and `/health?full=true` wired to an uptime monitor.
- Optional extras from the master plan worth keeping on the list: PDF export of a report, and WebSocket streaming (only worth it if latency after the STT change is still above target).

## 5. Suggested order at a glance

1. **Tests + CI scaffold** (D)
2. **P0 fixes:** F2, F7, F1, F3, F8, F13
3. **P1 fixes:** F12, F4, F5, F6, F9, F16, F14
4. **P2 cleanup:** F10, F11, F15, F17–F21
5. **Phase 4 → 5 → 6** (analysis features; each small, all build on F7)
6. **Phase 7 → 8** (reports unlock progress)
7. **Phase 9 → 10** (personalisation needs report history)
8. **Phase 11** (deploy)

## 6. Housekeeping notes from the original test session *(historical)*

- Your **Docker Desktop was not running**; I started it, and `aura_postgres` came up on its own (restart policy). Your `aura_db` was only read (alembic version, row counts: 56 users / 72 conversations / 257 messages / 52 corrections), never written. My `aura_test` DB is dropped; all servers I started are stopped; the git tree is unchanged apart from this file.
- `.env` contains live-looking keys (Groq, Google, Resend, Cloudinary). It's correctly git-ignored. I never printed values. The master plan already recommends rotating the Groq key once it has been exposed in a session, so do that if it ever was.
- Of the 56 users in your dev DB, **43 are anonymous pre-auth rows** (no email, no password, no Google) that can never log in; 11 have a password and 2 are Google-linked. Worth a cleanup before any real data goes in.
