/**
 * Client-side auth: token storage and the signup/login/logout calls.
 *
 * The token is the only identity the client holds — the previous
 * localStorage-UUID "user id" is gone, since the server now derives the owner
 * from the JWT and ignores any client-supplied id.
 */

import { safeNextPath } from "@/lib/redirects";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const TOKEN_KEY = "aura_token";
const USER_KEY = "aura_user";

export function getToken() {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getStoredUser() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function persistSession({ access_token, user }) {
  try {
    localStorage.setItem(TOKEN_KEY, access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    /* private mode / storage disabled — session just won't survive a reload */
  }
  return user;
}

export function logout() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    /* ignore */
  }
}

/** Pages that work without a session; an expired token must not bounce these. */
const PUBLIC_PATHS = ["/", "/login", "/signup", "/forgot-password"];
// (/verify-email needs a session, so an expired token there does go back to /login.)

/**
 * Called when the server rejects our token (expired, tampered, or the account
 * is gone). Clears the session and, if the user is on a protected page, sends
 * them to /login with an explanation — otherwise they would sit on a page
 * whose every request fails.
 */
export function expireSession() {
  logout();
  if (typeof window === "undefined") return;
  const { pathname } = window.location;
  if (PUBLIC_PATHS.includes(pathname) || pathname.startsWith("/auth/")) return;
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- runs outside React (no router available); a full reload also drops any in-memory state tied to the dead session
  window.location.href = "/login?error=session_expired";
}

export function isLoggedIn() {
  return Boolean(getToken());
}

async function postAuth(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(extractErrorMessage(data, res.status));
  }
  return persistSession(data);
}

export function signup({ email, password, displayName }) {
  return postAuth("/api/auth/signup", {
    email,
    password,
    display_name: displayName || null,
  });
}

export function login({ email, password }) {
  return postAuth("/api/auth/login", { email, password });
}

/**
 * FastAPI returns validation errors as `detail: [{msg, loc}, ...]` but simple
 * errors as `detail: "..."`. Flatten both into one readable string.
 */
function extractErrorMessage(data, status) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((d) => d.msg || "Invalid input").join(", ");
  }
  return `Request failed (${status})`;
}

/**
 * Authenticated fetch for the profile/password endpoints below. This is a
 * separate (small, duplicated) helper rather than importing lib/api.js's
 * authFetch — that module already imports getToken/logout from THIS file,
 * so importing back would be a circular dependency.
 */
async function authFetch(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: token ? { ...options.headers, Authorization: `Bearer ${token}` } : options.headers,
  });
  if (res.status === 401) {
    expireSession();
    throw new Error("Your session has expired. Please log in again.");
  }
  return res;
}

async function authFetchJson(path, options) {
  const res = await authFetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(extractErrorMessage(data, res.status));
  return data;
}

const USER_UPDATED_EVENT = "aura:user-updated";

/**
 * Updates the cached user in localStorage (e.g. after a profile edit or
 * avatar upload) and broadcasts it in-tab. The native "storage" event only
 * fires in OTHER tabs, so components like AppSidebar that cache their own
 * copy of the user (read once on mount) would otherwise go stale after an
 * edit made elsewhere on the same page.
 */
export function syncUser(updatedUser) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(USER_KEY, JSON.stringify(updatedUser));
  } catch {
    /* private mode / storage disabled */
  }
  window.dispatchEvent(new CustomEvent(USER_UPDATED_EVENT, { detail: updatedUser }));
}

/** Subscribes to in-tab user updates from syncUser(). Returns an unsubscribe function. */
export function onUserUpdated(callback) {
  const handler = (e) => callback(e.detail);
  window.addEventListener(USER_UPDATED_EVENT, handler);
  return () => window.removeEventListener(USER_UPDATED_EVENT, handler);
}

/** Fetches the current user fresh from the server (not the cached localStorage copy). */
export async function getMe() {
  const user = await authFetchJson("/api/auth/me");
  syncUser(user);
  return user;
}

/**
 * Sends only the fields provided (undefined keys are dropped by JSON.stringify).
 * `difficultyOverride` is a level (1-5) to pin, or `null` to go back to automatic.
 */
export async function updateProfile({ displayName, bio, preferredVoice, preferredStyle, difficultyOverride }) {
  const user = await authFetchJson("/api/auth/profile", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      display_name: displayName,
      bio,
      preferred_voice: preferredVoice,
      preferred_style: preferredStyle,
      difficulty_override: difficultyOverride,
    }),
  });
  syncUser(user);
  return user;
}

