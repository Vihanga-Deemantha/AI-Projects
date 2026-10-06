import assert from "node:assert/strict";
import { test } from "node:test";
import { speaks, styleAccent, styleRowNote, voiceRowNote, whyNot, withArticle } from "./accents.js";

// The shape of GET /api/config/options, cut down to what these helpers read. Australian exists for Ryan and Alan only.
const options = {
  voices: [
    { id: "amy", label: "Amy", styles: ["standard", "american", "british", "irish"] },
    { id: "ryan", label: "Ryan", styles: ["standard", "american", "british", "irish", "australian"] },
    { id: "alan", label: "Alan", styles: ["standard", "american", "british", "irish", "australian"] },
    { id: "lessac", label: "Lessac", styles: ["standard", "american", "british", "irish"] },
  ],
  styles: [
    { id: "standard", label: "Standard English", accent: null },
    { id: "american", label: "American English", accent: "American" },
    { id: "british", label: "British English", accent: "British" },
    { id: "irish", label: "Irish English", accent: "Irish" },
    { id: "australian", label: "Australian English", accent: "Australian" },
  ],
};

test("speaks says whether a companion has a voice for a style, and allows everything until the options load", () => {
  assert.equal(speaks(options, "amy", "irish"), true);
  assert.equal(speaks(options, "amy", "australian"), false);
  assert.equal(speaks(options, "ryan", "australian"), true);
  assert.equal(speaks(null, "amy", "australian"), true);
  assert.equal(speaks(options, "unknown-voice", "australian"), true);
});

test("styleAccent and withArticle give the accent a style asks for, in a sentence", () => {
  assert.equal(styleAccent(options, "australian"), "Australian");
  assert.equal(styleAccent(options, "standard"), null);
  assert.equal(withArticle("Irish"), "an Irish");
  assert.equal(withArticle("Scottish"), "a Scottish");
});

test("whyNot names the companion, the accent and who does have the voice", () => {
  assert.equal(whyNot(options, "amy", "australian"), "Amy doesn't have an Australian voice yet. Ryan and Alan do.");
  assert.equal(whyNot(options, "lessac", "australian"), "Lessac doesn't have an Australian voice yet. Ryan and Alan do.");
});

test("styleRowNote is the visible sentence under the style chips, and absent when nothing is switched off", () => {
  assert.equal(styleRowNote(options, "amy"), "Amy doesn't have an Australian voice yet. Ryan and Alan do.");
  assert.equal(styleRowNote(options, "ryan"), null);
  assert.equal(styleRowNote(null, "amy"), null);
});

test("voiceRowNote is the visible sentence under the companion chips, and absent when everyone can speak the style", () => {
  assert.equal(voiceRowNote(options, "australian"), "Only Ryan and Alan have an Australian voice yet.");
  assert.equal(voiceRowNote(options, "irish"), null);
  assert.equal(voiceRowNote(options, "standard"), null);
  assert.equal(voiceRowNote(null, "australian"), null);
});
