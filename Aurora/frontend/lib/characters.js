/**
 * The six AURA companions and the seven practice scenarios, plus the paths to
 * their art (built into public/characters by scripts/build-characters.cjs).
 *
 * Companion ids match the backend voice ids (backend/personalities.py VOICES),
 * so a stored `voice` / `preferred_voice` is directly a companion id.
 */

import { withArticle } from "@/lib/accents";

// Sprites live on a shared 700x680 canvas, feet pinned to the bottom edge.
export const SPRITE_ASPECT = 700 / 680;

// What the six companions really differ in is their NAME, FACE and VOICE: the coach's conversation prompt is the
// same for all of them (it varies by scenario, speaking style, difficulty and practice focus, never by companion).
// So everything written here describes the voice, in the words of backend/personalities.py VOICES `desc`, and never
// promises a way of conversing. Keep it that way: a line that says a companion "changes subject often" or "notices
// register slips" would be false until the prompt actually does it.
//
// `tag` is one playful word for the voice's vibe, shown next to the name. It is deliberately NOT the accent,
// because the accent follows the speaking style (American / British / Scottish / ...): a style sets the coach's
// words AND the accent, and the companion adopts it. `accent` is the accent of the companion's OWN voice (its Piper
// model's locale: en_US or en_GB), what they sound like under Standard English; it appears in a hover tooltip (see
// companionHint) rather than on the card.
export const CAST = [
  {
    id: "eida", name: "Eida", tag: "Zen", accent: "American",
    tagline: "A calm, unhurried voice.",
    blurb: "Eida speaks with a calm, unhurried voice. Choose her when you would like to listen without feeling rushed.",
    traits: ["Calm", "Unhurried", "American by default"],
    line: "Eida is ready when you are.",
  },
  {
    id: "maya", name: "Maya", tag: "Bubbly", accent: "American",
    tagline: "An upbeat, energetic voice.",
    blurb: "Maya speaks with an upbeat, energetic voice. Choose her when you want the conversation to feel bright.",
    traits: ["Upbeat", "Energetic", "American by default"],
    line: "Maya is ready when you are.",
  },
  {
    id: "amy", name: "Amy", tag: "Sunny", accent: "American",
    tagline: "A friendly voice.",
    blurb: "Amy is the default companion: a friendly voice with an American accent under Standard English.",
    traits: ["Friendly", "Default companion", "American by default"],
    line: "Amy is ready when you are.",
  },
  {
    id: "ryan", name: "Ryan", tag: "Cozy", accent: "American",
    tagline: "A warm voice.",
    blurb: "Ryan speaks with a warm voice and an American accent under Standard English.",
    traits: ["Warm", "American by default"],
    line: "Ryan is ready when you are.",
  },
  {
    id: "alan", name: "Alan", tag: "Stickler", accent: "British",
    tagline: "A measured voice.",
    blurb: "Alan speaks with a measured voice and a British accent under Standard English. He is the one to choose when you want to hear British English.",
    traits: ["Measured", "British by default"],
    line: "Alan is ready when you are.",
  },
  {
    id: "lessac", name: "Lessac", tag: "Dramatic", accent: "American",
    tagline: "A deep, deliberate voice.",
    blurb: "Lessac speaks with a deep, deliberate voice and an American accent under Standard English.",
    traits: ["Deep", "Deliberate", "American by default"],
    line: "Lessac is ready when you are.",
  },
];

export const CAST_BY_ID = Object.fromEntries(CAST.map((c) => [c.id, c]));

/** Falls back to the first companion for unknown/legacy ids so callers never crash. */
export function getCompanion(id) {
  return CAST_BY_ID[id] || CAST_BY_ID.amy;
}

export function isCompanion(id) {
  return Boolean(CAST_BY_ID[id]);
}

/**
 * Hover text for a companion: the accent you will hear and what their voice is like. Their own voice
 * has a home accent, but the speaking style brings its own accent and the companion adopts it, e.g.
 * "Alan · will speak with a Scottish accent, to match your speaking style. A measured voice.".
 * `styleAccent` is the chosen style's accent ("Scottish"), or null for Standard English.
 */
export function companionHint(companion, styleAccent = null) {
  let sound;
  if (!styleAccent) sound = `${companion.name} · ${companion.accent} accent by default. It changes with your speaking style.`;
  else if (styleAccent === companion.accent) sound = `${companion.name} · ${companion.accent} accent, which matches your speaking style.`;
  else sound = `${companion.name} · will speak with ${withArticle(styleAccent)} accent, to match your speaking style.`;
  return `${sound} ${companion.tagline}`;
}

// Scene-setting copy for the landing page's scenarios chapter. Keys match the backend scenario ids. The `setting`
// only describes what the scenario prompt (backend/personalities.py SCENARIOS) really asks the coach to do, and the
// `line` is an EXAMPLE of how a coach might speak in it (the page labels it so): the real coach answers after you.
export const SCENES = [
  { key: "casual", label: "Casual chat", setting: "A slow afternoon, nothing at stake. The conversation wanders wherever you take it.", skills: ["Small talk", "Opinions", "Everyday tense"], line: "So — how has your week actually been? Give me the honest version." },
  { key: "interview", label: "Job interview", setting: "A quiet room and a desk. Questions start easy and get harder as the interview goes on.", skills: ["Formal register", "Structured answers", "Experience"], line: "Thanks for coming in. Tell me about a piece of work you are proud of." },
  { key: "travel", label: "Travel / airport", setting: "A departures hall, a hotel desk, a stranger who knows the way. The practical English a trip asks of you.", skills: ["Requests", "Directions", "Numbers"], line: "Good evening — do you have a reservation with us tonight?" },
  { key: "debate", label: "Debate", setting: "Opposite sides of a table. A position is taken, your argument is challenged, evidence is asked for.", skills: ["Argument", "Hedging", "Counter-points"], line: "I will argue remote work makes people worse at their jobs. Convince me otherwise." },
  { key: "seminar", label: "University seminar", setting: "Eight chairs in a circle and a reading nobody finished. You are expected to explain, not assert.", skills: ["Academic vocabulary", "Explaining", "Citing"], line: "Could you summarise the argument of the chapter in your own words?" },
  { key: "cafe", label: "Café / ordering", setting: "A counter, a queue behind you, a menu you half understand. Short, quick exchanges.", skills: ["Ordering", "Polite requests", "Clarifying"], line: "Hi there, what can I get for you? We are out of the almond croissants." },
  { key: "phone", label: "Phone call", setting: "No face, no gestures, and now and then a request to repeat. Everything is carried by words and tone alone.", skills: ["Listening", "Spelling aloud", "Confirming"], line: "Hello, thanks for holding — could I take your name and spell it back?" },
];

export const spriteSrc = (id, pose = "idle") => `/characters/sprites/${id}_${pose}.webp`;
export const faceSrc = (id, expr = "neutral") => `/characters/faces/${id}_${expr}.webp`;
export const sceneSrc = (key) => `/characters/scenes/${key}.webp`;

const titleCase = (id) => String(id || "").replace(/[_-]/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());

/** Display label for a stored scenario id, including retired ones like "university". */
export function sceneLabel(id) {
  return SCENES.find((s) => s.key === id)?.label || titleCase(id);
}

/** Display label for a stored speaking-style id, including retired ones like "pirate". */
export function styleLabel(id) {
  return titleCase(id);
}

/** Preload images so a crossfade never waits on the network mid-dissolve. */
export function preload(srcs) {
  if (typeof window === "undefined") return;
  for (const src of srcs) {
    const img = new Image();
    img.src = src;
  }
}
