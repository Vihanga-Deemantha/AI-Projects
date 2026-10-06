import assert from "node:assert/strict";
import { test } from "node:test";
import { audioFileName, micErrorMessage, pickRecordingMimeType, recordingSupportProblem } from "./recording.js";

test("the first format the browser can record wins", () => {
  // Chrome / Edge
  assert.equal(pickRecordingMimeType(() => true), "audio/webm;codecs=opus");
  // Firefox records Ogg but not WebM
  assert.equal(pickRecordingMimeType((t) => t.startsWith("audio/ogg")), "audio/ogg;codecs=opus");
  // Safari records MP4 only
  assert.equal(pickRecordingMimeType((t) => t === "audio/mp4"), "audio/mp4");
  // Nothing on the list: let the browser choose
  assert.equal(pickRecordingMimeType(() => false), "");
});

test("the upload is named after what was recorded, so a Safari recording is not called .webm", () => {
  assert.equal(audioFileName({ type: "audio/webm;codecs=opus" }), "audio.webm");
  assert.equal(audioFileName({ type: "audio/ogg;codecs=opus" }), "audio.ogg");
  assert.equal(audioFileName({ type: "audio/mp4" }), "audio.m4a");
  assert.equal(audioFileName({ type: "audio/mp4;codecs=mp4a.40.2" }), "audio.m4a");
  assert.equal(audioFileName({ type: "audio/x-m4a" }), "audio.m4a");
  assert.equal(audioFileName({ type: "audio/wav" }), "audio.wav");
  assert.equal(audioFileName({ type: "" }), "audio.webm");
  assert.equal(audioFileName(null), "audio.webm");
});

test("recordingSupportProblem tells an old browser from an insecure page", () => {
  const recorder = class {};
  const mic = { mediaDevices: { getUserMedia() {} } };
  assert.equal(recordingSupportProblem({ MediaRecorder: recorder, navigator: mic, isSecureContext: true }), null);
  assert.equal(recordingSupportProblem({ navigator: mic, isSecureContext: true }), "UnsupportedError"); // no MediaRecorder
  assert.equal(recordingSupportProblem({ MediaRecorder: recorder, navigator: {}, isSecureContext: false }), "InsecureContextError");
  assert.equal(recordingSupportProblem({ MediaRecorder: recorder, navigator: {}, isSecureContext: true }), "UnsupportedError");
});

test("each microphone failure gets its own advice, and the too-short advice follows the mode", () => {
  assert.match(micErrorMessage({ name: "NotAllowedError" }), /permission/i);
  assert.match(micErrorMessage({ name: "NotFoundError" }), /No microphone/);
  assert.match(micErrorMessage({ name: "NotReadableError" }), /already in use/);
  assert.match(micErrorMessage({ name: "InsecureContextError" }), /secure page/);
  assert.match(micErrorMessage({ name: "UnsupportedError" }), /can't record/);
  assert.match(micErrorMessage({ name: "TooShortError" }), /hold the mic button/);
  assert.match(micErrorMessage({ name: "TooShortError" }, "tap"), /tap to start/);
  assert.match(micErrorMessage(new Error("something odd")), /Could not access the microphone/);
  assert.match(micErrorMessage(undefined), /Could not access the microphone/);
});
