/**
 * The six AURA companions and the seven practice scenarios, plus the paths to
 * their art (built into public/characters by scripts/build-characters.cjs).
 *
 * Companion ids match the backend voice ids (backend/personalities.py VOICES),
 * so a stored `voice` / `preferred_voice` is directly a companion id.
 */

// Sprites live on a shared 700x680 canvas, feet pinned to the bottom edge.
export const SPRITE_ASPECT = 700 / 680;

export const CAST = [
  {
    id: "eida", name: "Eida", tag: "Introvert",
    tagline: "The one who lets the silence sit.",
    blurb: "Eida speaks slowly and leaves the pauses alone. She will not talk over you and she will not fill a gap you are still thinking in.",
    traits: ["Gentle pace", "Long pauses", "Calm voice"],
    line: "Eida is waiting. She never rushes you.",
  },
  {
    id: "maya", name: "Maya", tag: "Extrovert",
    tagline: "The one who keeps it moving.",
    blurb: "Maya is cheerful, quick and slightly relentless. She reacts out loud to everything you say and changes subject twice a minute.",
    traits: ["Fast turns", "High energy", "Upbeat voice"],
    line: "Maya is waiting. She talks fast and laughs faster.",
  },
  {
    id: "amy", name: "Amy", tag: "American",
    tagline: "The easiest voice to follow at full speed.",
    blurb: "Friendly American English, clean consonants, nothing showy. The voice most learners can follow without asking for a repeat.",
    traits: ["Friendly", "Clear diction", "en_US"],
    line: "Amy is waiting. The clearest voice of the six.",
  },
  {
    id: "ryan", name: "Ryan", tag: "American",
    tagline: "The one who goes deeper instead of wider.",
    blurb: "The lowest, warmest register of the six. He asks follow-up questions rather than new ones, so conversations stay on one subject.",
    traits: ["Warm tone", "Deep follow-ups", "en_US"],
    line: "Ryan is waiting. He asks the second question.",
  },
  {
    id: "alan", name: "Alan", tag: "British",
    tagline: "The one to practise with before it matters.",
    blurb: "British English, measured, exacting about tense and register. He notices when you slip from formal into casual mid-sentence.",
    traits: ["Formal register", "Exacting", "en_GB"],
    line: "Alan is waiting. Mind your tenses.",
  },
  {
    id: "lessac", name: "Lessac", tag: "American",
    tagline: "The one who shows you where the stress lands.",
    blurb: "Lessac speaks the way people speak when they are being listened to. Wide intonation and deliberate emphasis make him the best of the six for hearing which word in a sentence is carrying it.",
    traits: ["Expressive", "Wide range", "en_US"],
    line: "Lessac is waiting. He will show you where the stress lands.",
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

// Marketing copy for the landing page's scenarios chapter. Keys match the
// backend scenario ids.
export const SCENES = [
  { key: "casual", label: "Casual chat", setting: "A slow afternoon, nothing at stake. The conversation wanders wherever you take it.", skills: ["Small talk", "Opinions", "Everyday tense"], line: "So — how has your week actually been? Give me the honest version." },
  { key: "interview", label: "Job interview", setting: "A quiet room and a desk. Questions start easy and get harder, and nothing is rephrased for you.", skills: ["Formal register", "Structured answers", "Experience"], line: "Thanks for coming in. Tell me about a piece of work you are proud of." },
  { key: "travel", label: "Travel / airport", setting: "A departures hall, a hotel desk, a stranger who knows the way. Real consequences if you are not understood.", skills: ["Requests", "Directions", "Numbers"], line: "Good evening — do you have a reservation with us tonight?" },
  { key: "debate", label: "Debate", setting: "Opposite sides of a table. A position is taken, your argument is challenged, evidence is asked for.", skills: ["Argument", "Hedging", "Counter-points"], line: "I will argue remote work makes people worse at their jobs. Convince me otherwise." },
  { key: "seminar", label: "University seminar", setting: "Eight chairs in a circle and a reading nobody finished. You are expected to explain, not assert.", skills: ["Academic vocabulary", "Explaining", "Citing"], line: "Could you summarise the argument of the chapter in your own words?" },
  { key: "cafe", label: "Café / ordering", setting: "A counter, a queue behind you, a menu you half understand. The fastest English there is.", skills: ["Ordering", "Polite requests", "Clarifying"], line: "Hi there, what can I get for you? We are out of the almond croissants." },
  { key: "phone", label: "Phone call", setting: "No face, no gestures, slightly bad line. Everything is carried by words and tone alone.", skills: ["Listening", "Spelling aloud", "Confirming"], line: "Hello, thanks for holding — could I take your name and spell it back?" },
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
