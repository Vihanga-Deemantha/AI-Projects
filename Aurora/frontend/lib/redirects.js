/**
 * Where to send the browser after signing in. The destination comes from the address bar
 * (?next=...), so it is untrusted: only a path on this site is allowed. Anything else (another
 * site, a protocol-relative "//host", a backslash trick, a control character) falls back to the
 * default, so a crafted link can never bounce a signed-in user to someone else's page.
 */
export function safeNextPath(next, fallback = "/practice") {
  if (typeof next !== "string") return fallback;
  if (!next.startsWith("/") || next.startsWith("//")) return fallback;
  // Backslashes and control characters (tab, newline) are read as slashes by some browsers.
  if (/[\u0000-\u001f\u007f\\]/.test(next)) return fallback;
  return next;
}
