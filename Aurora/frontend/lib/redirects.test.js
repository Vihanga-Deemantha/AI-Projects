import assert from "node:assert/strict";
import { test } from "node:test";
import { safeNextPath } from "./redirects.js";

test("a path on this site is kept", () => {
  assert.equal(safeNextPath("/practice"), "/practice");
  assert.equal(safeNextPath("/history/abc/report"), "/history/abc/report");
  assert.equal(safeNextPath("/profile#difficulty"), "/profile#difficulty");
  assert.equal(safeNextPath("/practice?focus=grammar%3Apast_tense"), "/practice?focus=grammar%3Apast_tense");
});

test("anything that could leave the site falls back to the default", () => {
  for (const bad of [
    "https://evil.example",
    "http://evil.example/practice",
    "//evil.example",
    "/\\evil.example",
    "\\\\evil.example",
    "/\t/evil.example",
    "/\n/evil.example",
    "javascript:alert(1)",
    "practice",
    " /practice",
    "",
    null,
    undefined,
    42,
  ]) {
    assert.equal(safeNextPath(bad), "/practice", `expected ${JSON.stringify(bad)} to be refused`);
  }
});

test("the fallback can be chosen", () => {
  assert.equal(safeNextPath("https://evil.example", "/login"), "/login");
});
