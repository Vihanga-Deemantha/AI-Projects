# AURA — AI English Speaking Coach

> This is the **setup, configuration and operations guide**. The repository's top-level [README](../README.md) has the project overview, who it is for, the full feature tour, the architecture and the API reference.

Practise spoken English out loud with an AI coach. You hold a button and talk; AURA transcribes you, replies in a natural voice, and — without interrupting the conversation — finds your grammar, vocabulary and phrasing mistakes, measures how you spoke (pace, pauses, filler words, clarity), and turns every session into a report, a progress chart, a list of your recurring weaknesses, and a conversation that gets harder as you improve.

- **Voice loop**: microphone → speech-to-text → LLM → sentence-by-sentence text-to-speech, streamed so the coach starts speaking before it has finished thinking.
- **Feedback while you talk**: corrections appear as you go (grammar, vocabulary, naturalness, with praise for idioms you use well).
- **Speech metrics**: words per minute, pauses, fillers, and a clarity estimate (see [Limitations](#limitations)).
- **Session reports**: five scores plus an overall score, strengths, what to work on, your most common mistakes and words worth practising.
- **Progress**: weekly trends, streaks, totals and milestones.
- **Weakness profile & today's practice**: what you keep getting wrong, whether it is improving, and one click to start a conversation that quietly steers toward it.
- **Adaptive difficulty**: five levels that follow your recent scores one step at a time; pin a level on your profile if you prefer.
- **Speaking styles with matching accents**: Standard, American, British, Australian, Irish, Scottish and Canadian English. A style sets the words your coach uses *and* the accent you hear, so the screen never promises an accent you won't get (see [Companions, speaking styles and accents](#companions-speaking-styles-and-accents)).
- **Accounts**: email + password, Google sign-in, email verification, password reset by code, profile photo, account deletion.

Tech: FastAPI · PostgreSQL (SQLAlchemy, Alembic) · Groq (LLM and optionally Whisper) · faster-whisper · Piper TTS · Next.js 16 (JavaScript, Tailwind v4) · pytest · Playwright.

---

## Contents

1. [How it works](#how-it-works)
2. [Quick start](#quick-start)
3. [Configuration](#configuration)
4. [Choosing a speech-to-text provider](#choosing-a-speech-to-text-provider)
5. [Database and migrations](#database-and-migrations)
6. [Testing](#testing)
7. [Deploying](#deploying)
8. [API overview](#api-overview)
9. [Project layout](#project-layout)
10. [Limitations](#limitations)
11. [Troubleshooting](#troubleshooting)

---

## How it works

One spoken turn:

1. The browser records audio while the mic button is held and posts it to `POST /api/conversation/message-stream`.
2. The server caps the size, transcribes it (local Whisper or Groq Whisper), saves the turn, and streams back a `transcript` event and a `metrics` event (fluency and clarity for that turn).
3. **At the same time**, in the background, an LLM call in JSON mode analyses the transcript for mistakes. The page polls until those corrections arrive; it never waits for the session to end.
4. The coach's reply streams from the LLM, is cut into sentences, and each sentence is synthesised by Piper and sent as an `audio_chunk` event. The browser plays chunks in order while the rest is still being generated.
5. A final `done` event carries the timings (`stt_ms`, `llm_ttfs_ms`, `first_audio_ms`, `total_ms`). Every code path ends with `done`, so the client can never hang.

When a session ends, a report is generated in the background (after waiting for the last turn's analysis). Scores come from deterministic formulas in `backend/services/scoring.py` (mistakes per 100 words weighted by severity; a dimension with no evidence is left blank rather than scored 100), and each report records the scoring version it was computed with. The progress page, weakness profile and the next difficulty level are all derived from those reports.

**Difficulty** (`backend/services/difficulty.py`): the average overall score of your last three scored sessions maps to a level (90+ Advanced, 78+ Upper-Intermediate, 65+ Intermediate, 50+ Elementary, otherwise Beginner), but the level moves **at most one step per scored session**, so one lucky or terrible session never lurches the conversation. It is replayed from your report history rather than stored, so it can't drift and abandoned sessions don't move it. A level pinned on the profile always wins. New learners start at Elementary.

### Companions, speaking styles and accents

Three independent choices shape a session:

- **Companion** (Eida, Maya, Amy, Ryan, Alan, Lessac): who you talk to. Each has a personality and a home voice.
- **Speaking style** (Standard, American, British, Australian, Irish, Scottish, Canadian): the coach's *words* (the style's vocabulary and phrasing, in the prompt) **and the accent you hear**. Under Standard English a companion speaks in their own voice; under a regional style they speak in a voice of that accent, and a companion whose home accent already matches keeps their own voice.
- **Scenario** (casual chat, interview, café, ...): the situation.

The regional voices are real speakers, not an effect applied to another voice: `en_GB-vctk-medium` (109 speakers from the CSTR VCTK Corpus, each labelled with their accent and region in the corpus's own speaker table) and `en_GB-alba-medium` (a Scottish speaker from Edinburgh). `ACCENT_VOICES` in `backend/personalities.py` picks, for each companion and accent, a speaker of the **same gender** and the right accent, so a female companion never turns into a man's voice. `backend/tests/test_accents.py` checks every chosen speaker against the corpus's table (accent, gender) and that a style is never offered when no voice exists for it.

Who speaks what:

- **Standard**: every companion, in their own voice.
- **American**: every companion; Alan (whose home voice is British) uses an American speaker.
- **British**: every companion; Alan keeps his own voice, the others use a British speaker.
- **Irish, Scottish, Canadian**: every companion, each with a speaker of that accent and their gender (Eida's Scottish voice is Alba).
- **Australian**: **Ryan and Alan only.** The corpus has just two Australian speakers and both are men, and Piper's catalogue has no Australian woman, so the female companions have no Australian voice yet.

A pair with no voice is greyed out in the pickers (the hover text says who does have one), refused by the API with a `400` that says why, and a companion/style saved on a profile before this rule existed falls back to Standard English with a note on the profile page. The accent models are not needed for Standard English: if they aren't installed, the styles that use them are hidden instead of failing (`python scripts/download_voices.py --check` and `python check_setup.py` report it). Each accent model is loaded the first time a session needs it (about 4 seconds, in the background while the session starts); `PREWARM_MODELS` only prewarms the six companion voices.

**Credits.** The regional voices come from two corpora published by the University of Edinburgh's Centre for Speech Technology Research under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), turned into Piper voice models by the [Piper project](https://github.com/rhasspy/piper) (`rhasspy/piper-voices`):

- Yamagishi, J., Veaux, C. and MacDonald, K. (2019), *CSTR VCTK Corpus: English Multi-speaker Corpus for CSTR Voice Cloning Toolkit (version 0.92)*, University of Edinburgh, <https://datashare.ed.ac.uk/handle/10283/3443>
- Valentini-Botinhao, C. and Yamagishi, J. (2019), *Alba speech corpus*, University of Edinburgh, <https://datashare.ed.ac.uk/handle/10283/3270>

The profile page repeats the credit next to the speaking-style picker. The companions' own voices are separate Piper models (see their model cards for their licences).

## Quick start

You need: **Python 3.14** (what everything here is tested on), **Node 22**, **Docker** (for PostgreSQL), and a free **Groq API key** from [console.groq.com](https://console.groq.com).

From the `Aurora/` folder:

```bash
# 1. PostgreSQL on localhost:5432
docker compose up -d

# 2. Python environment and the voice models: six companion voices plus two accent voices (~550 MB, downloaded once)
python -m venv venv
venv\Scripts\activate                 # macOS/Linux: source venv/bin/activate
pip install -r backend/requirements.txt
python scripts/download_voices.py

# 3. Configuration: copy the template, then set GROQ_API_KEY and JWT_SECRET
cp .env.example .env                  # Windows: copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"      # paste as JWT_SECRET

# 4. Create the tables, then check everything is in place
alembic -c backend/alembic.ini upgrade head
python check_setup.py

# 5. Run the API (http://localhost:8000, docs at /docs)
uvicorn backend.main:app --reload
```

In a second terminal, the web app:

```bash
cd frontend
cp .env.local.example .env.local      # points the app at http://localhost:8000
npm install
npm run dev                           # http://localhost:3000
```

Sign up, hold the mic button and talk. In development, without a Resend key, the email verification code is printed in the API's log.

The first start loads Whisper and the six companion voices (~25 seconds); `/health` answers immediately and reports whether they are ready. The two accent voices load the first time a session uses them.

## Configuration

Everything is read in `backend/config.py` from environment variables or `.env` (see `.env.example`, which documents each one). **Never commit `.env`.**

| Variable | Default | What it does |
|---|---|---|
| `GROQ_API_KEY` | *required* | Groq API access (LLM, and Whisper if you choose it) |
| `DATABASE_URL` | *required* | `postgresql://user:password@host:5432/dbname` |
| `JWT_SECRET` | *required* | Signs login tokens. 32+ random characters; rotating it logs everyone out |
| `ENVIRONMENT` | `development` | Anything else switches on production behaviour (see [Deploying](#deploying)) |
| `FRONTEND_URL` | `http://localhost:3000` | Where the web app lives: Google sign-in redirects here, and CORS always allows it |
| `CORS_ORIGINS` | *(empty)* | Extra allowed browser origins, comma-separated (e.g. Vercel preview URLs) |
| `LLM_CONVERSATION_MODEL` | `openai/gpt-oss-120b` | The coach |
| `LLM_ANALYSIS_MODEL` | `openai/gpt-oss-120b` | Finds your mistakes. 120b passed all 23 cases it was tuned on, 20b 20 of 23 (and once flagged correct English) |
| `LLM_REASONING_EFFORT` | `low` | For the gpt-oss models; blank it for llama models |
| `LLM_CONTEXT_MESSAGES` | `20` | How many recent messages the coach sees |
| `LLM_ANALYSIS_RETRIES` | `5` | How many times the background analysis waits out a rate limit |
| `STT_PROVIDER` | `local` | `local` (faster-whisper) or `groq` — [see below](#choosing-a-speech-to-text-provider) |
| `GROQ_STT_MODEL` | `whisper-large-v3-turbo` | Used when `STT_PROVIDER=groq` |
| `WHISPER_MODEL_SIZE` / `WHISPER_DEVICE` / `WHISPER_COMPUTE_TYPE` | `base.en` / `cpu` / `int8` | Used when `STT_PROVIDER=local` |
| `MAX_AUDIO_BYTES` / `MAX_AUDIO_SECONDS` | 5 MB / 120 | Per-turn limits |
| `RATE_LIMITS_ENABLED` | on | Limits on login, signup, codes, uploads and voice turns (in memory, per process) |
| `PREWARM_MODELS` | on | Load Whisper and the six companion voices at startup instead of on first use (the two accent voices always load on first use) |
| `CHECK_MIGRATIONS_ON_STARTUP` | on | Compare the database's schema version with the code's |
| `LOG_LEVEL` / `SQL_ECHO` | `INFO` / off | `SQL_ECHO` logs every query (including emails and transcripts), so keep it off |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | *(blank)* | Google sign-in; blank disables it |
| `RESEND_API_KEY` / `EMAIL_FROM` | *(blank)* | Email codes (verification, reset). Blank: codes go to the log in development |
| `CLOUDINARY_*` (3 values) | *(blank)* | Profile photos; blank disables uploads |
| `SENTRY_DSN` | *(blank)* | Error tracking with Sentry. Sends no personal data, request bodies or local variables |
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | **Frontend**: where the API is |

## Choosing a speech-to-text provider

`STT_PROVIDER` picks who turns your audio into text. Measured with `scripts/loadtest_voice.py` on a development laptop (CPU only), the same 6-second clip, medians of a few turns:

| | Local Whisper `base.en` | Groq `whisper-large-v3-turbo` |
|---|---|---|
| Speech-to-text, 1 learner | 1.13 s | 0.82 s |
| Speech-to-text, 3 learners at once | **3.05 s** | **0.89 s** |
| Time to first audio, 1 learner | 2.19 s | 1.45 s |
| Time to first audio, 3 at once | 4.24 s (worst 5.3 s) | 2.84 s (worst 7.6 s)\* |
| Filler words ("um", "uh") | dropped, so not counted | kept, so fluency counts them |
| Clarity | per-word, with a "hard to catch" list and *hear it* buttons | a rougher whole-turn estimate, no word list |
| Accented speech | weaker | stronger |
| Privacy | audio stays on your server | audio goes to Groq (already your LLM provider) |
| Server cost | ~0.15 GB more RAM, and CPU contention under load | none (hosted) |

\* One of those three-learner turns hit Groq's LLM rate limit (below), which is where that worst case comes from. The speech-to-text rows are the like-for-like comparison: part of the one-learner first-audio gap is the LLM happening to answer faster in that run.

These are single runs on one machine, so treat them as the shape rather than precise figures. A small cloud CPU is likely to be *slower* than a laptop at local Whisper, and slower still with several learners. **For a deployed instance with more than one simultaneous learner, `groq` is the better default; choose `local` when audio must not leave your server or you want the per-word clarity list.** Re-run `scripts/loadtest_voice.py` against your real deployment before deciding.

**Groq rate limits are the next ceiling.** On Groq's free tier, `openai/gpt-oss-120b` allowed about 8,000 tokens per minute and 200,000 per day in testing (a day of load tests and live evaluation used the whole daily allowance). A conversation turn plus its analysis is a couple of thousand tokens, so three learners talking at once exhausted it: one turn got no reply from the coach (it now says "The coach is very busy right now. Please try again in a few seconds."), and the background analysis now waits and retries instead of giving up. In a deliberate worst case (three learners each sending a turn every few seconds: nine turns in about a minute) eight replies arrived, the ninth was that "busy" message, and six of the nine analyses finished; the other three gave up after their retries. Real conversations are much slower than that, but the free tier clearly supports only a couple of simultaneous learners. Each model has its own budget, so using a different model for `LLM_CONVERSATION_MODEL` and `LLM_ANALYSIS_MODEL` raises the ceiling; a paid Groq tier raises it much further.

## Database and migrations

Schema changes are made only with Alembic; the app never creates tables itself.

```bash
alembic -c backend/alembic.ini upgrade head                       # apply everything (from Aurora/)
alembic -c backend/alembic.ini revision --autogenerate -m "what changed"   # after editing a model
alembic -c backend/alembic.ini check                              # fails if models and migrations disagree
```

At startup the API compares the database's revision with the code's. In development a mismatch is logged as an error; in any other environment **it refuses to start**, so a bad deploy fails at once rather than on a user's request. `GET /health` reports the same thing (`"migrations": "up to date" | "behind"`).

Upgrading an existing database: run `upgrade head` before starting the new code. Phase-by-phase, existing rows are preserved (accounts that signed in with Google become verified; old turns are marked analysed; sessions from before reports existed get a report the first time they are opened).

## Testing

| What | Command (from `Aurora/`) | Needs |
|---|---|---|
| Backend suite | `pip install -r backend/requirements-dev.txt` then `pytest` | PostgreSQL (`docker compose up -d`); creates its own `aura_test` database |
| Live analysis regression | `pytest -m llm` (optionally `REGRESSION_MODEL=...`) | A real Groq key in `.env`; costs a little quota |
| Frontend lint, unit tests and build | `cd frontend && npm run lint && npm test && npm run build` | Node 22 |
| Browser tests | `cd frontend && npm run e2e` (or one file: `npx playwright test e2e/public.spec.js --project=desktop`) | The whole stack running, Chrome installed |
| Latency / concurrency | `python scripts/loadtest_voice.py --users 1 3 --turns 2` | A running backend |
| A built image | `docker build -t aura-backend .` then `python scripts/smoke_container.py` | Docker and the compose PostgreSQL; takes a few minutes |

The backend suite uses in-process fakes for Whisper, Piper, Groq and email, so it needs no network, no model files and no keys, and it never touches your real database or `.env` (it refuses to run against a database whose name doesn't end in `_test`). That holds on a machine with no voices installed, which is what CI is: every test sees a stand-in voices folder (an empty placeholder per model) so the real availability logic runs, and a test that reaches the real LLM without the `ai` fixture is failed instead of calling Groq. The few tests of the genuine Piper models (`@real` in `test_tts_voices.py`, marked `real_voices`) use `voices/` and skip where it's empty, so run `python scripts/download_voices.py` first if you want them. It covers authentication and account safety, ownership checks, the voice stream (including every failure path), analysis cleaning, fluency, clarity, scoring, reports, progress, weaknesses, difficulty, rate limiting, migrations (upgrade, downgrade, data preservation, no drift) and the production checks.

Run `pytest -m llm` after **any** change to the analysis prompt or model: a tweak that fixes one case can silently break another, and nothing else would notice.

**Why the image check matters.** The suite fakes Whisper, Piper and Groq, so it cannot notice a broken dependency pin or a missing model file. `scripts/smoke_container.py` starts the real image on a throwaway database and checks that migrations run, the models load, a recording is transcribed, a voice speaks and the health check passes. It exists because the first real container run found that `faster-whisper` 1.2.1 and `av` 19 (the version a fresh install resolved to) are incompatible, so every local transcription failed while all tests passed. `av` is now pinned to 18.x in `requirements.txt` with a test (`tests/test_stt.py`) that decodes real WAV and WebM/Opus recordings through the real libraries. Re-run the image check whenever you change `requirements.txt`.

The browser tests drive the real app in Chrome with a fake microphone playing `frontend/e2e/fixtures/speech.wav`. `smoke.spec.js` is the whole journey: sign up, speak, see corrections arrive, end the session, read the report, find it in history, pin a difficulty, delete the account; two shorter tests cover the speaking-style pickers (only companions who can speak a style are on offer, the reason is written on the page, the choice is saved, and a profile saved with a pair nobody can speak starts in Standard English). The other files cover leaving a session (`lifecycle.spec.js`), keyboard use of the microphone, titles and an axe accessibility scan of every page (`accessibility.spec.js`), what a signed-out visitor sees and the security headers (`public.spec.js`), and a 390 px phone screen (`responsive.spec.js`). Only the journey spends speech-to-text and language-model calls; the rest fake the server's reply. Run them against a throwaway database and your own ports, never your development database (see `frontend/README.md`).

`npm test` (from `frontend/`) runs the frontend's unit tests with Node's built-in runner, no browser needed: the formatters, the accent rules, reading the reply stream, choosing a recording format, and refusing a redirect that leaves the site.

ESLint's `no-undef` rule is switched on in `frontend/eslint.config.mjs` (Next's preset leaves it off): a variable that exists only in another component builds cleanly and then crashes the page when it is opened, which is exactly what the full journey caught once.

GitHub Actions (`.github/workflows/ci.yml`) runs the backend suite on PostgreSQL and the frontend lint, unit tests and build on every push that touches `Aurora/`. The suite sets its own `DATABASE_URL` from `TEST_DATABASE_URL` before the app is imported, so the workflow only needs the latter.

## Deploying

AURA is two deployables plus a database.

**Backend → container.** The `Dockerfile` in this folder produces one image with the code, the six companion voices, the two accent voices and (by default) the Whisper model baked in, so nothing downloads at start-up.

```bash
docker build -t aura-backend .                         # add --build-arg BAKE_WHISPER=false if you'll use STT_PROVIDER=groq
docker run -p 8000:8000 --env-file .env aura-backend
```

On start it applies migrations (`RUN_MIGRATIONS=false` to skip) and serves on `$PORT` (default 8000) with `--proxy-headers`. It runs as a non-root user and defaults to `ENVIRONMENT=production`. Use it on any host that runs containers (Render, Railway, Fly.io, a VM); set the environment variables in the host's dashboard rather than shipping a `.env`.

- **Memory.** Measured in the container (`docker stats`, one learner): about **0.75 GB** right after start-up with local Whisper and the six companion voices (about **0.85 GB** once a turn has run), **0.65 GB** with `STT_PROVIDER=groq` and the six voices, and **0.1-0.2 GB** with `STT_PROVIDER=groq` and `PREWARM_MODELS=false` (each voice, about 90 MB, then loads the first time someone picks it). The two accent voices are never prewarmed: the first session in a regional style adds about 100 MB (the multi-speaker model) and the first one that needs Alba (Eida's Scottish voice) about 125 MB more, so the default setup sits at **about 1 GB** once both are in use, before a turn's own working memory. So give the default setup 1.5 GB if learners will use the regional accents (a 1 GB instance is comfortable with `STT_PROVIDER=groq`), and a 512 MB one is only realistic for the lean setup. Several simultaneous turns need more headroom than these single-learner figures.
- **Image size.** About 0.9 GB to pull (compressed) and 1.45 GB unpacked: Python packages ~595 MB, voices ~580 MB (six companions ~440 MB, two accent voices ~140 MB), the Whisper model ~150 MB, the OS and Python ~120 MB (Docker Desktop's image list may show about double because it counts both copies). `--build-arg BAKE_WHISPER=false` drops the model (~130 MB less to pull) when you use `STT_PROVIDER=groq`.
- **One worker.** Rate limits live in process memory, and each worker would load its own copy of the models. Run a single uvicorn worker; if you ever scale out, move the limiter to Redis first.
- **Behind a proxy.** Behind your platform's proxy every request seems to come from the proxy, which would put all learners into one rate-limit bucket (ten signups an hour for *everyone*). So the image sets `FORWARDED_ALLOW_IPS=*`, and uvicorn takes each learner's address from `X-Forwarded-For`. The catch: with `*` it trusts the **left-most** address in that header, which a client can forge if your platform appends to what the client sent instead of replacing it. Per-IP limits (signup, login, password-reset requests) could then be sidestepped, while the per-account limits (failed logins per email, code attempts, voice turns per learner) cannot. If your platform publishes its proxies' addresses, set `FORWARDED_ALLOW_IPS` to those instead: uvicorn then reads the header from the right and ignores forged entries. Never run the container directly on the internet with `*`.
- **Health.** Point your platform's health check at `/health` (fast: database, schema, speech models) and your uptime monitor at `/health?full=true` (also pings Groq; adds a couple of seconds). Both answer **503** when the app can't do its job (database down, schema behind, no voices installed, Groq down on the full check); being rate-limited by Groq is reported but not treated as an outage. The body never includes error text.

**Database → any managed PostgreSQL** (Neon, Supabase, Render, RDS). Use the provider's connection string as `DATABASE_URL` (usually with `?sslmode=require`).

**Frontend → Vercel** (or any Node host). Import the repository, set the project's root directory to `Aurora/frontend`, and set `NEXT_PUBLIC_API_BASE` to your API's public URL (and `NEXT_PUBLIC_SITE_URL` to the app's own, so shared links get a preview card). Then on the API side set `FRONTEND_URL` to the Vercel URL (and `CORS_ORIGINS` for any preview URLs).

### Production checklist

With `ENVIRONMENT` set to anything but `development`, the API checks its own configuration at startup and logs each finding as `Production check: …` (it never refuses to start over them, so read your first deploy's log). It covers:

- `JWT_SECRET` is at least 32 random characters and not a placeholder
- `FRONTEND_URL` isn't localhost and is https; `CORS_ORIGINS` has no localhost
- `GOOGLE_REDIRECT_URI` is https when Google sign-in is configured, and registered in the Google console
- `RESEND_API_KEY` is set and `EMAIL_FROM` is on a domain you've verified with Resend (the default and `onboarding@resend.dev` only reach your own address)
- Cloudinary is configured (photo uploads) and `SENTRY_DSN` is set (error tracking)
- `RATE_LIMITS_ENABLED` is on, `SQL_ECHO` is off, `LOG_LEVEL` isn't `DEBUG`

`python check_setup.py` runs the same checklist against your `.env` (set `ENVIRONMENT=production` first), so you can fix problems before deploying.

Also: rotate any key that has ever been pasted into a chat or committed, and keep the database private.

## API overview

All endpoints except health, options, signup, login and the password-reset/Google entry points need `Authorization: Bearer <token>`. Interactive docs: `/docs`.

| Area | Endpoints |
|---|---|
| Health | `GET /health`, `GET /health?full=true` |
| Accounts | `POST /api/auth/signup`, `login`, `change-password`, `forgot-password`, `verify-otp`, `verify-email`, `resend-verification`; `GET /api/auth/me`; `PATCH /api/auth/profile`; `POST /api/auth/avatar`; `DELETE /api/auth/account` |
| Google | `GET /api/auth/google`, `GET /api/auth/google/callback`, `POST /api/auth/google/link-code`, `google/exchange`, `google/disconnect` |
| Setup | `GET /api/config/options` (voices, styles, scenarios, difficulty levels, focus areas) |
| Conversation | `POST /api/conversation/start`, `POST /api/conversation/message-stream`, `POST /api/conversation/{id}/end` |
| Feedback | `GET /api/analysis/conversation/{id}/recent` |
| History | `GET /api/history/sessions`, `GET /api/history/sessions/{id}`, `GET /api/history/sessions/{id}/report` |
| Progress | `GET /api/progress/summary` |
| Practice | `GET /api/practice/today`, `GET /api/practice/weaknesses`, `GET /api/practice/difficulty` |
| Speech | `POST /api/speech/word` (hear a word pronounced, optionally slowly, in the session's accent when you pass its `style`) |

## Project layout

```
Aurora/
├── backend/
│   ├── main.py                 app, startup checks, routers, middleware
│   ├── config.py               every environment variable, in one place
│   ├── personalities.py        companions, speaking styles and the voice behind each accent, scenarios, difficulty levels, system prompt
│   ├── taxonomy.py             the mistake categories/subtypes and practice focuses
│   ├── production_checks.py    the startup production checklist
│   ├── routers/                HTTP endpoints (one file per area)
│   ├── services/               stt, tts, llm, analysis, fluency, clarity, scoring, reports,
│   │                           progress, weaknesses, difficulty, rate limiting, auth, uploads
│   ├── models/ schemas/        SQLAlchemy tables / Pydantic request and response shapes
│   ├── alembic/                database migrations
│   └── tests/                  pytest suite (+ regression/ for the live-LLM cases)
├── frontend/                   Next.js app (app/, components/, lib/, e2e/)
├── scripts/                    download_voices.py, loadtest_voice.py
├── voices/                     Piper models (downloaded, git-ignored)
├── check_setup.py              "is my machine set up correctly?"
├── local_client.py             optional terminal client (see requirements-local.txt)
├── Dockerfile  .dockerignore   the backend image
├── docker-compose.yml          local PostgreSQL
└── AURA_remaining_work_plan.md the test report, what was built, and what was found
```

## Limitations

Worth knowing before you rely on it:

- **Clarity is an estimate, not pronunciation scoring.** It comes from the speech recogniser's confidence: unclear words, background noise, rare words and mis-heard homophones all lower it, and a high score doesn't prove native-like sounds. The product labels it as such.
- **Fillers need `STT_PROVIDER=groq`.** Local `base.en` drops "um" and "uh", so with it the fluency score has no filler information.
- **Analysis is an LLM's judgement.** It is accurate on the regression set (27 cases), but model output varies a little between runs and it can occasionally miss a mistake or, rarely, flag a correct sentence. Per-turn feedback isn't a grade from a teacher.
- **Praise for phrasal verbs is unreliable.** The coach praises idioms consistently, but praised a correct sentence full of phrasal verbs ("figure out", "sort out") only about half the time in testing, on either model. It never calls them mistakes. The regression suite records this as a known weak spot (`xfail`).
- **The accents are real regional speakers, but no native speaker has judged them.** Each voice was chosen from a corpus's own labels (accent, region, gender) and checked for intelligibility by round-tripping it through the speech recogniser, which proves the speech is clear, not that it sounds authentically Irish or Scottish. Where a voice exists matters too: the corpus has two Australian speakers (both men), so the female companions have no Australian voice, and its British speakers are mostly from southern England. The coach's *words* for each style (vocabulary and phrasing) come from the prompt and are as reliable as any LLM output.
- **Free-tier Groq limits** cap how many learners can practise at once (see above).
- **Single process.** Rate limits are in memory; see Deploying.
- **Browsers.** Recording has been exercised in Chrome. Firefox and Safari recording, and the light theme on every page, haven't been tested.
- **Not exercised against the real services:** the Google sign-in success path (a human has to click through consent), real Resend email delivery and real Cloudinary uploads were tested with fakes and validation only. `local_client.py` wasn't re-run after the authentication changes. The GitHub Actions workflow's first run failed because the suite quietly depended on the voice files being installed; that is fixed and was checked in a CI-like copy of the project (no voices, no `.env`), but the fixed workflow hasn't been re-run on GitHub yet.
- **Not built:** PDF export of a report, and WebSocket streaming (streaming over HTTP meets the latency target).
- Sessions from before speech metrics existed have no fluency or clarity data, and are shown as not analysed rather than scored.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| The page says it can't reach the backend | The API isn't running on port 8000, or `NEXT_PUBLIC_API_BASE` is wrong |
| Startup log: *Database schema is X, code expects Y* | Run `alembic -c backend/alembic.ini upgrade head` |
| The coach is silent but text appears | A voice file is missing: `python scripts/download_voices.py --check` |
| A speaking style or companion is greyed out ("doesn't have a ... voice yet") | That companion has no voice for the accent (Australian exists for Ryan and Alan only), or the accent model isn't installed: `python scripts/download_voices.py --check` |
| `/health` says `behind` or answers 503 | Check the API log: it names the exact problem (database unreachable, schema behind, no voices) |
| "The coach is very busy right now" | Groq's rate limit: wait a few seconds, or see the notes above |
| First turn after a restart is slow | Models are still loading; `/health` shows `speech.stt.ready` and `speech.voices.loaded` |
| Verification email never arrives (development) | Without `RESEND_API_KEY` the code is printed in the API's log |
| Tests refuse to start | PostgreSQL isn't running (`docker compose up -d`), or `TEST_DATABASE_URL` doesn't end in `_test` |
| `npm run dev` shows stale pages after edits | Restart the dev server (file watching on synced folders such as OneDrive can miss changes) |