export async function uploadAvatar(file) {
  const form = new FormData();
  form.set("file", file);
  const { avatar_url } = await authFetchJson("/api/auth/avatar", { method: "POST", body: form });
  const user = getStoredUser();
  if (user) syncUser({ ...user, avatar_url });
  return avatar_url;
}

/**
 * Changing a password ends every OTHER session on the server (the token
 * version is bumped), and the response carries a fresh token for this one —
 * persist it, or the next request would be rejected and log the user out.
 */
export async function changePassword({ currentPassword, newPassword }) {
  const data = await authFetchJson("/api/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  persistSession(data);
  syncUser(data.user);
  return data.user;
}

/** Confirms the signed-in user's email with the code we emailed them. */
export async function verifyEmail(otp) {
  const user = await authFetchJson("/api/auth/verify-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ otp }),
  });
  syncUser(user);
  return user;
}

/** Emails a fresh verification code (the server enforces a 60s cooldown). */
export async function resendVerification() {
  await authFetchJson("/api/auth/resend-verification", { method: "POST" });
}

/** Permanently deletes the account, then clears the local session. */
export async function deleteAccount({ confirmEmail, password }) {
  await authFetchJson("/api/auth/account", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm_email: confirmEmail, password: password || null }),
  });
  logout();
}

export async function forgotPassword(email) {
  const res = await fetch(`${API_BASE}/api/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(extractErrorMessage(data, res.status));
  }
}

export function verifyOTP({ email, otp, newPassword }) {
  return postAuth("/api/auth/verify-otp", { email, otp, new_password: newPassword });
}

/**
 * The Google sign-in URL (used as the buttons' href; the click handler below
 * does the real work). Connecting Google to an existing account needs the
 * caller's identity, and a top-level redirect can't carry an Authorization
 * header — but a session token must never go in a URL either (history, logs,
 * referrers). So that flow first asks the server for a short-lived link code
 * (see startGoogleAuth) and puts only that in the URL.
 */
export function getGoogleAuthUrl() {
  return `${API_BASE}/api/auth/google`;
}

/**
 * Click handler for the Google buttons. They're plain links (the whole page
 * navigates to the backend), so a stopped backend would otherwise strand the
 * user on the browser's connection-refused page. Probe the server first and
 * hand a readable message to `onError` instead. `no-cors` keeps the probe
 * independent of CORS config — only "reachable or not" matters here.
 *
 * With `link: true` ("connect Google to my account"), it fetches the link code
 * first and navigates with that.
 */
export async function startGoogleAuth(event, { link = false, onError } = {}) {
  event.preventDefault();
  try {
    await fetch(`${API_BASE}/health`, { mode: "no-cors", signal: AbortSignal.timeout(4000) });
  } catch {
    onError?.("Can't reach the AURA server right now. Please try again in a moment.");
    return;
  }

  if (!link) {
    window.location.assign(getGoogleAuthUrl());
    return;
  }
  try {
    const { link_code } = await authFetchJson("/api/auth/google/link-code", { method: "POST" });
    const url = `${getGoogleAuthUrl()}?link_code=${encodeURIComponent(link_code)}`;
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- the API server's OAuth endpoint (another origin), not a Next.js page
    window.location.assign(url);
  } catch (err) {
    onError?.(err.message || "Couldn't start connecting Google. Please try again.");
  }
}

export async function disconnectGoogle() {
  const user = await authFetchJson("/api/auth/google/disconnect", { method: "POST" });
  syncUser(user);
  return user;
}

/**
 * Finishes a Google sign-in. The backend's callback redirects here with
 * ?code=...&next=... (failures redirect straight to /login with ?error=
 * instead); the code is a single-use, 2-minute credential, not a session, so
 * the real token travels in the response body of a POST rather than in a URL.
 * Strips the params from the address bar first, persists the session, and
 * resolves to { user, next } — or { user: null, next } if the code is missing,
 * expired or already used.
 *
 * Call it once per page load (the code can only be redeemed once).
 */
export async function completeGoogleSignIn() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  // The address bar can say anything, so only a path on this site is accepted as the destination.
  const next = safeNextPath(params.get("next"));
  window.history.replaceState({}, "", window.location.pathname);

  if (!code) return { user: null, next };
  try {
    const res = await fetch(`${API_BASE}/api/auth/google/exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    if (!res.ok) return { user: null, next };
    return { user: persistSession(await res.json()), next };
  } catch {
    return { user: null, next };
  }
}
