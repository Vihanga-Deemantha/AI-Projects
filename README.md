<div align="center">

# AURA — AI English Speaking Coach

**Speak naturally. Get smarter feedback. Become a better English speaker.**

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4-06B6D4?logo=tailwindcss&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)

</div>

AURA is a web app for practising **spoken** English. You hold a button and talk to an AI companion. AURA transcribes what you said and answers out loud in a natural voice (on a development laptop the first words arrive in about one and a half to two seconds). Without interrupting the conversation, it also works out your grammar, vocabulary and phrasing mistakes, measures *how* you spoke (pace, pauses, filler words, clarity), and turns every session into a score report, a progress chart, a list of the habits you keep repeating, and a conversation that gets harder as you improve.

It is a complete full-stack system: a **FastAPI** backend that runs speech recognition, an LLM conversation and neural text-to-speech as one streamed pipeline; a **PostgreSQL** database; and a **Next.js** web app with accounts, history, reports and progress tracking.

### At a glance

| | |
|---|---|
| **Companions** | 6, each with their own voice and face |
| **Speaking styles** | 7 English varieties; each changes the coach's words **and** the accent you hear |
| **Scenarios** | 7: casual chat, job interview, travel, debate, university seminar, café, phone call |
| **Difficulty** | 5 levels that follow your recent scores one step at a time (or pin one yourself) |
| **Feedback** | mistakes, suggestions and praise on grammar, vocabulary and naturalness (33 labelled kinds) |
| **Speech measures** | fluency (pace, pauses, fillers, repeats) and clarity, for every turn you speak |
| **Reports** | 5 scores plus an overall score, strengths, what to work on, common mistakes, words to practise |
| **Progress** | weekly trends, practice streaks, milestones, a weak-spot profile and a daily exercise |
| **Accounts** | email and password, Google sign-in, email verification, password reset, profile photo, account deletion |
| **Stack** | FastAPI, PostgreSQL, Groq (LLM), faster-whisper (speech to text), Piper (text to speech), Next.js, React, Tailwind CSS |
| **Quality** | More than 560 offline backend tests, a live-LLM regression suite, Playwright browser tests, CI, a container smoke test |

