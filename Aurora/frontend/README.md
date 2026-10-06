# AURA — web app

The browser side of AURA: Next.js 16 (App Router), React 19, Tailwind CSS v4, **JavaScript** (not TypeScript). The project overview, setup, configuration and deployment guide are in [the main README](../README.md); this file is only about working on the frontend.

## Run it

```bash
cp .env.local.example .env.local     # NEXT_PUBLIC_API_BASE=http://localhost:8000
npm install
npm run dev                          # http://localhost:3000
```

The API must be running too (see the main README's quick start).

| Script | What it does |
|---|---|
| `npm run dev` | Development server with hot reload |
| `npm run build` / `npm start` | Production build / serve it |
| `npm run lint` | ESLint (includes the React rules; keep it clean) |
| `npm run e2e` | Playwright journey against the **running** stack (API + this app), using Chrome's fake microphone |

Deploying: any Node host; Vercel works with the project root set to `Aurora/frontend`. The only variable it needs is `NEXT_PUBLIC_API_BASE`, the API's public URL, and the API must list this app's address in `FRONTEND_URL` / `CORS_ORIGINS`.

## Where things are

```
app/            routes: / (landing), login, signup, forgot-password, verify-email,
                practice, history, history/[id], history/[id]/report, progress, profile,
                auth/google/callback
components/     UI pieces (SessionSetup, ConversationView, CorrectionsPanel, SessionReportView,
                LineChart, TodaysPractice, DifficultyLabel, ...)
lib/api.js      every call to the API (voice stream, history, reports, progress, practice)
lib/auth.js     sign-in/up, profile and account calls, and the cached user
lib/audioQueue.js   plays the coach's sentence-sized audio chunks in order
public/characters   the companions' artwork
e2e/            the Playwright journey and its speech fixture
```

## Conventions

- **All API calls go through `lib/api.js` / `lib/auth.js`.** They attach the bearer token, turn a 401 into a cleared session and a redirect to login, and show the server's own error message instead of a bare status code.
- **Charts are hand-written SVG** (`LineChart.js`): no charting dependency.
- **Colours and type come from the tokens in `app/globals.css`**, so both themes stay consistent.
- This version of Next.js has breaking changes from older ones. Before relying on a remembered API, check `node_modules/next/dist/docs/` (see `AGENTS.md`).
- If the dev server shows stale pages after you edit a file, restart it: file watching on synced folders (OneDrive) can miss changes.
