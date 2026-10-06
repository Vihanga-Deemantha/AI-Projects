import assert from "node:assert/strict";
import { test } from "node:test";
import { formatClock, formatDuration, formatHours, formatMinutes } from "./format.js";

test("formatDuration shows minutes and seconds, and a dash when there is no duration", () => {
  assert.equal(formatDuration(null), "—");
  assert.equal(formatDuration(undefined), "—");
  assert.equal(formatDuration(0), "0s");
  assert.equal(formatDuration(45), "45s");
  assert.equal(formatDuration(90), "1m 30s");
  assert.equal(formatDuration(3725), "62m 5s");
});

test("formatDuration never shows 60 seconds", () => {
  assert.equal(formatDuration(59.6), "1m 0s");
  assert.equal(formatDuration(119.5), "2m 0s");
});

test("formatClock is a running m:ss clock", () => {
  assert.equal(formatClock(0), "0:00");
  assert.equal(formatClock(7.9), "0:07");
  assert.equal(formatClock(187), "3:07");
  assert.equal(formatClock(-5), "0:00");
  assert.equal(formatClock(undefined), "0:00");
});

test("formatHours works in whole minutes, so it never shows 1h 60m", () => {
  assert.equal(formatHours(0), "0m");
  assert.equal(formatHours(720), "12m");
  assert.equal(formatHours(3600), "1h 0m");
  assert.equal(formatHours(13200), "3h 40m");
  assert.equal(formatHours(7170), "2h 0m");
});

test("formatMinutes is at least one minute", () => {
  assert.equal(formatMinutes(5), "1 min");
  assert.equal(formatMinutes(90), "2 min");
  assert.equal(formatMinutes(600), "10 min");
});
