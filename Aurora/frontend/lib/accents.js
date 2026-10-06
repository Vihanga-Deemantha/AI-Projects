/**
 * Which companions can speak which speaking styles.
 *
 * A style brings an accent, and not every companion has a voice for every accent (for example the
 * female companions have no Australian-accent voice), so the pickers only offer combinations that work.
 * The server is the source of truth: GET /api/config/options lists, for each companion, the styles
 * they can speak, and starting a session with any other pair is refused.
 */

/** Can this companion speak this style? (True while the options haven't loaded: don't block anything yet.) */
export function speaks(options, voiceId, styleId) {
  const voice = options?.voices?.find((v) => v.id === voiceId);
  return voice ? voice.styles.includes(styleId) : true;
}

/** The accent a style asks for ("Scottish"), or null for Standard English. */
export function styleAccent(options, styleId) {
  return options?.styles?.find((s) => s.id === styleId)?.accent ?? null;
}

/** An accent's name with the right article, for sentences: "an Irish", "a Scottish". */
export function withArticle(accent) {
  return `${/^[aeiou]/i.test(accent) ? "an" : "a"} ${accent}`;
}

/** "Ryan", "Ryan and Alan", "Ryan, Alan and Lessac". */
function joinNames(names) {
  return names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/**
 * The explanation of a chip that is switched off because this companion has no voice for this style, e.g.
 * "Amy doesn't have an Australian voice yet. Ryan and Alan do." It says why and who to pick instead.
 */
export function whyNot(options, voiceId, styleId) {
  const name = options?.voices?.find((v) => v.id === voiceId)?.label ?? "This companion";
  const accent = styleAccent(options, styleId) ?? "matching";
  const others = (options?.voices ?? []).filter((v) => v.styles.includes(styleId)).map((v) => v.label);
  return `${name} doesn't have ${withArticle(accent)} voice yet.${others.length ? ` ${joinNames(others)} ${others.length === 1 ? "does" : "do"}.` : ""}`;
}

/**
 * The sentence under the speaking-style chips when some of them are switched off for the chosen companion
 * (null when none are): "Amy doesn't have an Australian voice yet. Ryan and Alan do." Shown on the page itself,
 * because a hover tooltip never appears on a touch screen and a switched-off button can't be tabbed to.
 */
export function styleRowNote(options, voiceId) {
  const off = (options?.styles ?? []).filter((s) => !speaks(options, voiceId, s.id));
  return off.length ? off.map((s) => whyNot(options, voiceId, s.id)).join(" ") : null;
}

/**
 * The sentence under the companion chips when some of them are switched off for the chosen speaking style
 * (null when none are): "Only Ryan and Alan have an Australian voice yet."
 */
export function voiceRowNote(options, styleId) {
  const voices = options?.voices ?? [];
  const can = voices.filter((v) => v.styles.includes(styleId)).map((v) => v.label);
  if (can.length === 0 || can.length === voices.length) return null;
  return `Only ${joinNames(can)} ${can.length === 1 ? "has" : "have"} ${withArticle(styleAccent(options, styleId) ?? "matching")} voice yet.`;
}
