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
| `npm test` | Unit tests of the pure helpers in `lib/` (`lib/*.test.js`), with Node's built-in runner: no browser, no server |
| `npm run e2e` | Playwright tests against the **running** stack (API + this app), using Chrome's fake microphone |

Deploying: any Node host; Vercel works with the project root set to `Aurora/frontend`. The variables it needs are `NEXT_PUBLIC_API_BASE`, the API's public URL (and the API must list this app's address in `FRONTEND_URL` / `CORS_ORIGINS`), and `NEXT_PUBLIC_SITE_URL`, this app's own address, which link previews are built from.

## Where things are

```
app/            routes: / (landing), login, signup, forgot-password, verify-email, auth/google/callback,
                and (app)/ for the signed-in screens: practice, progress, history, history/[id],
                history/[id]/report, profile. A route group does not appear in the URL: it is there so those
                screens share ONE layout (the login check and the sidebar) that stays mounted as you move between them.
                Also: not-found.js, error.js, global-error.js, opengraph-image.js (the share-preview card)
components/     UI pieces. AppShell + AppSidebar frame every signed-in page; SessionSetup, ConversationView,
                CorrectionsPanel, SessionReportView, RecordButton, LineChart, ...
lib/api.js      every call to the API (voice stream, history, reports, progress, practice)
lib/auth.js     sign-in/up, profile and account calls, and the cached user
lib/audioQueue.js   plays the coach's sentence-sized audio chunks in order
lib/*.js        pure helpers, each with a *.test.js beside it: format (durations and dates), ndjson (reading the
                reply stream, with its timeouts), recording (formats per browser, microphone errors),
                redirects (only a path on this site), accents (which companion can speak which style)
hooks/          motion.js (pointer parallax, reduced motion), media.js (media queries)
public/characters   the companions' artwork
aura-project-assets the source images that artwork is built from (scripts/build-characters.cjs)
e2e/            the Playwright tests: smoke (the journey), lifecycle, accessibility, public, responsive (the "phone"
                project); helpers.js; and the speech fixture
```

## Conventions

- **All API calls go through `lib/api.js` / `lib/auth.js`.** They attach the bearer token, turn a 401 into a cleared session and a redirect to login, and show the server's own error message instead of a bare status code.
- **Logic that can be a pure function lives in `lib/` with a test.** `npm test` runs them in plain Node, so they cannot import `@/...` paths or React: that is the point, it keeps them small and testable.
- **Pages are client components, so a section sets its tab title in a tiny `layout.js`** next to its page (`export const metadata = { title: "Practice" }`); the root layout's template turns it into "Practice — AURA".
- **Copy must describe only what is real.** The six companions differ in voice, face and name; the coach's prompt is the same for all of them. A sample (the landing page's dashboard) must not show anything the real screen lacks. `e2e/public.spec.js` guards the phrases that were removed.
- **A switched-off control explains itself in visible text.** A tooltip never shows on a touch screen, and a `disabled` button cannot be tabbed to: use `aria-disabled` and write the reason on the page (see `SessionSetup.js`).
- **Motion respects `prefers-reduced-motion`**: use `usePrefersReducedMotion()` from `hooks/motion.js` for anything that moves for decoration.
- **Charts are hand-written SVG** (`LineChart.js`): no charting dependency.
- **Colours and type come from the tokens in `app/globals.css`**, so both themes stay consistent. The text and chart colours were checked against WCAG AA contrast; recheck if you change a token.
- This version of Next.js has breaking changes from older ones. Before relying on a remembered API, check `node_modules/next/dist/docs/` (see `AGENTS.md`). For example, an `error.js` boundary receives `retry`, not `reset`.
- If the dev server shows stale pages after you edit a file, restart it: file watching on synced folders (OneDrive) can miss changes.

## Running the browser tests without touching your dev database

`npm run e2e` creates accounts, so point it at a throwaway database, not your own. From `Aurora/`: create a database (say `aura_e2e_test`) in the compose PostgreSQL, run `alembic -c backend/alembic.ini upgrade head` with `DATABASE_URL` pointing at it, start the API on another port (`uvicorn backend.main:app --port 8001` with that `DATABASE_URL`, `CORS_ORIGINS` and `FRONTEND_URL` set to the front end's address, and `RATE_LIMITS_ENABLED=false`), build and serve the front end on another port (`NEXT_PUBLIC_API_BASE=http://localhost:8001 npm run build`, then `npx next start -p 3001`), and run:

```bash
E2E_BASE_URL=http://localhost:3001 E2E_API_BASE=http://localhost:8001 npm run e2e
```

A production build is what the security-header and share-preview tests need. Drop the throwaway database afterwards.