> **Where to start.** New here? Read [What is AURA?](#what-is-aura) and [A tour of the features](#a-tour-of-the-features). Want to run it? Jump to [Getting started](#getting-started). Operating or deploying it? See [Deployment](#deployment) and the operations guide in [`Aurora/README.md`](Aurora/README.md).

---

## Table of contents

1. [What is AURA?](#what-is-aura)
2. [Who benefits](#who-benefits)
3. [Feature overview](#feature-overview)
4. [A tour of the features](#a-tour-of-the-features)
5. [How the system works](#how-the-system-works)
6. [Tech stack](#tech-stack)
7. [Repository layout](#repository-layout)
8. [Getting started](#getting-started)
9. [Configuration reference](#configuration-reference)
10. [API reference](#api-reference)
11. [Database and migrations](#database-and-migrations)
12. [Testing and quality](#testing-and-quality)
13. [Deployment](#deployment)
14. [Performance and limits](#performance-and-limits)
15. [Privacy and security](#privacy-and-security)
16. [Known limitations](#known-limitations)
17. [Roadmap](#roadmap)
18. [Troubleshooting and FAQ](#troubleshooting-and-faq)
19. [Contributing and extending AURA](#contributing-and-extending-aura)
20. [Credits and licences](#credits-and-licences)
21. [Glossary](#glossary)

---

## What is AURA?

### The problem

Speaking is the hardest part of a language to practise alone. Reading and listening apps never make you talk. A human tutor is expensive and not available at 11 pm. Many people feel anxious about making mistakes in front of others. Voice assistants answer commands but do not coach, and even a kind conversation partner rarely gives you exact, itemised feedback without breaking the flow of the conversation.

### The idea

**Practise out loud with an AI; get the coaching on the side, not in the way.** AURA splits every turn into two pipelines that run at the same time:

- **Path A, the conversation.** Your speech is transcribed, a large language model writes a short, warm reply, and each finished sentence is turned into audio and streamed back immediately, so the coach starts talking before it has finished thinking.
- **Path B, the analysis.** While the coach is still speaking, a second LLM call reads what you said and returns structured feedback: what was wrong, what could be better, and what you did well. It never delays the reply, and it never interrupts.

On top of those two paths, AURA measures *how* you spoke from the recogniser's word timings and confidences, and then turns the pile of evidence into things a learner can act on: a report per session, trends across weeks, a ranked list of recurring weaknesses, and a conversation steered at the weakest one.

### What makes it different

| A generic voice assistant | AURA |
|---|---|
| Answers commands | Holds a real conversation in a scenario you choose (interview, café, phone call, ...) |
| No language feedback | Itemised grammar, vocabulary and naturalness feedback, with the better wording and a one-sentence reason |
| One pipeline (speak, then reply) | Two pipelines: the spoken reply is never slowed down by the analysis |
| Stateless | Every session is stored: transcripts, corrections, scores, reports |
| One voice | 6 companions and 7 English varieties, each with a matching accent where a real voice exists |
| Fixed difficulty | Difficulty follows your recent scores, one step per session |
| Generic | Notices what you keep getting wrong and steers the next conversation towards it, without announcing it |

### Design principles: honest by design

These rules run through the whole code base and are worth knowing, because they explain choices you will see in the interface.

1. **Conversation first, correction on the side.** Detailed feedback arrives separately. The coach may *gently model* a correct form in its reply at most once per session, and never says "you made an error".
2. **Measure, don't flatter.** Scores are *densities* (mistakes per 100 words), so a long, brave answer is not punished for having more words to slip in. A dimension with no evidence shows as blank, never as a flattering 100.
3. **Say what an estimate is.** Clarity comes from the speech recogniser's confidence. It is labelled as an estimate everywhere, because it is not phoneme-level pronunciation scoring.
4. **Never invent a problem.** Any piece of feedback whose quoted words are not really in the transcript is thrown away. Spoken English is informal, so contractions and "gonna" are not mistakes. Regional forms are *correct* in their variety.
5. **Never promise what is not there.** A companion is only offered a speaking style if a real voice of that accent exists for them. A filler count says "could not hear them" (an asterisk) instead of a false "0" when the recogniser drops *um* and *uh*.
6. **Private by default.** Audio is never stored, speech recognition can run entirely on your own server, and deleting your account removes everything.
7. **Fail soft.** Every voice turn ends with a `done` event. If a sentence cannot be spoken, the text still appears; if the LLM is rate-limited, the coach says so instead of hanging.

### Project status and history

The project was built in phases. All of them are implemented and tested; what remains is listed under [Known limitations](#known-limitations) and [Roadmap](#roadmap).

| Phase | What it added |
|---|---|
| 0 Foundations | Project structure, configuration, database, migrations |
| 1 Voice loop | Speech to text, streamed LLM reply, sentence-by-sentence text to speech, and a terminal client to prove it |
| 2 Feedback | The asynchronous grammar and vocabulary analysis, stored as corrections |
| 3 Web app | Next.js conversation screen with push-to-talk, live transcript and corrections |
| 3b Accounts | Sign-up and login, protected API, home page, speech history |
| 3c Profile and recovery | Profile photo, password reset by emailed code, Google sign-in |
| 3d Hardening | Email verification, rate limits, token revocation, account deletion, Alembic-only schema, test suite, CI |
| 4 Fluency | Pace, pauses, fillers and repetitions measured on every turn |
| 5 Clarity | Recogniser-confidence estimate, "hard to catch" words, hear-it buttons |
| 6 Naturalness | Suggestions and praise for idioms, phrasal verbs and strong phrasing |
| 7 Reports | A scored report for every finished session |
| 8 Progress | Weekly trends, streaks, totals and milestones |
| 9 Weaknesses | A ranked weak-spot profile and a daily exercise that steers the conversation |
| 10 Adaptive difficulty | Five levels that follow recent scores |
| 11 Polish and deployment | Docker image, health checks, production self-check, Sentry, documentation |
| Later | The six-companion system, and speaking styles whose accents match their words |

---

## Who benefits

### Learners (the primary audience)

AURA is built for people who want more **speaking** practice than they can get from a book, a video or a weekly class:

- **Self-study learners** who have nobody to practise with, or who want practice outside class hours.
- **People preparing for a moment that matters**: a job interview, a university seminar, a trip, a phone call with a bank. Each has its own scenario, and the coach stays in role.
- **Shy or anxious speakers** who would rather make mistakes in front of software first. Nothing is graded by a person, and the tone is encouraging.
- **Learners who will meet different Englishes** at work, university or while travelling, and want to hear American, British, Australian, Irish, Scottish and Canadian speakers (see [Speaking styles and accents](#speaking-styles-and-accents) for what exists and what does not).
- **Busy people** who can fit in five minutes, and want streaks, reports and a visible trend to keep going.

What a learner gets out of a session: corrections they can see and compare (their words struck through, the better wording next to them, and why), praise for things they did well, hard-to-catch words they can hear again slowly, and a report that says what to work on next.

### Teachers, tutors and language schools

AURA does not have a teacher dashboard (see [Roadmap](#roadmap)), but its output is useful in a lesson: the report names a learner's most common mistakes with real examples, the weak-spot list shows which habits persist over weeks, and the history keeps full transcripts. A learner can bring these to a lesson, and a teacher can treat the daily exercise as speaking homework.

### Developers and students

AURA is also a **reference implementation of a real-time voice AI application**, written to be read:

- a streamed pipeline (audio in, NDJSON out) with sentence-level audio chunking and well-defined failure behaviour on every path;
- LLM output treated as *untrusted input* (validated, normalised, quote-checked, capped);
- pure, unit-tested scoring code, versioned so a formula change never silently changes what a chart means;
- an authentication system with the hardening a real product needs (see [Privacy and security](#privacy-and-security));
- a test suite that needs no network, no model files and no keys, plus a live regression suite for the one component (the LLM) that cannot be unit-tested;
- migrations, health checks, a production self-check, a Docker image and a smoke test that actually starts it.

### People who run it themselves

Operators who care where their data goes can run speech recognition **on their own machine** (audio never leaves the server), choose the LLM models, and deploy on any host that runs containers. See [Deployment](#deployment) and [Privacy and security](#privacy-and-security).

### What AURA is not

- **Not an exam or a certificate.** Scores are a practice aid, not a CEFR/IELTS/TOEFL grade.
- **Not a replacement for a teacher.** Feedback is an LLM's judgement: accurate on the project's regression set, but it can occasionally miss a mistake or, rarely, flag a correct sentence.
- **Not pronunciation scoring.** Clarity is an estimate built on recogniser confidence, and says so.

---

## Feature overview

| Area | What you can do | Details |
|---|---|---|
| **Voice conversation** | Hold to talk (or tap to talk, or hold Space), hear the coach reply sentence by sentence, pause and resume its voice | [The practice screen](#the-practice-screen) |
| **Companions** | Choose one of six companions, each with a voice and a face | [Companions](#companions) |
| **Speaking styles and accents** | Seven English varieties; the coach's words and its accent both follow the style | [Speaking styles and accents](#speaking-styles-and-accents) |
| **Scenarios** | Casual chat, job interview, travel, debate, university seminar, café, phone call | [Scenarios](#scenarios) |
| **Adaptive difficulty** | Five levels that follow your scores, or pin one | [Difficulty levels](#difficulty-levels) |
| **Instant feedback** | Mistakes, suggestions and praise, live, while you keep talking | [Instant feedback](#instant-feedback-corrections-suggestions-and-praise) |
| **Speech measures** | Fluency and clarity for every turn; hard-to-catch words with hear-it buttons | [How you spoke](#how-you-spoke-fluency-and-clarity), [Hear a word again](#hear-a-word-again) |
| **Session reports** | Overall score, five dimensions, strengths, next steps, common mistakes, practice words | [Session reports](#session-reports) |
| **History** | Every past session with its transcript and feedback | [Speech history](#speech-history) |
| **Progress** | Weekly score trends, streaks, totals, milestones | [Progress](#progress) |
| **Weak spots and daily practice** | A ranked weakness profile and a conversation steered at your weakest habit | [Weak spots and daily practice](#weak-spots-and-daily-practice) |
| **Accounts** | Email or Google sign-in, verification, reset, profile, deletion | [Accounts and sign-in](#accounts-and-sign-in), [Profile and account settings](#profile-and-account-settings) |
| **Look and feel** | Light and dark themes, responsive layout, reduced-motion support | [Looks and accessibility](#looks-and-accessibility) |
| **Developer tools** | Terminal client, setup checker, load test, container smoke test, health endpoints | [Tools for developers and operators](#tools-for-developers-and-operators) |

---

## A tour of the features

### A first session, step by step

1. **Open the landing page and choose "Start speaking".** Sign up with an email and a password (eight characters or more), or with Google. You are signed in immediately and land on the practice screen. A banner in the sidebar asks you to verify your email; it is optional.
2. **Set up the session.** Pick a companion (Amy is the default), a speaking style (Standard English is the default) and a scenario (Casual Conversation). New learners start at the *Elementary* level; the screen says so and explains that it adapts as you practise.
3. **Hold the microphone button and talk; release to send.** The first time, the browser asks for microphone permission. Holding the button is enough to start a session; there is also a "Start session" button if you prefer.
4. **Watch your words arrive.** Within a second or two your transcript appears as a bubble with small chips under it: a fluency score, words per minute, pauses, fillers and a clarity score. Then the coach starts speaking, sentence by sentence, while the text fills in.
5. **Read the feedback as it lands.** A moment later the Corrections panel fills in: your original words struck through, the better wording, and a one-sentence reason. There are also suggestions ("a fluent speaker would say it like this") and praise ("Nice · Idiom").
6. **Keep talking.** The turn counter, elapsed time, correction count and average fluency and clarity update as you go. You can pause and resume the coach's voice.
7. **End the session.** A "Session complete" banner shows the turns, time and corrections, with a link to your report. The transcript and feedback stay on screen as a recap until you start another session.
8. **Read the report.** An overall score, five dimension scores, a short note from your coach, what went well, what to work on next, your most common mistakes with examples, and words worth practising (with buttons to hear them).
9. **Come back tomorrow.** *Today's practice* on the practice screen suggests your weakest recurring habit, the *Progress* page shows your trend and streak, and *History* keeps every transcript.

### The landing page

The public home page (`/`) is a six-chapter scrolling introduction:

1. **Meet AURA**: a rotating cast of companions in different poses.
2. **Meet the characters**: a roster you can step through, with each companion's name, one-word vibe, a short description of their voice and a "Practise with ..." button. A line under it says that all six coach the same way and differ in voice, face and name.
3. **Enter different scenarios**: all seven scenarios, each with its setting, the skills it exercises and an example of a line the coach might say (labelled as an example: the real coach answers after you speak).
4. **Practise English**: a sample session with corrections, labelled as written for the page rather than recorded, and in the order a real session goes: you speak first.
5. **Track your improvement**: a sample of the real Progress screen (the same four figures and the same weekly score chart) with made-up numbers, labelled as sample data. A sample must not show anything the real screen does not have; `e2e/public.spec.js` checks that.
6. **Start speaking**: the call to action.

The header shows *Log in* and *Start speaking*, or *Go to practice* when you are signed in. Characters lean gently towards the pointer; this switches off when your system asks for reduced motion. The footer states plainly what speaking styles do and do not cover.

### Accounts and sign-in

| Feature | How it behaves |
|---|---|
| **Sign up** (`/signup`) | Email, password (at least 8 characters, no maximum), optional name. You are signed in straight away. "Sign up with Google" is the alternative. |
| **Email verification** (`/verify-email`) | A six-digit code is emailed (valid 15 minutes, three attempts, a new one can be requested after 60 seconds). Confirming is encouraged but optional ("Skip for now"); a reminder stays in the sidebar until you do. A password reset or a Google sign-in also proves you own the address. Emails are sent with Resend; without a Resend key the code is printed in the server log in development. |
| **Log in** (`/login`) | Email and password. A wrong password and an unknown email give the *same* message and take the *same* time, so nobody can discover which addresses have accounts. |
| **Forgot password** (`/forgot-password`) | Three steps: your email, the six-digit code, a new password. The page always says a code "is on its way", whether or not the account exists. Success signs you in and ends every other session. |
| **Google sign-in** | OAuth 2.0 with a CSRF-protected state. Google must vouch for the email address. An existing Google account signs in; a password account with the same email is linked; otherwise a new account is created. |
| **Sessions** | A signed token (JWT, 7 days by default) that carries a *token version*. Changing or resetting a password bumps the version and logs out every other session at once. |
| **Delete account** | Type your email (and your password, if you have one). Everything under the account is removed: sessions, transcripts, corrections, metrics, reports, and the stored profile photo. |

**A subtle protection worth knowing:** an unverified email address is never trusted. If someone pre-registers `victim@example.com` with a password they know, and the real owner later signs in with Google, AURA discards that password, clears pending codes and revokes every existing session before linking. Without this rule the attacker's password would still open the account.

### The practice screen

The practice screen (`/practice`) is where everything happens. A status chip in the header always says what state you are in: *Not started*, *Ready*, *Listening*, *Thinking*, *Speaking*, *Paused* or *Session ended*, next to the *Start session*, *Pause / Resume* and *End session* buttons.

**Left column, the stage and the controls**

- **The stage.** The selected companion stands in a tinted panel and changes pose with the conversation: listening while you hold the mic, thinking while a reply is written, talking (the mouth alternates between two poses) while the reply plays, idle otherwise. Under it, a live waveform reacts to your microphone or to the coach's voice.
- **The talk button.** Two ways to use it, and neither needs a mouse. *Hold* (the default): hold the bar (mouse, touch or pen, or Space or Enter while it is focused) and release to send. *Tap*: tap to start and tap again to send, for anyone who cannot comfortably hold a button down for a whole sentence; a link under the button switches between the two, and the choice is remembered in your browser. A live timer runs while you record. Recordings shorter than 0.4 seconds are rejected on the spot with a friendly message, and a recording stops by itself at 60 seconds. Microphone problems (permission denied, no device, a page that is not served over https, a browser that cannot record) each get a plain-language explanation.
- **Latency badge.** After each turn it shows **first audio**, the number you actually wait for, with a *Details* link for the server's own timings: speech to text, the language model's first sentence, and the whole turn.
- **Session stats.** Turns, elapsed time, corrections so far, and your average fluency and clarity for this session.
- **Today's practice.** Your weakest live habit with a one-click "Practise this" (see [Weak spots and daily practice](#weak-spots-and-daily-practice)).
- **Session setup.** Companion, speaking style, scenario, and the difficulty the session will run at, with an example question and the reason ("Based on your last 3 session scores: 82, 78, 70."). The choices are dimmed and locked while a session is live and unlock when it ends. Companions and styles that cannot go together are dimmed, and the reason is written under the chips ("Amy doesn't have an Australian voice yet. Ryan and Alan do.") as well as in a hover tooltip; a dimmed chip can still be focused with Tab, so a screen reader can read why (see [Speaking styles and accents](#speaking-styles-and-accents)). Your companion and style are saved to your profile as soon as you pick them.

**Right column, the conversation and the feedback**

- **Conversation.** Chat bubbles with each speaker's face (yours is your profile photo or initial). Under each of your bubbles are the speech chips, and, when the recogniser was unsure of some words, a "Hard to catch" list with *hear* and *slow* buttons. While the coach is writing its reply you see animated "thinking" dots. Beneath the conversation, once, are the footnotes for those chips: that Clarity is an estimate from speech-recognition confidence rather than pronunciation scoring, and what a `*` means (a rough clarity score, or a filler count that cannot see "um" and "uh").
- **Corrections panel.** Feedback for the session, newest first, with an "Analysing..." indicator while the analysis of your latest turn is still running (it polls every 1.5 seconds, for at most 30 seconds). The header counts fixes and praise separately ("3 this session · 1 nice").

**Ending a session** closes it on the server (so it gets a duration in your history), stops the timer, and keeps the whole conversation on screen as a recap with a *Start new session* action. The recap only clears when you actually start another session. The report is generated in the background and the page looks again for new guidance a few seconds later. If you press *End session* while a reply is still arriving, the coach's voice stops at once; the rest of the reply still lands as text, so the transcript is complete.

**Leaving without ending.** If you walk away from a live session (a link inside the app, a closed tab, another site), AURA stops the coach's voice and ends the session for you, so it still gets its score and report. If that request is lost (offline, a browser that drops requests while a tab closes), the session shows as *unfinished* in History, and its page there has a *Finish session* button. A session that has been quiet for more than 30 minutes when it is ended is closed at its **last message**, not at "now", so idle time is never counted as practice, never moves the session to another day for the streak, and never inflates the practice time on the Progress page.

### Companions

Six companions, each with a name, a face, a voice and a one-word vibe. The vibe is deliberately *not* an accent, because the accent follows the speaking style (next section).

| Companion | Vibe | Voice (Piper model) | Home accent | The voice, in a phrase |
|---|---|---|---|---|
| **Eida** | Zen | `en_US-kristin-medium` (female) | American | A calm, unhurried voice. |
| **Maya** | Bubbly | `en_US-hfc_female-medium` (female) | American | An upbeat, energetic voice. |
| **Amy** | Sunny | `en_US-amy-medium` (female) | American | A friendly voice. |
| **Ryan** | Cozy | `en_US-ryan-high` (male) | American | A warm voice. |
| **Alan** | Stickler | `en_GB-alan-medium` (male) | British | A measured voice. |
| **Lessac** | Dramatic | `en_US-norman-medium` (male) | American | A deep, deliberate voice. |

Amy is the default. Hovering a companion shows their home accent and what they will sound like with the current speaking style. The companions' artwork (a set of poses, faces and scene illustrations) lives in `Aurora/frontend/public/characters` and is rebuilt from the source images by `scripts/build-characters.cjs`.

> **Honest note.** Companions differ in **voice, face and name**, and in nothing else. The coach's conversation prompt is the same for all six (it varies by scenario, style, difficulty and focus, never by companion), so everything the app says about a companion describes their *voice*, in the words of `VOICES[...]["desc"]` in `personalities.py`, and the landing page says outright that all six coach the same way. An earlier version described personalities ("changes subject twice a minute", "exacting about tense") that the prompt never produced; that copy is gone, and `e2e/public.spec.js` fails if those phrases come back on the landing page. The one-word vibes are playful labels for the voice; two of them (*Stickler* for Alan's "measured" voice and *Dramatic* for Lessac's "deep, deliberate" one) go a little beyond the voice descriptions, and are one word each to change in `frontend/lib/characters.js`. Per-companion personas are listed under [Roadmap](#roadmap).

### Speaking styles and accents

A **speaking style** is an English variety. It changes two things together, so the words and the sound always agree:

1. **The coach's words.** The style adds a short instruction to the prompt (vocabulary, idiom, phrasing), with guardrails: light and natural usage, standard spelling, never caricature, never phonetic dialect, nothing that mocks a community.
2. **The accent you hear.** The companion speaks in a voice of that accent.

| Style | Typical wording the coach reaches for | Accent |
|---|---|---|
| **Standard English** | Clear, neutral wording | The companion's own voice |
| **American English** | apartment, elevator, sidewalk, "I've gotten" | American |
| **British English** | flat, lift, queue, "not bad", "cheers" | British |
| **Australian English** | arvo, reckon, "no worries", "heaps" | Australian |
| **Irish English** | grand, "sure look", "fair play" | Irish |
| **Scottish English** | wee, aye, "how's it going" | Scottish |
| **Canadian English** | washroom, toque, "eh", "double-double" | Canadian |

The grammar analysis is style-aware too: vocabulary and phrasing that is standard in the chosen variety is treated as *correct* ("flat" and "lift" are not errors in British English), and a regional alternative may be offered as a suggestion.

**Where the accents come from.** The regional voices are *recordings of real people*, not an effect applied to another voice. They come from two University of Edinburgh speech corpora, served by two extra Piper models: the **VCTK corpus** (109 speakers, each labelled with their accent, region and gender by the corpus itself) and **Alba**, a Scottish speaker. For every companion and accent AURA picks a speaker of the **same gender** and the right accent, so a female companion never turns into a man's voice.

**Who speaks what.** Standard English is every companion's own voice. For a regional style, a companion whose home accent already matches keeps their own voice (so American is their own voice for everyone except Alan, and British is Alan's own voice); otherwise they use a speaker from the table below.

| | American | British | Australian | Irish | Scottish | Canadian |
|---|---|---|---|---|---|---|
| **Eida** | own voice | regional | not available | regional | regional (Alba) | regional |
| **Maya** | own voice | regional | not available | regional | regional | regional |
| **Amy** | own voice | regional | not available | regional | regional | regional |
| **Ryan** | own voice | regional | regional | regional | regional | regional |
| **Alan** | regional | own voice | regional | regional | regional | regional |
| **Lessac** | own voice | regional | not available | regional | regional | regional |

**Australian is available for Ryan and Alan only.** The corpus has just two Australian speakers, and both are men, so only two companions can have a distinct Australian voice, and those are Ryan and Alan. Piper's catalogue has no Australian woman, so Eida, Maya and Amy have none, and Lessac would have to share a voice, which AURA does not do.

<details>
<summary><strong>The exact speakers used</strong> (from <code>ACCENT_VOICES</code> in <code>Aurora/backend/personalities.py</code>)</summary>

| Companion | British | Australian | Irish | Scottish | Canadian |
|---|---|---|---|---|---|
| Eida (F) | p268, southern England | none | p283, Cork | Alba, Edinburgh | p343, Alberta |
| Maya (F) | p229, southern England | none | p295, Dublin | p234, West Dumfries | p312, Hamilton |
| Amy (F) | p225, southern England | none | p340, Dublin | p262, Edinburgh | p303, Toronto |
| Ryan (M) | p254, Surrey | p326, Sydney | p298, Tipperary | p281, Edinburgh | p302, Montreal |
| Alan (M) | own voice | p374, Australia | p364, Donegal | p272, Edinburgh | p363, Toronto |
| Lessac (M) | p226, Surrey | none | p245, Dublin | p246, Selkirk | p316, Alberta |

For the American style, only Alan needs a regional speaker: p311 (male, Iowa). The tests check every speaker against the corpus's own accent and gender table.

</details>

**What happens when a pair has no voice.** The interface never offers it, and the server refuses it:

- On the practice screen and the profile, a companion or style that cannot go with the current choice is **dimmed**, and the hover text explains why and who *does* have the voice ("Amy doesn't have an Australian voice yet. Ryan and Alan do.").
- `POST /api/conversation/start` and `PATCH /api/auth/profile` answer `400` with the same explanation.
- A profile saved before this rule existed, with a pair nobody can speak, starts in Standard English and the profile page says so.
- If the accent models are not installed on the server, the styles that need them simply do not appear; Standard English always works.

**Loading.** Each accent model is loaded the first time a session needs it (about four seconds, in the background while the session starts), so the first reply is not slow. See [Performance and limits](#performance-and-limits) for the memory cost.

> **Honest caveat.** The speakers were chosen from the corpus's own labels and checked to be intelligible (speak a line, transcribe it back), but no native speaker has judged how convincing each one sounds. See [Known limitations](#known-limitations).

### Scenarios

A scenario is the situation the coach plays. It is independent of the companion and the style.

| Scenario | What the coach does |
|---|---|
| **Casual Conversation** | A warm, relaxed chat about your day, hobbies and opinions; short turns |
| **Job Interview Practice** | A friendly but professional interviewer: strengths, weaknesses, experience, motivation; questions get gradually harder |
| **Travel English** | Airport, hotel, restaurant, directions and bookings; the coach plays staff and locals |
| **Debate** | Takes a side respectfully, challenges your arguments, asks for evidence, offers counter-points |
| **University Seminar** | Seminar discussion, study group, office hours; academic vocabulary; asks you to explain and present ideas |
| **Café / Ordering** | A busy barista or waiter: orders, sizes, milk, "for here or to go", things being out of stock; fast and natural |
| **Phone Call** | No visual cues: spelling names, repeating numbers, confirming details, occasionally asking you to repeat, as on a slightly bad line |

### Difficulty levels

How demanding the coach's questions are, in five levels:

| Level | Label | Example question |
|---|---|---|
| 1 | Beginner | "What did you do today?" |
| 2 | Elementary | "What was the most interesting part of your day?" |
| 3 | Intermediate | "Do you prefer working alone or in a team? Why?" |
| 4 | Upper-Intermediate | "What do you think are the most important skills for success today?" |
| 5 | Advanced | "Do you think AI will fundamentally change how humans learn languages? Defend your view." |

**Automatic by default.** The average overall score of your last three scored sessions maps to a level (90 and above: Advanced; 78 and above: Upper-Intermediate; 65 and above: Intermediate; 50 and above: Elementary; below 50: Beginner), but the level moves **at most one step per scored session**, so one lucky or terrible session never lurches the conversation. New learners start at Elementary.

**Or pin it.** Choose a level on the profile page and it always wins. Switch back to *Automatic* at any time.

A session's level is fixed when it starts and is recorded with it, so history and reports show the level each session ran at. See [Adaptive difficulty, replayed from history](#adaptive-difficulty-replayed-from-history) for how it is computed.

### Instant feedback: corrections, suggestions and praise

While the coach is still speaking, a second model call reads what you said and returns up to five items of three kinds:

| Kind | Meaning | How it looks |
|---|---|---|
| **Mistake** | Something is wrong | Your words struck through, then the better wording, then the reason |
| **Suggestion** | Correct, but a fluent speaker would say it differently | Labelled "Suggestion", same layout |
| **Praise** | You used something genuinely natural or advanced, correctly | "Nice · Idiom" with the expression and what it means |

Every item belongs to one of **three categories** and one of **33 labelled subtypes**, so that "you keep getting the past tense wrong" can be counted across sessions:

<details>
<summary><strong>All the kinds of feedback</strong></summary>

| Category | Subtypes |
|---|---|
| **Grammar** (mistakes) | Past tense, Present perfect, Verb tense, Subject-verb agreement, Articles (a, an, the), Prepositions, Plurals, Word order, Pronouns, Modal verbs, Conditionals, Comparatives, Gerunds and infinitives, Countable / uncountable nouns, Forming questions, Negatives, Other |
| **Vocabulary** (mistakes) | Wrong word, Word partnerships (collocations), Word form, False friend, Formal vs casual, Other |
| **Naturalness** (suggestions) | More natural phrasing, Stronger vocabulary, Overused words, A more advanced way to say it, Filler words |
| **Naturalness** (praise) | Idiom, Phrasal verb, Natural word pairing, Well-built sentence |
| **Naturalness** (catch-all) | Naturalness |

</details>

**How the output is kept honest.** The model's answer is treated as untrusted input:

- each item is validated on its own, so one malformed entry cannot discard the batch;
- subtypes are mapped onto the fixed list (synonyms such as `simple_past` become `past_tense`; anything unknown becomes the category's catch-all) so they are countable;
- an item whose quoted words are **not actually in your transcript** is dropped, because a model that "corrects" words you never said is worse than no model;
- "corrections" that change nothing (a comma swapped for a semicolon) are dropped, as is praise that points at a whole sentence instead of an expression;
- duplicates are removed, and the result is capped at **five items**: mistakes first, then at most two suggestions and two pieces of praise;
- punctuation, capitalisation and spelling are never mentioned (they are artefacts of transcription), and contractions and "gonna" are not mistakes;
- a **severity** (high, medium, low) weights each mistake in your scores.

Transcripts shorter than five characters are not analysed. The analysis is told which speaking style you are practising, so that style's normal wording should not be reported as an error.

### How you spoke: fluency and clarity

Under each of your bubbles, AURA shows how you spoke, computed from the recogniser's word timings and confidences. Both are explained in plain words, and hovering a chip shows what it means.

**Fluency** (0 to 100) is built from four things:

| Measure | What counts |
|---|---|
| **Speaking rate** | Words per minute across the time you were actually talking (learners do best around 100 to 180) |
| **Pauses** | A gap of at least 0.5 seconds *in the middle of a thought*; 1.5 seconds or more is a long pause. A gap after a full stop is just a breath, and a short gap after a comma is normal phrasing, so neither is penalised. |
| **Fillers** | "um", "uh", "er", "hmm", and discourse fillers such as "you know", "I mean", "kind of", "sort of", "like", "basically". *like*, *you know* and *kind of* are ordinary words too, so they only count when you set them off with commas. |
| **Repetitions** | A word said twice in a row ("I I went"), except legitimate doubles such as "had had" or "that that" |

The score starts at 100 and subtracts for each problem, with every deduction capped so one bad habit cannot zero it:

| Deduction | Amount |
|---|---|
| Rate below 60 / 80 / 100 words per minute | -25 / -20 / -8 |
| Rate above 180 / 200 words per minute | -3 / -10 |
| Each pause (up to -20), each long pause (up to -12) | -3, -4 |
| Each filler (up to -25) | -4 |
| Each repetition (up to -10) | -2 |
| Under 10 words (too little speech to judge) | -15 |

**A filler count needs a recogniser that keeps fillers.** The local `base.en` model *drops* "um" and "uh". When that is the case the interface shows an asterisk ("1 filler\*") with an explanation instead of a false "0 fillers". Setting `STT_PROVIDER=groq` keeps them.

**Clarity** (0 to 100) is how confidently speech recognition identified your words. When pronunciation is unclear, the audio is muffled, or you said a different word than you meant, the recogniser's per-word confidence drops on exactly those words. It is a useful pointer to words worth practising, and it is **not** phoneme-level pronunciation scoring: a low score can also mean background noise or a rare word, and a high one does not prove native-like sounds. The score is 60% average confidence plus 40% share of words recognised confidently (80% or more). With the hosted recogniser, which gives no per-word confidence, a rougher whole-turn estimate is used and marked with an asterisk.

**"Hard to catch" words.** Up to five words per turn that were recognised with less than 80% confidence (at least three letters long; very common function words such as "the" or "would" are left out) are listed with their confidence and two buttons: **hear** and **slow**.

### Hear a word again

The *hear* and *slow* buttons next to a hard-to-catch word (and next to the practice words in a report) play that single word in the companion's voice, at normal pace or stretched to about 1.7 times its length. The word is spoken **in the session's accent**: a Scottish session plays the word in the Scottish speaker's voice. If the companion has no voice for that accent, the word is played in their own voice. Behind it, `POST /api/speech/word` accepts a single word (letters, apostrophes and hyphens), is rate-limited, and is cached.

### Session reports

Every finished session gets a report, written automatically in the background. It contains:

- **An overall score** shown as a ring, with the session's scenario, style and level.
- **A short note from your coach** (two sentences, written by the LLM; if that call fails the note is simply left out and the rest of the report is unaffected).
- **Five scores**, each with a hover explanation: Grammar, Vocabulary, Fluency, Clarity, Naturalness.
- **What went well** (up to three), for example "Good use of idiom: "a piece of cake"", "A comfortable speaking pace (126 words per minute)" or "No grammar or vocabulary mistakes this session".
- **Work on next** (up to three), for example "Past tense — 2 mistakes (e.g. "I go" → "I went")", "Cut down on filler words (um ×3)", "Practise saying: library, comfortable".
- **Most common mistakes** (up to five), each with how many times and one before/after example.
- **Words to practise**, with hear and slow buttons.
- **Facts**: turns, words spoken, length, words per minute, praise received.

The scores are **deterministic formulas**, not LLM opinions (only the short note is written by the model): the same session always scores the same.

| Score | How it is computed |
|---|---|
| **Grammar** | 100 minus 4 points per *weighted* grammar mistake per 100 words |
| **Vocabulary** | 100 minus 5 points per weighted vocabulary mistake per 100 words |
| **Naturalness** | Starts at 90, minus 3 per suggestion per 100 words, plus 5 per piece of praise (at most +20) |
| **Fluency** | The mean of the per-turn fluency scores |
| **Clarity** | The mean of the per-turn clarity scores |
| **Overall** | A weighted mean of the scores that have evidence: Grammar 30%, Fluency 25%, Vocabulary 15%, Clarity 15%, Naturalness 15% |

Mistakes are weighted by severity (high 1.5, medium 1.0, low 0.5). A density is never computed over fewer than 15 words, so a very short answer cannot swing a score wildly. A dimension with no evidence is blank rather than 100, and the overall score averages only what exists. Each report records the **scoring version** it was computed with, so if a formula ever changes, old reports can be recognised and recomputed instead of silently mixing two meanings of "grammar 82".

**Timing.** Right after you end a session the report can be "still being written" for a few seconds, because it waits (up to 25 seconds) for the analysis of your last answer, so those mistakes are in the score. The report page shows "Finishing the analysis of your last answer..." and checks again every two seconds for up to a minute. Sessions that ended before reports existed are reported on the first time they are opened.

### Speech history

`/history` lists every past session, newest first, 20 per page: the companion's face, the scenario and style, the date, the level, "unfinished" for sessions that were never ended, and figures for turns, score, fixes, fluency, clarity and length. A strip at the top totals the sessions, turns, corrections and time.

Opening a session (`/history/[id]`) shows the full transcript with each of your turns' speech chips and its corrections laid out beneath it, plus a link to the report. A session that was never finished instead shows a banner with a **Finish session** button: ending a session is what gives it a score and a report, and nothing else in the app can end it later. (The server closes it where you stopped talking, so the time it sat open is not counted.) Another learner's session is reported as "not found" (never "forbidden"), so ids cannot be probed.

### Progress

`/progress` turns your reports into a picture of improvement:

- **Totals**: sessions, practice time, best score.
- **Streak**: consecutive days with at least one session, with a seven-day strip and your best streak. The streak stays alive through the current day (it only breaks once a whole day is missed), so opening the page in the morning never shows a discouraging zero.
- **Scores by week**: a line chart of the last 12 weeks (the API supports 4 to 52), with each of the six scores switchable on and off. Empty weeks are shown as honest gaps.
- **Worth celebrating**: up to four milestones, most notable first: a dimension that improved by at least five points between your first three and your latest three sessions (needs at least four sessions); streaks of 3, 7, 14, 30, 60 and 100 days; a new personal best; practice time of 1, 5, 10, 25, 50 and 100 hours; sessions completed at 1, 10, 25, 50 and 100.
- **Your focus areas**: your five most frequent mistake kinds, newest habits weighted highest, each with a trend (*New*, *Improving*, *Steady*, *Slipping*) and a **Practise** link that starts a session steered at it.
- **Recent sessions**: the last eight, each linking to its report.

**Days and weeks are yours, not the server's.** The page sends your UTC offset, so practising at 11:30 pm in Colombo is still "today" there even when it is already tomorrow in UTC, and weeks start on Monday.

### Weak spots and daily practice

AURA remembers *what* you get wrong, not just how many mistakes you make.

- Every mistake (not suggestions, not praise) is counted by kind, across all sessions, and ranked: a mistake from the last 30 days counts three times as much as an older one.
- **Trend.** The last 30 days are compared with the 30 days before, **per session**, not per month. Counting per month would punish you for practising more (twice the sessions, twice the mistakes, "worsening!"). A kind is *Improving* when its recent rate is under 60% of the earlier rate, *Slipping* when it is over 140%, *New* when it first appeared in the last 30 days, and *Steady* otherwise. Fewer than two mistakes in a window is too little to call.
- **Today's practice** appears on the practice screen: your top weakness that is still live (it appeared in the last 30 days; the catch-all "Other" bucket is never used), with a plain reason ("3 past tense mistakes in the last 30 days — and improving. Keep it up."), and a *Practise this* button. If you have no history yet it says "Get to know your coach".
- **Practise this** selects that focus and the scenario where the habit comes up most naturally. The coach then steers the conversation through its *own questions and topics* (for the past tense it asks about yesterday, last weekend, a past trip) and **never announces it**, never names a grammar point and never quizzes you. The focus applies to one session only.

The weakness table is a cache: it is rebuilt from your corrections whenever it is missing or older than an hour, so it can never drift from the evidence.

### Profile and account settings

`/profile` has seven cards:

1. **Identity**: your profile photo (JPEG, PNG or WebP up to 5 MB, stored on Cloudinary as a 256 × 256 face-aware crop; replacing it overwrites the old one). Photo upload needs Cloudinary to be configured on the server; without it the feature is off.
2. **Personal info**: display name (up to 100 characters) and a short bio (up to 300).
3. **Companions**: your default companion and speaking style, with the accent rules and the voice credits.
4. **Difficulty**: Automatic or a pinned level, with how the current level was decided.
5. **Security**: set a password (Google-only accounts) or change it (asks for the current one; ends every other session and keeps this one signed in).
6. **Connected accounts**: connect or disconnect Google. Disconnecting is refused until a password is set, so you can never lock yourself out.
7. **Danger zone**: permanently delete the account.

### Looks and accessibility

- **Light and dark themes.** A toggle in the sidebar and on the landing page. Until you choose, AURA follows your operating system; the choice is applied before the page paints, so there is no flash of the wrong theme.
- **Responsive layout.** On phones and tablets the sidebar becomes a slide-in drawer with a top bar. While it is closed its links cannot be reached with Tab; open, it takes focus, closes on Escape, on a tap outside or on any link, and hands focus back to the menu button, and the page behind it is made inert.
- **Keyboard.** Everything can be used without a mouse, including the talk button (hold Space or Enter, or switch to tap-to-talk). The sidebar marks the current page (`aria-current`), and every page has its own tab title.
- **Screen readers.** The phase of the session ("Listening...", "Amy is thinking...") and the corrections status are live regions, and what the recogniser heard you say is announced. The coach's reply is deliberately not read out as text, because it is spoken aloud. Selectable chips expose their pressed state, avatars and sprites carry text labels, errors use alert and status regions, and unavailable choices explain themselves in written text, not only by being greyed out or in a tooltip.
- **Reduced motion.** Parallax, the login card's tilt, the idle waveform, the poses' crossfades and smooth scrolling all switch off when your system asks for reduced motion. (A live microphone or voice level keeps moving: it is information, not decoration.)
- **Contrast.** The palette was checked by calculation against WCAG AA: text against each surface it sits on (4.5:1) and the chart lines against the panel (3:1), in both themes. The colours are tokens in `app/globals.css`.

An automated axe scan (`e2e/accessibility.spec.js`) fails on any accessibility problem of moderate or worse impact on every page; that is a floor, not an audit. AURA has not been audited against WCAG by a person or tested with a screen reader, and recording has only been exercised in Chrome (see [Known limitations](#known-limitations)).

### Tools for developers and operators

| Tool | What it does |
|---|---|
| `local_client.py` | A **terminal** version of the conversation: microphone in, speakers out, Silero voice-activity detection for hands-free turn-taking, latency numbers printed for every stage. Needs `backend/requirements-local.txt`. |
| `check_setup.py` | "Is my machine set up correctly?": packages, `.env`, database and migrations, all eight voice models, and (optionally) a tiny Groq request. |
| `scripts/download_voices.py` | Downloads exactly the voice models the app uses (read from `personalities.py`), skips ones already complete, and never leaves a half-downloaded file in place. `--check` only reports. |
| `scripts/loadtest_voice.py` | Measures the voice loop's latency, alone and with several simultaneous learners, on the machine you deploy to. |
| `scripts/smoke_container.py` | Starts the real Docker image against a throwaway database and checks migrations, model loading, a real transcription, a spoken word, accent voices, rate limits behind a proxy and the image's own health check. |
| `GET /health` | Fast health check (database, schema version, speech models); answers `503` when the app cannot do its job. `?full=true` also pings Groq. |
| Startup self-check | Outside development, the server logs a production checklist (secrets, URLs, email, photo storage, rate limits) at start-up. |

---

## How the system works

### The big picture

```mermaid
flowchart LR
    B["Browser: Next.js 16 and React 19"]
    A["FastAPI backend: one worker"]

    B -->|"REST with a JWT, and the recording"| A
    A -->|"NDJSON stream: transcript, metrics, audio chunks"| B

    A --> S["Speech to text: faster-whisper, or Groq Whisper"]
    A --> L["LLM client: Groq gpt-oss models"]
    A --> T["Text to speech: Piper, 8 voice models"]
    A --> J["Background work: feedback analysis and reports"]
    J --> L
    A --> D[("PostgreSQL 16")]
    J --> D
    A -.-> X["Resend email, Cloudinary photos, Google sign-in, Sentry"]
```

| Component | Responsibility | Where |
|---|---|---|
| **Web app** | Pages, recording, ordered audio playback, the cached signed-in user | `Aurora/frontend` (`app/`, `components/`, `lib/`) |
| **API** | Routing, authentication, validation, rate limits, the streamed voice endpoint | `Aurora/backend/main.py`, `routers/` |
| **Speech to text** | Transcript with word timings and confidences | `services/stt.py` |
| **LLM client** | Every call to Groq goes through one wrapper | `services/llm.py` |
| **Text to speech** | Piper voices, multi-speaker accent models, sentence splitting | `services/tts.py` |
| **Analysis** | Turns one transcript into validated mistakes, suggestions and praise | `services/analysis.py`, `taxonomy.py` |
| **Scoring** | Pure, unit-tested functions: fluency, clarity, report scores, difficulty, progress, weaknesses | `services/fluency.py`, `clarity.py`, `scoring.py`, `difficulty.py`, `progress.py`, `weaknesses.py` |
| **Reports** | Builds and stores one report per finished session | `services/reports.py` |
| **Personalities** | Companions, speaking styles, accent voices, scenarios, difficulty prompts, the system prompt | `personalities.py` |
| **Persistence** | SQLAlchemy models, Alembic migrations, the startup schema check | `models/`, `alembic/`, `migrations_check.py` |

### One spoken turn, step by step

```mermaid
sequenceDiagram
    autonumber
    actor L as Learner
    participant B as Browser
    participant A as FastAPI
    participant S as Whisper (STT)
    participant D as PostgreSQL
    participant G as Groq LLM
    participant P as Piper (TTS)

    L->>B: hold the mic, speak, release
    B->>A: POST /api/conversation/message-stream (audio)
    A->>S: transcribe (word timings and confidence)
    S-->>A: text, words, average log-probability
    A->>D: save the turn with its fluency and clarity
    A-->>B: event: transcript
    A-->>B: event: metrics
    par Path B: analysis in the background
        A->>G: find mistakes, suggestions and praise (JSON mode)
        G-->>A: items (validated and cleaned)
        A->>D: save corrections
        B->>A: GET /api/analysis/.../recent (polling)
        A-->>B: corrections and how many turns are still pending
    and Path A: the spoken reply
        A->>G: stream the coach's reply (system prompt and the last 20 messages)
        loop for every finished sentence
            G-->>A: tokens
            A->>P: synthesise the sentence
            P-->>A: WAV audio
            A-->>B: event: audio_chunk
            B->>L: play it while the rest is still being written
        end
    end
    A->>D: save the reply
    A-->>B: event: done (timings)
```

1. **Record.** The browser records with `MediaRecorder` (WebM/Opus, or Ogg/Opus on Firefox) while you hold the button and posts the file, with the session id, to `POST /api/conversation/message-stream` along with your token.
2. **Gate.** The server checks the per-learner rate limit (30 turns a minute), that the session is yours (someone else's is a `404`) and still open (an ended one is `409`), copies the upload to a temporary file while enforcing the size cap, and **releases its database connection** before the long work starts, so a handful of slow turns cannot exhaust the connection pool.
3. **Transcribe.** Speech to text runs in a worker thread and returns the text, every word with its start, end and confidence, the audio duration and the average log-probability. Failures end the turn cleanly (see [Concurrency and reliability](#concurrency-and-reliability)).
4. **Measure and save.** Fluency and clarity are computed by pure functions, the turn is saved with its metrics, and the `transcript` and `metrics` events are sent immediately, so your words appear before the coach has said anything.
5. **Analyse (Path B).** If the transcript is at least five characters, the analysis starts at once *in parallel* with the reply, as a task that outlives the request (FastAPI's own background tasks would only start after the response finished, so feedback would arrive a turn late).
6. **Build the prompt.** Coaching rules, the scenario, the speaking style (plus its guardrails), the difficulty, and, if you chose today's practice, a hidden focus, followed by the last 20 messages.
7. **Stream the reply (Path A).** Groq's tokens are read in their own thread and handed to the event loop through a queue (so waiting for the next token never occupies a thread-pool worker). Text is cut into sentences: a hard stop (`.`, `!`, `?`) ends a chunk once it is long enough (18 characters for the *first* chunk, which the learner waits for in silence; 45 for later ones, which gives better prosody), and a comma only splits a sentence that has run past 120 characters. Each sentence is synthesised by Piper in a worker thread and sent as an `audio_chunk` event.
8. **Play.** The browser queues the chunks and plays them strictly in order through the Web Audio API while later sentences are still being written.
9. **Finish.** The reply is saved and a `done` event carries the timings.

**The stream protocol.** The response is newline-delimited JSON (`application/x-ndjson`). Every code path ends with a `done` line, so the client can never hang.

| Event | Fields | Meaning |
|---|---|---|
| `transcript` | `text`, `message_id` | What the recogniser heard |
| `metrics` | `message_id`, `fluency`, `clarity` | How you spoke (either may be `null`) |
| `audio_chunk` | `index`, `text`, `data` (base64 WAV), `tts_ms` | One spoken sentence |
| `warning` | `message` | Non-fatal, e.g. one sentence could not be spoken (its text is still shown) |
| `error` | `message` | Something failed; a `done` always follows |
| `done` | `full_reply`, `timings` (`stt_ms`, `llm_ttfs_ms`, `first_audio_ms`, `total_ms`) | The turn is over |

### The two-pipeline idea

Path A has to be fast; Path B can take as long as it needs. Combining them into one LLM call would make the reply slow, break the flow of the conversation, and make it impossible to improve the analysis without touching the conversation. Splitting them also lets each use the model that suits it (the two models are configured separately), and lets the analysis **retry rate limits patiently** (up to five times, honouring the provider's `Retry-After`) where a live reply fails fast with a friendly message. The learner sees the effect directly: the reply starts while "Analysing..." is still showing, and the corrections arrive a few seconds later.

### Turning feedback into scores

```mermaid
flowchart TD
    subgraph Turn["Every spoken turn"]
        W["Word timings and confidence from the recogniser"]
        W --> F["Fluency: pace, pauses, fillers, repeats, 0 to 100"]
        W --> C["Clarity: recogniser confidence, 0 to 100"]
        T["Transcript"] --> AN["LLM analysis: mistakes, suggestions, praise"]
    end
    subgraph Session["When the session ends"]
        F --> M1["Fluency score: mean of the turns"]
        C --> M2["Clarity score: mean of the turns"]
        AN --> G["Grammar and vocabulary: weighted mistakes per 100 words"]
        AN --> N["Naturalness: suggestions lower it, praise raises it"]
        M1 --> O["Overall: weighted mean of the scores that have evidence"]
        M2 --> O
        G --> O
        N --> O
    end
    O --> R["Session report"]
    R --> PR["Progress charts, streaks and milestones"]
    R --> DI["The next session's difficulty"]
    AN --> WK["Weak-spot profile and today's practice"]
```

The exact formulas are in [How you spoke](#how-you-spoke-fluency-and-clarity) and [Session reports](#session-reports). The fluency, clarity, scoring, difficulty, progress and weak-spot boxes are **pure functions** (no database, network or clock: even "now" is passed in), which is why they are tested directly and cheaply. Only the LLM analysis is not, and it has its own live regression suite.

### Adaptive difficulty, replayed from history

The automatic level is **derived, not stored**. To find it, AURA replays your finished, scored sessions from oldest to newest, starting at the default level. After each session the level takes *one step* toward what the average of your last three scores says.

Worked example, with overall scores 60, 72, 80, 88 (oldest first):

| After session | Scores in the window | Average | The level they point to | Level now |
|---|---|---|---|---|
| 1 | 60 | 60 | Elementary (2) | 2 Elementary |
| 2 | 60, 72 | 66 | Intermediate (3) | 3 Intermediate |
| 3 | 60, 72, 80 | 71 | Intermediate (3) | 3 Intermediate |
| 4 | 72, 80, 88 | 80 | Upper-Intermediate (4) | 4 Upper-Intermediate |

Because it is replayed rather than nudged, it is deterministic, immune to abandoned sessions (*starting* a session moves nothing; *finishing a scored one* does), and can never drift out of step with the reports it comes from. Sessions are ordered by when they *ended*, so a report back-filled later for an old session is never mistaken for recent performance. A level you pin on your profile always wins.

### Weak spots and trends

```text
corrections  ->  mistakes only (not suggestions, not praise)
             ->  grouped by kind, counted all-time / last 30 days / the 30 days before
             ->  priority = 3 x recent + older
             ->  trend from mistakes PER SESSION (so practising more never looks like "worsening")
             ->  stored in user_weaknesses (a cache: rebuilt when missing or older than an hour)
             ->  today's practice = the top weakness that is still live
             ->  a hidden focus instruction in the next session's system prompt
```

### Accounts and sessions

Every authenticated route depends on one function, `get_current_user`, so identity always comes from a **verified token**, never from request data (an earlier design accepted a `user_id` form field; that hole was closed).

- **Tokens.** A signed JWT (`sub` is the user id, `tv` the token version). A token is valid only if its signature is good, it has not expired, **and** its version matches the account's current `token_version`. Changing or resetting a password increments the version, which ends every other session instantly.
- **Short-lived, single-purpose tokens** carry a credential for exactly one step without putting a session token in a URL (where it would land in browser history, server logs and referrers). They carry a `purpose` claim, can never act as a session, and the exchange code can be used once.
- **Passwords** are pre-hashed (SHA-256, base64) and then bcrypt-hashed (12 rounds). The pre-hash removes bcrypt's 72-byte limit and its null-byte truncation, so long passphrases stay fully significant. One-time codes are hashed the same way.
- **Uniform behaviour.** A wrong password, an unknown email and a Google-only account all cost the same bcrypt work and return the same error; "forgot password" always answers `204`; the reset-code check gives one generic failure for every reason.

```mermaid
sequenceDiagram
    participant B as Browser
    participant A as AURA API
    participant G as Google
    B->>A: GET /api/auth/google
    A-->>B: redirect to Google (CSRF state in a short-lived cookie)
    B->>G: consent screen
    G-->>B: redirect to /api/auth/google/callback with a code
    B->>A: callback (the state must match the cookie)
    A->>G: exchange the code and read the profile (the email must be verified)
    A-->>B: redirect to the web app with a single-use code (valid 2 minutes)
    B->>A: POST /api/auth/google/exchange
    A-->>B: session token (JWT)
```

### Accents: from a style to a voice

```mermaid
flowchart TD
    A["Companion and speaking style"] --> B{"Does the style have an accent?"}
    B -->|"no, it is Standard English"| OWN["The companion's own voice"]
    B -->|"yes"| C{"Is it the companion's home accent?"}
    C -->|"yes"| OWN
    C -->|"no"| D{"Is there a speaker for this pair?"}
    D -->|"yes"| SPK["A regional speaker of the same gender, from VCTK or Alba"]
    D -->|"no"| NO["The pair is not offered, and the API answers 400"]
```

The mapping lives in one table, `ACCENT_VOICES` in `personalities.py`, and one function, `voice_for(companion, style)`. A multi-speaker Piper model holds many voices, so a speaker is chosen **by name** from the model's own speaker map at synthesis time. Models are cached by file (one VCTK model serves many speakers) and loaded lazily; the server pre-warms only the six companions' own voices at start-up. If a needed model, or a needed speaker inside it, is missing, the pair is reported as unavailable with a reason instead of failing mid-conversation.

### Data model

```mermaid
erDiagram
    USERS ||--o{ CONVERSATIONS : "practises in"
    USERS ||--o{ CORRECTIONS : "receives"
    USERS ||--o{ SESSION_REPORTS : "earns"
    USERS ||--o{ USER_WEAKNESSES : "has"
    CONVERSATIONS ||--o{ MESSAGES : "contains"
    CONVERSATIONS ||--o| SESSION_REPORTS : "is summarised by"
    MESSAGES ||--o{ CORRECTIONS : "gets feedback"
    MESSAGES ||--o| FLUENCY_SCORES : "is measured by"
    MESSAGES ||--o| CLARITY_SCORES : "is measured by"
    FLUENCY_SCORES ||--o{ FLUENCY_EVENTS : "lists"

    USERS {
        string id PK
        string email UK
        string display_name
        string password_hash "null for Google-only accounts"
        string google_id UK
        bool email_verified
        int token_version "bumped to revoke every session"
        string preferred_voice
        string preferred_style
        int difficulty_override "null means automatic"
    }
    CONVERSATIONS {
        string id PK
        string user_id FK
        string scenario
        string style
        string voice
        int difficulty "fixed when the session starts"
        string focus "hidden practice focus"
        int overall_score
        bool is_complete
        datetime started_at
        datetime ended_at
    }
    MESSAGES {
        string id PK
        string conversation_id FK
        string role "user or assistant"
        text content
        float audio_duration_seconds
        text word_timestamps_json
        float whisper_avg_logprob
        string analysis_status "pending, done, failed or skipped"
    }
    CORRECTIONS {
        string id PK
        string message_id FK
        string category "grammar, vocabulary or naturalness"
        string subtype
        text original
        text correction
        text explanation
        bool is_error
        bool is_positive
        string severity
    }
    FLUENCY_SCORES {
        string id PK
        string message_id FK
        int score
        float wpm
        int pause_count
        int filler_count
        int repetition_count
        bool hesitations_tracked
    }
    FLUENCY_EVENTS {
        string id PK
        string fluency_score_id FK
        string kind "pause, long_pause, filler or repetition"
        float start_seconds
        float end_seconds
    }
    CLARITY_SCORES {
        string id PK
        string message_id FK
        int score
        bool word_level
        json unclear_words
    }
    SESSION_REPORTS {
        string id PK
        string conversation_id FK, UK
        int scoring_version
        int overall_score
        int grammar_score
        int vocabulary_score
        int fluency_score
        int clarity_score
        int naturalness_score
        json strengths
        json improvements
        json top_errors
        text summary
    }
    USER_WEAKNESSES {
        string id PK
        string user_id FK
        string category
        string subtype
        int occurrence_count
        int recent_count
        float priority
        string trend "new, improving, stable or worsening"
    }
```

| Table | What it holds |
|---|---|
| `users` | Accounts, preferences, one-time-code state, the token version |
| `conversations` | One practice session: scenario, style, companion, the level it ran at, its focus, its score |
| `messages` | Each turn, with the raw speech metadata (word timings, recogniser confidence) and the analysis status |
| `corrections` | Mistakes, suggestions and praise attached to a user turn |
| `fluency_scores`, `fluency_events` | Per-turn fluency, and every individual pause, filler and repetition with its timestamp |
| `clarity_scores` | Per-turn clarity and the least clearly recognised words |
| `session_reports` | One report per finished session, with the scoring version it used (the conversation id is unique) |
| `user_weaknesses` | The weak-spot cache, rebuilt from `corrections` |

Deleting a user cascades through every table, in the database itself (`ON DELETE CASCADE`), so removing an account stays cheap however long the history is. **Audio is not stored**: only transcripts, timings and feedback.

### Concurrency and reliability

- **Blocking work stays off the event loop.** Speech recognition, synthesis and avatar uploads run in worker threads; the LLM stream runs in its own thread and talks to the loop through an `asyncio.Queue`.
- **One worker, by design.** Whisper and the Piper voices live in memory once, and the rate limiter is in-process. To scale out, run one worker per instance and move the limiter to Redis first.
- **Every path ends.** STT failure, no speech, a recording that is too long, TTS failing for one sentence, an LLM that stalls for 30 seconds or is rate-limited, a client that disconnects mid-stream: each yields a clear event, always followed by `done`; the temporary audio file is deleted on every path.
- **Generation takes turns.** Two things can try to write the same session report at once (the end-of-session task and you opening the page). Inside the process they take turns, so the second one finds the first one's report instead of paying for a second LLM note, and a unique key on the report is the net underneath for anything else.
- **The schema is checked at start-up.** In development a mismatch with the code is a loud error; elsewhere the process **refuses to start**, so a bad deploy fails at once rather than on a learner's request.
- **Health is honest.** `/health` answers `503` when the database is down, the schema is behind, or no voice is installed. Its body names only the *kind* of error, never its text (which could carry hostnames or account details).

---

## Tech stack

| Layer | Technology | Role |
|---|---|---|
| **Backend** | Python 3.14, **FastAPI** 0.141, Uvicorn 0.52, Starlette, Pydantic 2 | HTTP API, validation, the streamed voice endpoint |
| **Database** | **PostgreSQL 16**, SQLAlchemy 2, Alembic, psycopg2 | Persistence; schema changes only through migrations |
| **Speech to text** | **faster-whisper** 1.2 (CTranslate2, `base.en`, CPU int8) or **Groq-hosted Whisper** (`whisper-large-v3-turbo`), PyAV 18 | Transcript with word timings and confidences |
| **Language model** | **Groq**-hosted open-weight models: `openai/gpt-oss-120b` (the default for the coach and the analysis) and `openai/gpt-oss-20b`; Llama models also work | The coach's replies, the feedback analysis, the report note |
| **Text to speech** | **Piper** 1.8 on ONNX Runtime; 6 companion voices plus 2 accent models (CSTR VCTK and Alba) | Neural voices, run locally |
| **Auth** | python-jose (JWT, HS256), bcrypt, Google OAuth 2.0 | Sessions, passwords, social sign-in |
| **Frontend** | **Next.js 16** (App Router, Turbopack), **React 19**, **Tailwind CSS 4**, plain JavaScript (no TypeScript) | The web app |
| **Browser APIs** | MediaRecorder, Web Audio API | Hold-to-talk recording, ordered playback, live waveform |
| **Charts, art and type** | A hand-written SVG line chart; WebP artwork generated by a build script (`sharp`); Playfair Display and Plus Jakarta Sans fetched at build time by `next/font` and served from your own host | No charting or UI library, and no runtime requests to a font CDN |
| **Services** | Resend (email), Cloudinary (profile photos), Sentry (optional error tracking) | Each optional and off when not configured |
| **Quality** | pytest 9, Node's built-in test runner, Playwright (Chrome) with axe-core, ESLint 9, GitHub Actions | Offline suite, frontend unit tests, browser tests and accessibility scans, lint, CI |
| **Packaging** | Docker (python:3.14-slim, non-root), docker-compose for local PostgreSQL | One image with code, voices and the Whisper model baked in |

Why these choices, in short:

- **FastAPI** gives streaming responses, dependency injection for the single authentication gate, and Pydantic validation with very little ceremony.
- **PostgreSQL and Alembic** because the data is relational and long-lived, and because "the app never creates tables itself" makes deploys safe and reviewable.
- **Whisper locally or hosted** because the trade-off is real (privacy and cost against accuracy and speed under load), so it is a setting, with measured numbers to decide by.
- **Piper** because neural voices that run on a CPU, with no per-character fee and no audio leaving the server, make a conversation loop affordable; its multi-speaker models are what make real regional accents possible.
- **Groq** because its latency is what makes a spoken conversation feel live, and open-weight models keep the choice of model open.
- **Plain JavaScript and no UI kit** keeps the frontend small and readable, and the dependency list short.

---

## Repository layout

```text
AI-Projects/                          (the repository)
├── README.md                         this file
├── .github/workflows/ci.yml          CI: backend tests on PostgreSQL; frontend lint, unit tests and build
└── Aurora/                           the AURA project
    ├── README.md                     operations guide: setup, configuration, STT choice, deploying
    ├── AURA_remaining_work_plan.md   test report, what was built, what was found
    ├── Dockerfile  .dockerignore     the backend image
    ├── docker-compose.yml            local PostgreSQL
    ├── .env.example                  every setting, documented
    ├── pytest.ini                    test configuration
    ├── check_setup.py                "is my machine set up correctly?"
    ├── local_client.py               optional terminal client (microphone and speakers)
    ├── main_prototype.py             the original single-file prototype (kept for history, not maintained)
    ├── backend/
    │   ├── main.py                   app wiring, startup checks, middleware, routers
    │   ├── config.py                 every environment variable, in one place
    │   ├── database.py               engine and session factory
    │   ├── dependencies.py           get_current_user, the single authentication gate
    │   ├── personalities.py          companions, styles, accent voices, scenarios, difficulty levels, system prompt
    │   ├── taxonomy.py               the kinds of feedback, and the practice focuses
    │   ├── production_checks.py      the start-up production checklist
    │   ├── migrations_check.py       compares the database revision with the code's
    │   ├── observability.py          optional Sentry set-up (sends no personal data)
    │   ├── logging_config.py  middleware.py
    │   ├── routers/                  health, auth, google, conversation, analysis, config,
    │   │                             history, practice, progress, speech
    │   ├── services/                 stt, tts, llm, analysis, turns, speech_metrics, fluency, clarity,
    │   │                             scoring, reports, progress, weaknesses, difficulty, ratelimit,
    │   │                             auth, google_oauth, upload, background
    │   ├── models/  schemas/         SQLAlchemy tables / Pydantic request and response shapes
    │   ├── alembic/                  database migrations (11 revisions)
    │   ├── tests/                    the pytest suite, plus regression/ for the live-LLM cases
    │   └── requirements*.txt         pinned runtime, development and terminal-client dependencies
    ├── frontend/
    │   ├── app/                      the routes: landing and auth pages, plus (app)/ for the signed-in ones
    │   │                             (practice, progress, history, report, profile), which share one layout
    │   │                             (login check + sidebar); not-found, error, opengraph-image
    │   ├── components/               UI pieces (AppShell and AppSidebar frame every signed-in page)
    │   ├── lib/                      api.js, auth.js, audioQueue.js, accents.js, characters.js, theme.js, wordAudio.js,
    │   │                             and the pure helpers with unit tests: format, ndjson, recording, redirects
    │   ├── hooks/                    motion hooks (pointer parallax, reduced motion) and media-query hooks
    │   ├── public/characters/        the companions' artwork: sprites, faces, scenes
    │   ├── aura-project-assets/      the source images the artwork is built from
    │   ├── e2e/                      Playwright tests (journey, lifecycle, accessibility, public, phone) and the speech fixture
    │   └── scripts/build-characters.cjs   rebuilds the artwork from the source images
    ├── scripts/                      download_voices.py, loadtest_voice.py, smoke_container.py
    └── voices/                       Piper models (downloaded; git-ignored)
```

---

## Getting started

### What you need

| Requirement | Notes |
|---|---|
| **Python 3.14** | What everything here is tested on (the dependency pins and CI use it) |
| **Node.js 22** | For the web app |
| **Docker** | Runs PostgreSQL locally (`docker compose`); also used to build the backend image |
| **A Groq API key** | Free at [console.groq.com](https://console.groq.com). The free tier is enough to try AURA (see [Performance and limits](#performance-and-limits)) |
| **Google Chrome** | The browser the app has been tested in (Firefox and Safari are not tested; see [Known limitations](#known-limitations)) |
| **About 700 MB of disk** | Eight voice models (about 550 MB) plus the Whisper model (about 150 MB, downloaded on first use) |
| *Optional* | A Resend key (email codes), Cloudinary credentials (profile photos), Google OAuth credentials (Google sign-in). Each feature is simply off when its settings are blank |

### Run it locally

From the repository root:

```bash
git clone https://github.com/Vihanga-Deemantha/AI-Projects.git
cd AI-Projects/Aurora
```

**1. PostgreSQL** on `localhost:5432`:

```bash
docker compose up -d
```

**2. Python environment and the voice models** (the voices are downloaded once and are git-ignored):

```bash
python -m venv venv
venv\Scripts\activate                 # macOS/Linux: source venv/bin/activate
pip install -r backend/requirements.txt
python scripts/download_voices.py     # eight Piper models, about 550 MB
```

**3. Configuration.** Copy the template, then set `GROQ_API_KEY` and `JWT_SECRET` (never commit `.env`):

```bash
cp .env.example .env                  # Windows: copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"      # paste the output as JWT_SECRET
```

**4. Create the tables, then check everything is in place:**

```bash
alembic -c backend/alembic.ini upgrade head
python check_setup.py
```

**5. Run the API** (http://localhost:8000, interactive docs at `/docs`):

```bash
uvicorn backend.main:app --reload
```

**6. In a second terminal, run the web app** (http://localhost:3000):

```bash
cd frontend
cp .env.local.example .env.local      # points the app at http://localhost:8000
npm install
npm run dev
```

**7. Use it.** Open http://localhost:3000, sign up, allow the microphone, hold the mic button and talk. In development, without a Resend key, the email verification code is printed in the API's log.

**First start.** The server loads Whisper and the six companion voices in the background (about 25 seconds; `/health` answers immediately and reports whether they are ready), and the very first run downloads the Whisper model from Hugging Face. The two accent voices load the first time a session needs them.

### Handy commands

| Task | Command (from `Aurora/` unless noted) |
|---|---|
| Start the database / stop it / wipe it | `docker compose up -d` / `docker compose down` / `docker compose down -v` |
| Run the API with auto-reload | `uvicorn backend.main:app --reload` |
| Check your set-up | `python check_setup.py` (add `--skip-groq` to avoid the one tiny Groq request) |
| Which voice models are installed? | `python scripts/download_voices.py --check` |
| Apply migrations / check for drift | `alembic -c backend/alembic.ini upgrade head` / `alembic -c backend/alembic.ini check` |
| Backend tests | `pip install -r backend/requirements-dev.txt`, then `pytest` |
| Live LLM regression (spends Groq quota) | `pytest -m llm` |
| Frontend lint, unit tests and production build (from `frontend/`) | `npm run lint`, `npm test` and `npm run build` |
| Browser tests (from `frontend/`; the whole stack must be running) | `npm run e2e` (everything), or one file, for example `npx playwright test e2e/public.spec.js --project=desktop` |
| Build and smoke-test the container | `docker build -t aura-backend .` then `python scripts/smoke_container.py` |
| Measure latency | `python scripts/loadtest_voice.py --users 1 3 --turns 2` |
| Talk from the terminal | `pip install -r backend/requirements-local.txt`, then `python local_client.py --email you@example.com --voice alan --style irish --scenario interview` |

---

## Configuration reference

Everything is read in `Aurora/backend/config.py` from environment variables or `.env`; `Aurora/.env.example` documents each one. **Never commit `.env`.** The three required settings make the server refuse to start when they are missing (for `JWT_SECRET` in particular, because a fallback secret would silently make every token forgeable).

<details>
<summary><strong>Backend settings</strong></summary>

| Variable | Default | What it does |
|---|---|---|
| `GROQ_API_KEY` | *required* | Groq API access (LLM, and Whisper if you choose it) |
| `DATABASE_URL` | *required* | `postgresql://user:password@host:5432/dbname` |
| `JWT_SECRET` | *required* | Signs login tokens. 32+ random characters; rotating it logs everyone out |
| `JWT_EXPIRE_MINUTES` | `10080` | Token lifetime (7 days) |
| `JWT_ALGORITHM` | `HS256` | Token signing algorithm |
| `BCRYPT_ROUNDS` | `12` | Password hash cost (clamped to 4 to 15; the tests use 4) |
| `ENVIRONMENT` | `development` | Anything else switches on production behaviour (schema mismatch refuses to start, the production checklist runs) |
| `LOG_LEVEL` / `SQL_ECHO` | `INFO` / off | `SQL_ECHO` logs every query, including emails and transcripts, so keep it off |
| `FRONTEND_URL` | `http://localhost:3000` | Where the web app lives: Google sign-in redirects here, and CORS always allows it |
| `CORS_ORIGINS` | *(empty)* | Extra allowed browser origins, comma-separated (for example preview URLs). In development the usual localhost origins are added automatically |
| `LLM_CONVERSATION_MODEL` | `openai/gpt-oss-120b` | The coach |
| `LLM_ANALYSIS_MODEL` | `openai/gpt-oss-120b` | Finds your mistakes (the larger model was clearly more reliable on the regression set) |
| `LLM_REASONING_EFFORT` | `low` | For the gpt-oss reasoning models; blank it for Llama models |
| `LLM_CONTEXT_MESSAGES` | `20` | How many recent messages the coach sees each turn |
| `LLM_ANALYSIS_RETRIES` | `5` | How many times the background analysis waits out a rate limit |
| `STT_PROVIDER` | `local` | `local` (faster-whisper) or `groq` (hosted Whisper), see [Performance and limits](#performance-and-limits) |
| `GROQ_STT_MODEL` | `whisper-large-v3-turbo` | Used when `STT_PROVIDER=groq` |
| `WHISPER_MODEL_SIZE` / `WHISPER_DEVICE` / `WHISPER_COMPUTE_TYPE` | `base.en` / `cpu` / `int8` | Used when `STT_PROVIDER=local` |
| `MAX_AUDIO_BYTES` / `MAX_AUDIO_SECONDS` | 5 MB / 120 | Per-turn limits |
| `RATE_LIMITS_ENABLED` | on | Limits on login, sign-up, codes, uploads and voice turns (in memory, per process) |
| `PREWARM_MODELS` | on | Load Whisper and the six companion voices at start-up instead of on first use (the two accent voices always load on first use) |
| `CHECK_MIGRATIONS_ON_STARTUP` | on | Compare the database's schema version with the code's |
| `VOICES_DIR` | `voices` | Where the Piper models live (relative to `Aurora/`) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | *(blank)* / *(blank)* / `http://localhost:8000/api/auth/google/callback` | Google sign-in; blank disables it |
| `RESEND_API_KEY` / `EMAIL_FROM` | *(blank)* / `noreply@aura.app` | Email codes. Without a key, development prints the code in the log |
| `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` | *(blank)* | Profile photos; blank disables uploads |
| `SENTRY_DSN` | *(blank)* | Error tracking with Sentry; sends no personal data, request bodies or local variables |
| `TEST_DATABASE_URL` | `postgresql://aura:aura_dev_pass@localhost:5432/aura_test` | **Tests only.** The suite never uses `DATABASE_URL`; the database name must end in `_test` |

</details>

<details>
<summary><strong>Frontend and container settings</strong></summary>

| Variable | Default | What it does |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | **Frontend.** Where the API is (set in `frontend/.env.local`, or at build time) |
| `NEXT_PUBLIC_SITE_URL` | `http://localhost:3000` | **Frontend.** The public address of the web app, which link previews (the card shown when the site is shared) are built from. Only matters once it is deployed |
| `E2E_BASE_URL` / `E2E_API_BASE` | `http://localhost:3000` / `http://localhost:8000` | **Browser tests.** Which stack the Playwright tests drive |
| `PORT` | `8000` | **Container.** The port uvicorn serves on |
| `RUN_MIGRATIONS` | `true` | **Container.** Apply migrations on start (set `false` when a release step migrates instead) |
| `FORWARDED_ALLOW_IPS` | `*` | **Container.** Trust `X-Forwarded-For` from the platform's proxy (see [Deployment](#deployment)) |
| Build args `BAKE_WHISPER`, `WHISPER_MODEL_SIZE` | `true`, `base.en` | **Container build.** Bake the Whisper model into the image (set `BAKE_WHISPER=false` with `STT_PROVIDER=groq`) |

</details>

---

## API reference

Interactive documentation is served by the running backend at **`/docs`** (OpenAPI). All endpoints except health, options, sign-up, log-in and the password-reset and Google entry points need `Authorization: Bearer <token>`.

| Area | Method and path | Notes |
|---|---|---|
| **Health** | `GET /health`, `GET /health?full=true` | Database, schema, speech models (and Groq with `full`). `503` when degraded |
| **Accounts** | `POST /api/auth/signup`, `POST /api/auth/login` | Return `{access_token, token_type, user}` |
| | `GET /api/auth/me`, `PATCH /api/auth/profile` | Profile: display name, bio, companion, style, pinned difficulty. A companion and style with no voice together are refused (`400`) |
| | `POST /api/auth/avatar` | Multipart image, JPEG, PNG or WebP, up to 5 MB |
| | `POST /api/auth/change-password` | Returns a fresh token; every other session ends |
| | `POST /api/auth/forgot-password` | Always `204` |
| | `POST /api/auth/verify-otp` | Reset the password with the emailed code; returns a token |
| | `POST /api/auth/verify-email`, `POST /api/auth/resend-verification` | Confirm email ownership |
| | `DELETE /api/auth/account` | Needs the email typed back, plus the password if one is set |
| **Google** | `GET /api/auth/google`, `GET /api/auth/google/callback` | The OAuth redirect flow |
| | `POST /api/auth/google/link-code`, `POST /api/auth/google/exchange`, `POST /api/auth/google/disconnect` | Connect, finish sign-in, unlink |
| **Setup** | `GET /api/config/options` | Companions (each with the styles they can speak), styles, scenarios, focus areas, difficulty levels, defaults |
| **Conversation** | `POST /api/conversation/start` | Form fields `scenario`, `style`, `voice`, optional `focus`. Returns the session id and the level it will run at |
| | `POST /api/conversation/message-stream` | Multipart `conversation_id` and `audio_file`; streams NDJSON (see [the stream protocol](#one-spoken-turn-step-by-step)) |
| | `POST /api/conversation/{id}/end` | Idempotent; starts the report in the background |
| **Feedback** | `GET /api/analysis/conversation/{id}/recent?limit=N` | `{corrections, pending}`: `pending` is how many turns are still being analysed |
| **History** | `GET /api/history/sessions?limit=&offset=` | Past sessions (1 to 100 per page) |
| | `GET /api/history/sessions/{id}` | One session in full: transcript, corrections, metrics |
| | `GET /api/history/sessions/{id}/report` | `200` ready, `202` still being written, `404` nothing to report on, `409` session not ended |
| **Practice** | `GET /api/practice/today`, `/weaknesses`, `/difficulty` | Today's exercise, the weak-spot profile, the next session's level and why |
| **Progress** | `GET /api/progress/summary?weeks=&tz_offset=` | Weekly trends, streak, totals, milestones; `tz_offset` is minutes from UTC |
| **Speech** | `POST /api/speech/word` | JSON `{word, voice?, style?, slow?}`; returns `audio/wav` |

**Conventions.** `401` not authenticated (or token revoked); `404` for anything that is not yours (never `403`, so ids cannot be probed); `429` with a `Retry-After` header when rate-limited; `413` for an oversized upload; `400` for validation errors and for unavailable companion and style pairs; `503` when the server cannot do its job.

<details>
<summary><strong>A complete session from the command line</strong></summary>

```bash
BASE=http://localhost:8000

# 1. Sign up (returns a token)
curl -s -X POST $BASE/api/auth/signup -H "Content-Type: application/json" \
  -d '{"email":"me@example.com","password":"correct-horse-battery"}'

TOKEN=...        # paste the access_token from the response

# 2. Start a session: Maya, speaking Scottish English, in the casual scenario
curl -s -X POST $BASE/api/conversation/start -H "Authorization: Bearer $TOKEN" \
  -F scenario=casual -F style=scottish -F voice=maya
# {"conversation_id":"...","style":"scottish","voice":"maya","difficulty":{"tier":2,"label":"Elementary"},...}

# 3. Send one spoken turn and read the stream (one JSON event per line)
curl -s -N -X POST $BASE/api/conversation/message-stream -H "Authorization: Bearer $TOKEN" \
  -F conversation_id=<id> -F "audio_file=@frontend/e2e/fixtures/speech.wav;type=audio/wav"

# 4. The feedback so far
curl -s "$BASE/api/analysis/conversation/<id>/recent?limit=10" -H "Authorization: Bearer $TOKEN"

# 5. End the session, then read the report (202 while the last answer is still being analysed)
curl -s -X POST $BASE/api/conversation/<id>/end -H "Authorization: Bearer $TOKEN"
curl -s $BASE/api/history/sessions/<id>/report -H "Authorization: Bearer $TOKEN"
```

</details>

---

## Database and migrations

The schema is managed **only** by Alembic; the application never creates tables itself. There are 11 revisions, from the initial schema through corrections, password hashes, profile and Google fields, email verification and token versions, fluency and clarity tables, praise, reports, weaknesses and session focus, to adaptive difficulty.

```bash
alembic -c backend/alembic.ini upgrade head                                 # apply everything (from Aurora/)
alembic -c backend/alembic.ini revision --autogenerate -m "what changed"    # after editing a model
alembic -c backend/alembic.ini check                                        # fails if models and migrations disagree
```

At start-up the API compares the database's revision with the code's. In development a mismatch is logged as an error; in any other environment **it refuses to start**. `GET /health` reports the same thing (`"migrations": "up to date"` or `"behind"`). To upgrade an existing database, run `upgrade head` *before* starting the new code. Existing rows are preserved phase by phase: accounts that signed in with Google become verified, old turns are marked analysed, and sessions from before reports existed get a report the first time they are opened. The test suite proves upgrade, downgrade, data preservation and "no drift between models and migrations".

---

## Testing and quality

| Layer | What it checks | Command | Needs |
|---|---|---|---|
| **Backend suite** | 572 tests at the time of writing: authentication and account safety, ownership checks, the voice stream and every failure path, analysis cleaning, fluency, clarity, scoring, reports, progress, weaknesses, difficulty, accents and voices, rate limiting, Google sign-in, migrations, production checks | `pytest` | PostgreSQL; creates its own `aura_test` database |
| **Live regression** | 27 cases of the real analysis prompt against the real model, so a prompt tweak that fixes one case cannot silently break another | `pytest -m llm` | A Groq key; costs about 40,000 tokens of quota |
| **Frontend unit tests** | The pure helpers, in plain Node with no browser: duration and clock formatting, the accent rules and the sentences that explain a switched-off choice, reading the reply stream (a line split across chunks, a stream that goes quiet, a caller that gives up), choosing a recording format per browser, and refusing a redirect that leaves the site | `npm test` (from `frontend/`) | Node 22 |
| **Browser tests** | Five files: **the journey** (sign up, speak with Chrome's fake microphone playing a recorded sentence, see corrections arrive, end the session, read the report, find it in history, pin a difficulty, delete the account; plus the speaking-style pickers and a legacy saved pair); **lifecycle** (leaving mid-session, finishing a session later, a reply cut off part-way); **accessibility** (the microphone by keyboard and in tap mode, page titles, and an axe scan of every page); **public** (titles, the 404 page, the security headers, the share preview, the honesty guards on the landing page, the forgot-password flow); **phone** (a 390 px screen: the drawer menu and no sideways scrolling) | `npm run e2e` (from `frontend/`) | The whole stack running; Chrome. Only the journey spends speech-to-text and language-model calls: the other files fake the server's reply |
| **Lint and build** | ESLint (including `no-undef`) and a production build | `npm run lint`, `npm run build` | Node |
| **Container smoke test** | Starts the real image on a throwaway database: migrations run, models load, a recording is transcribed, voices (including accent voices) speak, rate limits see real client addresses, the health check passes | `python scripts/smoke_container.py` | Docker and the compose PostgreSQL |
| **CI** | The backend suite on PostgreSQL, and the frontend lint, unit tests and build, on every push that touches `Aurora/` | `.github/workflows/ci.yml` | GitHub Actions |

**The offline suite is hermetic.** It needs no network, no model files and no keys, and it never touches your real database or `.env`:

- the environment is forced to a dedicated test database and dummy credentials *before* anything from `backend` is imported, and the suite refuses to run against a database whose name does not end in `_test`;
- Whisper, Groq, Piper and email are replaced by in-process fakes (the `ai` fixture), which can also inject failures (an STT error, an LLM that dies mid-reply, a TTS failure);
- every test sees a *stand-in voices folder* (an empty placeholder per model) so the real availability logic runs on a machine with no voices installed, which is exactly what CI is; the few tests of the genuine Piper models are marked `real_voices` and skip where the models are missing;
- a test that reaches the real LLM without the fake is *failed*, so nothing can quietly call the Groq API with the dummy key.

**Why the container check exists.** The suite fakes Whisper, Piper and Groq, so it cannot notice a broken dependency pin or a missing model file. The first real container run found that `faster-whisper` 1.2.1 and PyAV 19 (what a fresh install resolved to) were incompatible, so every local transcription failed while every test passed. PyAV is now pinned to 18.x with a test that decodes real WAV and WebM/Opus recordings through the real libraries.

**Run the live regression after any change to the analysis prompt or model.** Model output varies a little from run to run, so the suite allows a few attempts on the nondeterministic praise cases while still failing if correct English is ever called a mistake. One case (praise for phrasal verbs) is recorded as a known weak spot (`xfail`).

---

## Deployment

AURA is two deployables and a database.

```mermaid
flowchart LR
    U["Learner's browser"] --> FE["Frontend: Vercel or any Node host"]
    U -->|"API calls and audio"| BE["Backend container: FastAPI, Whisper, Piper"]
    FE -.->|"NEXT_PUBLIC_API_BASE"| BE
    BE --> PG[("Managed PostgreSQL: Neon, Supabase, RDS, Render")]
    BE --> GQ["Groq API"]
    BE --> EM["Resend"]
    BE --> CL["Cloudinary"]
    BE --> GO["Google OAuth"]
    BE --> SE["Sentry (optional)"]
```

> The container image has been built and exercised end to end on a development machine. The steps below are the intended path to a hosted deployment; AURA's own hosted deployment is not covered by this repository.

**Backend, as a container.** The `Dockerfile` produces one image with the code, the six companion voices, the two accent voices and (by default) the Whisper model baked in, so nothing downloads at start-up.

```bash
docker build -t aura-backend .          # add --build-arg BAKE_WHISPER=false if you will use STT_PROVIDER=groq
docker run -p 8000:8000 --env-file .env aura-backend
```

On start it applies migrations (`RUN_MIGRATIONS=false` to skip) and serves on `$PORT` (default 8000) with `--proxy-headers`. It runs as a non-root user and defaults to `ENVIRONMENT=production`. Use it on any host that runs containers (Render, Railway, Fly.io, a VM), and set the variables in the host's dashboard rather than shipping a `.env`. Inside the container `localhost` is the container itself, so `DATABASE_URL` must point at a database it can reach: your managed database in production, or `host.docker.internal` for a local Docker run against the compose PostgreSQL (the smoke test does exactly that).

| Topic | Guidance |
|---|---|
| **Memory** | About 0.75 GB right after start-up with local Whisper and the six companion voices (0.85 GB once a turn has run); 0.65 GB with `STT_PROVIDER=groq`; 0.1 to 0.2 GB with `STT_PROVIDER=groq` and `PREWARM_MODELS=false`. The two accent voices are loaded on first use and add about 100 MB and 125 MB, so the default setup sits near 1 GB once both are in use. Plan on **1.5 GB** for the default setup if learners will use regional accents. |
| **Image size** | About 0.9 GB to pull (compressed) and 1.45 GB unpacked: Python packages about 595 MB, voices about 580 MB, the Whisper model about 150 MB, the OS and Python about 120 MB |
| **One worker** | Rate limits live in process memory and each worker would load its own copy of the models. Run a single worker; to scale out, move the limiter to Redis first |
| **Behind a proxy** | The image sets `FORWARDED_ALLOW_IPS=*` so each learner's address is read from `X-Forwarded-For` (otherwise every learner shares the proxy's rate-limit bucket). With `*` the *left-most* address is trusted, which a client can forge if your platform appends to what the client sent instead of replacing it. If your platform publishes its proxies' addresses, set `FORWARDED_ALLOW_IPS` to those. Never run the container directly on the internet with `*` |
| **Health checks** | Point the platform at `/health` (fast) and an uptime monitor at `/health?full=true` (also pings Groq, a couple of seconds). Both answer `503` when the app cannot do its job; being rate-limited by Groq is reported but is not an outage |
| **Database** | Any managed PostgreSQL. Use the provider's connection string as `DATABASE_URL`, usually with `?sslmode=require` |
| **Frontend** | Import the repository into Vercel, set the project's root directory to `Aurora/frontend`, and set `NEXT_PUBLIC_API_BASE` to the API's public URL (and `NEXT_PUBLIC_SITE_URL` to the app's own, so shared links get their preview card). On the API side set `FRONTEND_URL` to the Vercel URL (and `CORS_ORIGINS` for any preview URLs). The microphone only works on `https://` pages (and on `localhost`) |

**Production checklist.** With `ENVIRONMENT` set to anything but `development`, the API checks its own configuration at start-up and logs each finding as `Production check: ...` (it never refuses to start over them, so read your first deploy's log). It covers: `JWT_SECRET` is at least 32 random characters and not a placeholder; `FRONTEND_URL` is not localhost and is https; `CORS_ORIGINS` has no localhost; `GOOGLE_REDIRECT_URI` is https when Google sign-in is configured; `RESEND_API_KEY` is set and `EMAIL_FROM` is on a domain you have verified with Resend; Cloudinary is configured and `SENTRY_DSN` is set; `RATE_LIMITS_ENABLED` is on, `SQL_ECHO` is off and `LOG_LEVEL` is not `DEBUG`. `python check_setup.py` runs the same checklist against your `.env` (set `ENVIRONMENT=production` first). Also: rotate any key that has ever been pasted into a chat or committed, and keep the database private.

---

## Performance and limits

**Latency.** How fast a turn feels depends mostly on the hardware (speech to text and synthesis are CPU-bound) and the network distance to Groq. Measured with `scripts/loadtest_voice.py` on a development laptop (CPU only), the same six-second clip, medians of a few turns:

| | Local Whisper `base.en` | Groq `whisper-large-v3-turbo` |
|---|---|---|
| Speech to text, 1 learner | 1.13 s | 0.82 s |
| Speech to text, 3 learners at once | **3.05 s** | **0.89 s** |
| Time to first audio, 1 learner | 2.19 s | 1.45 s |
| Time to first audio, 3 at once | 4.24 s (worst 5.3 s) | 2.84 s (worst 7.6 s)\* |
| Filler words ("um", "uh") | dropped, so not counted | kept, so fluency counts them |
| Clarity | per word, with a "hard to catch" list and *hear it* buttons | a rougher whole-turn estimate, no word list |
| Accented speech | weaker | stronger |
| Privacy | audio stays on your server | audio goes to Groq (already your LLM provider) |

\* One of those three-learner turns hit Groq's LLM rate limit, which is where that worst case comes from.

These are single runs on one machine, so treat them as the shape rather than precise figures. A small cloud CPU is likely to be slower than a laptop at local Whisper, and slower still with several learners. **For a deployed instance with more than one simultaneous learner, `groq` is the better default; choose `local` when audio must not leave your server or you want the per-word clarity list.** Re-run the load test against your real deployment before deciding.

**Groq's rate limits are the next ceiling.** On Groq's free tier, `openai/gpt-oss-120b` allowed about 8,000 tokens a minute and 200,000 a day in testing. A conversation turn plus its analysis is a couple of thousand tokens, so three learners talking at once exhausted it: the coach then says "The coach is very busy right now. Please try again in a few seconds.", and the background analysis waits and retries instead of giving up. The free tier clearly supports only a couple of simultaneous learners. Each model has its own budget, so using a different model for `LLM_CONVERSATION_MODEL` and `LLM_ANALYSIS_MODEL` raises the ceiling; a paid Groq tier raises it much further.

**Limits and budgets.**

| Limit | Value |
|---|---|
| Upload per turn | 5 MB and 120 seconds (the web app stops recording at 60 seconds and rejects holds under 0.4 seconds) |
| Coach's reply | 2 to 3 sentences, at most 400 tokens |
| Conversation context | the last 20 messages |
| Feedback per turn | at most 5 items (2 suggestions, 2 praise) |
| Report | up to 3 strengths, 3 improvements, 5 top mistakes, 5 practice words |
| History page | 20 sessions (up to 100 through the API) |
| Request bodies | 1 MB by default; 5 MB for audio and for avatars |

---

## Privacy and security

### What is stored, and what is not

| Stored | Not stored |
|---|---|
| Your account (email, display name, bio, preferences, a password hash), sessions, transcripts, word timings and recogniser confidence, corrections, fluency and clarity metrics, reports, the weak-spot cache | **Audio.** Each recording is written to a temporary file, transcribed, and deleted on every path. The coach's audio is generated on the fly and not kept (only single hear-it words are cached in memory) |

Deleting your account removes everything under it from the database in one step, and the profile photo from Cloudinary on a best-effort basis.

### Where data goes

| Service | What it receives | When |
|---|---|---|
| **Groq** | Transcript text and prompts (always); **audio** only if `STT_PROVIDER=groq` | Every turn |
| **Resend** | Your email address and the six-digit code | Sign-up verification, password reset |
| **Cloudinary** | Your profile photo | Only if you upload one |
| **Google** | The OAuth sign-in exchange | Only if you use Google sign-in |
| **Sentry** | Where and what broke, with no personal data, request bodies or local variables | Only if `SENTRY_DSN` is set |
| **Hugging Face** | Nothing about you; downloads the voice and Whisper models | Set-up and first run |

### Security measures

- **Passwords:** SHA-256 pre-hash then bcrypt (12 rounds); minimum 8 characters, no maximum; one-time codes hashed the same way, expire in 15 minutes and allow three attempts.
- **No account enumeration:** identical errors and identical work for unknown email, wrong password and Google-only account; "forgot password" always answers `204`; one generic failure for every bad reset code.
- **Rate limits on everything guessable** (table below), including per-IP *and* per-email counters so one person cannot lock a victim out from their own machine.
- **Token revocation:** a password change or reset bumps the token version and ends every other session, including one an attacker may have created.
- **Google account safety:** CSRF state cookie, single-use short-lived exchange codes (no session token ever appears in a URL), and the unverified-email takeover protection described above.
- **Ownership checks everywhere:** another user's session, report or conversation is a `404`.
- **Request limits before buffering:** oversized bodies are rejected with `413` before the framework spools them to disk.
- **CORS allow-list** built from `FRONTEND_URL` and `CORS_ORIGINS`; the OAuth cookie is `Secure` outside local development.
- **Browser security headers** on every page (`frontend/next.config.mjs`): the page cannot be framed by another site (`frame-ancestors 'none'`, plus `X-Frame-Options`), no `<base>` or `<object>` can be injected, forms may only post to this site, MIME sniffing is off, the referrer is trimmed for other sites, the microphone is allowed for this site only, and the `X-Powered-By` banner is gone. The Content-Security-Policy is deliberately only this safe subset: a strict `script-src` needs a fresh nonce on every request, which Next.js supports only on dynamically rendered pages, and that would mean giving up prerendering the whole app. `e2e/public.spec.js` checks the headers on a production build.
- **Sign-in redirects stay on the site.** The destination after Google sign-in comes from the address bar, so only a path on this site is accepted (anything else, including `//host` and backslash tricks, falls back to the practice page).
- **LLM output is untrusted input:** validated, normalised, quote-checked and capped before it touches the database.
- **Production self-check, honest health endpoint, privacy-safe Sentry set-up, non-root container.**

<details>
<summary><strong>Rate limits</strong> (in memory, per process)</summary>

| Action | Limit |
|---|---|
| Login attempts per IP | 30 per 15 minutes |
| Failed logins per IP and email / per email from anywhere | 5 / 20 per 15 minutes |
| Sign-ups per IP | 10 per hour |
| Forgot-password per IP / per email | 10 / 3 per hour (an email over its limit is silently skipped) |
| Reset-code checks per email / per IP | 10 / 30 per 15 minutes |
| Email-verification attempts per user | 10 per 15 minutes |
| Verification codes sent per user | 5 per hour, and one per 60 seconds |
| Wrong current password on a password change | 5 per 15 minutes |
| Photo uploads per user | 10 per hour |
| Voice turns per user | 30 per minute |
| Hear-a-word requests per user | 60 per minute |
| Account-deletion attempts per user | 5 per hour |
| Google exchange per IP | 30 per 15 minutes |

</details>

### Honest notes

- The session token is kept in the browser's `localStorage` (the usual trade-off for a single-page app: simple, but readable by any script that runs on the page). The app avoids putting tokens in URLs and the frontend loads no third-party scripts (not even a font CDN at run time), but there is no `HttpOnly` cookie option today, and the Content-Security-Policy is the safe subset described above rather than a strict script policy.
- Rate limits are per process, which matches the single-worker design; behind several workers they would need a shared store.
- Transcripts of what you say are sent to Groq. If that matters for your use, read Groq's terms, and consider that `STT_PROVIDER=local` at least keeps *audio* on your server.

---

## Known limitations

Worth knowing before you rely on it:

- **Clarity is an estimate, not pronunciation scoring.** It comes from the recogniser's confidence; unclear words, background noise, rare words and mis-heard homophones all lower it, and a high score does not prove native-like sounds. The product labels it as such.
- **Fillers need `STT_PROVIDER=groq`.** Local `base.en` drops "um" and "uh", so with it the fluency score has no filler information (and says so).
- **Analysis is an LLM's judgement.** It is accurate on the regression set (27 cases), but model output varies a little between runs and it can occasionally miss a mistake or, rarely, flag a correct sentence. Per-turn feedback is not a grade from a teacher.
- **Praise for phrasal verbs is unreliable.** The coach praises idioms consistently, but praised a correct sentence full of phrasal verbs only about half the time in testing, on either model. It never calls them mistakes.
- **The accents are real regional speakers, but no native speaker has judged them.** Each voice was chosen from a corpus's own labels (accent, region, gender) and checked for intelligibility, which proves the speech is clear, not that it sounds authentically Irish or Scottish. The corpus has two Australian speakers (both men), so Eida, Maya, Amy and Lessac have no Australian voice, and its British speakers are mostly from southern England.
- **Companions differ in voice, face and name, not in conversation style.** The prompt is the same for all six, and the app's copy describes only their voices.
- **Free-tier Groq limits** cap how many learners can practise at once.
- **Single process.** Rate limits are in memory; see [Deployment](#deployment).
- **Browsers.** Everything has been exercised in Chrome, on a desktop and in a phone-sized window with Chrome's own emulation. **Safari (iPhone and Mac) and Firefox have not been tested.** The code follows what Safari is known to need (recording MP4, the audio system woken inside the press that starts a turn, the upload named for what was recorded), but until it has run there on a real device, treat voice on Safari as unproven. No screen reader has been used on it either.
- **Leaving a session.** Ending a session when the tab is closed is a best-effort request that some browsers drop; the fallback is the *Finish session* button on the session's History page, which is always there.
- **Not exercised against the real services:** the Google sign-in success path (a human has to click through consent), real Resend email delivery and real Cloudinary uploads were tested with fakes and validation only.
- **Not built:** PDF export of a report, and WebSocket streaming (streaming over HTTP meets the latency target).
- Sessions from before speech metrics existed have no fluency or clarity data, and are shown as not analysed rather than scored.

---

## Roadmap

Ideas that follow from the limitations above. They are suggestions, not promises.

- **Per-companion personas** in the conversation prompt, so each companion could really converse differently (and the app's copy could then describe that, which today it must not).
- **More accents and more speakers**, including an Australian female voice, and review of every accent by native speakers.
- **Phoneme-level pronunciation feedback** with a dedicated model, alongside (not instead of) the honest clarity estimate.
- **A teacher view**: share a report or a weak-spot list with a tutor.
- **Hands-free turn-taking in the browser** (voice-activity detection, as the terminal client already does) and WebSocket streaming.
- **Report export** (PDF) and review of past corrections (a spaced-repetition list of your own mistakes).
- **Scaling out**: shared rate limiting (Redis) and more than one worker.
- **Cookie-based sessions** (`HttpOnly`) as an alternative to `localStorage` tokens.

---

## Troubleshooting and FAQ

| Symptom | Likely cause and fix |
|---|---|
| The page says it can't reach the backend | The API isn't running on port 8000, or `NEXT_PUBLIC_API_BASE` is wrong |
| `ModuleNotFoundError: backend` | Run `uvicorn` and `pytest` from the `Aurora/` folder, with the virtual environment active |
| `docker compose up -d` fails | Docker isn't running. Start Docker Desktop (or the Docker service) first |
| Start-up log: *Database schema is X, code expects Y* | Run `alembic -c backend/alembic.ini upgrade head` |
| The coach is silent but text appears | A voice file is missing: `python scripts/download_voices.py --check` |
| `/health` says `behind` or answers 503 | Check the API log: it names the exact problem (database unreachable, schema behind, no voices) |
| "The coach is very busy right now" | Groq's rate limit: wait a few seconds, or see [Performance and limits](#performance-and-limits) |
| The first turn after a restart is slow | Models are still loading; `/health` shows `speech.stt.ready` and `speech.voices.loaded` |
| A speaking style or companion is greyed out ("doesn't have a ... voice yet") | That companion has no voice for the accent (Australian exists for Ryan and Alan only), or the accent model isn't installed: `python scripts/download_voices.py --check` |
| The microphone does nothing | Allow microphone access in the browser's site settings. On a deployed site the page must be served over `https://` |
| Verification email never arrives (development) | Without `RESEND_API_KEY` the code is printed in the API's log |
| Tests refuse to start | PostgreSQL isn't running (`docker compose up -d`), or `TEST_DATABASE_URL` doesn't end in `_test` |
| `npm run dev` shows stale pages after edits | Restart the dev server (file watching on synced folders such as OneDrive can miss changes) |

**Does AURA keep my voice?** No. Audio is transcribed and deleted; only the transcript, timings and feedback are stored.

**Does it work offline?** Partly. Speech recognition and the voices run on your machine, but the coach and the analysis need the Groq API.

**Why does my filler count show an asterisk?** The local recogniser drops "um" and "uh", so a count of 0 would be false. Use `STT_PROVIDER=groq` to count them.

**Is the clarity score pronunciation scoring?** No. It is the recogniser's confidence, and it says so.

**Why can't I pick Australian English with Amy?** No Australian voice exists for her (see [Speaking styles and accents](#speaking-styles-and-accents)). Pick Ryan or Alan, or another style.

**Can I use different models?** Yes: `LLM_CONVERSATION_MODEL`, `LLM_ANALYSIS_MODEL`, `GROQ_STT_MODEL` and `WHISPER_MODEL_SIZE` are settings.

**How do I reset my local database?** `docker compose down -v`, then `docker compose up -d` and `alembic -c backend/alembic.ini upgrade head`. This deletes the development data.

---

## Contributing and extending AURA

### Working on the code

1. Follow [Getting started](#getting-started) to run the stack, and install the dev dependencies (`pip install -r backend/requirements-dev.txt`).
2. **Backend conventions.** Type hints; docstrings that explain *why*; log through `logging.getLogger("aura.<area>")`, never `print`; read settings only from `backend/config.py`; change the schema only with an Alembic migration (autogenerate, then review, then `alembic check`); keep scoring code pure and bump `SCORING_VERSION` whenever a formula changes.
3. **Frontend conventions.** Plain JavaScript (deliberately not TypeScript); keep every API call in `lib/api.js` or `lib/auth.js`; put logic that can be a pure function in `lib/` with a `*.test.js` beside it; run `npm run lint`, `npm test` and `npm run build`. New signed-in pages go in `app/(app)/` (they get the sidebar and the login check from its layout), with a small `layout.js` that sets the tab title. **Never write copy that promises what the app does not do** (a companion's personality, a dashboard figure that does not exist): describe only what is real, and explain a switched-off control in visible text, not only a tooltip. **Next.js 16 differs from older versions**: read the relevant guide in `frontend/node_modules/next/dist/docs/` before relying on remembered APIs (for instance, an error boundary receives `retry`, not `reset`).
4. **Tests.** Add a test with every change. New backend tests must stay hermetic (use the `ai` fixture; never call the real LLM). After touching the analysis prompt or model, run `pytest -m llm`. Before a pull request, run the backend suite, lint, build and, for UI changes, the browser journey.
5. **Honesty rules.** If a feature cannot deliver something, the interface must not promise it (the accent pairs are the model example).

### Recipes

| To add... | Edit |
|---|---|
| **A scenario** | Add it to `SCENARIOS` in `backend/personalities.py` (id, label, prompt). Add its landing-page copy to `SCENES` in `frontend/lib/characters.js` and its artwork to `public/characters/scenes/<id>.webp`. The pickers read the list from the API. |
| **A speaking style** | Add it to `STYLES` (label, example words, prompt, `accent`). If the accent is new, add it to `ACCENT_LABELS` and give each companion that can speak it an entry in `ACCENT_VOICES`; update the tables in `backend/tests/test_accents.py`. |
| **An accent speaker** | Add one line to `ACCENT_VOICES` (model file, speaker name, gender, region). `test_accents.py` checks it against the corpus's own accent and gender table. |
| **A kind of feedback** | Add it to `SUBTYPES` in `backend/taxonomy.py` (label and the steering "focus" text), plus synonyms and the praise or suggestion lists if needed. The analysis prompt lists the ids automatically; add a live regression case. |
| **A companion** | Add it to `VOICES` and give it `ACCENT_VOICES` entries; add the character to `CAST` in `frontend/lib/characters.js` with artwork built by `scripts/build-characters.cjs`; run `python scripts/download_voices.py`. |
| **A difficulty tweak** | `DIFFICULTY_LEVELS` (prompts) in `personalities.py`; `THRESHOLDS` and `HISTORY` in `services/difficulty.py`. |

---

## Credits and licences

**Built by** Vihanga Deemantha ([@Vihanga-Deemantha](https://github.com/Vihanga-Deemantha)).

### Acknowledgements

AURA stands on a lot of other people's work:

- **Groq**, for the fast inference that makes a spoken conversation feel live, and **OpenAI** for the open-weight `gpt-oss` models and **Whisper**.
- **The Piper project** and its voice contributors, and **the University of Edinburgh's Centre for Speech Technology Research** for the VCTK and Alba corpora behind the regional accents (credits below).
- The maintainers of **faster-whisper and CTranslate2**, **FastAPI, Starlette and Uvicorn**, **SQLAlchemy and Alembic**, **PostgreSQL**, **Next.js, React and Tailwind CSS**, and **Playwright**.
- The free tiers of **Groq**, **Resend**, **Cloudinary** and **Sentry**, which make it possible to build and test the whole system at no cost.

### Voice credits (required by their licences)

The regional voices come from two University of Edinburgh corpora released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), turned into Piper voice models by the [Piper project](https://github.com/rhasspy/piper) (`rhasspy/piper-voices`):

- Yamagishi, J., Veaux, C. and MacDonald, K. (2019), *CSTR VCTK Corpus: English Multi-speaker Corpus for CSTR Voice Cloning Toolkit (version 0.92)*, University of Edinburgh, <https://datashare.ed.ac.uk/handle/10283/3443>
- Valentini-Botinhao, C. and Yamagishi, J. (2019), *Alba speech corpus*, University of Edinburgh, <https://datashare.ed.ac.uk/handle/10283/3270>

The profile page repeats this credit. The six companions' own voices are separate Piper models; see each model card in `rhasspy/piper-voices` for its licence.

### Licences

- **AURA itself:** no `LICENSE` file has been added to the repository yet, so by default all rights are reserved. Add a licence before inviting contributions or reuse. The companion artwork in `Aurora/frontend/public/characters` and `Aurora/frontend/aura-project-assets` is project material and is not covered by the third-party notes here.
- **Dependencies:** each carries its own licence, declared in its package metadata. Most of the Python runtime is MIT, BSD or Apache-2.0 (FastAPI, SQLAlchemy, Alembic, Pydantic, faster-whisper, ONNX Runtime, the Groq SDK, bcrypt and others). Two deserve a look before you *distribute* anything: **`piper-tts` is GPL-3.0-or-later**, so redistributing a container image that bundles it can carry GPL obligations (check before you do), and `psycopg2-binary` is LGPL with exceptions.
- **Models:** the `gpt-oss` models are Apache-2.0, Whisper is MIT, and every Piper voice has its own model card.

---

## Glossary

| Term | Meaning |
|---|---|
| **Companion** | One of the six characters you talk to: a name, a face and a voice |
| **Speaking style** | An English variety (Standard, American, British, Australian, Irish, Scottish, Canadian) that sets the coach's words and, where a voice exists, the accent |
| **Accent voice** | A recording of a real regional speaker, served by a multi-speaker Piper model, used for a companion under a regional style |
| **Scenario** | The situation the coach plays (café, interview, phone call, ...) |
| **Session** | One practice conversation, from the first turn to *End session* |
| **Turn** | One thing you say, and the coach's reply to it |
| **Path A / Path B** | The spoken conversation (fast) and the background analysis (patient), which run at the same time |
| **Correction** | A piece of feedback on a turn: a *mistake*, a *suggestion* or *praise* |
| **Subtype** | The specific kind of a correction (for example "Past tense"); fixed in `taxonomy.py` so habits can be counted |
| **Severity** | How serious a mistake is (high, medium, low); weights it in the scores |
| **Density** | Mistakes per 100 words; what grammar and vocabulary scores are built from |
| **Fluency** | How smoothly you spoke: rate, pauses, fillers, repeats (0 to 100) |
| **Clarity** | How confidently the recogniser identified your words (0 to 100); an estimate |
| **Hard-to-catch words** | The words the recogniser was least sure of, with hear and slow buttons |
| **Scoring version** | The number stored with each report that says which formulas produced it |
| **Difficulty tier** | One of five levels of question difficulty, automatic or pinned |
| **Weak spot** | A kind of mistake you keep making, ranked by how recent and how frequent |
| **Focus** | A hidden steering instruction that makes the coach's questions give you practice at a weak spot |
| **Token version** | A counter on your account that, when bumped, ends every other session |
| **NDJSON** | Newline-delimited JSON: the streamed format of a voice turn, one event per line |
| **Pre-warm** | Loading the speech models at start-up so the first turn is not slow |
| **Stand-in voices** | The placeholder voices folder that lets the test suite run with no model files |
